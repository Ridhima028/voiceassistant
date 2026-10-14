"""
Object storage for audio files, written against the plain S3 API (boto3).

Locally this talks to MinIO; in production the same code talks to AWS S3 —
only the S3_* env vars change. Nothing in here is MinIO-specific.

The database stores only the object KEY (e.g. "audio/7/3f2a...c1.webm");
the bytes themselves live here.
"""

import os
import tempfile
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, ConnectionClosedError, EndpointConnectionError

from config import (
    S3_ENDPOINT_URL, S3_PUBLIC_ENDPOINT_URL, S3_ACCESS_KEY, S3_SECRET_KEY,
    S3_REGION, S3_BUCKET, S3_PRESIGNED_EXPIRY_SECONDS,
)

# Storage is unreachable (container restarting, network blip). Callers should
# treat these as "try again later", not as "the file is gone".
TRANSIENT_ERRORS = (EndpointConnectionError, ConnectionClosedError)


class AudioObjectNotFound(Exception):
    """The key doesn't exist in the bucket. Permanent — retrying won't help."""
    pass


def _make_client(endpoint_url):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name=S3_REGION,
        config=Config(
            signature_version="s3v4",
            # MinIO serves buckets at http://host/bucket/key ("path" style);
            # AWS prefers bucket.host ("virtual" style), which "auto" picks.
            s3={"addressing_style": "path" if endpoint_url else "auto"},
            # Fail fast when storage is down, so the caller's own retry/backoff
            # (Celery in the worker) decides what happens next.
            connect_timeout=5,
            read_timeout=60,
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


# One client per process, reused for every call. boto3 clients are
# thread-safe and keep a connection pool, so creating one per request
# would just waste time on new TCP connections.
_client = _make_client(S3_ENDPOINT_URL)

# Used ONLY to sign presigned URLs — it never makes a network call. A
# presigned URL's signature covers the Host header, so it must be signed for
# the host the browser will actually request (localhost:9000), not the
# internal Docker hostname (minio:9000).
_presign_client = (
    _client if S3_PUBLIC_ENDPOINT_URL == S3_ENDPOINT_URL
    else _make_client(S3_PUBLIC_ENDPOINT_URL)
)


def _is_not_found(e: ClientError) -> bool:
    return e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NoSuchBucket", "NotFound")


def ensure_bucket() -> None:
    """Creates the bucket if it doesn't exist. Safe to call on every startup.
    The bucket stays private (no public policy): all access goes through
    our credentials or a short-lived presigned URL."""
    try:
        _client.head_bucket(Bucket=S3_BUCKET)
        return
    except ClientError as e:
        if not _is_not_found(e):
            raise

    kwargs = {"Bucket": S3_BUCKET}
    # AWS rejects an explicit LocationConstraint for us-east-1, and requires
    # one for every other region.
    if S3_REGION != "us-east-1":
        kwargs["CreateBucketConfiguration"] = {"LocationConstraint": S3_REGION}
    try:
        _client.create_bucket(**kwargs)
    except ClientError as e:
        # Another process created it between our check and our create.
        if e.response.get("Error", {}).get("Code") not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            raise


def upload_file(local_path: str, key: str, content_type: str) -> None:
    # upload_file switches to multipart upload automatically for big files.
    _client.upload_file(
        local_path, S3_BUCKET, key,
        ExtraArgs={"ContentType": content_type},
    )


def download_to_tempfile(key: str) -> str:
    """
    Downloads the object to a new temp file and returns its path. The CALLER
    must delete it. Keeps the key's extension so the audio decoder gets a
    hint about the format.
    """
    fd, path = tempfile.mkstemp(suffix=Path(key).suffix)
    os.close(fd)
    try:
        _client.download_file(S3_BUCKET, key, path)
    except ClientError as e:
        os.unlink(path)
        if _is_not_found(e):
            raise AudioObjectNotFound(
                f"Audio file not found in storage (key: {key}). Please re-upload."
            ) from e
        raise
    except BaseException:
        # Includes connection errors: never leave a half-written temp file.
        os.unlink(path)
        raise
    return path


def delete_object(key: str) -> None:
    # S3 deletes are idempotent: deleting a missing key still succeeds.
    _client.delete_object(Bucket=S3_BUCKET, Key=key)


def object_exists(key: str) -> bool:
    try:
        _client.head_object(Bucket=S3_BUCKET, Key=key)
        return True
    except ClientError as e:
        if _is_not_found(e):
            return False
        raise


def presigned_get_url(key: str, expires: int = S3_PRESIGNED_EXPIRY_SECONDS) -> str:
    """A temporary, signed link to download one object without credentials.
    Pure computation (HMAC over the request) — no call to storage."""
    return _presign_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=expires,
    )
