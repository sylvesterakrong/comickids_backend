from django.db import models

# Create your models here.
class ComicStrip(models.Model):
    topic = models.CharField(max_length=200)
    subject = models.CharField(max_length=100)
    age_group= models.CharField(max_length=50)
    prompt = models.TextField()
    image_url = models.URLField(blank=True, null=True)  # Add this line    
    text = models.TextField()      # Any narration/dialogue
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.topic