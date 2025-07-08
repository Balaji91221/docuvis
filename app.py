from flask import Flask, request, render_template
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image
import re

# Set Tesseract-OCR path for Windows, change if you installed elsewhere
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

app = Flask(__name__)

def allowed_file(filename):
    return any(filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.pdf'])

def extract_text(file, filename):
    if filename.lower().endswith('.pdf'):
        file.seek(0)
        pdf_bytes = file.read()
        images = convert_from_bytes(pdf_bytes)
        text = ''.join([pytesseract.image_to_string(img) for img in images])
        return text
    else:
        img = Image.open(file.stream)
        return pytesseract.image_to_string(img)

def classify_doc_type(text):
    lower_text = text.lower()
    # PAN: check strictly for PAN pattern
    if re.search(r'[a-z]{5}[0-9]{4}[a-z]', lower_text):
        return "PAN Card"
    if any(word in lower_text for word in ["income tax", "permanent account number", "pan card"]):
        return "PAN Card"
    # Aadhaar after PAN
    if any(word in lower_text for word in ["aadhaar", "aadhar", "adhar", "uidai", "unique identification"]):
        return "Aadhar Card"
    if any(word in lower_text for word in ["statement period", "debit", "credit", "bank statement", "account summary"]):
        return "Bank Statement"
    return "Others"

def mask_aadhar(aadhar_number):
    if not aadhar_number:
        return aadhar_number
    parts = aadhar_number.split(' ')
    if len(parts) == 3 and all(part.isdigit() and len(part) == 4 for part in parts):
        return 'XXXX XXXX ' + parts[2]
    digits = ''.join(filter(str.isdigit, aadhar_number))
    if len(digits) == 12:
        return 'XXXX XXXX ' + digits[-4:]
    return aadhar_number

def mask_account_number(acc_num):
    if not acc_num:
        return acc_num
    digits = ''.join(filter(str.isdigit, acc_num))
    if len(digits) >= 4:
        return 'X' * (len(digits)-4) + digits[-4:]
    return acc_num

def extract_fields(text, doc_type):
    result = {}
    if doc_type == "Aadhar Card":
        result['Name'] = _extract_after_keywords(text, ["Name", "नाम"])
        result['DOB'] = _extract_regex(text, r'(\d{2}/\d{2}/\d{4})')
        aadhar_number = _extract_regex(text, r'\d{4} \d{4} \d{4}')
        result['Aadhar Number'] = mask_aadhar(aadhar_number)
        result['Gender'] = _extract_regex(text, r'(Male|Female|Transgender)', re.I)
        result['Address'] = _extract_address(text)
        return result
    elif doc_type == "PAN Card":
        result['Name'] = _extract_after_keywords(text, ["Name"])
        result["Father's Name"] = _extract_after_keywords(text, ["Father's Name"])
        result['DOB'] = _extract_regex(text, r'(\d{2}/\d{2}/\d{4})')
        result['PAN Number'] = _extract_regex(text, r'[A-Z]{5}[0-9]{4}[A-Z]{1}')
        return result
    elif doc_type == "Bank Statement":
        result['Bank Name'] = _extract_after_keywords(text, ["Bank Name"])
        acc_number = _extract_regex(text, r'Account\s*Number\s*:? ([Xx\d\*]{4,20})')
        result['Account Number (masked)'] = mask_account_number(acc_number)
        result['Account Number (unmasked)'] = acc_number
        result['Statement Period'] = _extract_regex(text, r'Period\s*:? (\d{2}/\d{2}/\d{4})\s*to\s*(\d{2}/\d{2}/\d{4})')
        result['Transactions'] = _extract_transactions(text)
        return result
    else:
        return {}

def _extract_after_keywords(text, keywords):
    for key in keywords:
        match = re.search(r'%s[:\s]+([A-Za-z .]+)' % re.escape(key), text, re.I)
        if match:
            return match.group(1).strip()
    return None

def _extract_regex(text, pattern, flags=0):
    match = re.search(pattern, text, flags)
    if match:
        return ' '.join(match.groups()) if match.groups() else match.group(0)
    return None

def _extract_address(text):
    address = None
    address_match = re.search(r'Address[\s:]*([\S\s]{0,90})\n', text, re.I)
    if address_match:
        address = address_match.group(1).replace('\n', ' ').strip()
    return address

def _extract_transactions(text):
    transactions = []
    lines = text.split('\n')
    for line in lines:
        m = re.match(r'(\d{2}/\d{2}/\d{4})\s+([A-Za-z0-9 ,&.-]+)\s+([-\d,]+(?:\.\d+)?)\s+(Debit|Credit)\s+([-\d,]+(?:\.\d+)?)', line)
        if m:
            transactions.append({
                'Date': m.group(1),
                'Description': m.group(2),
                'Amount': m.group(3),
                'Type': m.group(4),
                'Balance': m.group(5)
            })
    return transactions if transactions else None

@app.route('/', methods=['GET', 'POST'])
def upload_and_process():
    result = None
    if request.method == 'POST':
        file = request.files['document']
        if file and allowed_file(file.filename):
            try:
                file.stream.seek(0)
                text = extract_text(file, file.filename)
                print('\n===== OCR OUTPUT =====\n', text, '\n======================\n')
                doc_type = classify_doc_type(text)
                data = extract_fields(text, doc_type)
                if not any(data.values()):
                    data = None
                result = {
                    'type': doc_type,
                    'data': data
                }
            except Exception as e:
                result = {'type': 'Error', 'data': str(e)}
    return render_template('upload.html', result=result)

if __name__ == '__main__':
    app.run(debug=True)