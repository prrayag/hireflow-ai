# HireFlow API - production image for EC2
FROM python:3.11-slim

WORKDIR /app

# System deps for PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-prod.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
EXPOSE 5001

# Long timeout for first ML model download + batch upload
CMD ["gunicorn", "-b", "0.0.0.0:5001", "-w", "1", "--timeout", "300", "--keep-alive", "5", "app:app"]
