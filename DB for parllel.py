import os
import sqlite3
import pytesseract
from PIL import Image
import fitz
import cv2
import numpy as np
import io
import pandas as pd
from parallel_runner import parlleliser

# Set the path to the Tesseract executable
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


# Function to correct skewness in an image
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


# Function to extract text from an image using OCR
def extract_text_from_image(image):
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    text = pytesseract.image_to_string(gray_image)
    return text.strip()


# Function to check if a PDF contains scanned images

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
            images.append((image, page_num + 1))  # Tuple with image and page number

    return images


# Function to extract text from a PDF document
def extract_text_from_pdf(pdf_file):
    extracted_texts = []

    images = check_scanned_pdf(pdf_file)

    if images:
        for image, page_num in images:
            image = correct_skewness(image)
            text_from_image = extract_text_from_image(image)
            extracted_texts.append((page_num, text_from_image.strip(), 'Image'))  # Marking text extracted from image
    else:
        pdf_doc = fitz.open(pdf_file)
        for index, page in enumerate(pdf_doc):
            text = page.get_text().strip()
            extracted_texts.append((index + 1, text, 'PDF'))

    return extracted_texts


# Function to create SQLite tables for different categories
def create_sqlite_table(db_name):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Create separate tables for each subfolder
    for subfolder in ['contracts', 'policies', 'iso', 'GDMS']:
        table_name = subfolder
        cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            category TEXT,
            pagenumber INTEGER,
            text TEXT
        )
        """)
        print(f"Created {table_name} table.")

    conn.commit()
    conn.close()


# Function to insert extracted text data into SQLite tables
def insert_into_sqlite_table(db_name, table_name, file_name, texts):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Insert data
    for page_num, text, source in texts:
        text_with_source = f"{text} [{source}]"  # Append source information to text
        cursor.execute(f"INSERT INTO {table_name} (filename, category, pagenumber, text) VALUES (?, ?, ?, ?)",
                       (file_name, table_name, page_num, text_with_source))

    conn.commit()
    conn.close()


# Function to search for data in SQLite tables based on keywords
def search_data(db_name, keywords, category=None):
    conn = sqlite3.connect(db_name)

    dfs = []
    for subfolder in ['contracts', 'policies', 'iso', 'GDMS']:
        try:
            query = f"SELECT id, filename, '{subfolder.capitalize()}' AS category, pagenumber, text FROM {subfolder} WHERE text LIKE ?"
            params = (f"%{keywords}%",)
            df = pd.read_sql_query(query, conn, params=params)
            df['table_name'] = subfolder  # Add table name
            dfs.append(df)
        except sqlite3.OperationalError as e:
            print(f"Table {subfolder} not found in the database.")
            continue

    conn.close()

    return pd.concat(dfs, ignore_index=True)


def ocr_function(filename,subfolder,sub_src_folder,db_name):
    if filename.endswith('.pdf'):
        src_path = os.path.join(sub_src_folder, filename)

        # Check if file exists in SQLite database
        with sqlite3.connect(db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT filename FROM {subfolder} WHERE filename=?", (filename,))
            result = cursor.fetchone()

        if result:
            print(f"File {filename} already exists in the {subfolder} table.")
        else:
            # Extract text from PDF
            texts = extract_text_from_pdf(src_path)

            # Insert into SQLite table
            insert_into_sqlite_table(db_name, subfolder, filename, texts)
            print(f"Inserted text from {filename} in folder {subfolder} into {subfolder} table")

class file:
    def __init__(self,filename,subfolder,sub_src_folder,db_name, ocr_function):
        self.filename = filename
        self.subfolder=subfolder
        self.sub_src_folder = sub_src_folder
        self.db_name = db_name
        self.ocr_function = ocr_function

    def run_ocr(self):
        self.ocr_function(self.filename,self.subfolder,self.sub_src_folder,self.db_name)


# Main block
if __name__ == "__main__":
    # Define the base directory containing PDF files
    base_directory = "Policies"
    # Define the name of the SQLite database
    db_name = "CHATBOT.db"

    # Create SQLite table
    create_sqlite_table(db_name)

    # Iterate through subfolders and extract text from PDFs
    tasks = []
    for subfolder in ['contracts', 'policies', 'iso','GDMS']:
        sub_src_folder = os.path.join(base_directory, subfolder)
        for filename in os.listdir(sub_src_folder):
            task = file(filename,subfolder,sub_src_folder,db_name,ocr_function)
            tasks += [task.run_ocr]

    parlleliser(tasks)

    print("Done")