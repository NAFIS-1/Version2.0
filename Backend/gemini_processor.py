import json
import google.generativeai as genai
from fastapi import HTTPException, status
from config import API_KEY, GEMINI_MODEL_NAME

# Configure Gemini API
if not API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set or API_KEY is empty.")

try:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL_NAME)
except Exception as e:
    raise RuntimeError(f"Failed to initialize Gemini GenerativeModel: {e}")


def _calculate_resume_completeness(extracted_data: dict) -> tuple[int, list[str]]:
    """
    Calculates a completeness percentage and identifies missing fields
    based on extracted resume fields.
    Returns a tuple: (integer percentage, list of missing field names).
    """
    # Define expected fields and their completeness criteria
    # These are the top-level keys. For arrays, we check if the array is populated.
    # For nested objects, we check for presence of key sub-fields (e.g., jobTitle for work experience).
    completeness_criteria = {
        "firstName": lambda x: isinstance(x, str) and bool(x.strip()),
        "lastName": lambda x: isinstance(x, str) and bool(x.strip()),
        "professionalTitle": lambda x: isinstance(x, str) and bool(x.strip()),
        "email": lambda x: isinstance(x, str) and bool(x.strip()),
        "phone": lambda x: isinstance(x, str) and bool(x.strip()),
        "location": lambda x: isinstance(x, str) and bool(x.strip()),
        "linkedinURL": lambda x: isinstance(x, str) and bool(x.strip()),
        "website": lambda x: isinstance(x, str) and bool(x.strip()),
        "professionalSummary": lambda x: isinstance(x, str) and bool(x.strip()),
        "workExperience": lambda arr: isinstance(arr, list) and len(arr) > 0 and
                                       all(item.get("jobTitle") and item.get("company") for item in arr),
        "education": lambda arr: isinstance(arr, list) and len(arr) > 0 and
                                 all(item.get("degreeCertification") and item.get("institutionName") for item in arr),
        "skills": lambda arr: isinstance(arr, list) and len(arr) > 0 and
                              all(item.get("name") for item in arr), # Check if skill name exists
        "languages": lambda arr: isinstance(arr, list) and len(arr) > 0 and
                                 all(item.get("name") for item in arr), # Check if language name exists
        "certifications": lambda arr: isinstance(arr, list) and len(arr) > 0
    }

    total_fields = len(completeness_criteria)
    populated_fields = 0
    missing_fields = []

    for field, check_func in completeness_criteria.items():
        value = extracted_data.get(field)
        if value is not None and check_func(value):
            populated_fields += 1
        else:
            missing_fields.append(field) # Add to missing list if criteria not met

    if total_fields == 0:
        return 0, missing_fields

    completeness_percentage = int((populated_fields / total_fields) * 100)
    return min(completeness_percentage, 100), missing_fields


def extract_info_with_gemini(text_content: str) -> dict:
    """
    Sends resume text to Gemini API for information extraction.
    Returns a dictionary containing the extracted data, a completeness percentage,
    and a list of remaining (missing) fields.
    """
    prompt = f"""
    Analyze the following resume text and extract the specified information.
    Return the information as a single, valid JSON object. Do NOT use markdown like ```json ... ```.
    The JSON object must strictly adhere to the following keys and structures.
    If a key's information is not found, use `null` for string fields or an empty array `[]` for array fields.
    For arrays of objects, if no suitable entry is found, the array should be empty `[]`.

    Expected JSON Structure:
    {{
      "firstName": "string (e.g., 'John')",
      "lastName": "string (e.g., 'Doe')",
      "professionalTitle": "string (e.g., 'Software Engineer', 'Project Manager')",
      "email": "string (e.g., 'john.doe@example.com')",
      "phone": "string (e.g., '+1-123-456-7890' or '123.456.7890')",
      "location": "string (e.g., 'Bengaluru, India' or 'San Francisco, CA')",
      "linkedinURL": "string (full URL, e.g., 'https://www.linkedin.com/in/johndoe')",
      "website": "string (full URL, e.g., 'https://johndoeportfolio.com')",
      "professionalSummary": "string (concise summary of professional experience and goals)",
      "workExperience": [
        {{
          "jobTitle": "string (e.g., 'Senior Software Engineer')",
          "company": "string (e.g., 'Google')",
          "location": "string (e.g., 'Mountain View, CA')",
          "startDate": "string (e.g., 'Jan 2020' or '2020')",
          "endDate": "string (e.g., 'Dec 2022' or 'Present' or '2022')",
          "description": "string (key responsibilities and achievements, ideally bullet points merged into a string)"
        }}
      ],
      "education": [
        {{
          "degreeCertification": "string (e.g., 'Master of Science in CS', 'AWS Certified Developer Associate')",
          "institutionName": "string (e.g., 'Stanford University')",
          "location": "string (e.g., 'Stanford, CA')",
          "startYear": "string (e.g., '2016')",
          "endYear": "string (e.g., '2018' or 'Present')",
          "description": "string (relevant coursework, GPA, honors, thesis title, etc.)"
        }}
      ],
      "skills": [
        {{
          "name": "string (e.g., 'Python', 'Data Analysis')",
          "level": "string (e.g., 'Expert', 'Advanced', 'Intermediate', 'Beginner'). If no level is specified in the resume, default to 'Beginner'."
        }}
      ],
      "languages": [
        {{
          "name": "string (e.g., 'English')",
          "level": "string (e.g., 'Native', 'Fluent', 'Conversational', 'Beginner'). If no level is specified, default to 'Beginner'."
        }}
      ],
      "certifications": [
        "string (for standalone certifications not tied to an educational degree, e.g., 'PMP', 'CSM')"
      ]
    }}

    Ensure the entire output is ONLY the JSON object, with no surrounding text, explanations, or markdown.
    Pay close attention to extracting all details for work experience and education, including dates and locations.
    For skills and languages, always include a 'level' field, defaulting to 'Beginner' if no explicit level is found.

    Resume Text to Analyze:
    ---
    {text_content}
    ---
    """
    try:
        response = model.generate_content(prompt)
        
        generated_text = ""
        if response.candidates and \
           response.candidates[0].content and \
           response.candidates[0].content.parts:
            generated_text = response.candidates[0].content.parts[0].text
        elif hasattr(response, 'text') and response.text:
            print("Accessing Gemini response via .text attribute as fallback.")
            generated_text = response.text
        else:
            print("Gemini API response did not contain expected content structure.")
            print(f"Full Gemini response: {response}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Gemini API response did not contain expected content structure."
            )

        try:
            parsed_json = json.loads(generated_text.strip())
            
            # Calculate completeness score and get missing fields
            completeness_score, missing_fields = _calculate_resume_completeness(parsed_json)

            return {
                "extractedData": parsed_json,
                "completenessPercentage": completeness_score,
                "remainingFields": missing_fields # NEW: Include missing fields
            }

        except json.JSONDecodeError:
            print(f"Gemini response was not valid JSON. Raw response: {generated_text}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="AI response was not valid JSON. The AI may have failed to structure the data correctly. Check raw AI response for details.",
                headers={"X-Raw-AI-Response": generated_text.strip()}
            )

    except HTTPException: # Re-raise HTTPExceptions from _calculate_resume_completeness or JSONDecodeError
        raise
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        print(f"Gemini request prompt (first 500 chars): {prompt[:500]}...")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to communicate with AI model: {e}"
        )