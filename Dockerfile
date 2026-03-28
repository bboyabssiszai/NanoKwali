FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
COPY nanobot ./nanobot

RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY web ./web
COPY bootstrap_workspace ./bootstrap_workspace
COPY runtime/nanobot-config.example.json ./runtime/nanobot-config.example.json

EXPOSE 10000

CMD ["sh", "-c", "uvicorn app.server:app --host 0.0.0.0 --port ${PORT:-10000}"]
