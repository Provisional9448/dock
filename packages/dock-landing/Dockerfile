# Landing page only. Set the Railway service root directory to /packages/dock-landing.
# The Dockerfile at the repo root is the live desk. Do not point this service at it.
FROM python:3.12-slim

WORKDIR /srv
COPY index.html styles.css serve.py ./

ENV PORT=8080
EXPOSE 8080

CMD ["python", "-u", "serve.py"]
