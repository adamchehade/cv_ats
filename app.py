import os
import re
from flask import Flask, render_template, request, flash, redirect
from pypdf import PdfReader
import docx
from langdetect import detect, DetectorFactory

DetectorFactory.seed = 0

app = Flask(__name__)
app.secret_key = 'dev_key_very_secret'

# --- 1. UI TRANSLATIONS (Required for the frontend) ---
TRANSLATIONS = {
    "en": {
        "title": "ATS Optimizer",
        "subtitle": "Analyze your CV with or without a job description",
        "job_label": "Job Description (Optional)",
        "job_placeholder": "Paste job offer here...",
        "cv_label": "Upload CV (PDF/DOCX)",
        "scan_btn": "Scan CV",
        "back_btn": "New Scan",
        "score_title": "Match Score",
        "missing_title": "Missing Keywords"
    },
    "fr": {
        "title": "Optimiseur ATS",
        "subtitle": "Analysez votre CV avec ou sans offre d'emploi",
        "job_label": "Description du poste (Optionnel)",
        "job_placeholder": "Collez l'offre ici...",
        "cv_label": "Télécharger CV (PDF/DOCX)",
        "scan_btn": "Analyser le CV",
        "back_btn": "Nouvelle Analyse",
        "score_title": "Score de Correspondance",
        "missing_title": "Mots-clés Manquants"
    }
}

# --- 2. SMART DICTIONARIES ---

SYNONYMS = {
    "github": "git",
    "gitlab": "git",
    "reactjs": "react",
    "node.js": "node",
    "nodejs": "node",
    "agiles": "agile",
    "scrums": "scrum",
    "equipe": "équipe",
    "teams": "team"
}

GENERIC_KEYWORDS = {
    "en": {
        "python", "java", "c++", "javascript", "sql", "html", "css", "react", "node", 
        "docker", "kubernetes", "aws", "azure", "linux", "git", "agile", "scrum", 
        "communication", "leadership"
    },
    "fr": {
        "python", "java", "c++", "c#", "javascript", "sql", "html", "css", "react", "node",
        "docker", "kubernetes", "aws", "azure", "linux", "git", "agile", "scrum",
        "communication", "gestion", "équipe", "anglais"
    }
}

SECTIONS_DB = {
    "en": {
        "Experience": ["experience", "work history", "employment", "job history"],
        "Education": ["education", "academic", "university", "degree"],
        "Skills": ["skills", "competencies", "technologies", "stack"],
        "Projects": ["projects", "portfolio", "personal projects"],
        "Languages": ["languages", "linguistic"]
    },
    "fr": {
        "Experience": ["expérience", "parcours professionnel", "emploi", "postes", "stages"],
        "Education": ["formation", "éducation", "diplômes", "cursus", "académique"],
        "Skills": ["compétences", "technologies", "outils", "technique", "programmation"],
        "Projects": ["projets", "réalisations", "travaux", "portfolio"],
        "Languages": ["langues", "linguistique"]
    }
}

# --- 3. ROBUST LOGIC ---

def extract_text(file, filename):
    text = ""
    try:
        if filename.endswith('.pdf'):
            reader = PdfReader(file)
            for page in reader.pages:
                text += (page.extract_text() or "") + "\n"
        elif filename.endswith('.docx'):
            doc = docx.Document(file)
            text = "\n".join([para.text for para in doc.paragraphs])
    except Exception as e:
        print(f"Extraction Error: {e}")
        return None
    return text

def normalize_text(text):
    text = text.lower()
    text = re.sub(r'[/,:\(\)\-]', ' ', text)
    return text

def clean_text_to_words(text):
    text = normalize_text(text)
    raw_tokens = text.split()
    clean_tokens = set()
    for token in raw_tokens:
        token = token.strip('.?!;*')
        if re.match(r'^[\w\+#]+$', token):
            clean_tokens.add(token)
            if token in SYNONYMS:
                clean_tokens.add(SYNONYMS[token])
    return clean_tokens

def analyze_contacts(text):
    email = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    phone_pattern = r'(?:(?:\+|00)\d{1,3}|0)\s*[1-9](?:[\s.-]*\d{2}){4}'
    phone = re.search(phone_pattern, text)
    linkedin = re.search(r'linkedin\.com/in/[\w-]+', text, re.I)
    github = re.search(r'(?:github\.com|gitlab\.com)/[\w-]+', text, re.I)
    
    score = 0
    if email: score += 40
    if phone: score += 40
    if linkedin or github: score += 20
    
    return min(100, score), {
        "email": email.group(0) if email else None,
        "phone": phone.group(0) if phone else None,
        "linkedin": "Found" if linkedin else None,
        "github": "Found" if github else None
    }

def analyze_cv(cv_text, job_text=None):
    lang = 'fr' if detect(cv_text) == 'fr' else 'en'
    
    cv_words = clean_text_to_words(cv_text)
    word_count = len(cv_words)
    advice = []
    
    if job_text and len(job_text.strip()) > 10:
        target_words = clean_text_to_words(job_text)
        mode = "Job Match"
    else:
        target_words = GENERIC_KEYWORDS[lang]
        mode = "Generic Audit"
        advice.append("General Audit Mode (No Job Description provided).")

    matches = cv_words.intersection(target_words)
    missing = target_words - cv_words
    
    kw_score = (len(matches) / len(target_words)) * 100 if target_words else 0
        
    found_sections = []
    missing_sections = []
    db = SECTIONS_DB[lang]
    
    cv_text_lower = cv_text.lower()
    for section_name, keywords in db.items():
        if any(k in cv_text_lower for k in keywords):
            found_sections.append(section_name)
        else:
            missing_sections.append(section_name)
            
    section_score = (len(found_sections) / len(db)) * 100

    contact_score, contact_info = analyze_contacts(cv_text)
    length_score = 100 if 300 <= word_count <= 1200 else 50
    if word_count < 300: advice.append(f"CV is short ({word_count} words). Aim for 300+.")

    total_score = (kw_score * 0.45) + (section_score * 0.25) + (contact_score * 0.2) + (length_score * 0.1)
    
    if not contact_info["email"]: advice.append("Critical: Add your Email address.")
    if not contact_info["phone"]: advice.append("Critical: Add your Phone number.")
    if "Projects" in missing_sections: 
        advice.append("Tip: Add a 'Projects' or 'Réalisations' section to showcase your work.")

    return {
        "total_score": round(total_score),
        "mode": mode,
        "lang": lang.upper(),
        "details": {
            "keywords": round(kw_score),
            "sections": round(section_score),
            "contacts": contact_score,
            "length": length_score
        },
        "data": {
            "matches": list(matches),
            "missing": list(missing)[:15],
            "found_sections": found_sections,
            "missing_sections": missing_sections,
            "contacts": contact_info,
            "word_count": word_count,
            "raw_text": cv_text[:800] + "...",
            "advice": advice
        }
    }

# --- 4. ROUTES (FIXED UI PASSING) ---
@app.route('/', methods=['GET', 'POST'])
def index():
    # 1. Get Language
    lang = request.args.get('lang', 'en')
    if lang not in TRANSLATIONS: lang = 'en'
    
    # 2. Get UI Text
    ui = TRANSLATIONS[lang]

    if request.method == 'POST':
        if 'cv_file' not in request.files: return redirect(request.url)
        file = request.files['cv_file']
        if file.filename == '': return redirect(request.url)

        cv_text = extract_text(file, file.filename.lower())
        if not cv_text:
            flash("Error extracting text.")
            return redirect(request.url)

        job_text = request.form.get('job_offer', '')
        results = analyze_cv(cv_text, job_text)
        
        # IMPORTANT: Pass 'ui' here too!
        return render_template('result.html', r=results, ui=ui, lang=lang)

    # IMPORTANT: Pass 'ui' here for the initial load
    return render_template('index.html', ui=ui, lang=lang)

if __name__ == '__main__':
    app.run(debug=True)