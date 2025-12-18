import boto3
from botocore.config import Config
import os

aws_access_key = os.environ.get("MASSIVE_ACCESS_KEY", 'a6fad976-77aa-4591-ba20-4528b70a05fe')
aws_secret_key = os.environ.get("MASSIVE_SECRET_KEY", 'keXDhBdz5zuofjHkeiYMznzUiyDerXgu')
endpoint_url = 'https://files.massive.com'
bucket_name = 'flatfiles'

session = boto3.Session(
    aws_access_key_id=aws_access_key,
    aws_secret_access_key=aws_secret_key,
)

s3 = session.client(
    's3',
    endpoint_url=endpoint_url,
    config=Config(signature_version='s3v4'),
)


def list_buckets():
    try:
        response = s3.list_buckets()
        print("\n--- Buckets ---")
        for bucket in response['Buckets']:
            print(f"BUCKET: {bucket['Name']}")
    except Exception as e:
        print(f"Error listing buckets: {e}")

def recursive_list(prefix, depth=0):
    if depth > 3: return
    
    try:
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix, Delimiter='/')
        if 'CommonPrefixes' in response:
            for p in response['CommonPrefixes']:
                dir_name = p['Prefix']
                print(f"DIR: {dir_name}")
                # Recursively check if it looks interesting or just go deeper
                recursive_list(dir_name, depth+1)
    except Exception as e:
        print(f"Error listing {prefix}: {e}")

print("Listing All Buckets...")
list_buckets()

print("\nRecursive Crawl of us_options_opra/...")
recursive_list("us_options_opra/")
