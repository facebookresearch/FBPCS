#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

import unittest
from unittest.mock import create_autospec

from botocore.exceptions import ClientError

from fbpcs.infra.pce_deployment_library.cloud_library.aws.aws import AWS
from fbpcs.infra.pce_deployment_library.errors_library.aws_errors import (
    AccessDeniedError,
    S3BucketCreationError,
)


class TestAws(unittest.TestCase):
    def setUp(self) -> None:
        self.aws = AWS()
        self.aws.sts.get_caller_identity = create_autospec(
            self.aws.sts.get_caller_identity
        )

    def test_check_s3_buckets_exists(self) -> None:
        s3_bucket_name = "fake_bucket"
        self.aws.s3_client.head_bucket = create_autospec(self.aws.s3_client.head_bucket)

        with self.subTest("basic"):
            with self.assertLogs() as captured:
                self.aws.check_s3_buckets_exists(
                    s3_bucket_name=s3_bucket_name, bucket_version=False
                )
                self.assertEqual(len(captured.records), 2)
                self.assertEqual(
                    captured.records[1].getMessage(),
                    f"S3 bucket {s3_bucket_name} already exists in the AWS account.",
                )

        with self.subTest("BucketNotFound"):
            self.aws.s3_client.create_bucket = create_autospec(
                self.aws.s3_client.create_bucket
            )
            self.aws.s3_client.put_bucket_versioning = create_autospec(
                self.aws.s3_client.put_bucket_versioning
            )
            self.aws.s3_client.head_bucket.side_effect = ClientError(
                error_response={"Error": {"Code": "404"}},
                operation_name="head_bucket",
            )
            with self.assertLogs() as captured:
                self.aws.check_s3_buckets_exists(
                    s3_bucket_name=s3_bucket_name, bucket_version=False
                )
                self.assertEqual(len(captured.records), 4)
                self.assertEqual(
                    captured.records[2].getMessage(),
                    f"Creating new S3 bucket {s3_bucket_name}",
                )
                self.assertEqual(
                    captured.records[3].getMessage(),
                    f"Create S3 bucket {s3_bucket_name} operation was successful.",
                )

        with self.subTest("AccessDenied"):
            self.aws.s3_client.head_bucket.side_effect = ClientError(
                error_response={"Error": {"Code": "403"}},
                operation_name="head_bucket",
            )
            with self.assertRaisesRegex(AccessDeniedError, "Access denied*"):
                self.aws.check_s3_buckets_exists(
                    s3_bucket_name=s3_bucket_name, bucket_version=False
                )

        with self.subTest("CatchAllError"):
            self.aws.s3_client.head_bucket.side_effect = ClientError(
                error_response={"Error": {"Code": None}},
                operation_name="head_bucket",
            )
            with self.assertRaisesRegex(
                S3BucketCreationError, "Couldn't create bucket*"
            ):
                self.aws.check_s3_buckets_exists(
                    s3_bucket_name=s3_bucket_name, bucket_version=False
                )
