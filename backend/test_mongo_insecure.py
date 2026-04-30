
from pymongo import MongoClient
import sys

MONGO_URI = "mongodb+srv://admin:hireflow1234%40studio@hireflowai.sfqk6hv.mongodb.net/?appName=HireFlowAI"

def test_connection():
    print(f"Testing connection (with tlsAllowInvalidCertificates=True) to: {MONGO_URI.split('@')[1]}")
    try:
        # Adding tlsAllowInvalidCertificates=True to bypass local cert issues
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, tlsAllowInvalidCertificates=True)
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
