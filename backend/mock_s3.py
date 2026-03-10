# mock_s3.py - simulates uploading files to AWS S3
# TODO: replace this with actual boto3 S3 upload when we set up AWS

def mock_upload_to_s3(filepath):
    """
    Pretends to upload a file to S3.
    Right now it just prints a message - we'll swap this out
    for real boto3 code once we have our AWS credentials set up.
    """
    print(f"[MOCK S3] would upload {filepath} to s3://hireflow-bucket/resumes/")
    return True
