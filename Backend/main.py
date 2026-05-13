import uuid
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from database.session import get_db
from database.user import User
from auth.deps import get_current_user
from database.chat import ChatService
load_dotenv()
import database

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
    """Прокси к LLM"""
    try:
        from llm.llm_client import _request

        history_lines = []
        for m in request.messages:
            prefix = "Пользователь" if m.role == "user" else "Ассистент"
            history_lines.append(f"{prefix}: {m.content}")

        history_text = "\n".join(history_lines)

        system_prompt = request.system or (
            "Ты Study AI — умный учебный ассистент. Отвечай на русском языке. "
            "Объясняй чётко, с примерами."
        )

        full_prompt = f"{system_prompt}\n\n{history_text}"
        answer = await _request(full_prompt)

        return {"answer": answer}
    except Exception as e:
        print(f"Chat error: {e}")
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


@app.post("/upload", tags=["Documents"])
async def upload_file(
        file: UploadFile = File(...),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    if not file.filename:
        raise HTTPException(400, "No filename")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Allowed: {ALLOWED_EXTENSIONS}")

    # Сохраняем файл
    file_path = UPLOAD_DIR / f"{uuid.uuid4()}{ext}"
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(413, "File too large")

    with open(file_path, "wb") as f:
        f.write(content)

    # Обработка документа
    try:
        text, summary_text = await process_file(file_path, file.filename)

        document = await documents_router.create_document(  # или напрямую через сервис
            user_id=current_user.id,
            filename=file.filename,
            file_path=str(file_path),
            text=text
        )

        # Автоматически создаём/привязываем чат
        chat_service = ChatService(db)
        session = await chat_service.create_session(
            user_id=current_user.id,
            title=Path(file.filename).stem[:80],  # красивое название
            document_id=document.id
        )

        # Сохраняем summary
        await chat_service.save_summary(session.id, summary_text)

        return {
            "success": True,
            "document_id": str(document.id),
            "session_id": str(session.id),
            "title": session.title,
            "summary": {"text": summary_text[:1500] + "..." if len(summary_text) > 1500 else summary_text}
        }
    except Exception as e:
        print(f"Upload error: {e}")
        raise HTTPException(500, str(e))