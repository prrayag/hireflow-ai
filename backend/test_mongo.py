
from pymongo import MongoClient
import sys

MONGO_URI = "mongodb+srv://admin:hireflow1234%40studio@hireflowai.sfqk6hv.mongodb.net/?appName=HireFlowAI"

def test_connection():
    print(f"Testing connection to: {MONGO_URI.split('@')[1]}")
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        # The ismaster command is cheap and does not require auth.
        client.admin.command('ismaster')
        print("MongoDB Connection: SUCCESS")
        
        db = client['hireflow_db']
        collection = db['candidates']
        count = collection.count_documents({})
        print(f"Document count in 'candidates': {count}")
        
    except Exception as e:
        print(f"MongoDB Connection: FAILED")
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_connection()
