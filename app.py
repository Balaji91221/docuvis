"""
Flask entry-point: upload endpoint + static demo page.
"""
import os, uuid
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

import cv2, numpy as np
from pdf2image import convert_from_path

from utils import (
    allowed,
    MAX_FILE_MB,
    preprocess,
    ocr_image,
    classify,
    run_extraction,
)

# ---------------- configuration ----------------
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
CORS(app)  # enable CORS for local testing; remove or tighten in prod


# ---------------- routes ----------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    # ----------- validation -------------
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400
    if not allowed(file.filename):
        return jsonify({"error": "Unsupported file type"}), 400

    file.seek(0, os.SEEK_END)
    if file.tell() > MAX_FILE_MB * 1024 * 1024:
        return jsonify({"error": "File > 10 MB"}), 400
    file.seek(0)

    # ----------- save to disk -----------
    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4()}.{ext}"
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(path)

    # ----------- OCR pipeline -----------
    texts = []
    if ext == "pdf":
        images = convert_from_path(path, dpi=300, first_page=1, last_page=3)
        for pil_img in images:
            img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            th = preprocess(img)
            texts.append(ocr_image(th))
    else:
        img = cv2.imread(path)
        th = preprocess(img)
        texts.append(ocr_image(th))

    full_text = "\n".join(texts)
    doc_type = classify(full_text)
    extracted = run_extraction(doc_type, full_text)

    return jsonify(
        {
            "document_type": doc_type,
            "extracted_fields": extracted,
            "raw_text_snippet": full_text[:1000],
        }
    )


# ---------------- main ----------------
if __name__ == "__main__":
    app.run(port=8000, debug=True)