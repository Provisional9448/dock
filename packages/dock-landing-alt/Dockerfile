# Alternate Dock landing. Point the Railway service root at this directory.
# Railway injects PORT; serve.py binds 0.0.0.0 and reads it.
FROM python:3.12-slim
WORKDIR /app
COPY index.html serve.py ./
ENV PORT=8080
EXPOSE 8080
CMD ["python", "-u", "serve.py"]
