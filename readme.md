# DocuVision – Mini-PoC  
Intelligent document-type detection & key–value extraction for  
• Aadhaar • PAN • Bank statements  

This repository contains a **proof-of-concept** built with Flask, OpenCV and Tesseract.  
It lets you 1) upload an image/PDF, 2) auto-classify the document, 3) return a JSON payload of the most important fields, plus a web demo page (`/`).

> ⚠️  Accuracy and security are purposely minimal so you can read & extend the code.  
> For a production-ready service, see the “Next Steps” section.

---

## 1.  Features

* Drag-and-drop web UI (HTML/CSS/JS)  
* REST endpoint `POST /upload` (multipart form)  
* File validation — JPG / PNG / PDF ≤ 10 MB  
* Lightweight pre-processing (deskew, denoise, adaptive threshold)  
* OCR with Tesseract  
* Keyword-based document-type classifier  
* Regex-based field extraction  
  * Aadhaar → name, DOB, gender, number (masked & unmasked)  
  * PAN     → name, father’s name, DOB, PAN number  
  * Bank-statement → bank name, account # (masked/unmasked), statement period, basic transaction list  
* JSON response with truncated raw text for debugging

---

## 2.  Folder layout

```
docuvision/
├─ app.py            # Flask server
├─ utils.py          # helpers: preprocessing, OCR, extraction
├─ requirements.txt  # Python dep’s
│
├─ templates/
│  └─ index.html     # demo UI
└─ static/
   └─ style.css
```

Uploaded files are stored in `uploads/` (auto-created).

---

## 3.  Prerequisites

| Component         | Windows 10/11                           | macOS / Linux              |
|-------------------|-----------------------------------------|----------------------------|
| Python ≥ 3.9      | https://python.org                      | via package manager        |
| **Tesseract OCR** | `winget install UB-Mannheim.Tesseract-OCR` <br>or download EXE from UB-Mannheim | `brew install tesseract` / `apt install tesseract-ocr` |
| **Poppler** (PDF) | `winget install Poppler.Poppler` or zip → PATH | `brew install poppler` / `apt install poppler-utils` |

> If you skip Poppler you can still process images, but not PDFs.

After installing, verify:

```powershell
tesseract --version     # must print version info
pdftoppm  -v            # optional, for PDFs
```

If you don’t want to touch PATH, add inside `utils.py`:

```python
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

---

## 4.  Setup & Run

```bash
# 1) clone / copy repo
cd docuvision

# 2) (optional) create venv
python -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate

# 3) install Python dep’s
pip install -r requirements.txt

# 4) launch server
python app.py        # http://localhost:8000
```

Open a browser at http://localhost:8000 and test with any supported document.

### CURL test

```bash
curl -F "file=@samples/aadhaar.jpg" http://localhost:8000/upload
```

Expected JSON:

```json
{
  "document_type": "AADHAAR",
  "extracted_fields": {
    "name": "MOHAN LAL",
    "aadhaar_number": "1234 5678 9123",
    "aadhaar_number_masked": "********9123",
    "dob": "14/09/1982",
    "gender": "MALE"
  },
  "raw_text_snippet": "GOVERNMENT OF INDIA ..."
}
```

---

## 5.  API reference (v0)

| Method | Path    | Description                            |
|--------|---------|----------------------------------------|
| GET    | `/`     | Returns demo web page                  |
| POST   | `/upload` | Multipart form `file=<binary>`. Returns JSON result (above). |

HTTP status codes  
* 200 OK          – success  
* 400 Bad Request – validation error (size, type, no file)  
* 500 Server Error – Tesseract/Poppler missing, etc.

---

## 6.  Customisation tips

* **Add new doc types** → edit `classify()` & `run_extraction()` in `utils.py`.  
* **Different masking logic** → tweak `mask_number()` helper.  
* **Better accuracy** → replace regex with LayoutLM / Donut / LLM prompts.  
* **Asynchronous jobs** → move long OCR work to Celery/RQ worker.  
* **Docker** → install Tesseract & Poppler in the image and copy code.  

---

## 7.  Common errors

| Symptom                         | Fix |
|---------------------------------|-----|
| `TesseractNotFoundError`        | Install Tesseract, add to PATH, or set `tesseract_cmd`. |
| `PDFInfoNotInstalledError`      | Install Poppler (pdftoppm). |
| `File too large` (HTTP 400)     | Default limit is 10 MB → change `MAX_FILE_MB` in `utils.py`. |
| Blank / poor OCR results        | Scan quality; try 300 DPI, straighten image, or enhance pre-processing. |

---

## 8.  Next steps for production

* Ensemble doc-type classifier (vision + text) with confidence scores.  
* High-recall field extraction (LayoutLM-v3, Donut, GPT-4o, Claude 3, etc.).  
* DB + object storage (S3) + job queue.  
* AuthN/AuthZ, TLS, rate limiting, audit logs, PII redaction.  
* Unit/integration tests, CI/CD, Docker/K8s deployment.  

---

## 9.  Credits

* [Tesseract-OCR](https://github.com/tesseract-ocr/tesseract) – Google / open-source community  
* UB-Mannheim Windows builds  
* Poppler – Xpdf / open-source community  

