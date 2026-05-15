from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
import uuid

_model = None

def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
    return _model


def embed(texts: List[str]) -> List[List[float]]:
    model = get_model()
    return model.encode(texts, convert_to_numpy=True).tolist()


async def save_chunks(db: AsyncSession, document_id: uuid.UUID, chunks: List[dict]):
    from database.chunk import DocumentChunk
    texts = [c["content"] for c in chunks]
    embeddings = embed(texts)
    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        db_chunk = DocumentChunk(
            document_id=document_id,
            chunk_index=i,
            content=chunk["content"],
            embedding=emb,
        )
        db.add(db_chunk)
    await db.flush()


async def search_chunks(db: AsyncSession, document_id: uuid.UUID, query: str, top_k: int = 5) -> List[str]:
    from database.chunk import DocumentChunk
    query_emb = embed([query])[0]
    result = await db.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == document_id)
    )
    chunks = result.scalars().all()
    if not chunks:
        return []

    scores = []
    for chunk in chunks:
        if chunk.embedding:
            a = np.array(query_emb)
            b = np.array(chunk.embedding)
            score = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
            scores.append((score, chunk.content))

    scores.sort(reverse=True)
    return [content for _, content in scores[:top_k]]