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
import requests
from urllib.request import urlopen
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
PLACEHOLDER_IMAGES = [
    "https://i.pinimg.com/736x/ec/fe/70/ecfe70dfa4f2787f8150cf37a0a48c95.jpg",
    "https://i.pinimg.com/736x/e0/e8/86/e0e886bcff958f78d42bd03ef0aaf9e9.jpg",
    "https://i.pinimg.com/736x/59/8c/15/598c158734a5ef537a3b27f2be2ebbe6.jpg",
    "https://i.pinimg.com/736x/78/f5/51/78f5517224e1ec547e10408b399c0ebc.jpg",
]

NUM_PANELS = 4

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
    Your task is to generate a script for a {NUM_PANELS}-panel comic strip.

    Learning Objective: {prompt}
    Mandatory Ghanaian Cultural Elements to be included to give it a natural feel

    The script for each panel must clearly define:
    1.  Panel Number: (e.g., Panel 1)
    2.  Scene Description: Detailed visual elements, setting, character appearances (simple, relatable Ghanaian characters), character actions, and expressions. Incorporate the cultural elements here.
    3.  Dialogue: What characters say (if any). Keep it simple and clear.
    4.  Narration/Caption: Text that explains the scene or reinforces the learning objective (if any).

    The story should be engaging, easy to understand for a primary school student, directly teach or illustrate the learning objective, and be culturally sensitive and relevant to Ghana. It should also be grammatically correct.
    Output the script as a clear, well-structured text. You could use Markdown for structure or a JSON-like format if specifically requested.
    """

    try:
        model = genai.GenerativeModel(TEXT_MODEL_NAME)
        response = model.generate_content(enhanced_prompt)

        if response.text:
            comic_script = response.text

            # Generate or get placeholder images for all panels
            panel_descriptions = extract_panel_descriptions(comic_script)
            image_urls = []
            for i, desc in enumerate(panel_descriptions):
                image_url = generate_panel_image(
                    panel_description=desc,
                    panel_number=i
                )
                image_urls.append(image_url)

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

def extract_panel_descriptions(script: str) -> list[str]:
    """Extracts scene descriptions for each panel from the script."""
    descriptions = []
    current_desc = ""
    for line in script.splitlines():
        if line.strip().startswith("Panel "):
            if current_desc:
                descriptions.append(current_desc.strip())
            current_desc = ""
        elif line.lower().startswith("scene description:"):
            current_desc += line.replace("Scene Description:", "", 1).strip() + " "
        elif current_desc and not line.lower().startswith("dialogue:") and not line.lower().startswith("narration:"):
            current_desc += line.strip() + " "
    if current_desc:
        descriptions.append(current_desc.strip())
    return descriptions

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
    """Parses the Gemini-generated script to extract dialogues for each panel."""
    dialogues = []
    current_dialogue = ""

    for line in script.splitlines():
        if line.startswith("Panel "):
            if current_dialogue:
                dialogues.append(current_dialogue.strip())
            current_dialogue = ""
        elif line.lower().startswith("dialogue:"):
            current_dialogue = line.replace("Dialogue:", "").strip()
    if current_dialogue:
        dialogues.append(current_dialogue.strip())
    
    return dialogues

def draw_speech_bubble(draw, text, x, y, font, padding=10):
    """Draw a speech bubble with automatic text wrapping."""
    
    # Calculate text size and wrap long text
    max_width = 300  # Maximum bubble width
    words = text.split()
    lines = []
    current_line = []
    current_width = 0

    for word in words:
        word_width = draw.textlength(word + " ", font=font)
        if current_width + word_width <= max_width:
            current_line.append(word)
            current_width += word_width
        else:
            lines.append(" ".join(current_line))
            current_line = [word]
            current_width = word_width
    
    if current_line:
        lines.append(" ".join(current_line))

    # Calculate bubble dimensions
    line_heights = [draw.textbbox((0, 0), line, font=font)[3] for line in lines]
    bubble_width = max(draw.textlength(line, font=font) for line in lines) + (padding * 2)
    bubble_height = sum(line_heights) + (padding * 2) + (5 * (len(lines) - 1))

    # Draw bubble background
    bubble_shape = [
        (x, y),
        (x + bubble_width, y),
        (x + bubble_width, y + bubble_height),
        (x, y + bubble_height)
    ]
    draw.polygon(bubble_shape, fill="white", outline="black")

    # Add tail to bubble
    tail_points = [
        (x + 10, y + bubble_height),
        (x - 10, y + bubble_height + 20),
        (x + 30, y + bubble_height)
    ]
    draw.polygon(tail_points, fill="white", outline="black")

    # Draw text
    current_y = y + padding
    for line in lines:
        draw.text((x + padding, current_y), line, fill="black", font=font)
        current_y += line_heights[0] + 5

def stitch_panels(image_urls: list[str], dialogues: list[str]) -> str:
    """Stitch panels together with dialogues in speech bubbles."""
    if not image_urls:
        return None

    try:
        # Load images
        panel_images = []
        for url in image_urls:
            if url.startswith('http'):
                response = requests.get(url)
                img = Image.open(BytesIO(response.content))
            else:
                img = Image.open(url.replace('/media/', settings.MEDIA_ROOT + '/'))
            panel_images.append(img)

        # Calculate dimensions
        panel_width = panel_images[0].width
        panel_height = panel_images[0].height
        gap = 10  # Gap between panels
        
        # Create canvas
        canvas = Image.new('RGB', 
            (panel_width * 2, 
             panel_height * ((len(panel_images) + 1) // 2)), 
            'white')

        # Load font
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except:
            font = ImageFont.load_default()

        # Place panels and add speech bubbles
        for idx, (img, dialogue) in enumerate(zip(panel_images, dialogues)):
            x = (idx % 2) * panel_width
            y = (idx // 2) * panel_height
            
            # Paste panel
            canvas.paste(img, (x, y))
            
            # Add speech bubble if there's dialogue
            if dialogue:
                draw = ImageDraw.Draw(canvas)
                draw_speech_bubble(
                    draw, 
                    dialogue, 
                    x + 20,  # Bubble position X 
                    y + 20,  # Bubble position Y
                    font
                )

        # Save stitched image
        output_path = os.path.join(
            settings.GENERATED_IMAGES_DIR, 
            f'comic_strip_{int(time.time())}.png'
        )
        canvas.save(output_path, 'PNG')
        
        # Return media URL
        return f"{settings.MEDIA_URL}generated_images/{os.path.basename(output_path)}"

    except Exception as e:
        print(f"Error stitching panels: {e}")
        return None

# --- Main execution block for testing utils.py directly ---
if __name__ == "__main__":
    if API_KEY_CONFIGURED:
        print("\n--- Testing Comic Generation Utility Functions ---")

        # Test with a single prompt
        test_prompt = "Teach children about the importance of keeping their environment clean"
        
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
                    image_data = generate_panel_image(desc, panel_number=i)
                    if image_data:
                        save_image(image_data, f"panel_{i+1}")
                    else:
                        print(f"Failed to generate image for Panel {i+1}.")
        else:
            print(
                "Comic script generation failed. Cannot proceed to image generation test."
            )
    else:
        print("Cannot run tests: Gemini API Key is not configured.")
