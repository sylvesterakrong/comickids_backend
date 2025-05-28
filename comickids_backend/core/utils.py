# core/utils.py

import PIL
import google.generativeai as genai
from decouple import config, UndefinedValueError
import os
import json
import requests
import time
import base64
from django.conf import settings
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

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
PLACEHOLDER_IMAGES = [PLACEHOLDER_IMAGE_PATH] * NUM_PANELS


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


# --- Comic Script Generation ---
def generate_comic(
    prompt: str,
) -> tuple[str | None, list | None]:
    """
    Generates a comic script and attempts to generate images, falling back to placeholders if needed.
    Returns a tuple of (script, list of image URLs)
    """
    if not API_KEY_CONFIGURED:
        print("Error in generate_comic_script: Gemini API Key not configured.")
        return None, None

    # --- Prompt Engineering for Script Generation ---
    enhanced_prompt = f"""
    You are an expert creator of educational comic strips for Ghanaian primary school students.
    Your task is to generate a script for a {NUM_PANELS}-panel comic  script with the following EXACT format:

    Learning Objective: {prompt}
    Mandatory Ghanaian Cultural Elements to be included to give it a natural feel
    
    Panel 1
    Scene Description: [Detailed visual elements, setting, character appearances (simple, relatable Ghanaian characters), character actions, and expressions. Incorporate the cultural elements here.]
    Dialogue: [Character dialogue, one line per character. Keep it simple and clear, using language appropriate for primary school students. Use Ghanaian names and phrases where relevant.]
    Narration: [ Text that explains the scene or reinforces the learning objective (if any).]

    Panel 2
    Scene Description: [Detailed visual elements, setting, character appearances (simple, relatable Ghanaian characters), character actions, and expressions. Incorporate the cultural elements here.]
    Dialogue: [Character dialogue, one line per character. Keep it simple and clear, using language appropriate for primary school students. Use Ghanaian names and phrases where relevant.]
    Narration: [ Text that explains the scene or reinforces the learning objective (if any).]

    [Continue for all {NUM_PANELS} panels]

    The story should be engaging, easy to understand for a primary school student, directly teach or illustrate the learning objective, and be culturally sensitive and relevant to Ghana. It should also be grammatically correct.
    Output the script as a clear, well-structured text. 
    
    Make sure each panel has content for dialogue and narration sections.

    """

    try:
        model = genai.GenerativeModel(TEXT_MODEL_NAME)
        response = model.generate_content(enhanced_prompt)

        if response.text:
            comic_script = response.text
            print("Debug: Script generated successfully")

            # Generate or get placeholder images for all panels
            panel_descriptions = extract_panel_descriptions(comic_script, NUM_PANELS)
            print(f"Debug: Extracted {len(panel_descriptions)} panel descriptions")

            image_urls = []
            for i, desc in enumerate(panel_descriptions):
                print(f"Debug: Generating image for panel {i+1}")
                image_url = generate_panel_image(panel_description=desc, panel_number=i)
                image_urls.append(image_url)

            if not image_urls:
                print("Debug: No image URLs generated")
                return comic_script, None

            return comic_script, image_urls
        else:
            print("Script generation failed: No text returned.")
            return None, None
    except Exception as e:
        print(f"Error during comic script generation: {e}")
        return None, None


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
        return PLACEHOLDER_IMAGES[panel_number % len(PLACEHOLDER_IMAGES)]

    try:
        prompt = f"{panel_description}. {style_description}"

        files = {
            "prompt": (None, prompt),
            "steps": (None, "30"),
            "width": (None, "1024"),
            "height": (None, "1024"),
            "samples": (None, "1"),
            "cfg_scale": (None, "7"),
        }

        response = requests.post(
            "https://api.stability.ai/v2beta/stable-image/generate/core",
            headers={
                "Authorization": f"Bearer {STABILITY_API_KEY}",
                "Accept": "application/json",
            },
            files=files,
            timeout=60,
        )

        print(f"Debug - Response Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            if "artifacts" in data and data["artifacts"]:
                img_b64 = data["artifacts"][0]["base64"]
                # Save the image and get its URL
                image_url = save_base64_image(img_b64, panel_number)
                if image_url:
                    return image_url
                print("Warning: Could not save image")
            else:
                print("Warning: No artifacts in response")
        else:
            print(f"Stability AI error: {response.status_code} {response.text}")

    except Exception as e:
        print(f"Error during image generation: {e}")

    return PLACEHOLDER_IMAGES[panel_number % len(PLACEHOLDER_IMAGES)]


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
                    dialogue_content = dialogue_content.strip('*"\'')
                    if dialogue_content:
                        current_panel["dialogue"].append(dialogue_content)
            continue
            
        # Narration/Caption section detection
        if any(keyword in line_lower for keyword in ["narration:", "caption:", "narration/caption:"]):
            in_narration_section = True
            in_dialogue_section = False
            # Check if narration content is on the same line
            if ":" in line:
                narration_content = line.split(":", 1)[1].strip()
                if narration_content and narration_content.lower() not in ["none", ""]:
                    # Clean up quotes and formatting
                    narration_content = narration_content.strip('*"\'')
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
            clean_line = clean_line.strip('*"\'')
            
            # Skip empty lines or "none" entries
            if clean_line and clean_line.lower() != "none":
                current_panel["dialogue"].append(clean_line)
                
        elif in_narration_section:
            # Clean up formatting for narration
            clean_line = line.lstrip("*-•1234567890. ").strip()
            clean_line = clean_line.strip('*"\'')
            
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
    panel_pattern = r'(?i)panel\s*\d+'
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
            r'(?i)dialogue:\s*(.+?)(?=narration|caption|scene|panel|$)',
            r'(?i)dialogue:\s*\n((?:.*\n?)*?)(?=narration|caption|scene|panel|$)',
        ]
        
        for pattern in dialogue_patterns:
            dialogue_match = re.search(pattern, section, re.DOTALL)
            if dialogue_match:
                dialogue_text = dialogue_match.group(1).strip()
                
                # Split dialogue into individual lines and clean them
                dialogue_lines = []
                for line in dialogue_text.split('\n'):
                    clean_line = line.strip().lstrip('*-•1234567890. ')
                    clean_line = clean_line.strip('*"\'')
                    if clean_line and clean_line.lower() != 'none':
                        dialogue_lines.append(clean_line)
                
                if dialogue_lines:
                    panel_data["dialogue"] = dialogue_lines
                break
        
        # Extract narration using multiple patterns
        narration_patterns = [
            r'(?i)(?:narration|caption):\s*(.+?)(?=dialogue|scene|panel|$)',
            r'(?i)(?:narration|caption):\s*\n((?:.*\n?)*?)(?=dialogue|scene|panel|$)',
        ]
        
        for pattern in narration_patterns:
            narration_match = re.search(pattern, section, re.DOTALL)
            if narration_match:
                narration_text = narration_match.group(1).strip()
                narration_text = narration_text.strip('*"\'')
                
                if narration_text and narration_text.lower() != 'none':
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
    """Draw a speech bubble with wrapped text."""
    if not text:
        return
    lines = wrap_text(draw, text, font, max_width)
    line_heights = [draw.textbbox((0, 0), line, font=font)[3] for line in lines]
    bubble_width = max(draw.textlength(line, font=font) for line in lines) + (
        padding * 2
    )
    bubble_height = sum(line_heights) + (padding * 2) + 5 * (len(lines) - 1)
    bubble_shape = [
        (x, y),
        (x + bubble_width, y),
        (x + bubble_width, y + bubble_height),
        (x, y + bubble_height),
    ]
    draw.polygon(bubble_shape, fill="white", outline="black")
    tail_points = [
        (x + 30, y + bubble_height),
        (x + 20, y + bubble_height + 20),
        (x + 50, y + bubble_height),
    ]
    draw.polygon(tail_points, fill="white", outline="black")
    current_y = y + padding
    for line in lines:
        draw.text((x + padding, current_y), line, fill="black", font=font)
        current_y += line_heights[0] + 5


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


def stitch_panels(
    image_urls: list[str], panel_texts: list[dict], title: str = "Comic Strip"
) -> str:
    """Stitch panels together with title, dialogue bubbles, and captions."""
    if not image_urls:
        return None

    try:
        # Load images
        panel_images = []
        for url in image_urls:
            print(f"Loading image from: {url}")
            try:
                img = Image.open(url).convert("RGB")
                panel_images.append(img)
            except Exception as e:
                print(f"Error loading image {url}: {e}")
                return None

        if not panel_images:
            return None

        # Set dimensions
        panel_width = 400  # Fixed width for each panel
        panel_height = 600  # Fixed height for each panel
        title_height = 80  # Space for title at top
        padding = 10

        # Resize all panels to be consistent
        panel_images = [img.resize((panel_width, panel_height)) for img in panel_images]

        # Create canvas with space for title
        canvas = Image.new(
            "RGB", (panel_width * 2, panel_height * 2 + title_height), "white"
        )
        draw = ImageDraw.Draw(canvas)

        # Load fonts
        try:
            title_font = ImageFont.truetype("arial.ttf", 36)
            font = ImageFont.truetype("arial.ttf", 20)
        except:
            title_font = ImageFont.load_default()
            font = ImageFont.load_default()

        # Draw title
        title_w = draw.textlength(title, font=title_font)
        draw.text(
            ((panel_width * 2 - title_w) // 2, padding),
            title,
            font=title_font,
            fill="black",
        )

        # Place panels and add text
        for idx, (img, texts) in enumerate(zip(panel_images, panel_texts)):
            x = (idx % 2) * panel_width
            y = (idx // 2) * panel_height + title_height

            # Paste panel
            canvas.paste(img, (x, y))

            # Draw each dialogue line as its own bubble, stacking vertically
            bubble_y = y + 40
            for dialogue_line in texts.get("dialogue", []):
                if dialogue_line:
                    draw_speech_bubble(
                        draw,
                        dialogue_line,
                        x + 20,
                        bubble_y,
                        font,
                        max_width=panel_width - 60,
                        padding=10,
                    )
                    bubble_y += 60  # Adjust vertical spacing between bubbles as needed

            # Draw caption at bottom
            if texts.get("narration"):
                draw_caption(
                    draw,
                    texts["narration"],
                    x,
                    y + panel_height,
                    panel_width,
                    font,
                    padding=10,
                )

        # Save stitched image
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"stitched_comic_{timestamp}.png"
        output_dir = os.path.join(settings.MEDIA_ROOT, "generated_images")
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, filename)
        canvas.save(file_path)

        return f"{settings.MEDIA_URL}generated_images/{filename}"
    except Exception as e:
        print(f"Error stitching panels: {e}")
        return None


# --- Main execution block for testing utils.py directly ---
if __name__ == "__main__":
    if API_KEY_CONFIGURED:
        print("\n--- Testing Comic Generation Utility Functions ---")

        # Test with a single prompt
        test_prompt = (
            "Teach children about the importance of keeping their environment clean"
        )

        comic_script_text, image_urls = generate_comic(
            prompt=test_prompt,
        )

        if comic_script_text:
            print("\n--- Generated Script Text ---")
            print(comic_script_text)
            print("---------------------------")

            # 2. Test Image Generation
            print("\n[2] Attempting to generate images based on script...")
            panel_descriptions = []
            current_panel_description = ""

            for line in comic_script_text.splitlines():
                if line.startswith("Panel "):
                    if current_panel_description:
                        panel_descriptions.append(current_panel_description.strip())
                    current_panel_description = ""
                elif line.lower().startswith("scene description:"):
                    current_panel_description += (
                        line.replace("Scene Description:", "", 1).strip() + " "
                    )
                elif (
                    current_panel_description
                    and not line.lower().startswith("dialogue:")
                    and not line.lower().startswith("narration:")
                ):
                    current_panel_description += line.strip() + " "

            if current_panel_description:
                panel_descriptions.append(current_panel_description.strip())

            if not panel_descriptions:
                print(
                    "Could not parse panel descriptions from script for image generation test."
                )
            else:
                for i, desc in enumerate(panel_descriptions):
                    if not desc:
                        print(
                            f"Skipping image generation for Panel {i+1} due to empty description."
                        )
                        continue

                    print(
                        f"\nGenerating image for Panel {i+1} (Description: '{desc[:100]}...')"
                    )
                    image_url = generate_panel_image(desc, panel_number=i)
                    if image_url:
                        print(f"Panel {i+1} image URL: {image_url}")
                    else:
                        print(f"Failed to generate image for Panel {i+1}.")
        else:
            print(
                "Comic script generation failed. Cannot proceed to image generation test."
            )
    else:
        print("Cannot run tests: Gemini API Key is not configured.")
