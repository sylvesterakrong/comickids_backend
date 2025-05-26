from django.db import models

# Create your models here.
class ComicStrip(models.Model):
    prompt = models.TextField()
    image_url = models.URLField(blank=True, null=True)  
    text = models.TextField()    
    created_at = models.DateTimeField(auto_now_add=True)

def __str__(self):
        return f"ComicStrip {self.id} - {self.prompt[:50]}"