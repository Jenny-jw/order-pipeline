"""Thin wrapper over the S3 API: list the data files in a prefix, read one as text."""

from dataclasses import dataclass
from typing import Iterator

import boto3


@dataclass(frozen=True)
class S3Object:
    key: str
    etag: str
    size: int


class S3Reader:
    def __init__(self, bucket: str, profile: str | None = None, region: str | None = None):
        session = boto3.Session(profile_name=profile, region_name=region)
        self._s3 = session.client("s3")
        self._bucket = bucket

    def list_data_files(self, prefix: str) -> Iterator[S3Object]:
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                # Console-created "folders" are zero-byte objects whose key ends in "/".
                if obj["Key"].endswith("/") or obj["Size"] == 0:
                    continue
                yield S3Object(
                    key=obj["Key"],
                    etag=obj["ETag"].strip('"'),
                    size=obj["Size"],
                )

    def read_text(self, key: str) -> str:
        response = self._s3.get_object(Bucket=self._bucket, Key=key)
        # utf-8-sig drops the byte-order mark that Excel writes into exported CSVs.
        return response["Body"].read().decode("utf-8-sig")
