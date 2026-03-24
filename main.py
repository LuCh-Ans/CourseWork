import uuid
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from llm_client import summarize

UPLOAD_DIR = Path("files/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx"}
MAX_FILE_SIZE_MB  = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

app = FastAPI(
    title="Study Lab",
    description=(
        "Upload educational materials (PDF, TXT, DOCX) "
        "and receive an AI-generated summary."
    ),
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/test", tags=["Health"])
async def test() -> JSONResponse:
    """Smoke-test endpoint. Returns 200 if the server is running."""
    return JSONResponse({"status": "ok", "message": "Server is running."})


@app.post("/upload", tags=["Summarization"])
async def upload_file(file: UploadFile = File(...)) -> JSONResponse:
    """
    Pipeline:
      1. Validate file (type, size)
      2. Save to /uploads
      3. Extract text  ← Person 2's extract_text() will be called here
      4. Summarize via LLM
      5. Return summary to frontend (Person 3)
    """

    original_name = file.filename or "unknown"
    suffix = Path(original_name).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=(
                f"File type '{suffix}' is not supported. "
                f"Allowed: {sorted(ALLOWED_EXTENSIONS)}"
            ),
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
    save_path   = UPLOAD_DIR / unique_name
    save_path.write_bytes(raw_bytes)


    try:
        from pdf_service import extract_text
        text_content = extract_text(save_path)
    except ImportError:

        text_content = _fallback_read_text(raw_bytes)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Text extraction failed: {exc}",
        ) from exc

    if not text_content.strip():
        raise HTTPException(
            status_code=422,
            detail="No text could be extracted from the file.",
        )


    try:
        summary = await summarize(text_content)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


    return JSONResponse(
        {
            "original_filename":    original_name,
            "saved_as":             unique_name,
            "characters_extracted": len(text_content),
            "summary":              summary,
        }
    )


def _fallback_read_text(raw_bytes: bytes) -> str:

    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return raw_bytes.decode("latin-1")
