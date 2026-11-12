FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY . .

RUN --mount=from=ghcr.io/astral-sh/uv:0.12.9@sha256:8b940d3a9d65bed080436972241af2e21c84b5e8c9193f7014ed71479ee795ff,source=/uv,target=/usr/local/bin/uv \
    uv export --frozen --no-dev --no-emit-project --output-file /tmp/requirements.txt \
    && pip install --require-hashes -r /tmp/requirements.txt \
    && pip install --no-deps . \
    && rm /tmp/requirements.txt \
    && python -m pip uninstall --yes pip \
    && chmod +x entrypoint.sh \
    && useradd --system --uid 10001 --create-home --shell /usr/sbin/nologin app

ENV HOST=0.0.0.0 \
    PORT=8000 \
    DEBUG=false \
    WORKERS=1

USER app

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["python", "main.py"]
