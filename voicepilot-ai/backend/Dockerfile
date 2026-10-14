FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

# No PyTorch dependency anymore — semantic segmentation now uses the Gemini
# embeddings API instead of a local sentence-transformers model, so this
# build no longer needs the special CPU-torch install step that used to
# live here. Builds should be noticeably faster now.
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]