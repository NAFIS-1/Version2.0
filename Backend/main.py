import os
import shutil
from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates # Not strictly needed if returning raw HTML_CONTENT
from fastapi.middleware.cors import CORSMiddleware # Import CORSMiddleware

# Import modules from our new files
from config import UPLOAD_FOLDER, ALLOWED_EXTENSIONS, STATIC_FOLDER, TEMPLATES_FOLDER
from utils import allowed_file, extract_text_from_pdf, extract_text_from_docx
from gemini_processor import extract_info_with_gemini # Import the modified function

# === FastAPI App ===
app = FastAPI(
    title="Resume Parser API",
    description="Extracts information from PDF/DOCX resumes using Google Gemini AI."
)

# === CORS Configuration ===
# Define the origins that are allowed to make requests to your API.
# You can use ["*"] to allow all origins during development, but for production,
# it's recommended to list specific origins (e.g., ["http://localhost:8000", "https://your-frontend-domain.com"]).
origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    # Add any other origins where your frontend might be hosted
    "http://localhost:3000", # Example for a React/Vue/Angular dev server
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allows all standard methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allows all headers
)

# Create directories if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)
os.makedirs(TEMPLATES_FOLDER, exist_ok=True)

# Mount static files (CSS)
app.mount("/static", StaticFiles(directory=STATIC_FOLDER), name="static")

# No longer explicitly using Jinja2Templates for index.html if we embed it,
# but keeping the import just in case you switch to proper templating.
# templates = Jinja2Templates(directory=TEMPLATES_FOLDER)


# === FastAPI Routes ===

@app.get("/", response_class=HTMLResponse, summary="Serve Frontend HTML")
async def read_root():
    """Serves the main HTML page for the resume parser."""
    # This will read the HTML content from the file system
    with open(os.path.join(TEMPLATES_FOLDER, "index.html"), "r") as f:
        html_content = f.read()
    return html_content # Return the content of the file

@app.post("/upload", summary="Upload and Parse Resume")
async def upload_resume(file: UploadFile = File(...)):
    """
    Uploads a PDF or DOCX resume, extracts text, and parses information
    using Google Gemini AI.
    """
    if not allowed_file(file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Allowed types are PDF and DOCX."
        )

    filename = os.path.basename(file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        print(f"File saved to {file_path}")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving uploaded file: {e}"
        )
    finally:
        file.file.close()

    resume_text = ""
    try:
        if filename.lower().endswith('.pdf'):
            resume_text = extract_text_from_pdf(file_path)
        elif filename.lower().endswith('.docx'):
            resume_text = extract_text_from_docx(file_path)

        if not resume_text.strip():
            print(f"Extracted text from {filename} is empty.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract text from the document or document is empty."
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing file: {str(e)}"
        )

    try:
        # This will now return a dict like {"extractedData": ..., "completenessPercentage": ...}
        response_data = extract_info_with_gemini(resume_text)

        return response_data # FastAPI automatically converts dict to JSON response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process resume with AI: {str(e)}"
        )
    finally:
        if os.path.exists(file_path):
            try:
                # os.remove(file_path) # Uncomment to delete uploaded file after processing
                pass
            except Exception as e_remove:
                print(f"Error removing uploaded file {file_path}: {e_remove}")


# --- Embedded HTML and CSS (Only for initial file generation in startup) ---
# It's better to manage these in their respective files directly.
# These will be used by the @app.on_event("startup") to create the files if they don't exist.

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Resume Parser</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <div class="container">
        <h1>Upload Your Resume</h1>
        <form id="uploadForm" enctype="multipart/form-data">
            <div class="file-input-wrapper">
                <input type="file" id="resumeFile" name="file" accept=".pdf,.docx" required>
                <label for="resumeFile" class="file-input-label">Choose File</label>
                <span id="fileNameDisplay" class="file-name-display">No file chosen</span>
            </div>
            <button type="submit">Parse Resume</button>
        </form>

        <div id="loading" class="hidden">
            <div class="spinner"></div>
            <p id="loadingMessage">Parsing your resume... Please wait.</p>
            <p id="progressPercentage">0% Completed</p>
        </div>

        <div id="responseContainer" class="hidden">
            <h2>Extracted Information:</h2>
            <p id="completenessScore"></p> <pre id="responseContent"></pre>
        </div>

        <div id="errorContainer" class="hidden">
            <h2>Error:</h2>
            <p id="errorMessage"></p>
            <pre id="errorDetails"></pre>
        </div>
    </div>

    <script>
        const uploadForm = document.getElementById('uploadForm');
        const resumeFileInput = document.getElementById('resumeFile');
        const fileNameDisplay = document.getElementById('fileNameDisplay');
        const loadingDiv = document.getElementById('loading');
        const loadingMessage = document.getElementById('loadingMessage');
        const progressPercentage = document.getElementById('progressPercentage');
        const responseContainer = document.getElementById('responseContainer');
        const completenessScore = document.getElementById('completenessScore'); // Get the new completeness score element
        const responseContent = document.getElementById('responseContent');
        const errorContainer = document.getElementById('errorContainer');
        const errorMessage = document.getElementById('errorMessage');
        const errorDetails = document.getElementById('errorDetails');

        let clientProgressInterval;
        let currentClientProgress = 0;
        const clientTotalDuration = 15000; // Total duration for frontend percentage increase in milliseconds (e.g., 15 seconds)
        const clientUpdateInterval = 200; // Update every 200ms

        function startClientProgress() {
            currentClientProgress = 0;
            progressPercentage.textContent = '0% Completed';
            loadingMessage.textContent = 'Uploading and extracting text...';

            clientProgressInterval = setInterval(() => {
                if (currentClientProgress < 30) {
                    currentClientProgress += 1;
                } else if (currentClientProgress < 70) {
                    currentClientProgress += 1;
                    loadingMessage.textContent = 'Analyzing with AI...';
                } else if (currentClientProgress < 99) {
                    currentClientProgress += 1;
                    loadingMessage.textContent = 'Finalizing analysis...';
                } else if (currentClientProgress >= 99) {
                    currentClientProgress = 99;
                }
                progressPercentage.textContent = `${currentClientProgress}% Completed`;
            }, clientUpdateInterval);
        }

        function stopClientProgress() {
            clearInterval(clientProgressInterval);
            currentClientProgress = 0;
            loadingMessage.textContent = 'Parsing your resume... Please wait.';
            progressPercentage.textContent = '0% Completed';
        }

        resumeFileInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                fileNameDisplay.textContent = this.files[0].name;
            } else {
                fileNameDisplay.textContent = 'No file chosen';
            }
        });

        uploadForm.addEventListener('submit', async function(event) {
            event.preventDefault();

            responseContainer.classList.add('hidden');
            errorContainer.classList.add('hidden');
            loadingDiv.classList.remove('hidden');

            startClientProgress(); // Start the animated client-side progress bar

            const formData = new FormData();
            const file = resumeFileInput.files[0];

            if (!file) {
                alert('Please select a file to upload.');
                loadingDiv.classList.add('hidden');
                stopClientProgress();
                return;
            }

            formData.append('file', file);

            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });

                stopClientProgress(); // Stop client-side progress when response is received
                loadingDiv.classList.add('hidden');

                const data = await response.json();

                if (response.ok) {
                    // Display the completeness score
                    completenessScore.textContent = `Resume Completeness: ${data.completenessPercentage}%`;

                    // Display the extracted data (now nested under extractedData)
                    responseContent.textContent = JSON.stringify(data.extractedData, null, 2);
                    responseContainer.classList.remove('hidden');
                } else {
                    errorMessage.textContent = data.detail || data.error || 'An unknown error occurred.';
                    if (data.details) {
                        errorDetails.textContent = `Details: ${data.details}`;
                    } else if (data.raw_response) {
                        errorDetails.textContent = `Raw AI Response: ${data.raw_response}`;
                    } else if (data.detail && typeof data.detail === 'string') {
                        errorDetails.textContent = data.detail;
                    }
                    else {
                        errorDetails.textContent = JSON.stringify(data, null, 2);
                    }
                    errorContainer.classList.remove('hidden');
                }
            } catch (error) {
                console.error('Network or fetch error:', error);
                stopClientProgress();
                loadingDiv.classList.add('hidden');
                errorMessage.textContent = 'Failed to connect to the server. Please check your network connection.';
                errorDetails.textContent = `Error: ${error.message}`;
                errorContainer.classList.remove('hidden');
            }
        });
    </script>
</body>
</html>
"""

CSS_CONTENT = """
/* static/style.css */
body {
    font-family: Arial, sans-serif;
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
    margin: 0;
    background-color: #f4f4f4;
    color: #333;
}

.container {
    background-color: #fff;
    padding: 30px;
    border-radius: 8px;
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
    text-align: center;
    width: 100%;
    max-width: 600px;
}

h1 {
    color: #0056b3;
    margin-bottom: 25px;
}

form {
    margin-bottom: 25px;
}

.file-input-wrapper {
    position: relative;
    display: inline-block;
    width: 100%;
    margin-bottom: 20px;
}

.file-input-label {
    display: block;
    padding: 10px 15px;
    background-color: #007bff;
    color: white;
    border-radius: 5px;
    cursor: pointer;
    transition: background-color 0.3s ease;
}

.file-input-label:hover {
    background-color: #0056b3;
}

#resumeFile {
    /* Hide the default file input */
    opacity: 0;
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    cursor: pointer;
}

.file-name-display {
    display: block;
    margin-top: 10px;
    font-size: 0.9em;
    color: #555;
    word-wrap: break-word;
}


button {
    padding: 10px 20px;
    background-color: #28a745;
    color: white;
    border: none;
    border-radius: 5px;
    cursor: pointer;
    font-size: 1em;
    transition: background-color 0.3s ease;
}

button:hover {
    background-color: #218838;
}

.hidden {
    display: none !important;
}

#responseContainer, #errorContainer {
    margin-top: 20px;
    padding: 15px;
    border-radius: 5px;
    text-align: left;
}

#responseContainer {
    background-color: #e9f7ef;
    border: 1px solid #c3e6cb;
}

#errorContainer {
    background-color: #f8d7da;
    border: 1px solid #f5c6cb;
    color: #721c24;
}

#responseContent, #errorDetails {
    white-space: pre-wrap; /* Preserve formatting and wrap text */
    word-wrap: break-word; /* Ensure long words break */
    background-color: #eee;
    padding: 10px;
    border-radius: 5px;
    max-height: 400px; /* Limit height for long outputs */
    overflow-y: auto; /* Add scroll if content overflows */
    font-size: 0.9em;
    margin-top: 10px;
}

/* Loading spinner */
.spinner {
    border: 4px solid rgba(0, 0, 0, 0.1);
    border-left-color: #007bff;
    border-radius: 50%;
    width: 30px;
    height: 30px;
    animation: spin 1s linear infinite;
    margin: 20px auto 10px auto;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
"""

# This section ensures the CSS and HTML files are created when the script starts
@app.on_event("startup")
async def startup_event():
    # Ensure static and templates folders exist
    os.makedirs(STATIC_FOLDER, exist_ok=True)
    os.makedirs(TEMPLATES_FOLDER, exist_ok=True)

    # Write CSS content to file
    css_file_path = os.path.join(STATIC_FOLDER, 'style.css')
    if not os.path.exists(css_file_path):
        with open(css_file_path, 'w') as f:
            f.write(CSS_CONTENT)
        print(f"Created {css_file_path}")

    # Write HTML content to file
    html_file_path = os.path.join(TEMPLATES_FOLDER, 'index.html')
    # Only write if it doesn't exist, to avoid overwriting user edits
    if not os.path.exists(html_file_path):
        with open(html_file_path, 'w') as f:
            f.write(HTML_CONTENT)
        print(f"Created {html_file_path}")