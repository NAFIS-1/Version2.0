import os

# --- API Key Configuration ---
# IMPORTANT: Use environment variables for production!
# For local development, you might temporarily hardcode it or use a .env file.
API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyDFaqYzccpuwY2kUJbcUC6YovKfdCZaSiQ") # Use environment variable, fallback to hardcoded for demo

# --- File Upload Configuration ---
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'pdf', 'docx'}

# --- Static and Template Folders ---
STATIC_FOLDER = "static"
TEMPLATES_FOLDER = "templates"

# --- Gemini Model ---
GEMINI_MODEL_NAME = "gemini-2.5-flash-preview-05-20"