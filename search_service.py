import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict

class VectorSearchService:
    def __init__(self, model_name: str = "intfloat/multilingual-e5-small"):
        """
        Инициализация сервиса поиска.
        Загружает модель один раз при старте сервера.
        """
        self.model = SentenceTransformer(model_name)
        self.index = None
        self.chunks: List[Dict] = []

    def build_index(self, chunks: List[Dict]):
        """
        Создает векторный индекс из предоставленных чанков текста.
        """
        if not chunks:
            return
            
        self.chunks = chunks
        texts = [c["content"] for c in chunks]
        embeddings = self.model.encode(texts, normalize_embeddings=True)        
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(np.array(embeddings).astype('float32'))
        print(f"--- FAISS: Индексировано {len(texts)} чанков ---")

    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        """
        Ищет наиболее релевантные фрагменты текста для заданного вопроса.
        """
        if self.index is None or not self.chunks:
            print("Ошибка: Попытка поиска по пустому индексу.")
            return []
        query_vector = self.model.encode([query], normalize_embeddings=True)
        distances, indices = self.index.search(
            np.array(query_vector).astype('float32'), 
            top_k
        )
        results = []
        for idx in indices[0]:
            if idx != -1 and idx < len(self.chunks):
                results.append(self.chunks[idx])
                
        return results