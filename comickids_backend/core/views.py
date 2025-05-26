from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import ComicStrip
from .utils import generate_comic, extract_panel_dialogues, stitch_panels


def home_view(request):
    return render(request, 'core/home.html')


class GenerateComicView(APIView):
    def post(self, request):
        prompt = request.data.get("prompt")
        
        # Generate script and images
        script_text, image_urls = generate_comic(prompt)
        
        if script_text is None:
            return Response(
                {"error": "Failed to generate comic script"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Extract dialogues and create comic with speech bubbles
        dialogues = extract_panel_dialogues(script_text)
        stitched_image_url = stitch_panels(image_urls, dialogues)

        # Save to database
        comic = ComicStrip.objects.create(
            prompt=prompt,
            text=script_text,
            image_url=stitched_image_url
        )

        return Response({
            "text": script_text,
            "id": comic.id,
            "image_url": stitched_image_url,
            "warning": None if stitched_image_url else "Image generation failed"
        }, status=status.HTTP_201_CREATED)
