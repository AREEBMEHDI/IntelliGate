FROM python:3.11-slim

WORKDIR /app

# System deps for OpenCV + psycopg
RUN apt-get update && apt-get install -y \
    libpq-dev gcc libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
