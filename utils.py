"""
Lightweight helpers: extension validation, image pre-processing, OCR,
document classification and rule-based field extraction.
"""
import os, re, cv2, numpy as np, pytesseract
from typing import List, Dict

ALLOWED_EXT = {"png", "jpg", "jpeg", "pdf"}
MAX_FILE_MB = 10


# --------------------------------------------------
def allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def mask_number(num: str, show_last: int = 4) -> str:
    digits = re.sub(r"\D", "", num)
    if len(digits) <= show_last:
        return digits
    return "*" * (len(digits) - show_last) + digits[-show_last:]


# --------------------------------------------------
def preprocess(img: np.ndarray) -> np.ndarray:
    """
    Very small pipeline: grayscale → (optional) deskew → denoise → adaptive-threshold.
    Works ‘okay’ for clean scans; replace with something fancier if needed.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # ---------- deskew (quick ‘minimum area rectangle’ trick)
    coords = np.column_stack(np.where(gray > 0))
    if len(coords) > 0:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        (h, w) = gray.shape
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        gray = cv2.warpAffine(
            gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
        )

    # ---------- denoise + threshold
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    th = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 2
    )
    return th


# --------------------------------------------------
def ocr_image(img: np.ndarray) -> str:
    """Run Tesseract and return upper-cased text."""
    return pytesseract.image_to_string(img, lang="eng").upper()


# --------------------------------------------------
def classify(text: str) -> str:
    """
    Super-basic keyword classifier.
    Return: AADHAAR | PAN | BANK_STATEMENT | UNKNOWN
    """
    if re.search(r"\bAADHAAR\b|\bUNIQUE IDENTIFICATION\b", text):
        return "AADHAAR"
    if re.search(r"\bPERMANENT ACCOUNT NUMBER\b|\bINCOME TAX DEPARTMENT\b", text):
        return "PAN"
    if re.search(r"\bSTATEMENT\b|\bACCOUNT NUMBER\b", text) and re.search(
        r"\bDEBIT\b|\bCREDIT\b", text
    ):
        return "BANK_STATEMENT"
    return "UNKNOWN"


# --------------------------------------------------
def extract_aadhaar(text: str) -> Dict:
    out = {}
    aadhaar_no = re.search(r"(\d{4}\s\d{4}\s\d{4})", text)
    dob = re.search(r"(\d{2}/\d{2}/\d{4})", text)
    gender = "MALE" if "MALE" in text else ("FEMALE" if "FEMALE" in text else None)

    out["aadhaar_number"] = aadhaar_no.group(1) if aadhaar_no else None
    if out["aadhaar_number"]:
        out["aadhaar_number_masked"] = mask_number(out["aadhaar_number"])
    out["dob"] = dob.group(1) if dob else None
    out["gender"] = gender

    # naive name guess: first OCR line that isn’t a common keyword
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    name = next(
        (
            ln
            for ln in lines
            if not any(
                kw in ln
                for kw in ["GOVERNMENT", "INDIA", "AADHAAR", "DOB", "YEAR", "MALE", "FEMALE"]
            )
        ),
        None,
    )
    out["name"] = name
    return out


def extract_pan(text: str) -> Dict:
    out = {}
    pan = re.search(r"([A-Z]{5}\d{4}[A-Z])", text)
    dob = re.search(r"(\d{2}/\d{2}/\d{4})", text)
    out["pan_number"] = pan.group(1) if pan else None
    out["dob"] = dob.group(1) if dob else None

    # naïve name & father name extraction
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    try:
        idx = lines.index("INCOME TAX DEPARTMENT") + 1
        out["name"] = lines[idx]
        out["father_name"] = lines[idx + 1]
    except (ValueError, IndexError):
        pass

    return out


def extract_bank(text: str) -> Dict:
    out = {}
    acc = re.search(r"ACCOUNT\s*NUMBER[:\s\-]*([0-9Xx*]{6,})", text)
    period = re.search(r"(\d{2}/\d{2}/\d{4}).*?(\d{2}/\d{2}/\d{4})", text)

    if acc:
        raw = acc.group(1)
        digits = re.sub(r"\D", "", raw)
        out["account_number_unmasked"] = digits
        out["account_number_masked"] = mask_number(digits)

    if period:
        out["statement_period"] = {"from": period.group(1), "to": period.group(2)}

    # extremely simple transaction parser (date leading line)
    txns: List[Dict] = []
    for line in text.split("\n"):
        m = re.match(
            r"(\d{2}/\d{2}/\d{4})\s+(.+?)\s+([-+]?\d+[.,]?\d*)\s+([-+]?\d+[.,]?\d*)",
            line,
        )
        if m:
            txns.append(
                {
                    "date": m.group(1),
                    "description": m.group(2).strip(),
                    "amount": m.group(3),
                    "balance": m.group(4),
                }
            )
    out["transactions"] = txns
    out["bank_name"] = text.split("\n", 1)[0].title()
    return out


def run_extraction(doc_type: str, text: str) -> Dict:
    if doc_type == "AADHAAR":
        return extract_aadhaar(text)
    if doc_type == "PAN":
        return extract_pan(text)
    if doc_type == "BANK_STATEMENT":
        return extract_bank(text)
    return {}