import argparse
import glob
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


def main():
    parser = argparse.ArgumentParser(description="AWS S3 File Operations CLI Tool")
    parser.add_argument('--bucket', required=False, help="S3 bucket name")
    parser.add_argument('--action', required=True, choices=['list', 'upload', 'download', 'delete'], help="Action to perform")
    parser.add_argument('files', nargs='*', help="Files (or patterns) to process")
    parser.add_argument('-c', '--confirm', action='store_true', help="Confirm before deleting")
    args = parser.parse_args()

    # Load configuration from TOML
    TOML = load_rogkit_toml('aws')
    aws_config = AwsConfig(
        access_key_id=TOML.get('aws_access_key_id'),
        secret_access_key=TOML.get('aws_secret_access_key'),
        region_name=TOML.get('aws_region_name'),
        bucket_name=args.bucket or TOML.get('aws_bucket_name'),
    )

    # Initialize the S3 CLI tool with the loaded configuration
    s3_cli_tool = S3CliTool(config=aws_config)


    if args.action == 'list':
        res = s3_cli_tool.list_files()
        print(res)
    elif args.action == 'upload':
        for file_pattern in args.files:
            for filename in glob.glob(file_pattern):
                s3_cli_tool.upload_file(filename, filename)
    elif args.action == 'download':
        for file_pattern in args.files:
            for filename in glob.glob(file_pattern):
                s3_cli_tool.download_file(filename, filename)
    elif args.action == 'delete':
        for file_pattern in args.files:
            for object_name in glob.glob(file_pattern):
                if args.confirm:
                    s3_cli_tool.delete_file(object_name)
                else:
                    response = input(f"Are you sure you want to delete {object_name}? (y/n): ")
                    if response.lower() == 'y':
                        s3_cli_tool.delete_file(object_name)

if __name__ == "__main__":
    main()