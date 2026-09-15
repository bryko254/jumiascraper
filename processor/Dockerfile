FROM python:3.11-slim

WORKDIR /app

COPY processor/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY shared /app/shared
COPY processor /app/processor

ENV PYTHONPATH=/app

CMD ["python", "-m", "processor.processor"]
