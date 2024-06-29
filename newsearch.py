import os
import sqlite3
import pytesseract
from PIL import Image
import fitz
import cv2
import numpy as np
import io
from flask import Flask, render_template, request

directory = os.path.dirname(__file__)
os.chdir(directory)
app = Flask(__name__)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Set the base path to the folder containing PDF files
BASE_UPLOAD_FOLDER = 'Policies'
app.config['BASE_UPLOAD_FOLDER'] = BASE_UPLOAD_FOLDER

# Set the path to the folder where PDF images will be stored
IMAGE_BASE_DIR = 'pdfimag6'
app.config['IMAGE_BASE_DIR'] = IMAGE_BASE_DIR

# Create the base uploads directory if it doesn't exist
if not os.path.exists(BASE_UPLOAD_FOLDER):
    os.makedirs(BASE_UPLOAD_FOLDER)

# Create the image base directory if it doesn't exist
if not os.path.exists(IMAGE_BASE_DIR):
    os.makedirs(IMAGE_BASE_DIR)

def correct_skewness(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.bitwise_not(gray)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thresh > 0))
    angle = cv2.minAreaRect(coords)[-1]

    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    return rotated

def extract_text_from_image(image):
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    text = pytesseract.image_to_string(gray_image)
    return text.strip()

def check_scanned_pdf(pdf_file):
    images = []
    pdf_doc = fitz.open(pdf_file)
    for page_num in range(len(pdf_doc)):
        page = pdf_doc[page_num]
        image_list = page.get_images(full=True)
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = pdf_doc.extract_image(xref)
            image_bytes = base_image["image"]
            image = Image.open(io.BytesIO(image_bytes))
            image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            images.append((image, page_num + 1))
    return images

def extract_text_from_pdf(pdf_file):
    extracted_texts = []
    images = check_scanned_pdf(pdf_file)
    if images:
        for image, page_num in images:
            image = correct_skewness(image)
            text_from_image = extract_text_from_image(image)
            extracted_texts.append((page_num, text_from_image.strip(), 'Image'))
    else:
        pdf_doc = fitz.open(pdf_file)
        for index, page in enumerate(pdf_doc):
            text = page.get_text().strip()
            extracted_texts.append((index + 1, text, 'PDF'))
    return extracted_texts

def check_file_exists(db_name, filename):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    tables = ['contracts', 'policies', 'iso']
    for table in tables:
        cursor.execute(f"SELECT filename FROM {table} WHERE filename=?", (filename,))
        result = cursor.fetchone()
        if result:
            conn.close()
            return True, table  # Return True and table name if file exists
    conn.close()
    return False, None  # Return False if file does not exist in any table

def create_table_if_not_exists(db_name, table_name):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        category TEXT,
        pagenumber INTEGER,
        text TEXT
    )
    """)
    conn.commit()
    conn.close()

# PDF to Image Conversion Functions
def pdf_to_images(pdf_path, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    pdf_document = fitz.open(pdf_path)
    for page_number in range(pdf_document.page_count):
        page = pdf_document.load_page(page_number)
        pix = page.get_pixmap()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img_array = np.array(img)
        if img_array.shape[2] == 4:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)
        enhanced_image = cv2.convertScaleAbs(img_array, alpha=0.85, beta=0)
        kernel = np.array([[0, -0.5, 0], [-0.5, 3, -0.5], [0, -0.5, 0]])
        sharpened_image = cv2.filter2D(enhanced_image, -1, kernel)
        image_path = os.path.join(output_folder, f"{page_number + 1}.png")
        cv2.imwrite(image_path, sharpened_image)
    pdf_document.close()

def convert_pdfs_to_images(source_folder, dest_folder):
    for subfolder_name in os.listdir(source_folder):
        subfolder_path = os.path.join(source_folder, subfolder_name)
        if os.path.isdir(subfolder_path):
            dest_subfolder_path = os.path.join(dest_folder, subfolder_name)
            os.makedirs(dest_subfolder_path, exist_ok=True)
            for file_name in os.listdir(subfolder_path):
                file_path = os.path.join(subfolder_path, file_name)
                if file_name.endswith(".pdf"):
                    pdf_name = os.path.splitext(file_name)[0]
                    pdf_output_folder = os.path.join(dest_subfolder_path, pdf_name)
                    os.makedirs(pdf_output_folder, exist_ok=True)
                    pdf_to_images(file_path, pdf_output_folder)

@app.route('/upload', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        category = request.form['category']
        file = request.files['file']
        if file:
            filename = file.filename
            category_path = os.path.join(app.config['BASE_UPLOAD_FOLDER'], category)
            if not os.path.exists(category_path):
                os.makedirs(category_path)
            file_path = os.path.join(category_path, filename)
            file.save(file_path)

            # Convert the PDF to images
            pdf_name = os.path.splitext(filename)[0]
            pdf_output_folder = os.path.join(app.config['IMAGE_BASE_DIR'], category, pdf_name)
            os.makedirs(pdf_output_folder, exist_ok=True)
            pdf_to_images(file_path, pdf_output_folder)

            db_name = "fietails2.db"
            file_exists, table_name = check_file_exists(db_name, filename)
            if file_exists:
                return f"File {filename} is already present in {table_name} table."
            else:
                create_table_if_not_exists(db_name, category)
                texts = extract_text_from_pdf(file_path)
                conn = sqlite3.connect(db_name)
                cursor = conn.cursor()
                for page_num, text, source in texts:
                    text_with_source = f"{text} [{source}]"
                    cursor.execute(f"INSERT INTO {category} (filename, category, pagenumber, text) VALUES (?, ?, ?, ?)",
                                   (filename, category, page_num, text_with_source))
                conn.commit()
                conn.close()
                return f"Inserted text from {filename} in category {category} into database."
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9000, debug=False)
    # app.run(host='0.0.0.0', port=9000, debug=True)