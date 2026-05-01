# config.py - backend configuration for deployment
import os

# We use environment variables instead of hardcoding URLs so that the
# code can run on any environment (localhost or the EC2 server) without
# needing to be changed.
BACKEND_URL = os.environ.get("HIREFLOW_BACKEND_URL", "http://localhost:5001")

# MongoDB Atlas connection string
# Set MONGO_URI environment variable in production; falls back to this default for local dev.
MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://admin:hireflow1234%40studio@hireflowai.sfqk6hv.mongodb.net/?appName=HireFlowAI"
)

# MongoDB database and collection names
MONGO_DB_NAME = "hireflow_db"
MONGO_COLLECTION = "candidates"
