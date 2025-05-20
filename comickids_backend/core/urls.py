from django.urls import path
from .views import GenerateComicView, home_view

urlpatterns = [
    path('', home_view, name='home'),
    path('generate/', GenerateComicView.as_view(), name='generate-comic'),
]
