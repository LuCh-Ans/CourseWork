import pdfplumber
import PyPDF2
from pdfminer.high_level import extract_pages, extract_text
from pdfminer.layout import LTTextContainer, LTChar, LTRect, LTFigure
from PIL import Image
from pdf2image import convert_from_path
import pytesseract 
import os
#print(os.path.exists(r"C:\Users\yanaa\Downloads\poppler\poppler-25.12.0\Library\bin"))

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

#print(os.path.exists(r"C:\Users\yanaa\Downloads\tesseract-ocr-w64-setup-5.5.0.20241111.exe"))
def extract_text(pdf):
    text = []
    with pdfplumber.open(pdf) as f:
        for page in f.pages:
            page_text = page.extract_text()
            if page_text:
                text.append(page_text)
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    row_text = " | ".join(map(str, filter(None, row)))
                    text.append(row_text)
    images = convert_from_path(pdf, poppler_path=(r"C:\Users\yanaa\Downloads\poppler\poppler-25.12.0\Library\bin"))

    for i in images:
        ocr_text = pytesseract.image_to_string(i)
        if ocr_text.strip():
            text.append(ocr_text)


    return "\n".join(text)

def clean_text(text):
    line = text.split('\n')
    result_text = []
    for i in line:
        i = i.strip()
        if i:
            result_text.append(i)
    result = " ".join(result_text)
    return result

def limit(text, max_size = 5000):
    threshold = [text[i:i+max_size] for i in range(0, len(text), max_size)]
    return threshold

#analyzing
def analyze_pdf(pdf):
    for page_num, page_layout in enumerate(extract_pages(pdf)):
        print("Page:", page_num + 1)
        for element in page_layout:
            if isinstance(element, LTTextContainer):
                print("Text")
            elif isinstance(element, LTFigure):
                print("Image")
            elif isinstance(element, LTRect):
                print("Graphic/Table")

def process(pdf):
    pdf = "Example PDF.pdf"
    raw_text = extract_text(pdf)
    cleaned_text = clean_text(raw_text)
    chunks = limit(cleaned_text)
    print(chunks)