"""
AWS S3 file operations CLI tool.

Provides commands for listing, uploading, downloading, and deleting files
from AWS S3 buckets. Supports versioned buckets and bulk purge operations.
Configuration via rogkit config.toml.

# WARNING: Purge action removes ALL versions and delete markers
amaz --action purge -c --all-versions --show-errors
"""
import argparse
import glob
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

try:
    import boto3  # type: ignore
    from botocore.exceptions import NoCredentialsError  # type: ignore
except ImportError as import_error:  # pragma: no cover - optional dependency
    boto3 = None  # type: ignore[assignment]

    class NoCredentialsError(RuntimeError):  # type: ignore[no-redef]
        """Raised when AWS credentials are missing."""

    _BOTO_IMPORT_ERROR: Optional[ImportError] = import_error
else:
    _BOTO_IMPORT_ERROR = None
from ..bin.tomlr import load_rogkit_toml


@dataclass
class AwsConfig:
    """AWS S3 connection configuration."""
    access_key_id: str
    secret_access_key: str
    bucket_name: str
    region_name: str = 'us-east-1'  # Keep default arguments after non-default arguments

    def __post_init__(self):
        if _BOTO_IMPORT_ERROR is not None:
            raise RuntimeError(
                "boto3 is required for AWS S3 operations. "
                "Install the 'aws' dependency group (uv sync --group aws)."
            ) from _BOTO_IMPORT_ERROR
        self.s3_resource = boto3.resource(
            's3',
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name=self.region_name
        )

@dataclass
class S3CliTool:
    """S3 CLI operations wrapper."""
    config: AwsConfig
    s3_client: any = field(init=False)

    def __post_init__(self):
        self.s3_client = self.config.s3_resource

    def list_files(self, prefix: str | None = None) -> List[str]:
        bucket = self.s3_client.Bucket(self.config.bucket_name)
        it = bucket.objects.filter(Prefix=prefix) if prefix else bucket.objects.all()
        return [obj.key for obj in it]

    def upload_file(self, file_name: str, object_name: str | None = None):
        object_name = object_name or file_name
        try:
            self.s3_client.meta.client.upload_file(file_name, self.config.bucket_name, object_name)
            print(f"{file_name} -> s3://{self.config.bucket_name}/{object_name}")
        except NoCredentialsError:
            print("Credentials not available")

    def download_file(self, object_name: str, file_name: str | None = None):
        # default to saving just the basename
        file_name = file_name or Path(object_name).name
        try:
            self.s3_client.meta.client.download_file(self.config.bucket_name, object_name, file_name)
            print(f"s3://{self.config.bucket_name}/{object_name} -> {file_name}")
        except NoCredentialsError:
            print("Credentials not available")

    def delete_file(self, object_name: str):
        try:
            self.s3_client.meta.client.delete_object(Bucket=self.config.bucket_name, Key=object_name)
            print(f"deleted: s3://{self.config.bucket_name}/{object_name}")
        except NoCredentialsError:
            print("Credentials not available")

    def delete_all(self, prefix: str | None = None, dry_run: bool = False,
                all_versions: bool = True, show_errors: bool = True) -> int:
        """
        Delete everything (optionally by prefix).
        If all_versions=True and bucket is versioned, delete all versions + delete markers.
        Returns count of successfully deleted items.
        """
        bucket = self.s3_client.Bucket(self.config.bucket_name)

        # Detect versioning
        versioning = self.s3_client.BucketVersioning(self.config.bucket_name).status
        is_versioned = (versioning == 'Enabled') or (versioning == 'Suspended')

        deleted_count = 0
        errors_total = 0

        if all_versions and is_versioned:
            # Delete object versions + delete markers
            iterable = bucket.object_versions.filter(Prefix=prefix) if prefix else bucket.object_versions.all()
            # Build list of {"Key": key, "VersionId": vid}
            items = [{"Key": v.object_key, "VersionId": v.id} for v in iterable]
        else:
            # Delete current objects only
            iterable = bucket.objects.filter(Prefix=prefix) if prefix else bucket.objects.all()
            items = [{"Key": o.key} for o in iterable]

        if dry_run:
            for i in items:
                if "VersionId" in i:
                    print(f"would delete: s3://{self.config.bucket_name}/{i['Key']}?versionId={i['VersionId']}")
                else:
                    print(f"would delete: s3://{self.config.bucket_name}/{i['Key']}")
            print(f"DRY-RUN: {len(items)} objects matched")
            return 0

        # Chunked delete (<=1000 per request)
        for i in range(0, len(items), 1000):
            chunk = items[i:i+1000]
            resp = bucket.delete_objects(Delete={'Objects': chunk, 'Quiet': False})
            # Count only the ones S3 confirms
            deleted_count += len(resp.get('Deleted', []))
            errs = resp.get('Errors', [])
            errors_total += len(errs)
            if show_errors and errs:
                for e in errs[:10]:
                    print(f"ERROR deleting {e.get('Key')} "
                        f"{'(vId='+e.get('VersionId')+')' if e.get('VersionId') else ''}: "
                        f"{e.get('Code')} - {e.get('Message')}")
                if len(errs) > 10:
                    print(f"... {len(errs)-10} more errors not shown")

        print(f"Deleted {deleted_count} item(s) from s3://{self.config.bucket_name}/" + (prefix or ""))
        if errors_total:
            print(f"{errors_total} item(s) failed to delete.")
        return deleted_count


def main():
    """CLI entry point for AWS S3 file operations."""
    parser = argparse.ArgumentParser(description="AWS S3 File Operations CLI Tool")
    parser.add_argument('--bucket', required=False, help="S3 bucket name")
    parser.add_argument('--action', required=True, choices=['list', 'upload', 'download', 'delete', 'purge'], help="Action to perform")
    parser.add_argument('files', nargs='*', help="Local files (upload) or S3 keys (download/delete). No globs for S3.")
    parser.add_argument('--prefix', help="Limit list/delete/purge to keys starting with this prefix")
    parser.add_argument('-c', '--confirm', action='store_true', help="Skip prompt (assume yes)")
    parser.add_argument('-n', '--dry-run', action='store_true', help="Show what would happen without changing anything")
    parser.add_argument('--all-versions', action='store_true',
                    help="When purging a versioned bucket, delete all versions and delete markers")
    parser.add_argument('--show-errors', action='store_true',
                    help="Show per-object delete errors")
    args = parser.parse_args()

    TOML = load_rogkit_toml('aws')
    aws_config = AwsConfig(
        access_key_id=TOML.get('aws_access_key_id'),
        secret_access_key=TOML.get('aws_secret_access_key'),
        region_name=TOML.get('aws_region_name'),
        bucket_name=args.bucket or TOML.get('aws_bucket_name'),
    )
    s3 = S3CliTool(config=aws_config)

    if args.action == 'list':
        files = s3.list_files(prefix=args.prefix)
        for k in files:
            print(k)
        files = "files" if len(files) != 1 else "file"
        print(f"\n{len(files)} {files} listed from bucket: {aws_config.bucket_name}")

    elif args.action == 'upload':
        for file_pattern in args.files:
            # keep glob for LOCAL files only
            for filename in glob.glob(file_pattern):
                s3.upload_file(filename)

    elif args.action == 'download':
        # treat args.files as exact S3 KEYS; no local globbing
        for key in args.files:
            s3.download_file(key)

    elif args.action == 'delete':
        # delete specific S3 KEYS passed positionally (no glob)
        for key in args.files:
            if args.confirm or input(f"Delete s3://{aws_config.bucket_name}/{key}? (y/N): ").lower() == 'y':
                s3.delete_file(key)

    elif args.action == 'purge':
        if not args.confirm:
            resp = input(f"Really delete ALL objects{f' with prefix {args.prefix!r}' if args.prefix else ''} "
                        f"from s3://{aws_config.bucket_name}/ ? (type 'yes'): ")
            if resp.strip().lower() != 'yes':
                print("Aborted.")
                return
        s3.delete_all(prefix=args.prefix,
                    dry_run=args.dry_run,
                    all_versions=args.all_versions,
                    show_errors=args.show_errors)
        

if __name__ == "__main__":
    main()