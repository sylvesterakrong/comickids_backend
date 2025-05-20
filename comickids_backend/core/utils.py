# core/utils.py

import google.generativeai as genai
from decouple import config, UndefinedValueError
import os
import json
import requests
import time
import base64
from django.conf import settings
from datetime import datetime

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
    "https://placehold.co/600x400/png?text=Educational+Comic+Panel+1",
    "https://placehold.co/600x400/png?text=Educational+Comic+Panel+2",
    "https://placehold.co/600x400/png?text=Educational+Comic+Panel+3",
    "https://placehold.co/600x400/png?text=Educational+Comic+Panel+4",
]


# --- Comic Script Generation ---
def generate_comic(
    learning_objective: str,
    student_topic: str,
    cultural_elements: list,
    num_panels: int = 4,
) -> tuple[str | None, list | None]:
    """
    Generates a comic script and attempts to generate images, falling back to placeholders if needed.
    Returns a tuple of (script, list of image URLs)
    """
    if not API_KEY_CONFIGURED:
        print("Error in generate_comic_script: Gemini API Key not configured.")
        return None, None

    # --- Prompt Engineering for Script Generation ---
    cultural_elements_str = ", ".join(cultural_elements)
    prompt = f"""
    You are an expert creator of educational comic strips for Ghanaian primary school students.
    Your task is to generate a script for a {num_panels}-panel comic strip.

    Learning Objective: {learning_objective}
    Student's Topic Idea: {student_topic}
    Mandatory Ghanaian Cultural Elements to include naturally: {cultural_elements_str}

    The script for each panel must clearly define:
    1.  Panel Number: (e.g., Panel 1)
    2.  Scene Description: Detailed visual elements, setting, character appearances (simple, relatable Ghanaian characters), character actions, and expressions. Incorporate the cultural elements here.
    3.  Dialogue: What characters say (if any). Keep it simple and clear.
    4.  Narration/Caption: Text that explains the scene or reinforces the learning objective (if any).

    The story should be engaging, easy to understand for a primary school student, directly teach or illustrate the learning objective, and be culturally sensitive and relevant to Ghana.
    Output the script as a clear, well-structured text. You could use Markdown for structure or a JSON-like format if specifically requested.
    """

    try:
        model = genai.GenerativeModel(TEXT_MODEL_NAME)
        response = model.generate_content(prompt)

        if response.text:
            comic_script = response.text

            # Generate or get placeholder images for all panels
            image_urls = []
            for i in range(num_panels):
                image_url = generate_panel_image(
                    panel_description=comic_script, panel_number=i
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
    style_description: str = "Educational comic book style for young children, clear lines, vibrant colors, simple characters, Ghana setting.",
) -> str:
    """
    Generates an image using Stability AI, falls back to placeholder if generation fails.
    Returns a URL to the generated image or a placeholder.
    """
    if not STABILITY_API_KEY:
        print("Warning: Using placeholder image (Stability API key not configured)")
        return PLACEHOLDER_IMAGES[panel_number % len(PLACEHOLDER_IMAGES)]

    if not panel_description.strip():
        print("Warning: panel_description is empty, using placeholder.")
        return PLACEHOLDER_IMAGES[panel_number % len(PLACEHOLDER_IMAGES)]

    try:
        prompt = f"{panel_description.strip()}. {style_description}"

        # Print request details for debugging
        print(f"Debug - Sending request with prompt: {prompt[:50]}...")

        # Using the exact format from the Stability AI documentation
        headers = {
            "Authorization": f"Bearer {STABILITY_API_KEY}",
            "Accept": "application/json",
        }

        # This is key: use empty files dict and put parameters in data
        files = {"none": ""}
        data = {
            "prompt": prompt,
            "cfg_scale": "7",
            "height": "1024",
            "width": "1024",
            "samples": "1",
            "steps": "30",
            "output_format": "png",  # Explicitly specify output format
        }

        print(f"Debug - Request data: {data}")

        response = requests.post(
            "https://api.stability.ai/v2beta/stable-image/generate/core",
            headers=headers,
            files=files,
            data=data,
            timeout=60,
        )

        print(f"Debug - Response Status: {response.status_code}")
        print(f"Debug - Response Headers: {response.headers}")

        if response.status_code == 200:
            data = response.json()
            if "artifacts" in data and data["artifacts"]:
                img_b64 = data["artifacts"][0]["base64"]
                # Save the image and get its URL
                image_url = save_base64_image(img_b64, panel_number)
                if image_url:
                    return image_url

            print("Warning: Could not save image, falling back to placeholder")
        else:
            print(f"Stability AI error: {response.status_code} {response.text}")

    except Exception as e:
        print(f"Error during image generation: {e}")

    # Fallback to placeholder
    return PLACEHOLDER_IMAGES[panel_number % len(PLACEHOLDER_IMAGES)]


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


# --- Main execution block for testing utils.py directly ---
if __name__ == "__main__":
    if API_KEY_CONFIGURED:
        print("\n--- Testing Comic Generation Utility Functions ---")

        # 1. Test Script Generation
        print("\n[1] Generating comic script...")
        script_learning_objective = "Understanding how plants grow from seeds."
        script_student_topic = "My little farm"
        script_cultural_elements = [
            "yam planting",
            "children helping on a small family farm",
            "sunny Ghanaian countryside",
        ]

        comic_script_text, image_urls = generate_comic(
            script_learning_objective,
            script_student_topic,
            script_cultural_elements,
            num_panels=2,
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
