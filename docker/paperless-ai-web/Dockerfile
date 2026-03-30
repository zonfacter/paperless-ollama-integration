FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY web/server.py /app/server.py

EXPOSE 3000

CMD ["python", "/app/server.py"]

