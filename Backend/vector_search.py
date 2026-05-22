from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

_model = None

def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        # Оставляем новую модель из репозитория — она качественнее работает с русским языком
        _model = SentenceTransformer('intfloat/multilingual-e5-small')
    return _model


def embed(texts: List[str]) -> List[List[float]]:
    return get_model().encode(texts, convert_to_numpy=True).tolist()


async def save_chunks(db: AsyncSession, document_id: uuid.UUID, chunks: List[dict]):
    from database.chunk import DocumentChunk
    texts = [c["content"] for c in chunks]
    embeddings = embed(texts)
    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        db.add(DocumentChunk(
            document_id=document_id,
            chunk_index=i,
            content=chunk["content"],
            embedding=emb,
        ))
    await db.flush()


async def search_chunks(db: AsyncSession, document_id: uuid.UUID, query: str, top_k: int = 5) -> List[str]:
    from database.chunk import DocumentChunk
    query_emb = embed_query(query)
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

def embed(texts: List[str]) -> List[List[float]]:
    prefixed = [f"passage: {t}" for t in texts]
    return get_model().encode(prefixed, convert_to_numpy=True).tolist()


def embed_query(query: str) -> List[float]:
    prefixed = f"query: {query}"
    return get_model().encode([prefixed], convert_to_numpy=True).tolist()[0]

