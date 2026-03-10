# config.py - backend configuration for deployment
import os

# We use environment variables instead of hardcoding URLs so that the
# code can run on any environment (localhost or the EC2 server) without
# needing to be changed.
# The EC2 server will inject the real URL into HIREFLOW_BACKEND_URL.
# If it's missing (like on our local machines), it safely falls back to localhost.
BACKEND_URL = os.environ.get("HIREFLOW_BACKEND_URL", "http://localhost:5001")

# Database URL configuration
# AWS RDS will provide this in production. Locally, it targets a local SQLite file.
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///hireflow_dev.db"
)
