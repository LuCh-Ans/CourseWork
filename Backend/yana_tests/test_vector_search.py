"""
Запуск: python -X utf8 Backend/test_vector_search.py
"""

import time
import sys
import numpy as np
from pathlib import Path
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))

from pdf_service import process_file, create_chunks
from vector_search import embed, embed_query, get_model
TEST_DOCUMENT = r"C:\Users\yanaa\CourseWork\Backend\test_sample.txt"
TEST_QUESTIONS = [
    ("Что такое машинное обучение?",
     "подраздел, искусственный интеллект"),

    ("Какие данные используются при обучении с учителем?",
     "размеченные данные"),

    ("Что такое эмбеддинги и для чего они нужны?",
     "векторные представления, семантика, текст"),

    ("Что такое механизм внимания в трансформерах?",
     "attention mechanism, трансформеры"),

    ("Как RAG дополняет языковые модели?",
     "внешние данные, LLM, Retrieval-Augmented Generation"),
]

TOP_K = 5
SEP = "-" * 90
def cosine_similarity(a: list, b: list) -> float:
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
def search_in_memory(query_emb: list, chunks_with_emb: list, top_k: int = 5) -> list:
    scores = []
    for content, emb in chunks_with_emb:
        score = cosine_similarity(query_emb, emb)
        scores.append((score, content))
    scores.sort(reverse=True)
    return scores[:top_k]


def ask_relevance(question: str, results: list) -> list[bool]:
    print(f"\n  Вопрос: {question}")
    print(f"  {'─' * 70}")
    relevance = []
    for i, (score, content) in enumerate(results, 1):
        preview = content[:120].replace("\n", " ")
        print(f"\n  [{i}] score={score:.3f}")
        print(f"      {preview}...")
        while True:
            ans = input(f"      Релевантен? (y/n): ").strip().lower()
            if ans in ("y", "n"):
                relevance.append(ans in ("y", "д", "да"))
                break
            print("      Введи y или n")
    return relevance


def main():
    print(SEP)
    print("  ТЕСТ СЕМАНТИЧЕСКОГО ПОИСКА")
    print(SEP)
    doc_path = Path(TEST_DOCUMENT)
    print(f"\n  Документ: {doc_path.name}")
    t0 = time.perf_counter()
    blocks = process_file(doc_path)
    chunks = create_chunks(blocks)
    t_parse = round(time.perf_counter() - t0, 1)
    print(f"  Готово: {len(chunks)} чанков за {t_parse} сек")
    t0 = time.perf_counter()
    get_model()
    t_model = round(time.perf_counter() - t0, 1)
    print(f"  Модель загружена за {t_model} сек")
    t0 = time.perf_counter()
    texts = [c["content"] for c in chunks]
    embeddings = embed(texts)
    t_embed = round(time.perf_counter() - t0, 1)
    print(f"  Готово: {len(embeddings)} эмбеддингов за {t_embed} сек")

    chunks_with_emb = list(zip(texts, embeddings))
    print(f"\n{SEP}")
    print(f"  ТЕСТИРОВАНИЕ ПОИСКА ({len(TEST_QUESTIONS)} вопросов, top_k={TOP_K})")
    print(f"  Для каждого результата вводить y (релевантен) или n (не релевантен)")
    print(SEP)
    results_table = []
    for q_idx, (question, keywords) in enumerate(TEST_QUESTIONS, 1):
        print(f"\n  [{q_idx}/{len(TEST_QUESTIONS)}] {question}")
        print(f"  Ключевые слова: {keywords}")
        t0 = time.perf_counter()
        query_emb = embed_query(question)
        top_results = search_in_memory(query_emb, chunks_with_emb, top_k=TOP_K)
        t_search_ms = round((time.perf_counter() - t0) * 1000)
        relevance = ask_relevance(question, top_results)

        precision_at_k = round(sum(relevance) / TOP_K, 2)
        top1_relevant = relevance[0] if relevance else False
        top1_preview = top_results[0][1][:60].replace("\n", " ") if top_results else "—"

        print(f"\n  Precision@{TOP_K} = {precision_at_k}  |  Время: {t_search_ms} мс")

        results_table.append({
            "question": question,
            "top1_preview": top1_preview,
            "top1_relevant": "Да" if top1_relevant else "Нет",
            "precision": precision_at_k,
            "time_ms": t_search_ms,
        })
    avg_precision = round(sum(r["precision"] for r in results_table) / len(results_table), 2)
    avg_time = round(sum(r["time_ms"] for r in results_table) / len(results_table))
    top1_acc = round(sum(1 for r in results_table if r["top1_relevant"] == "Да") / len(results_table), 2)

    print(f"\n{SEP}")
    print("  ИТОГОВАЯ ТАБЛИЦА")
    print(SEP)
    print(f"  {'Вопрос':<45} {'Топ-1 релев.':<14} {'P@5':>5} {'Время':>8}")
    print(f"  {'-' * 80}")
    for r in results_table:
        q = r["question"][:43] + ".." if len(r["question"]) > 45 else r["question"]
        print(f"  {q:<45} {r['top1_relevant']:<14} {r['precision']:>5} {r['time_ms']:>6} мс")
    print(f"\n  Средний Precision@{TOP_K}:        {avg_precision}")
    print(f"  Точность топ-1 (Accuracy@1): {top1_acc}")
    print(f"  Среднее время поиска:        {avg_time} мс")
    print(f"  Чанков в индексе:            {len(chunks_with_emb)}")
    print(f"  Время векторизации индекса:  {t_embed} сек")
    out_path = Path(__file__).parent / "test_results_search.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ СЕМАНТИЧЕСКОГО ПОИСКА\n")
        f.write(f"top_k={TOP_K}, чанков в индексе: {len(chunks_with_emb)}\n")
        f.write("=" * 90 + "\n")
        f.write(f"{'Вопрос':<45} {'Топ-1':<6} {'P@5':>5} {'Время':>8}\n")
        f.write("-" * 90 + "\n")
        for r in results_table:
            q = r["question"][:43] + ".." if len(r["question"]) > 45 else r["question"]
            f.write(f"{q:<45} {r['top1_relevant']:<6} {r['precision']:>5} {r['time_ms']:>6} мс\n")
        f.write("=" * 90 + "\n")
        f.write(f"Средний Precision@{TOP_K}: {avg_precision}\n")
        f.write(f"Accuracy@1:          {top1_acc}\n")
        f.write(f"Среднее время:       {avg_time} мс\n")
if __name__ == "__main__":
    main()
