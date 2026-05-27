
import asyncio
import time
import sys
from pathlib import Path
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent))
from pdf_service import process_file, blocks_to_text
from llm.llm_client import summarize
TEST_FILES = [
    ("Короткий TXT",
     r"C:\Users\yanaa\CourseWork\Backend\test_sample.txt"),

    ("PDF текстовый (лекция, 2 стр.)",
     r"C:\Users\yanaa\Downloads\мотивация_артемьева (1).pdf"),

    ("PDF текстовый (учебник, 48 стр.)",
     r"C:\Users\yanaa\Downloads\Koldanovy_2024_2nd_site.pdf"),

    ("DOCX с таблицами",
     r"C:\Users\yanaa\Downloads\tablitsa-3-4ee788ab-308e-4092-ac6c-01907725b006.docx"),
]
QUALITY_CHECKS = {
    r"C:\Users\yanaa\CourseWork\Backend\test_sample.txt":
        ["машинное обучение", "нейронн", "градиентн", "RAG", "эмбеддинг"],

    r"C:\Users\yanaa\Downloads\мотивация_артемьева (1).pdf":
        [],

    r"C:\Users\yanaa\Downloads\Koldanovy_2024_2nd_site.pdf":
        ["вероятност"],

    r"C:\Users\yanaa\Downloads\tablitsa-3-4ee788ab-308e-4092-ac6c-01907725b006.docx":
        [],
}
SEP = "-" * 90
def check_quality(summary: str, keywords: list[str]) -> tuple[int, list[str]]:
    found = [kw for kw in keywords if kw.lower() in summary.lower()]
    return len(found), found
def count_mode(char_count: int) -> str:
    if char_count <= 15000:
        return "Прямой (1 запрос)"
    parts = (char_count + 14999) // 15000
    return f"Map-Reduce ({parts} частей)"


async def test_file(label: str, path: str) -> dict:
    result = {
        "label": label,
        "path": path,
        "chars_in": 0,
        "chars_out": 0,
        "compression": 0.0,
        "mode": "—",
        "t_ms": None,
        "status": "Успешно",
        "summary": "",
        "quality_found": [],
        "quality_total": 0,
    }

    file_path = Path(path)
    try:
        blocks = process_file(file_path)
        text = blocks_to_text(blocks)
    except Exception as e:
        result["status"] = f"Ошибка парсинга: {e}"
        return result

    if not text.strip():
        result["status"] = "Пустой текст"
        return result

    result["chars_in"] = len(text)
    result["mode"] = count_mode(len(text))
    try:
        t0 = time.perf_counter()
        summary = await summarize(text)
        t_ms = round((time.perf_counter() - t0) * 1000)
    except Exception as e:
        result["status"] = f"Ошибка LLM: {e}"
        return result

    result["t_ms"] = t_ms
    result["chars_out"] = len(summary)
    result["summary"] = summary
    result["compression"] = round(len(summary) / max(len(text), 1) * 100, 1)
    keywords = QUALITY_CHECKS.get(path, [])
    result["quality_total"] = len(keywords)
    if keywords:
        found_n, found_kw = check_quality(summary, keywords)
        result["quality_found"] = found_kw
        result["quality_score"] = f"{found_n}/{len(keywords)}"
    else:
        result["quality_score"] = "вручную"

    return result


async def main():
    print(SEP)
    print("  ТЕСТ СУММАРИЗАЦИИ")
    print(SEP)

    results = []

    for label, path in TEST_FILES:
        print(f"\n  [{label}]")
        print(f"  Файл: {Path(path).name}")
        print("  Суммаризация...", end="", flush=True)
        r = await test_file(label, path)
        results.append(r)
        if r["t_ms"] is not None:
            print(f"\r  Готово: {r['t_ms']} мс | "
                  f"Вход: {r['chars_in']:,} симв. | "
                  f"Выход: {r['chars_out']:,} симв. | "
                  f"Сжатие: {r['compression']}% | "
                  f"Режим: {r['mode']}")
            print(f"  Качество: {r.get('quality_score', '—')}")
            print(f"\n  Конспект (первые 400 симв.):")
            print(f"  {r['summary'][:400].replace(chr(10), chr(10) + '  ')}...")
        else:
            print(f"\r  Статус: {r['status']}")
    ok_results = [r for r in results if r["t_ms"] is not None]

    print(f"\n{SEP}")
    print("  ИТОГОВАЯ ТАБЛИЦА")
    print(SEP)
    print(f"  {'Документ':<32} {'Вход':>8} {'Выход':>7} {'Сжатие':>7} {'Время':>8}  {'Режим':<22} {'Кач.'}")
    print(f"  {'-' * 88}")

    for r in results:
        t = f"{r['t_ms']} мс" if r["t_ms"] else "—"
        chars_in = f"{r['chars_in']:,}" if r["chars_in"] else "—"
        chars_out = f"{r['chars_out']:,}" if r["chars_out"] else "—"
        comp = f"{r['compression']}%" if r["compression"] else "—"
        q = r.get("quality_score", "—")
        label = r["label"][:30] + ".." if len(r["label"]) > 32 else r["label"]
        print(f"  {label:<32} {chars_in:>8} {chars_out:>7} {comp:>7} {t:>8}  {r['mode']:<22} {q}")

    if ok_results:
        avg_t = round(sum(r["t_ms"] for r in ok_results) / len(ok_results))
        avg_comp = round(sum(r["compression"] for r in ok_results) / len(ok_results), 1)
        print(f"\n  Среднее время суммаризации: {avg_t} мс")
        print(f"  Среднее сжатие текста:      {avg_comp}%")
    out_path = Path(__file__).parent / "test_results_summarize.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ СУММАРИЗАЦИИ\n")
        f.write("=" * 90 + "\n\n")
        for r in results:
            f.write(f"ДОКУМЕНТ: {r['label']}\n")
            f.write(f"Файл: {Path(r['path']).name}\n")
            f.write(f"Режим: {r['mode']}\n")
            f.write(f"Вход: {r['chars_in']:,} симв. | Выход: {r['chars_out']:,} симв. | "
                    f"Сжатие: {r['compression']}%\n")
            f.write(f"Время: {r['t_ms']} мс\n")
            f.write(f"Качество (кл. слова): {r.get('quality_score', '—')}\n")
            if r["quality_found"]:
                f.write(f"Найдены: {', '.join(r['quality_found'])}\n")
            f.write(f"\nКОНСПЕКТ:\n{r['summary']}\n")
            f.write("-" * 90 + "\n\n")

        if ok_results:
            f.write(f"Среднее время: {avg_t} мс\n")
            f.write(f"Среднее сжатие: {avg_comp}%\n")

    print(SEP)
    print(f"  Результаты сохранены: {out_path}")
    print(SEP)


if __name__ == "__main__":
    asyncio.run(main())
