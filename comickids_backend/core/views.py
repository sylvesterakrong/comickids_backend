from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .utils import (
    extract_panel_texts_robust,
    generate_comic,
    extract_panel_dialogues,
    stitch_panels,
    extract_panel_texts,
)
from .models import ComicStrip
# FOR OPTIMIZATION
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import time
import gc


def home_view(request):
    return render(request, "core/home.html")


class GenerateComicView(APIView):
    def post(self, request):
        prompt = request.data.get("prompt")
        if not prompt:
            return Response(
                {"error": "No prompt provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ADD TIMEOUT WRAPPER HERE - This is the main change
        try:
            # Use threading to prevent timeout issues
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.generate_comic_with_timeout, prompt)
                try:
                    # 3.5 minute timeout (leave buffer for Render's 5min limit)
                    result = future.result(timeout=210)
                    return result
                except FuturesTimeoutError:
                    return Response(
                        {
                            'error': 'Comic generation timed out. The server is processing too many requests.',
                            'suggestion': 'Please try again in a few minutes.'
                        }, 
                        status=408
                    )
        except Exception as e:
            print(f"Error in comic generation wrapper: {str(e)}")
            return Response(
                {"error": f"Failed to generate comic: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ADD THIS NEW METHOD - Contains your existing logic with optimizations
    def generate_comic_with_timeout(self, prompt):
        """Your existing comic generation logic with optimizations"""
        start_time = time.time()
        print(f"Debug: Starting comic generation at {time.time()}")

        # Generate script and panel images with error handling
        try:
            # ADD TIMING DEBUG
            print("Debug: Calling generate_comic function...")
            comic_start_time = time.time()
            
            result = generate_comic(prompt)
            
            comic_generation_time = time.time() - comic_start_time
            print(f"Debug: generate_comic completed in {comic_generation_time:.2f} seconds")
            
            # Debug: Print the actual result structure
            print(f"Generate comic result type: {type(result)}")
            print(f"Generate comic result length: {len(result) if isinstance(result, tuple) else 'Not a tuple'}")
            
            # Handle the 3-value return: title, script, image_urls
            if isinstance(result, tuple) and len(result) == 3:
                title, script_text, image_urls = result
                print(f"Extracted - Title: {title}")
                print(f"Script length: {len(script_text) if script_text else 0}")
                print(f"Number of images: {len(image_urls) if image_urls else 0}")
            else:
                print(f"Unexpected result format from generate_comic: {result}")
                return Response(
                    {"error": "Invalid comic generation result format"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        except Exception as e:
            print(f"Error generating comic: {e}")
            return Response(
                {"error": f"Failed to generate comic: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Check if all required components were generated
        if not script_text or not image_urls or not title:
            missing_components = []
            if not title:
                missing_components.append("title")
            if not script_text:
                missing_components.append("script")
            if not image_urls:
                missing_components.append("images")
            
            return Response(
                {"error": f"Failed to generate comic components: {', '.join(missing_components)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Debug: Print the full script for analysis
        print("=== GENERATED SCRIPT ===")
        print(f"Title: {title}")
        print(f"Script: {script_text[:200]}...")  # Print first 200 chars
        print("========================")

        # Extract panel texts with debugging
        try:
            panel_extraction_start = time.time()
            panel_texts = extract_panel_texts(script_text)
            print("Extracted Panel Texts:", panel_texts)
            print(f"Debug: Panel extraction took {time.time() - panel_extraction_start:.2f} seconds")
            
            # Additional debugging: count non-empty panels
            non_empty_panels = sum(1 for panel in panel_texts if panel.get('dialogue') or panel.get('narration'))
            print(f"Non-empty panels found: {non_empty_panels} out of {len(panel_texts)}")
            
            # If most panels are empty, try the robust extraction method
            if non_empty_panels < len(panel_texts) / 2:
                print("Trying robust extraction method...")
                panel_texts = extract_panel_texts_robust(script_text)
                print("Robust extraction result:", panel_texts)
        
        except Exception as e:
            print(f"Error extracting panel texts: {e}")
            # Fallback to empty panel texts
            panel_texts = [{"dialogue": [], "narration": ""} for _ in range(4)]

        # ADD MEMORY CLEANUP AFTER PANEL EXTRACTION
        gc.collect()

        try:
            # Use the extracted title for the comic
            stitch_start_time = time.time()
            print("Debug: Starting panel stitching...")
            
            stitched_url = stitch_panels(image_urls, panel_texts, title=title)
            
            stitch_time = time.time() - stitch_start_time
            print(f"Debug: Panel stitching took {stitch_time:.2f} seconds")
            
        except Exception as e:
            print(f"Error stitching panels: {e}")
            return Response(
                {"error": f"Failed to stitch panels: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not stitched_url:
            return Response(
                {"error": "Failed to create final comic image"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Save to database
        try:
            db_start_time = time.time()
            comic = ComicStrip.objects.create(
                prompt=prompt, 
                text=script_text, 
                image_url=stitched_url
            )
            print(f"Debug: Database save took {time.time() - db_start_time:.2f} seconds")
            
        except Exception as e:
            print(f"Error saving to database: {e}")
            return Response(
                {"error": f"Failed to save comic: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # ADD FINAL MEMORY CLEANUP
        gc.collect()
        
        total_time = time.time() - start_time
        print(f"Debug: TOTAL comic generation time: {total_time:.2f} seconds")

        return Response(
            {
                "id": comic.id,
                "title": title,  # Include title in response
                # "text": script_text,
                "image_url": stitched_url,
                "panel_urls": image_urls,
                "generation_time": f"{total_time:.2f}s",  # ADD TIMING INFO
                # "panel_texts": panel_texts,  # Include extracted panel texts for debugging/frontend use
            },
            status=status.HTTP_201_CREATED,
        )