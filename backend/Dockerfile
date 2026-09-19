FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY . .

RUN pip install --upgrade pip \
    && pip install . \
    && chmod +x entrypoint.sh

ENV HOST=0.0.0.0 \
    PORT=8000 \
    DEBUG=false \
    WORKERS=1

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["python", "main.py"]
