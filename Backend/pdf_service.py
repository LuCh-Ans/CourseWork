import pdfplumber
import PyPDF2
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTChar, LTRect, LTFigure
from PIL import Image
from pdf2image import convert_from_path
import pytesseract
import os
from pathlib import Path
from docx import Document

pytesseract.pytesseract.tesseract_cmd = "/opt/homebrew/bin/tesseract"
POPPLER_PATH = None



def extract_text(file_path: Path) -> list[dict]:
    suffix = file_path.suffix.lower()
    if suffix == ".docx":
        return extract_text_docx(file_path)
    elif suffix == ".pdf":
        return extract_text_pdf(file_path)
    elif suffix == ".txt":
        raw = file_path.read_text(encoding="utf-8", errors="ignore")
        return [{
            "content": line.strip(),
            "metadata": {
                "source": file_path.name,
                "section": "General",
                "type": "text"
            }
        } for line in raw.split('\n') if line.strip()]
    else:
        raise ValueError(f"Формат {suffix} не поддерживается процессором.")


def extract_text_pdf(pdf: Path) -> list[dict]:
    content_blocks: list[dict] = []
    pdf_path_str = str(pdf)
    curr_section = 'General'

    with pdfplumber.open(pdf_path_str) as f:
        for page_num, page in enumerate(f.pages):
            page_text = page.extract_text()
            if page_text:
                for line in page_text.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    is_heading = len(line) < 80 and not line.endswith('.')

                    if is_heading:
                        curr_section = line
                        content_blocks.append({
                            "content": line,
                            "metadata": {
                                "source": pdf.name,
                                "section": curr_section,
                                "type": "heading",
                                "page": page_num + 1
                            }
                        })
                    else:
                        content_blocks.append({
                            "content": line,
                            "metadata": {
                                "source": pdf.name,
                                "section": curr_section,
                                "type": "text",
                                "page": page_num + 1
                            }
                        })
            tables = page.extract_tables()
            for table_idx, table in enumerate(tables):
                for row_idx, row in enumerate(table):
                    row_text = " | ".join(map(str, filter(None, row)))
                    if row_text.strip():
                        content_blocks.append({
                            "content": row_text,
                            "metadata": {
                                "source": pdf.name,
                                "section": curr_section,
                                "type": "table",
                                "page": page_num + 1,
                                "table_index": table_idx,
                                "row_index": row_idx
                            }
                        })

    images = convert_from_path(pdf_path_str)
    for page_num, image in enumerate(images):
        ocr_text = pytesseract.image_to_string(image).strip()
        if ocr_text:
            content_blocks.append({
                "content": ocr_text,
                "metadata": {
                    "source": pdf.name,
                    "section": curr_section,
                    "type": "ocr",
                    "page": page_num + 1
                }
            })

    return content_blocks


def extract_text_docx(file_path: Path) -> list[dict]:
    doc = Document(file_path)
    content_blocks: list[dict] = []
    curr_section = "General"
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        if paragraph.style.name.startswith('Heading'):
            curr_section = text
            content_blocks.append({
                "content": text,
                "metadata": {
                    "source": file_path.name,
                    "section": curr_section,
                    "type": "heading",
                    "level": paragraph.style.name
                }
            })
            continue
        content_blocks.append({
            "content": text,
            "metadata": {
                "source": file_path.name,
                "section": curr_section,
                "type": "text"
            }
        })
    for table_in, table in enumerate(doc.tables):
        for row_in, row in enumerate(table.rows):
            row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_text:
                content_blocks.append({
                    "content": " | ".join(row_text),
                    "metadata": {
                        "source": file_path.name,
                        "section": curr_section,
                        "type": "table",
                        "table_index": table_in,
                        "row_index": row_in
                    }
                })

    return content_blocks


def clean_text(text: str) -> str:
    line = text.split('\n')
    result_text = []
    for i in line:
        i = i.strip()
        if i:
            result_text.append(i)
    result = " ".join(result_text)
    return result


'''

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

 '''

'''def process(pdf):
    pdf = "Example PDF.pdf"
    raw_text = extract_text(pdf)
    cleaned_text = clean_text(raw_text)
    chunks = limit(cleaned_text)
    print(chunks)'''


def process_file(file_path: Path) -> list[dict]:
    blocks = extract_text(file_path)
    blocks = [
        {**b, "content": clean_text(b["content"])}
        for b in blocks
        if clean_text(b["content"])
    ]
    return blocks


def blocks_to_text(blocks: list[dict], max_length: int = 120_000) -> str:
    lines = []
    total_length = 0
    truncated = False

    for block in blocks:
        meta = block["metadata"]
        content = block["content"]

        if meta["type"] == "heading":
            line = f"\n## {content}\n"
        elif meta["type"] == "table":
            line = f"\n[Таблица — раздел «{meta['section']}»]\n{content}\n"
        elif meta["type"] == "ocr":
            line = f"\n[OCR, стр. {meta.get('page', '?')}]\n{content}\n"
        else:
            line = f"\n{content}"

        if total_length + len(line) > max_length:
            truncated = True
            break

        lines.append(line)
        total_length += len(line)

    text = "\n".join(lines).strip()
    if truncated:
        text += "\n\n... (документ обрезан)"
    return text