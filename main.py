import uuid
import os
from pathlib import Path
from dotenv import load_dotenv

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel


from pdf_service import process_file, create_chunks, blocks_to_text 
from search_service import VectorSearchService
from llm_client import summarize, call_llm

load_dotenv()

# --- Конфигурация ---
UPLOAD_DIR = Path("files/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx"}
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# --- Инициализация ---
app = FastAPI(
    title="Study Lab",
    description="Загрузка учебных материалов и ответы на вопросы по ним (RAG).",
    version="0.1.0",
)

search_service = VectorSearchService()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Модели данных ---
class QuestionRequest(BaseModel):
    question: str

# --- Эндпоинты ---

@app.get("/test", tags=["Health"])
async def test() -> JSONResponse:
    return JSONResponse({"status": "ok", "message": "Server is running."})

@app.post("/upload", tags=["Ingestion & Summarization"])
async def upload_file(file: UploadFile = File(...)) -> JSONResponse:
    original_name = file.filename or "unknown"
    suffix = Path(original_name).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"File type '{suffix}' is not supported.",
        )

    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File too large.")

    unique_name = f"{uuid.uuid4().hex}{suffix}"
    save_path = UPLOAD_DIR / unique_name
    save_path.write_bytes(raw_bytes)

    try:
        blocks = process_file(save_path)
        chunks = create_chunks(blocks)
        search_service.build_index(chunks)
        prompt_text = blocks_to_text(blocks)
        summary = await summarize(prompt_text)

        return JSONResponse({
            "original_filename": original_name,
            "saved_as": unique_name,
            "blocks_count": len(blocks),
            "summary": summary,
        })
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Processing failed: {exc}")

@app.post("/ask", tags=["RAG Query"])
async def ask_question(request: QuestionRequest):
    try:
        relevant_chunks = search_service.search(request.question, top_k=10
                                                )
        print(f"--- DEBUG: Найдено фрагментов: {len(relevant_chunks)}")
        for i, chunk in enumerate(relevant_chunks):
            print(f"--- Chunk {i}: {chunk['content'][:100]}...")

        if not relevant_chunks:
            return {"answer": "В загруженном документе нет информации по этому вопросу."}
            
        context_text = "\n\n".join([c["content"] for c in relevant_chunks])
        answer = await call_llm(context_text, request.question) 
        
        return {"answer": answer}

    except Exception as e:
        print(f"Ошибка в /ask: {e}")
        raise HTTPException(status_code=500, detail=str(e))