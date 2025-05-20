from django.test import TestCase
from rest_framework.test import APITestCase
from django.urls import reverse
from rest_framework import status

# Create your tests here.

class GenerateComicAPITest(APITestCase):
    def test_generate_comic_success(self):
        url = reverse('generate-comic')
        data = {
            "prompt": "Tell a story about sharing food",
            "topic": "A story about sharing food",
            "cultural_elements": ["kelewele", "Kente cloth patterns", "Adinkra symbols"],
            "subject": "Math",
            "age_group": "8-10"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("text", response.data)
        self.assertIn("id", response.data)