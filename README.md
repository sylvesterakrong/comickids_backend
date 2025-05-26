ComicKids Backend
ComicKids Backend is a Django REST API that generates educational comic strips for Ghanaian primary school students. It uses Google Gemini for script generation and Stability AI for panel image generation, then stitches the panels together with speech bubbles overlayed using Pillow.

Features
Script Generation: Uses Gemini to create a multi-panel comic script based on a learning objective.

Panel Image Generation: Uses Stability AI to generate unique images for each panel’s scene description.

Speech Bubble Overlay: Extracts dialogue from the script and overlays it as speech bubbles on each panel.

Panel Stitching: Combines all panels into a single comic strip image.

Media Serving: Serves generated images via Django’s media system.

Fallback Placeholders: Uses placeholder images if image generation fails.

Requirements
Python 3.10+
Django 4+
Pillow
requests
python-decouple
djangorestframework
Google Gemini API key
Stability AI API key

Usage
Visit http://127.0.0.1:8000/ to access the frontend.

Use the API endpoint /api/generate/ to POST a JSON payload:
The response will include the generated script and the URL to the stitched comic image.

Project Structure
comickids_backend/
├── core/
│   ├── [utils.py](http://_vscodecontentref_/1)         # Main logic for script, image, and comic generation
│   ├── views.py         # API views
│   ├── models.py        # ComicStrip model
│   └── templates/core/
│       └── home.html    # Frontend template
├── media/               # Generated images (auto-created)
├── static/              # Static files
├── .env                 # Environment variables (not committed)
├── [requirements.txt](http://_vscodecontentref_/2)
└── manage.py

Notes
Make sure to add .env and media/ to your .gitignore.
For production, set DEBUG=False and configure allowed hosts and secure settings.
The project uses a hardcoded number of panels (NUM_PANELS = 4). You can adjust this in core/utils.py.
License
MIT License

Acknowledgements
Google Gemini
Stability AI
Django
Pillow
Happy comic making!
Notes
Make sure to add .env and media/ to your .gitignore.
For production, set DEBUG=False and configure allowed hosts and secure settings.
The project uses a hardcoded number of panels (NUM_PANELS = 4). You can adjust this in core/utils.py.
License
MIT License

Acknowledgements
Google Gemini
Stability AI
Django
Pillow
Happy comic making!
