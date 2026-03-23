FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for P0 features:
# - libreoffice: PPTX→PDF conversion
# - poppler-utils: PDF→JPEG conversion
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
