# core/utils.py

import PIL
import google.generativeai as genai
from decouple import config, UndefinedValueError
import os
import uuid
import requests
import base64
from django.conf import settings
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from supabase import create_client
import gc
import time
import requests


# --- Configuration ---
API_KEY_CONFIGURED = False
GEMINI_API_KEY = None
STABILITY_API_KEY = config("STABILITY_API_KEY")

try:
    GEMINI_API_KEY = config("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        print("Warning: GEMINI_API_KEY is empty in configuration.")
    else:
        genai.configure(api_key=GEMINI_API_KEY)
        API_KEY_CONFIGURED = True
        print("Gemini API Key configured successfully.")
except UndefinedValueError:
    print(
        "CRITICAL: GEMINI_API_KEY not found. Please set it in your .env file or environment variables."
    )
except Exception as e:
    print(
        f"CRITICAL: An unexpected error occurred during Gemini API configuration: {e}"
    )

# --- Model Definitions ---
TEXT_MODEL_NAME = "gemini-2.0-flash"
# IMAGE_MODEL_NAME = "gemini-2.0-flash-preview-image-generation"

# Add placeholder definitions
NUM_PANELS = 4
PLACEHOLDER_IMAGE_PATH = os.path.join(settings.MEDIA_ROOT, "placeholder.png")
PLACEHOLDER_IMAGES = [f"{settings.MEDIA_URL}placeholder.png"] * NUM_PANELS
PLACEHOLDER_IMAGES = [PLACEHOLDER_IMAGE_PATH] * NUM_PANELS

# Initialize Supabase client
supabase_client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SERVICE_KEY
)

# --- Ensure Placeholder Image Exists ---
def ensure_placeholder_exists():
    path = os.path.join(settings.MEDIA_ROOT, "placeholder.png")
    if not os.path.exists(path):
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (400, 600), color="lightgray")
        d = ImageDraw.Draw(img)
        d.text((100, 300), "No Image", fill="black")
        img.save(path)


ensure_placeholder_exists()


def ensure_media_dirs():
    """Ensure all required media directories exist."""
    dirs = [
        settings.MEDIA_ROOT,
        os.path.join(settings.MEDIA_ROOT, "generated_images"),
    ]
    for directory in dirs:
        os.makedirs(directory, exist_ok=True)


ensure_media_dirs()

def cleanup_memory():
    """Force garbage collection to free memory"""
    gc.collect()
    print("Debug: Memory cleanup performed")


# --- Comic Script Generation ---
def generate_comic(
    prompt: str,
) -> tuple[str | None, str | None, list | None]:
    """
    Generates a comic script and attempts to generate images, falling back to placeholders if needed.
    Returns a tuple of (title, script, image URLs)
    """
    if not API_KEY_CONFIGURED:
        print("Error in generate_comic_script: Gemini API Key not configured.")
        return None, None, None

    learning_objective = prompt

    # --- Prompt Engineering for Script Generation ---
    enhanced_prompt = f"""
    You are an expert educational comic strip writer for Ghanaian primary school students.

    Your task is to generate a script for a {NUM_PANELS}-panel educational comic. Follow the EXACT structure below:

    Learning Objective: {prompt}

    Cultural Guidelines:
    - The story must reflect Ghanaian cultural values and moral customs.
    - All characters should be simple, relatable Ghanaian children or elders with Ghanaian names.
    - Clothing should be modest and culturally appropriate (e.g., kaba and slit, fugu, school uniforms).
    - Settings should reflect familiar Ghanaian environments (e.g., village, school compound, market, farm).
    - **Do not include any symbols, themes, or elements that go against traditional Ghanaian values** (e.g., LGBTQ+ themes, Western holidays, or modern urban culture not common in rural Ghana).
    - Use Akan, Ewe, or other Ghanaian terms where suitable, but explain them clearly or show context.
    - The story should be age-appropriate and avoid any sensitive or controversial material.

    Comic Script Format:

    Panel 1  
    Scene Description: [Detailed visual elements. Describe the setting, background, time of day, actions, and facial expressions of characters. Be vivid enough to help an illustrator picture the panel exactly. Include Ghanaian cultural elements naturally.]  
    Dialogue: [Character dialogue, one line per character. Use simple and clear language for primary school students.]  
    Narration: [Short caption to explain or support the learning objective.]

    Panel 2  
    Scene Description: [Detailed and vivid illustration description.]  
    Dialogue: [Character lines, culturally natural and child-friendly.]  
    Narration: [Supporting text.]

    [Repeat for {NUM_PANELS} panels]

    Final Requirements:
    - Each panel MUST include content for all three sections: Scene Description, Dialogue, Narration.
    - Use simple but **grammatically correct** English.
    - Dialogue must progress the story clearly and logically.
    - Narration should reinforce the learning objective in each panel.
    - The script must be culturally sensitive and educationally effective.

    Output a clearly structured, printable script for the comic.
    """


    try:
        script_start_time = time.time()
        print("Debug: Starting script generation...")

        model = genai.GenerativeModel(TEXT_MODEL_NAME)
        response = model.generate_content(enhanced_prompt)

        script_time = time.time() - script_start_time
        print(f"Debug: Script generation took {script_time:.2f} seconds")

        if response.text:
            comic_script = response.text
            print("Debug: Script generated successfully")

            # Extract title from the script
            title = extract_title_from_script(comic_script)
            if not title:
                # Create a fallback title from the prompt
                title = f"Comic: {prompt[:50]}{'...' if len(prompt) > 50 else ''}"
            print(f"Debug: Title extracted: {title}")

            # Extract panel descriptions
            panel_extraction_start = time.time()
            panel_descriptions = extract_panel_descriptions(comic_script, NUM_PANELS)
            print(f"Debug: Extracted {len(panel_descriptions)} panel descriptions")
            print(f"Debug: Panel extraction took {time.time() - panel_extraction_start:.2f} seconds")

            # Generate or get placeholder images for all panels
            images_start_time = time.time()
            image_urls = []
            for i, desc in enumerate(panel_descriptions):
                print(f"Debug: Generating image for panel {i+1}")
                try:
                    image_url = generate_panel_image(panel_description=desc, panel_number=i)
                    image_urls.append(image_url)
                    time.sleep(0.5)  # Optional: prevent rate limits
                except Exception as e:
                    print(f"Warning: Failed to generate image for panel {i+1}: {e}")
                    image_urls.append(None)

            images_time = time.time() - images_start_time
            print(f"Debug: All image generation took {images_time:.2f} seconds")

            if not image_urls or all(url is None for url in image_urls):
                print("Debug: No image URLs generated, using placeholders")
                image_urls = PLACEHOLDER_IMAGES[:NUM_PANELS]

            # Final cleanup
            gc.collect()

            return title, comic_script, image_urls
        else:
            print("Script generation failed: No text returned.")
            return None, None, None

    except Exception as e:
        print(f"Error during comic script generation: {e}")
        return None, None, None



# --- Panel Image Generation ---
def save_base64_image(b64_string: str, panel_number: int) -> str:
    """Save a base64 string as an image file and return its URL path."""
    try:
        # Remove the data URL prefix if present
        if "," in b64_string:
            b64_string = b64_string.split(",")[1]

        # Generate a unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"panel_{panel_number}_{timestamp}.png"
        filepath = os.path.join(settings.GENERATED_IMAGES_DIR, filename)

        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # Decode and save the image
        image_data = base64.b64decode(b64_string)
        with open(filepath, "wb") as f:
            f.write(image_data)

        # Return the URL path
        return f"{settings.MEDIA_URL}generated_images/{filename}"
    except Exception as e:
        print(f"Error saving image: {e}")
        return None


def generate_panel_image(
    panel_description: str,
    panel_number: int = 0,
    style_description: str = "Educational comic book style for young children.",
) -> str:
    if not STABILITY_API_KEY:
        print("Warning: Using placeholder image (Stability API key not configured)")
        # return PLACEHOLDER_IMAGES[panel_number % len(PLACEHOLDER_IMAGES)]
        return create_and_upload_placeholder(panel_number)
    try:
        prompt = f"{panel_description}. {style_description}"
        panel_start_time = time.time()
        
        files = {
            "prompt": (None, prompt),
            "steps": (None, "15"),
            "width": (None, "512"),
            "height": (None, "512"),
            "samples": (None, "1"),
            "cfg_scale": (None, "7"),
            "scheduler": "euler_a", 
            "output_format": "jpeg",
        }

        response = requests.post(
            "https://api.stability.ai/v2beta/stable-image/generate/core",
            headers={
                "Authorization": f"Bearer {STABILITY_API_KEY}",
                "Accept": "application/json",
            },
            files=files,
            timeout=45,
        )
        
        
        panel_time = time.time() - panel_start_time

        print(f"Debug - Response Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("Debug - Response keys:", list(data.keys()))  # See what keys exist
            
            # IMMEDIATE MEMORY CLEANUP
            gc.collect()
            # Try different possible response structures
            img_b64 = None
            
            # Option 1: artifacts (old format)
            if "artifacts" in data and data["artifacts"]:
                img_b64 = data["artifacts"][0]["base64"]
            # Option 2: image (new format)
            elif "image" in data:
                img_b64 = data["image"]
            # Option 3: data field
            elif "data" in data and isinstance(data["data"], list) and data["data"]:
                img_b64 = data["data"][0].get("base64")
            # Option 4: direct base64 field
            elif "base64" in data:
                img_b64 = data["base64"]
            
            if img_b64:
                image_url = save_base64_image_to_supabase(img_b64, panel_number)
                if image_url:
                    return image_url
                print("Warning: Could not save image")
            else:
                print("Warning: No image data found in response")
                print("Debug - Full response:", data)
        else:
            print(f"Stability AI error: {response.status_code} {response.text}")

    except Exception as e:
        print(f"Error during image generation: {e}")

    return create_and_upload_placeholder(panel_number)


def extract_title_from_script(script: str) -> str | None:
    """
    Extract a meaningful title from the comic script.
    Looks for the Learning Objective line and creates a short title from it.
    """
    try:
        if not script or not script.strip():
            return None

        lines = script.split("\n")
        for line in lines:
            line_lower = line.strip().lower()

            # Look for learning objective
            if line_lower.startswith("learning objective:"):
                objective = line.split(":", 1)[1].strip()
                # Create a shorter, more title-like version
                if len(objective) > 50:
                    # Take first part or create a summary
                    words = objective.split()
                    if len(words) > 8:
                        title = " ".join(words[:8]) + "..."
                    else:
                        title = objective
                else:
                    title = objective
                return title.strip()

            # Alternative patterns to look for
            elif any(
                keyword in line_lower for keyword in ["title:", "topic:", "subject:"]
            ):
                if ":" in line:
                    title_part = line.split(":", 1)[1].strip()
                    if title_part and len(title_part) > 3:  # Avoid very short titles
                        return title_part[:50] + ("..." if len(title_part) > 50 else "")

        # Fallback: look for the first substantial line that might be a title
        for line in lines:
            line = line.strip()
            if (
                line
                and len(line) > 10
                and not line.lower().startswith(
                    ("panel", "scene", "dialogue", "narration")
                )
                and not line.startswith(("Panel", "Scene", "Dialogue", "Narration"))
            ):
                return line[:50] + ("..." if len(line) > 50 else "")

        return None
    except Exception as e:
        print(f"Error extracting title: {e}")
        return None

def extract_panel_descriptions(script: str, num_panels=4) -> list[str]:
    descriptions = []
    current_desc = ""
    for line in script.splitlines():
        if line.strip().lower().startswith("panel"):
            if current_desc:
                descriptions.append(current_desc.strip())
            current_desc = ""
        elif "scene description" in line.lower():
            current_desc += line.split(":", 1)[-1].strip() + " "
        elif (
            current_desc
            and not line.lower().startswith("dialogue")
            and not line.lower().startswith("narration")
        ):
            current_desc += line.strip() + " "
    if current_desc:
        descriptions.append(current_desc.strip())
    # Always return num_panels descriptions
    while len(descriptions) < num_panels:
        descriptions.append("A generic educational comic panel for Ghanaian children.")
    return descriptions[:num_panels]

def extract_panel_texts(script: str, num_panels=4) -> list[dict]:
    """
    Extract dialogue (as a list) and narration for each panel, handling bullet lists and markdown.
    """
    panels = []
    lines = script.splitlines()
    current_panel = {"dialogue": [], "narration": ""}
    in_dialogue_section = False
    in_narration_section = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check if this is the start of a new panel
        if line.lower().startswith("panel"):
            # Save the previous panel if it has content
            if current_panel["dialogue"] or current_panel["narration"]:
                panels.append(current_panel.copy())
            # Reset for new panel
            current_panel = {"dialogue": [], "narration": ""}
            in_dialogue_section = False
            in_narration_section = False
            continue

        # Check for section headers
        line_lower = line.lower()

        # Dialogue section detection
        if "dialogue:" in line_lower or line_lower.startswith("dialogue"):
            in_dialogue_section = True
            in_narration_section = False
            # Check if dialogue content is on the same line
            if ":" in line:
                dialogue_content = line.split(":", 1)[1].strip()
                if dialogue_content and dialogue_content.lower() not in ["none", ""]:
                    # Clean up quotes and formatting
                    dialogue_content = dialogue_content.strip("*\"'")
                    if dialogue_content:
                        current_panel["dialogue"].append(dialogue_content)
            continue

        # Narration/Caption section detection
        if any(
            keyword in line_lower
            for keyword in ["narration:", "caption:", "narration/caption:"]
        ):
            in_narration_section = True
            in_dialogue_section = False
            # Check if narration content is on the same line
            if ":" in line:
                narration_content = line.split(":", 1)[1].strip()
                if narration_content and narration_content.lower() not in ["none", ""]:
                    # Clean up quotes and formatting
                    narration_content = narration_content.strip("*\"'")
                    if narration_content:
                        current_panel["narration"] = narration_content
            continue

        # Scene description detection (skip this section)
        if "scene description:" in line_lower or "scene:" in line_lower:
            in_dialogue_section = False
            in_narration_section = False
            continue

        # Process content based on current section
        if in_dialogue_section:
            # Clean up bullet points, quotes, and other formatting
            clean_line = line.lstrip("*-•1234567890. ").strip()
            clean_line = clean_line.strip("*\"'")

            # Skip empty lines or "none" entries
            if clean_line and clean_line.lower() != "none":
                current_panel["dialogue"].append(clean_line)

        elif in_narration_section:
            # Clean up formatting for narration
            clean_line = line.lstrip("*-•1234567890. ").strip()
            clean_line = clean_line.strip("*\"'")

            # Skip empty lines or "none" entries
            if clean_line and clean_line.lower() != "none":
                # If narration already exists, append to it
                if current_panel["narration"]:
                    current_panel["narration"] += " " + clean_line
                else:
                    current_panel["narration"] = clean_line

    # Don't forget to add the last panel
    if current_panel["dialogue"] or current_panel["narration"]:
        panels.append(current_panel.copy())

    # Ensure we have exactly num_panels panels
    while len(panels) < num_panels:
        panels.append({"dialogue": [], "narration": ""})

    # Truncate if we have too many panels
    return panels[:num_panels]

def extract_panel_texts_robust(script: str, num_panels=4) -> list[dict]:
    """
    More robust version that handles different script formatting styles.
    """
    import re

    panels = []

    # Split script into panel sections using regex
    panel_pattern = r"(?i)panel\s*\d+"
    panel_sections = re.split(panel_pattern, script)

    # Remove empty first section if it exists
    if panel_sections and not panel_sections[0].strip():
        panel_sections = panel_sections[1:]

    for section in panel_sections:
        if not section.strip():
            continue

        panel_data = {"dialogue": [], "narration": ""}

        # Extract dialogue using multiple patterns
        dialogue_patterns = [
            r"(?i)dialogue:\s*(.+?)(?=narration|caption|scene|panel|$)",
            r"(?i)dialogue:\s*\n((?:.*\n?)*?)(?=narration|caption|scene|panel|$)",
        ]

        for pattern in dialogue_patterns:
            dialogue_match = re.search(pattern, section, re.DOTALL)
            if dialogue_match:
                dialogue_text = dialogue_match.group(1).strip()

                # Split dialogue into individual lines and clean them
                dialogue_lines = []
                for line in dialogue_text.split("\n"):
                    clean_line = line.strip().lstrip("*-•1234567890. ")
                    clean_line = clean_line.strip("*\"'")
                    if clean_line and clean_line.lower() != "none":
                        dialogue_lines.append(clean_line)

                if dialogue_lines:
                    panel_data["dialogue"] = dialogue_lines
                break

        # Extract narration using multiple patterns
        narration_patterns = [
            r"(?i)(?:narration|caption):\s*(.+?)(?=dialogue|scene|panel|$)",
            r"(?i)(?:narration|caption):\s*\n((?:.*\n?)*?)(?=dialogue|scene|panel|$)",
        ]

        for pattern in narration_patterns:
            narration_match = re.search(pattern, section, re.DOTALL)
            if narration_match:
                narration_text = narration_match.group(1).strip()
                narration_text = narration_text.strip("*\"'")

                if narration_text and narration_text.lower() != "none":
                    panel_data["narration"] = narration_text
                break

        panels.append(panel_data)

    # Ensure we have exactly num_panels panels
    while len(panels) < num_panels:
        panels.append({"dialogue": [], "narration": ""})

    return panels[:num_panels]


# --- Helper function to save images (optional, for testing) ---
def save_image(
    image_bytes: bytes, filename_prefix: str, output_dir: str = "generated_comic_panels"
):
    """Saves image bytes to a file."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    from random import SystemRandom

    file_path = os.path.join(
        output_dir, f"{filename_prefix}_{SystemRandom().randint(1000, 9999)}.png"
    )
    try:
        with open(file_path, "wb") as f:
            f.write(image_bytes)
        print(f"Image saved to {file_path}")
        return file_path
    except Exception as e:
        print(f"Error saving image {file_path}: {e}")
        return None

def save_base64_image_to_supabase(b64_string: str, panel_number: int) -> str:
    """Save a base64 string as an image to Supabase Storage and return its public URL."""
    try:
        # Remove the data URL prefix if present
        if "," in b64_string:
            b64_string = b64_string.split(",")[1]

        # Generate a unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        filename = f"panel_{panel_number}_{timestamp}_{unique_id}.png"

        # Decode the base64 string
        image_data = base64.b64decode(b64_string)

       # Upload to Supabase Storage
        try:
            result = supabase_client.storage.from_(settings.SUPABASE_STORAGE_BUCKET).upload(
                filename,
                image_data,
                file_options={"content-type": "image/png"}
            )

            # Handle different response formats from Supabase
            if hasattr(result, 'status_code'):
                if result.status_code == 200:
                    public_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{settings.SUPABASE_STORAGE_BUCKET}/{filename}"
                    return public_url
                else:
                    print(f"Upload failed with status {result.status_code}: {result}")
                    return None
            else:
                # Assume success if no status_code attribute
                public_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{settings.SUPABASE_STORAGE_BUCKET}/{filename}"
                return public_url

        except Exception as upload_error:
            print(f"Supabase upload error: {upload_error}")
            return None

    except Exception as e:
        print(f"Error saving image to Supabase: {e}")
        return None
    
def save_pil_image_to_supabase(pil_image, filename_prefix: str) -> str:
    """Save a PIL Image to Supabase Storage and return its public URL."""
    try:
        from io import BytesIO
        
        # Convert PIL image to bytes
        img_buffer = BytesIO()
        pil_image.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        filename = f"{filename_prefix}_{timestamp}_{unique_id}.png"
        
        # Upload to Supabase
        try:
            result = supabase_client.storage.from_(settings.SUPABASE_STORAGE_BUCKET).upload(
                filename,
                img_buffer.getvalue(),
                file_options={"content-type": "image/png"}
            )
            
            # Handle response
            if hasattr(result, 'status_code'):
                if result.status_code == 200:
                    public_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{settings.SUPABASE_STORAGE_BUCKET}/{filename}"
                    return public_url
                else:
                    print(f"Upload failed with status {result.status_code}: {result}")
                    return None
            else:
                # Assume success
                public_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{settings.SUPABASE_STORAGE_BUCKET}/{filename}"
                return public_url
                
        except Exception as upload_error:
            print(f"Error uploading to Supabase: {upload_error}")
            return None
            
    except Exception as e:
        print(f"Error saving PIL image to Supabase: {e}")
        return None


def extract_panel_dialogues(script: str) -> list[str]:
    dialogues = []
    current_dialogue = ""
    for line in script.splitlines():
        if "panel" in line.lower():
            if current_dialogue:
                dialogues.append(current_dialogue.strip())
            current_dialogue = ""
        elif "dialogue" in line.lower():
            # Handles Dialogue: or - Dialogue:
            parts = line.split(":", 1)
            if len(parts) > 1:
                current_dialogue = parts[1].strip().strip('"')
            else:
                current_dialogue = ""
    if current_dialogue:
        dialogues.append(current_dialogue.strip())
    return dialogues


def wrap_text(draw, text, font, max_width):
    """Wrap text for a given pixel width."""
    words = text.split()
    lines = []
    current_line = []
    for word in words:
        test_line = " ".join(current_line + [word])
        width = draw.textlength(test_line, font=font)
        if width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))
    return lines


def draw_speech_bubble(draw, text, x, y, font, max_width=300, padding=10):
    """Enhanced speech bubble with better styling and returns height."""
    if not text:
        return 0

    lines = wrap_text(draw, text, font, max_width)
    if not lines:
        return 0

    # Calculate bubble dimensions
    line_height = font.getbbox("A")[3] - font.getbbox("A")[1]
    bubble_width = max([draw.textlength(line, font=font) for line in lines]) + (
        padding * 2
    )
    bubble_height = len(lines) * line_height + (len(lines) - 1) * 3 + (padding * 2)

    # Draw bubble background with shadow
    shadow_offset = 2
    # Shadow
    draw.ellipse(
        [
            x + shadow_offset,
            y + shadow_offset,
            x + bubble_width + shadow_offset,
            y + bubble_height + shadow_offset,
        ],
        fill="gray",
    )

    # Main bubble
    draw.ellipse(
        [x, y, x + bubble_width, y + bubble_height],
        fill="white",
        outline="black",
        width=2,
    )

    # Draw tail
    tail_size = 15
    tail_points = [
        (x + 30, y + bubble_height),
        (x + 20, y + bubble_height + tail_size),
        (x + 45, y + bubble_height),
    ]
    draw.polygon(tail_points, fill="white", outline="black", width=2)

    # Draw text
    current_y = y + padding
    for line in lines:
        text_width = draw.textlength(line, font=font)
        text_x = x + (bubble_width - text_width) // 2
        draw.text((text_x, current_y), line, fill="black", font=font)
        current_y += line_height + 3

    return bubble_height + tail_size


def draw_caption(draw, text, x, y, width, font, padding=10):
    """Draw a caption box at the bottom of the panel with wrapped text."""
    if not text:
        return
    lines = wrap_text(draw, text, font, width - 2 * padding)
    text_height = draw.textbbox((0, 0), lines[0], font=font)[3]
    caption_height = len(lines) * (text_height + 5) + 2 * padding
    draw.rectangle(
        [x, y - caption_height, x + width, y],
        fill="white",
        outline="black",
    )
    current_y = y - caption_height + padding
    for line in lines:
        draw.text((x + padding, current_y), line, fill="black", font=font)
        current_y += text_height + 5


def wrap_text_for_title(draw, text, font, max_width):
    """Wrap text for title with proper line breaks."""
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        test_line = " ".join(current_line + [word])
        width = draw.textlength(test_line, font=font)
        if width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                # Word is too long for one line, force break
                lines.append(word)

    if current_line:
        lines.append(" ".join(current_line))

    return lines

def create_and_upload_placeholder(panel_number: int) -> str:
    """Create a placeholder image and upload it to Supabase"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # Create placeholder image
        img = Image.new("RGB", (400, 600), color="lightgray")
        draw = ImageDraw.Draw(img)
        
        try:
            # Try different font names for cross-platform compatibility
            font_names = ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "liberation-sans.ttf"]
            font = None
            for font_name in font_names:
                try:
                    font = ImageFont.truetype(font_name, 40)
                    break
                except:
                    continue
            
            if font is None:
                font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()
        
        draw.text((100, 280), f"Panel {panel_number + 1}", fill="black", font=font)
        draw.text((120, 320), "No Image", fill="black", font=font)
        
        # Upload to Supabase
        placeholder_url = save_pil_image_to_supabase(img, f"placeholder_panel_{panel_number}")
        return placeholder_url
        
    except Exception as e:
        print(f"Error creating placeholder: {e}")
        # Return a fallback URL or None
        return None

def stitch_panels(
    image_urls: list[str],
    panel_texts: list[dict],
    title: str = "Comic Strip",
    margin_width: int = 15,
    panel_border_width: int = 3,
) -> str:
    """
    Stitch panels together with title, dialogue bubbles, captions, and black margins for distinction and upload final comic to Supabase.
    """
    if not image_urls:
        return None

    try:
        # Load images
        panel_images = []
        for url in image_urls:
            print(f"Loading image from: {url}")
            try:
                if url.startswith(('http://', 'https://')):
                    # It's a URL, use requests
                    response = requests.get(url, stream=True, timeout=30)
                    response.raise_for_status()
                    img = Image.open(BytesIO(response.content)).convert("RGB")
                else:
                    # It's a local file path
                    if not os.path.isabs(url):
                        # Convert relative path to absolute path
                        if url.startswith(settings.MEDIA_URL):
                            relative_path = url.replace(settings.MEDIA_URL, '', 1)
                            file_path = os.path.join(settings.MEDIA_ROOT, relative_path)
                        else:
                            file_path = os.path.join(settings.MEDIA_ROOT, url)
                    else:
                        file_path = url
                    
                    if not os.path.exists(file_path):
                        print(f"File not found: {file_path}")
                        raise FileNotFoundError(f"File not found: {file_path}")
                    
                    img = Image.open(file_path).convert("RGB")
                
                panel_images.append(img)
                
            except Exception as e:
                print(f"Error loading image {url}: {e}")
                # Create a placeholder for failed images
                placeholder = Image.new("RGB", (400, 600), "lightgray")
                draw = ImageDraw.Draw(placeholder)
                draw.text((150, 300), "Image Error", fill="red")
                panel_images.append(placeholder)
                
                # Continue with other images instead of returning None
                continue

        if not panel_images:
            print("No images could be loaded")
            return None

        # Ensure we have at least 4 panels (pad with blank if needed)
        while len(panel_images) < 4:
            # Create a blank panel
            blank_panel = Image.new("RGB", (400, 600), "lightgray")
            draw_blank = ImageDraw.Draw(blank_panel)
            draw_blank.text((150, 300), "No Image", fill="black")
            panel_images.append(blank_panel)

        # Set dimensions
        panel_width = 400  # Fixed width for each panel
        panel_height = 600  # Fixed height for each panel
        title_height = 100  # Increased space for title
        padding = 10

        # Calculate total dimensions with margins
        total_width = (panel_width * 2) + (
            margin_width * 3
        )  # 3 margins: left, center, right
        total_height = (
            (panel_height * 2) + title_height + (margin_width * 3)
        )  # 3 margins: top, center, bottom

        # Resize all panels to be consistent
        panel_images = [img.resize((panel_width, panel_height)) for img in panel_images]

        # Create canvas with black background for margins
        canvas = Image.new("RGB", (total_width, total_height), "black")
        draw = ImageDraw.Draw(canvas)

        # Load fonts
        try:
            # Try to load better fonts with fallbacks
            title_font = ImageFont.truetype("arial.ttf", 28)
            font = ImageFont.truetype("arial.ttf", 16)
        except:
            try:
                title_font = ImageFont.truetype("Arial.ttf", 28)
                font = ImageFont.truetype("Arial.ttf", 16)
            except:
                try:
                    title_font = ImageFont.load_default()
                    font = ImageFont.load_default()
                except:
                    # Last resort - create basic fonts
                    title_font = ImageFont.load_default()
                    font = ImageFont.load_default()

        # Create title background area
        title_bg_height = title_height - margin_width
        draw.rectangle(
            [margin_width, margin_width, total_width - margin_width, title_bg_height],
            fill="white",
            outline="black",
            width=2,
        )

        # Draw title with text wrapping
        title_lines = wrap_text_for_title(
            draw, title, title_font, total_width - (margin_width * 4)
        )

        # Calculate title positioning
        line_height = title_font.getbbox("A")[3] - title_font.getbbox("A")[1]
        total_text_height = len(title_lines) * line_height + (len(title_lines) - 1) * 5
        start_y = (
            margin_width + (title_bg_height - margin_width - total_text_height) // 2
        )

        for i, line in enumerate(title_lines):
            line_width = draw.textlength(line, font=title_font)
            x = (total_width - line_width) // 2
            y = start_y + i * (line_height + 5)
            draw.text((x, y), line, font=title_font, fill="black")

        # Place panels with margins and borders
        panel_positions = [
            (margin_width, title_height + margin_width),  # Top-left
            (margin_width * 2 + panel_width, title_height + margin_width),  # Top-right
            (
                margin_width,
                title_height + margin_width * 2 + panel_height,
            ),  # Bottom-left
            (
                margin_width * 2 + panel_width,
                title_height + margin_width * 2 + panel_height,
            ),  # Bottom-right
        ]

        for idx, (img, texts) in enumerate(zip(panel_images, panel_texts)):
            if idx >= len(panel_positions):
                break

            x, y = panel_positions[idx]

            # Draw panel border
            draw.rectangle(
                [
                    x - panel_border_width,
                    y - panel_border_width,
                    x + panel_width + panel_border_width,
                    y + panel_height + panel_border_width,
                ],
                fill="black",
            )

            # Paste panel
            canvas.paste(img, (x, y))

            # Draw each dialogue line as its own bubble, stacking vertically
            bubble_y = y + 20
            bubble_spacing = 0

            for dialogue_line in texts.get("dialogue", []):
                if dialogue_line.strip():
                    bubble_height = draw_speech_bubble(
                        draw,
                        dialogue_line,
                        x + 10,
                        bubble_y + bubble_spacing,
                        font,
                        max_width=panel_width - 40,
                        padding=8,
                    )
                    bubble_spacing += bubble_height + 10

            # Draw caption at bottom with better styling
            if texts.get("narration"):
                draw_caption(
                    draw,
                    texts["narration"],
                    x,
                    y + panel_height - 5,
                    panel_width,
                    font,
                    padding=8,
                )

        # Save stitched image
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"stitched_comic_{timestamp}.png"
        output_dir = os.path.join(settings.MEDIA_ROOT, "generated_images")
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, filename)
        canvas.save(file_path)

        # Upload final stitched image to Supabase
        final_comic_url = save_pil_image_to_supabase(canvas, "stitched_comic")
        return final_comic_url
    
        return f"{settings.MEDIA_URL}generated_images/{filename}"
    except Exception as e:
        print(f"Error stitching panels: {e}")
        return None

