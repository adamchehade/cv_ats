import re
import pdfplumber
import docx
from collections import Counter

# --- Text Extraction Helpers ---
def extract_text_from_pdf(file_stream):
    text = ""
    try:
        with pdfplumber.open(file_stream) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"PDF Error: {e}")
        return None
    return text

def extract_text_from_docx(file_stream):
    try:
        doc = docx.Document(file_stream)
        return "\n".join([para.text for para in doc.paragraphs])
    except Exception as e:
        print(f"DOCX Error: {e}")
        return None

def clean_text(text):
    # Keep only words with 2+ letters
    return re.findall(r'\b[a-zA-ZÀ-ÿ]{2,}\b', text.lower())

# --- Core Analysis ---
def analyze_cv(cv_text, job_text=None, lang="en"):
    cv_words = clean_text(cv_text)
    cv_word_set = set(cv_words)
    word_count = len(cv_words)
    
    result = {
        "score": 0,
        "missing_keywords": [],
        "advice": [],
        "word_count": word_count,
        # Check for basic contact info
        "email_found": re.search(r'[\w\.-]+@[\w\.-]+', cv_text) is not None,
        "phone_found": re.search(r'\+?\d[\d -]{8,12}\d', cv_text) is not None
    }

    # MODE 1: Job Description Comparison
    if job_text and len(job_text.strip()) > 10:
        job_words = clean_text(job_text)
        job_word_set = set(job_words)
        
        # Calculate Match Score
        intersection = cv_word_set.intersection(job_word_set)
        if job_word_set:
            result["score"] = round((len(intersection) / len(job_word_set)) * 100, 1)
        
        # Identify missing keywords (filtering out common stopwords)
        missing = job_word_set - cv_word_set
        stop_words = {'the', 'and', 'for', 'with', 'that', 'this', 'from', 'your', 'will', 'have', 'les', 'des', 'pour', 'avec', 'une', 'dans', 'sur', 'par'}
        result["missing_keywords"] = [w for w in list(missing) if w not in stop_words][:15]

        # Contextual Advice
        if result["score"] < 50:
            result["advice"].append("Low match score. Tailor your CV specifically to the keywords in the job description.")
        elif result["score"] >= 80:
            result["advice"].append("Great match! Your CV is well-optimized.")

    # MODE 2: General Health Check (No Job Description)
    else:
        result["score"] = None  # Indicates "General Mode" to the UI
        result["advice"].append("General Audit Mode (No Job Description provided).")
        result["advice"].append("Focusing on general formatting and contact details.")

    # General Validation (Runs in both modes)
    if not result["email_found"]:
        result["advice"].append("Critical: No email address detected.")
    if not result["phone_found"]:
        result["advice"].append("Warning: No phone number detected.")
    if word_count < 200:
        result["advice"].append("Your CV seems too short. Aim for at least 300-400 words.")

    return result