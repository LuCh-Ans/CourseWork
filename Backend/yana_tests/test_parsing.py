import time
import os
import sys
from pathlib import Path
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent))
from pdf_service import process_file, create_chunks, blocks_to_text
TEST_FILES = [
    ("PDF текстовый (лекция)",             r"C:\Users\yanaa\Downloads\мотивация_артемьева (1).pdf",                         "pdf_text"),
    ("PDF текстовый (учебник)",            r"C:\Users\yanaa\Downloads\Koldanovy_2024_2nd_site.pdf",                         "pdf_text"),
    ("PDF сканированный (хор. кач.)",      r"C:\Users\yanaa\Downloads\Задание 18 2024 (2).pdf",                             "pdf_scan"),
    ("PDF сканированный (низ. кач.)",      r"C:\Users\yanaa\Downloads\2025_10_05_14.09.32.pdf",                             "pdf_scan"),
    ("DOCX с таблицами",                   r"C:\Users\yanaa\Downloads\tablitsa-3-4ee788ab-308e-4092-ac6c-01907725b006.docx","docx"),
    ("TXT",                                r"C:\Users\yanaa\Downloads\report_final.txt",                                                                             "txt"),
]
FALLBACK_DOCX = Path(__file__).parent.parent / "Отчёт_индивидуальная_часть_v2.docx"
for i, (label, path, ftype) in enumerate(TEST_FILES):
    if ftype == "docx" and path is None and FALLBACK_DOCX.exists():
        TEST_FILES[i] = (label + " (тест на отчёте)", str(FALLBACK_DOCX), ftype)
def count_pages_pdf(path: str) -> int:
    try:
        import pdfplumber
        with pdfplumber.open(path) as f:
            return len(f.pages)
    except Exception:
        return 0
def get_page_count(path: str, ftype: str) -> str:
    if ftype.startswith("pdf"):
        n = count_pages_pdf(path)
        return str(n) if n else "?"
    elif ftype == "docx":
        return "—"
    elif ftype == "txt":
        lines = Path(path).read_text(encoding="utf-8", errors="ignore").count("\n")
        return f"~{max(1, lines // 45)}"  
    return "?"
def run_test(label: str, path: str, ftype: str) -> dict:
    result = {
        "label": label,
        "pages": "—",
        "time_sec": None,
        "chars": 0,
        "blocks": 0,
        "chunks": 0,
        "status": "Успешно",
        "error": None,
    }
    result["pages"] = get_page_count(path, ftype)
    try:
        t_start = time.perf_counter()
        blocks = process_file(Path(path))
        t_end = time.perf_counter()

        elapsed = round(t_end - t_start, 1)
        total_chars = sum(len(b["content"]) for b in blocks)
        chunks = create_chunks(blocks)

        result["time_sec"] = elapsed
        result["chars"] = total_chars
        result["blocks"] = len(blocks)
        result["chunks"] = len(chunks)
        ocr_blocks = [b for b in blocks if b.get("metadata", {}).get("type") == "ocr"]
        if ocr_blocks:
            result["status"] = f"Частично (OCR, {len(ocr_blocks)} стр.)"
        full_text = blocks_to_text(blocks)
        if "обрезан" in full_text:
            result["status"] += " (обрезан)"

    except Exception as e:
        result["status"] = "Ошибка"
        result["error"] = str(e)

    return result

SEP = "-" * 90

def main():
    print(SEP)
    print("  ТЕСТ МОДУЛЯ ПАРСИНГА")
    print(SEP)

    results = []
    for label, path, ftype in TEST_FILES:
        display_path = Path(path).name if path else "(не указан)"
        print(f"\n{label}")
        r = run_test(label, path, ftype)
        results.append(r)

        if r["time_sec"] is not None:
            print(f"  Время:   {r['time_sec']} сек")
            print(f"  Символов:{r['chars']:>10,}")
            print(f"  Блоков:  {r['blocks']:>10,}")
            print(f"  Чанков:  {r['chunks']:>10,}")
            print(f"  Статус:  {r['status']}")
        else:
            print(f"  Статус:  {r['status']}")
            if r["error"]:
                print(f"  Детали:  {r['error']}")

    print(f"\n{SEP}")
    print("  ИТОГОВАЯ ТАБЛИЦА (для Таблицы 9 в отчёте)")
    print(SEP)
    print(f"{'Тип документа':<40} {'Стр':>4} {'Время':>7} {'Символов':>10} {'Блоков':>7} {'Статус'}")
    print("-" * 90)
    for r in results:
        t = f"{r['time_sec']} с" if r["time_sec"] is not None else "—"
        chars = f"{r['chars']:,}" if r["chars"] else "—"
        blocks = str(r["blocks"]) if r["blocks"] else "—"
        print(f"{r['label']:<40} {r['pages']:>4} {t:>7} {chars:>10} {blocks:>7}  {r['status']}")
    out_path = Path(__file__).parent / "test_results_parsing.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ ПАРСИНГА\n")
        f.write(f"{'=' * 90}\n")
        f.write(f"{'Тип документа':<40} {'Стр':>4} {'Время':>7} {'Символов':>10} {'Блоков':>7} Статус\n")
        f.write(f"{'-' * 90}\n")
        for r in results:
            t = f"{r['time_sec']} с" if r["time_sec"] is not None else "—"
            chars = f"{r['chars']:,}" if r["chars"] else "—"
            blocks = str(r["blocks"]) if r["blocks"] else "—"
            f.write(f"{r['label']:<40} {r['pages']:>4} {t:>7} {chars:>10} {blocks:>7}  {r['status']}\n")
if __name__ == "__main__":
    main()
