FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY requirements.txt .
COPY setup.py .

EXPOSE 8321

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8321"]
