FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
# DejaVu нужен для кириллицы и казахских букв в PDF-записке
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY ddc ./ddc
COPY demo_data ./demo_data
COPY validation_textbooks.json validation_hours.json ./

# Ключ OpenRouter (необязателен) задаётся переменной окружения OPENROUTER_API_KEY на хостинге, в образ не кладётся
ENV PORT=8000
CMD ["sh", "-c", "uvicorn ddc.api:app --host 0.0.0.0 --port ${PORT}"]
