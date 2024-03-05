from dataclasses import dataclass, field
import boto3
from botocore.exceptions import NoCredentialsError
from typing import List
from ..bin.tomlr import load_rogkit_toml


@dataclass
class AwsConfig:
    access_key_id: str
    secret_access_key: str
    bucket_name: str
    region_name: str = 'us-east-1'  # Keep default arguments after non-default arguments

    def __post_init__(self):
        self.s3_resource = boto3.resource(
            's3',
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name=self.region_name
        )

@dataclass
class S3CliTool:
    config: AwsConfig
    s3_client: any = field(init=False)

    def __post_init__(self):
        self.s3_client = self.config.s3_resource

    def list_files(self) -> List[str]:
        bucket = self.s3_client.Bucket(self.config.bucket_name)
        return [file.key for file in bucket.objects.all()]

    def upload_file(self, file_name: str, object_name: str):
        try:
            self.s3_client.meta.client.upload_file(file_name, self.config.bucket_name, object_name)
            print(f"{file_name} has been uploaded as {object_name}.")
        except NoCredentialsError:
            print("Credentials not available")

    def download_file(self, object_name: str, file_name: str):
        try:
            self.s3_client.meta.client.download_file(self.config.bucket_name, object_name, file_name)
            print(f"{object_name} has been downloaded as {file_name}.")
        except NoCredentialsError:
            print("Credentials not available")

    def delete_file(self, object_name: str):
        try:
            self.s3_client.meta.client.delete_object(Bucket=self.config.bucket_name, Key=object_name)
            print(f"{object_name} has been deleted.")
        except NoCredentialsError:
            print("Credentials not available")

TOML = load_rogkit_toml('aws')
aws_config = AwsConfig(
    access_key_id=TOML.get('aws_access_key_id'),
    secret_access_key=TOML.get('aws_secret_access_key'),
    region_name=TOML.get('aws_region_name'),
    bucket_name=TOML.get('aws_bucket_name')
)


s3_cli_tool = S3CliTool(config=aws_config)

# List files
print(s3_cli_tool.list_files())

# # Upload a file
# s3_cli_tool.upload_file('path/to/your/local/file', 'your_desired_s3_key')

# # Download a file
# s3_cli_tool.download_file('your_s3_key', 'path/to/your/local/directory')

# # Delete a file
# s3_cli_tool.delete_file('your_s3_key')
