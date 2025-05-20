from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import ComicStrip
from .utils import generate_comic

def home_view(request):
    return render(request, 'core/home.html')

class GenerateComicView(APIView):
    def post(self, request):
        data = request.data
        learning_objective = data.get("prompt") 
        student_topic = data.get("topic")
        cultural_elements = data.get("cultural_elements", [])  # Expect a list from frontend
        subject = data.get("subject")
        age_group = data.get("age_group")

        # Ensure cultural_elements is a list
        if isinstance(cultural_elements, str):
            import json
            try:
                cultural_elements = json.loads(cultural_elements)
            except Exception:
                cultural_elements = [cultural_elements]

        result, image_url = generate_comic(learning_objective, student_topic, cultural_elements)
        
        if result is None :
            return Response({"error": "Failed to generate comic script"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        comic = ComicStrip.objects.create(
            topic=student_topic,
            subject=subject,
            age_group=age_group,
            prompt=learning_objective,
            text=result,
            image_url=image_url,
        )

        return Response({
            "text": result,
            "id": comic.id, 
            "image_url": image_url,    
            "warning": "Image generation failed" if image_url is None else None
        }, status=status.HTTP_201_CREATED)
