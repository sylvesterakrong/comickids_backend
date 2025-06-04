# ComicKids Backend

> An educational comic strip generator for Ghanaian primary school students, powered by AI.

## Overview

ComicKids Backend is a Django REST API that generates educational comic strips. It uses:

- **Google Gemini** for script generation
- **Stability AI** for panel image generation
- **Pillow** for stitching panels and adding speech bubbles

## ✨ Features

- 🤖 **Script Generation**: Creates multi-panel comic scripts using Gemini
- 🎨 **Panel Image Generation**: Generates unique images via Stability AI
- 💬 **Speech Bubble Overlay**: Adds dialogue bubbles to each panel
- 🔄 **Panel Stitching**: Combines panels into a single comic strip
- 📡 **Media Serving**: Serves images via Django's media system
- ⚡ **Fallback System**: Uses placeholders if image generation fails

## 🚀 Requirements

- Python 3.10+
- Django 4+
- Pillow
- requests
- python-decouple
- djangorestframework
- Google Gemini API key
- Stability AI API key

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/comickids_backend.git

# Navigate to project directory
cd comickids_backend

# Install dependencies
pip install -r requirements.txt

# Create .env file and add your API keys
echo "GEMINI_API_KEY=your_key_here" >> .env
echo "STABILITY_API_KEY=your_key_here" >> .env

# Run migrations
python manage.py migrate

# Start the server
python manage.py runserver
```

## 🔧 Usage

### Frontend

Visit `http://127.0.0.1:8000/` to access the web interface.

### API Endpoint

Send POST requests to `/api/generate/` with JSON payload:

```json
{
    "prompt": "Your learning objective here"
}
```

## 📁 Project Structure

```python

comickids_backend/
├── core/
│   ├── utils.py         # Main logic
│   ├── views.py         # API views
│   ├── models.py        # Database models
│   └── templates/core/
│       └── home.html    # Frontend template
├── media/               # Generated images
├── static/              # Static files
├── .env                 # Environment variables
└── manage.py
```

comickids_backend/
├── core/
│   ├── utils.py         # Main logic
│   ├── views.py         # API views
│   ├── models.py        # Database models
│   └── templates/core/
│       └── home.html    # Frontend template
├── media/               # Generated images
├── static/             # Static files
├── .env                # Environment variables
└── manage.py

```python
```
## ⚠️ Important Notes

- Add `.env` and `media/` to your `.gitignore`
- For production:
  - Set `DEBUG=False`
  - Configure allowed hosts
  - Set up secure settings
- Default: 4 panels per comic (configurable in `core/utils.py`)

## 📄 License

This project is licensed under the Apache License - see the [LICENSE](LICENSE) file for details.

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/sylvesterakrong/comickids_backend)

## 🙏 Acknowledgements

- [Google Gemini](https://cloud.google.com/vertex-ai/docs/generative-ai/model-reference/gemini)
- [Stability AI](https://stability.ai/)
- [Django](https://www.djangoproject.com/)
- [Pillow](https://python-pillow.org/)

---

Made with ❤️ for Ghanaian education
