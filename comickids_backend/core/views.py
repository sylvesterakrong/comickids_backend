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

        # Generate script and panel images
        script_text, image_urls = generate_comic(prompt)

        if not script_text or not image_urls:
            return Response(
                {"error": "Failed to generate comic"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Debug: Print the full script for analysis
        print("=== GENERATED SCRIPT ===")
        print(script_text)
        print("========================")

        # Extract panel texts with debugging
        panel_texts = extract_panel_texts(script_text)
        print("Extracted Panel Texts:", panel_texts)
        
        # Additional debugging: count non-empty panels
        non_empty_panels = sum(1 for panel in panel_texts if panel['dialogue'] or panel['narration'])
        print(f"Non-empty panels found: {non_empty_panels} out of {len(panel_texts)}")
        
        # If most panels are empty, try the robust extraction method
        if non_empty_panels < len(panel_texts) / 2:
            print("Trying robust extraction method...")
            panel_texts = extract_panel_texts_robust(script_text)
            print("Robust extraction result:", panel_texts)

        stitched_url = stitch_panels(image_urls, panel_texts)

        if not stitched_url:
            return Response(
                {"error": "Failed to stitch panels"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Save to database
        comic = ComicStrip.objects.create(
            prompt=prompt, 
            text=script_text, 
            image_url=stitched_url
        )

        return Response(
            {
                "id": comic.id,
                "text": script_text,
                "image_url": stitched_url,
                "panel_urls": image_urls,
            },
            status=status.HTTP_201_CREATED,
        )
