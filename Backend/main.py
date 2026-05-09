import uuid
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List

load_dotenv()
import database  # noqa — регистрирует все модели

from pdf_service import process_file, create_chunks, blocks_to_text
from vector_search import VectorSearchService
from llm.llm_client import summarize, call_llm
from auth.authent import router as auth_router
from auth.documents import router as documents_router
from auth.chat_router import router as chat_router

UPLOAD_DIR = Path("files/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx"}
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

app = FastAPI(
    title="Study Lab",
    description="Upload educational materials (PDF, TXT, DOCX) and receive an AI-generated summary.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="../frontend"), name="static")

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(chat_router)
search_service = VectorSearchService()

class QuestionRequest(BaseModel):
    question: str

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    system: str = ""

@app.get("/", response_class=HTMLResponse)
async def home_page():
    html_path = Path("../frontend/study_ai_combined.html")
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    html_path = Path("../frontend/study_ai_combined.html")
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

@app.get("/chat", response_class=HTMLResponse)
async def chat_page():
    html_path = Path("../frontend/study_ai_combined.html")
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

@app.get("/flashcards", response_class=HTMLResponse)
async def flashcards_page():
    html_path = Path("../frontend/study_ai_combined.html")
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

@app.get("/roadmap", response_class=HTMLResponse)
async def roadmap_page():
    html_path = Path("../frontend/study_ai_combined.html")
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

@app.get("/view/{doc_id}", response_class=HTMLResponse)
async def document_page(doc_id: str):
    html_path = Path("../frontend/study_ai_combined.html")
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

@app.get("/test", tags=["Health"])
async def test() -> JSONResponse:
    return JSONResponse({"status": "ok", "message": "Server is running."})

@app.post("/chat", tags=["Chat"])
async def chat_endpoint(request: ChatRequest):
    """Прокси к LLM для чат-интерфейса"""
    try:
        from llm.llm_client import _request
        history_lines = []
        for m in request.messages:
            prefix = "Пользователь" if m.role == "user" else "Ассистент"
            history_lines.append(f"{prefix}: {m.content}")
        history_text = "\n".join(history_lines)
        system_prompt = request.system if request.system else (
            "Ты Study AI — умный учебный ассистент. Отвечай на русском языке. "
            "Объясняй концепции чётко, с аналогиями и примерами. "
            "Используй маркированные списки и **жирный** для ключевых терминов."
        )
        full_prompt = f"{system_prompt}\n\n{history_text}"
        answer = await _request(full_prompt)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ask", tags=["RAG Query"])
async def ask_question(request: QuestionRequest):
    try:
        relevant_chunks = search_service.search(request.question, top_k=10)
        if not relevant_chunks:
            return {"answer": "В загруженном документе нет информации по этому вопросу."}
        context_text = "\n\n".join([c["content"] for c in relevant_chunks])
        answer = await call_llm(context_text, request.question)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload", tags=["Summarization"])
async def upload_file(file: UploadFile = File(...)) -> JSONResponse:
    original_name = file.filename or "unknown"
    suffix = Path(original_name).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"File type '{suffix}' is not supported. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    raw_bytes = await file.read()

    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(raw_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {MAX_FILE_SIZE_MB} MB size limit.",
        )

    unique_name = f"{uuid.uuid4().hex}{suffix}"
    save_path = UPLOAD_DIR / unique_name
    save_path.write_bytes(raw_bytes)

    blocks = process_file(save_path)
    if not blocks:
        raise HTTPException(status_code=422, detail="No text could be extracted from the file.")

    chunks = create_chunks(blocks)
    search_service.build_index(chunks)
    prompt_text = blocks_to_text(blocks)

    try:
        summary = await summarize(prompt_text)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return JSONResponse({
        "original_filename": original_name,
        "saved_as": unique_name,
        "characters_extracted": len(prompt_text),
        "blocks_count": len(blocks),
        "summary": summary,
    })