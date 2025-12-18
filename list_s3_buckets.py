
import boto3
from botocore.config import Config

ACCESS_KEY = 'a6fad976-77aa-4591-ba20-4528b70a05fe'
SECRET_KEY = 'keXDhBdz5zuofjHkeiYMznzUiyDerXgu'

session = boto3.Session(
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
)

s3 = session.client(
    's3',
    endpoint_url='https://files.massive.com',
    config=Config(signature_version='s3v4'),
)

bucket_name = 'flatfiles'
prefix = 'us_options_opra/'

print(f"Scanning {bucket_name}/{prefix}...")
response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix, Delimiter='/')

if 'CommonPrefixes' in response:
    print("FOUND FOLDERS:")
    for p in response['CommonPrefixes']:
        print(f" - {p['Prefix']}")
else:
    print("No folders found. Listing first 5 files...")
    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix, MaxKeys=5)
    for obj in response.get('Contents', []):
        print(f" - {obj['Key']}")
