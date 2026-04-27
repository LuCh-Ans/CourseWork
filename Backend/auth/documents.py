import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.deps import get_current_user
from config import settings
from database.session import get_db
from database.user import User
from database.document import DocumentListResponse, DocumentResponse
from database.summary import SummaryResponse, UploadResponse
from database.document import DocumentService

router = APIRouter(prefix="/documents", tags=["Documents"])

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx"}


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Загрузить файл → извлечь текст → суммаризировать → сохранить в БД."""
    original_name = file.filename or "unknown"
    suffix = Path(original_name).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{suffix}' is not supported. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    raw_bytes = await file.read()
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024

    if not raw_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty.")

    if len(raw_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.MAX_FILE_SIZE_MB} MB limit.",
        )

    # Сохраняем на диск
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_as = f"{uuid.uuid4().hex}{suffix}"
    (upload_dir / saved_as).write_bytes(raw_bytes)

    # Делегируем всю логику сервису
    try:
        doc, summary = await DocumentService(db).process_upload(
            user_id=current_user.id,
            original_filename=original_name,
            saved_as=saved_as,
            file_size_bytes=len(raw_bytes),
            raw_bytes=raw_bytes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return UploadResponse(
        document=DocumentResponse(
            id=doc.id,
            original_filename=doc.original_filename,
            file_size_bytes=doc.file_size_bytes,
            characters_extracted=doc.characters_extracted,
            chunks_count=doc.chunks_count,
            uploaded_at=doc.uploaded_at,
            has_summary=True,
        ),
        summary=SummaryResponse(
            id=summary.id,
            document_id=summary.document_id,
            text=summary.text,
            created_at=summary.created_at,
        ),
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список всех загруженных документов текущего пользователя."""
    docs, total = await DocumentService(db).list_documents(
        user_id=current_user.id,
        offset=offset,
        limit=limit,
    )
    return DocumentListResponse(
        items=[
            DocumentResponse(
                id=d.id,
                original_filename=d.original_filename,
                file_size_bytes=d.file_size_bytes,
                characters_extracted=d.characters_extracted,
                chunks_count=d.chunks_count,
                uploaded_at=d.uploaded_at,
                has_summary=d.summary is not None,
            )
            for d in docs
        ],
        total=total,
    )


@router.get("/{document_id}", response_model=UploadResponse)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить документ + саммари по ID."""
    try:
        doc = await DocumentService(db).get_document(
            document_id=document_id,
            user_id=current_user.id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    if not doc.summary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Summary not found.")

    return UploadResponse(
        document=DocumentResponse(
            id=doc.id,
            original_filename=doc.original_filename,
            file_size_bytes=doc.file_size_bytes,
            characters_extracted=doc.characters_extracted,
            chunks_count=doc.chunks_count,
            uploaded_at=doc.uploaded_at,
            has_summary=True,
        ),
        summary=SummaryResponse(
            id=doc.summary.id,
            document_id=doc.summary.document_id,
            text=doc.summary.text,
            created_at=doc.summary.created_at,
        ),
    )
