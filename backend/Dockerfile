FROM python:3.10-slim

# Install Java (required for PySpark) and system tools
RUN apt-get update && \
    apt-get install -y default-jre build-essential libgl1 libglib2.0-0 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set Java environment variable
ENV JAVA_HOME=/usr/lib/jvm/default-java

# Set working directory
WORKDIR /app

# Copy dependencies and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose the Flask port
EXPOSE 5001

# Command to run the application
CMD ["python", "app.py"]
