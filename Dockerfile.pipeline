FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pipeline.py .
COPY register_streams.py .

CMD ["sh", "-c", "python pipeline.py && python register_streams.py"]
