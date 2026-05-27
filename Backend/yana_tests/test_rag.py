"""
Запуск: python -X utf8 Backend\test_rag.py

"""

import asyncio
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
from llm.llm_client import call_llm, _request
TEST_DOCUMENT = r"C:\Users\yanaa\Downloads\Koldanovy_2024_2nd_site.pdf"
TEST_QUESTIONS = [
    ("Какие три основных подхода к определению вероятности существовали к моменту возникновения общепринятой аксиоматики?",                       "классический, геометрический, частотный"),
    ("Какой ученый впервые вычислил вероятность того, что при 24 одновременных бросаниях двух кубиков хотя бы раз выпадут две шестерки?",                    "Блез Паскаль"),
    ("Дайте определение понятию «пространство элементарных исходов» согласно учебнику.",                     "совокупность, исходы"),
    ("Назовите два обязательных требования, которым должна удовлетворять математическая модель эксперимента со случайными исходами (Ω, A).",                        "элементарный исход, подмножества"),
    ("На каких двух постулатах основан классический способ задания вероятности?",                    "постулат, конечность, равновозможность")
]

TOP_K = 5
SEP = "-" * 90
def cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
def search_in_memory(query_emb, chunks_with_emb, top_k=5):
    scores = [(cosine_similarity(query_emb, emb), content)
              for content, emb in chunks_with_emb]
    scores.sort(reverse=True)
    return scores[:top_k]
def check_keywords(answer: str, keywords: list[str]) -> list[str]:
    return [kw for kw in keywords if kw.lower() in answer.lower()]
async def ask_without_rag(question: str) -> tuple[str, int]:
    prompt = (
        f"Ответь на вопрос студента по учебному материалу.\n\n"
        f"Вопрос: {question}\n\n"
        f"Отвечай на русском языке, кратко и по существу."
    )
    t0 = time.perf_counter()
    answer = await _request(prompt)
    t_ms = round((time.perf_counter() - t0) * 1000)
    return answer, t_ms
async def ask_with_rag(question: str, chunks_with_emb: list) -> tuple[str, int, int]:
    t0 = time.perf_counter()
    query_emb = embed_query(question)
    top_results = search_in_memory(query_emb, chunks_with_emb, top_k=TOP_K)
    t_search_ms = round((time.perf_counter() - t0) * 1000)

    context = "\n\n".join(content for _, content in top_results)

    t0 = time.perf_counter()
    answer = await call_llm(context, question)
    t_llm_ms = round((time.perf_counter() - t0) * 1000)

    return answer, t_search_ms, t_llm_ms


async def main():
    print(SEP)
    print("  СРАВНЕНИЕ: LLM БЕЗ RAG  vs  LLM С RAG")
    print(SEP)
    doc_path = Path(TEST_DOCUMENT)
    print(f"\n  Документ: {doc_path.name}")
    blocks = process_file(doc_path)
    chunks = create_chunks(blocks)
    print(f"  Чанков: {len(chunks)}")
    t0 = time.perf_counter()
    get_model()
    texts = [c["content"] for c in chunks]
    embeddings = embed(texts)
    t_embed = round(time.perf_counter() - t0, 1)
    print(f"  Готово за {t_embed} сек")
    chunks_with_emb = list(zip(texts, embeddings))
    results = []

    for i, (question, keywords) in enumerate(TEST_QUESTIONS, 1):
        print(f"\n  [{i}/{len(TEST_QUESTIONS)}] {question}")
        print("  Запрос БЕЗ RAG...", end="", flush=True)
        ans_no_rag, t_no_rag = await ask_without_rag(question)
        found_no_rag = check_keywords(ans_no_rag, keywords)
        print(f"\r  БЕЗ RAG  | {t_no_rag} мс | "
              f"Кл.слова: {', '.join(found_no_rag) if found_no_rag else 'не найдены'}")
        print(f"  Ответ: {ans_no_rag[:150].replace(chr(10), ' ')}...")
        print("  Запрос С RAG...", end="", flush=True)
        ans_rag, t_search, t_llm = await ask_with_rag(question, chunks_with_emb)
        found_rag = check_keywords(ans_rag, keywords)
        print(f"\r  С RAG    | поиск {t_search} мс + LLM {t_llm} мс = {t_search+t_llm} мс | "
              f"Кл.слова: {', '.join(found_rag) if found_rag else 'не найдены'}")
        print(f"  Ответ: {ans_rag[:150].replace(chr(10), ' ')}...")

        results.append({
            "question": question,
            "keywords": keywords,
            "no_rag_answer": ans_no_rag,
            "no_rag_t_ms": t_no_rag,
            "no_rag_found": found_no_rag,
            "no_rag_ok": len(found_no_rag) > 0,
            "rag_answer": ans_rag,
            "rag_t_search_ms": t_search,
            "rag_t_llm_ms": t_llm,
            "rag_t_total_ms": t_search + t_llm,
            "rag_found": found_rag,
            "rag_ok": len(found_rag) > 0,
        })
    no_rag_ok  = sum(1 for r in results if r["no_rag_ok"])
    rag_ok     = sum(1 for r in results if r["rag_ok"])
    avg_no_rag = round(sum(r["no_rag_t_ms"]    for r in results) / len(results))
    avg_rag    = round(sum(r["rag_t_total_ms"]  for r in results) / len(results))

    print(f"\n{SEP}")
    print("  ИТОГОВАЯ ТАБЛИЦА")
    print(SEP)
    print(f"  {'Вопрос':<38} | {'БЕЗ RAG':^16} | {'С RAG':^22}")
    print(f"  {'':38} | {'Время':>6} {'Кл.сл.':>8} | {'Время':>10} {'Кл.сл.':>8}")
    print(f"  {'-' * 82}")

    for r in results:
        q = r["question"][:36] + ".." if len(r["question"]) > 38 else r["question"]
        no_rag_kw = "Да" if r["no_rag_ok"] else "Нет"
        rag_kw    = "Да" if r["rag_ok"]    else "Нет"
        rag_time  = f"{r['rag_t_search_ms']}+{r['rag_t_llm_ms']} мс"
        print(f"  {q:<38} | {r['no_rag_t_ms']:>4} мс {no_rag_kw:>6} | {rag_time:>14} {rag_kw:>6}")

    print(f"\n  Ключевые слова БЕЗ RAG: {no_rag_ok}/{len(results)}")
    print(f"  Ключевые слова С RAG:   {rag_ok}/{len(results)}")
    print(f"  Среднее время БЕЗ RAG:  {avg_no_rag} мс")
    print(f"  Среднее время С RAG:    {avg_rag} мс (включая поиск)")
    out_path = Path(__file__).parent / "test_results_rag.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("СРАВНЕНИЕ: LLM БЕЗ RAG vs LLM С RAG\n")
        f.write(f"Документ: {doc_path.name} | top_k={TOP_K}\n")
        f.write("=" * 90 + "\n\n")
        for r in results:
            f.write(f"ВОПРОС: {r['question']}\n")
            f.write(f"Ожидаемые ключевые слова: {', '.join(r['keywords'])}\n\n")
            f.write(f"[БЕЗ RAG] Время: {r['no_rag_t_ms']} мс | "
                    f"Найдены слова: {', '.join(r['no_rag_found']) or 'нет'}\n")
            f.write(f"Ответ: {r['no_rag_answer']}\n\n")
            f.write(f"[С RAG]   Поиск: {r['rag_t_search_ms']} мс | "
                    f"LLM: {r['rag_t_llm_ms']} мс | "
                    f"Найдены слова: {', '.join(r['rag_found']) or 'нет'}\n")
            f.write(f"Ответ: {r['rag_answer']}\n")
            f.write("-" * 90 + "\n\n")
        f.write(f"Кл. слова БЕЗ RAG: {no_rag_ok}/{len(results)}\n")
        f.write(f"Кл. слова С RAG:   {rag_ok}/{len(results)}\n")
        f.write(f"Среднее время БЕЗ RAG: {avg_no_rag} мс\n")
        f.write(f"Среднее время С RAG:   {avg_rag} мс\n")
if __name__ == "__main__":
    asyncio.run(main())
