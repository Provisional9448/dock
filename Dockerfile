# Dock live desk (dock-web --live). The voice agent runs elsewhere and writes here with DOCK_LIVE_URL.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY . .
RUN uv sync --frozen --no-dev
ENV DOCK_ROOT=/app PORT=8741
CMD ["sh", "-c", "uv run --no-sync dock-web --live --host 0.0.0.0 --port ${PORT}"]
