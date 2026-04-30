#!/bin/bash
# start.sh - starts the backend server on the EC2 instance

# 1. Activate the Python virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# 2. Install any missing requirements
echo "Installing dependencies..."
pip install -r requirements.txt

# 3. Start the production Gunicorn server
# We use 3 workers to handle multiple requests concurrently.
# Binding to 0.0.0.0 allows external traffic to reach the server.
echo "Starting Gunicorn server on port 5001..."
gunicorn -w 3 -b 0.0.0.0:5001 wsgi:app
