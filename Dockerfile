FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    poppler-utils \
    libpq-dev \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY Backend/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir faiss-cpu

RUN pip install --no-cache-dir torch==2.4.0 --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir transformers==4.44.0 sentence-transformers==2.7.0

COPY Backend/ .

COPY frontend/ /frontend/

RUN mkdir -p files/uploads

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade heads && uvicorn main:app --host 0.0.0.0 --port 8000"]