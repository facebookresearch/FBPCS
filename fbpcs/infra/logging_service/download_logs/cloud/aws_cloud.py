# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

import logging
import os
from typing import Optional

import boto3
import botocore
from botocore.exceptions import NoCredentialsError, NoRegionError

from fbpcs.infra.logging_service.download_logs.cloud.cloud_baseclass import (
    CloudBaseClass,
)

# TODO: Convert this to factory
class AwsCloud(CloudBaseClass):
    """
    Class AwsCloud verifies the credentials needed to call the boto3 APIs
    """

    def __init__(
        self,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_region: Optional[str] = None,
        logger_name: str = "logging_service",
    ) -> None:

        aws_access_key_id = aws_access_key_id or os.environ.get("AWS_ACCESS_KEY_ID")
        aws_secret_access_key = aws_secret_access_key or os.environ.get(
            "AWS_SECRET_ACCESS_KEY"
        )
        aws_region = aws_region or os.environ.get("AWS_REGION")
        self.log: logging.Logger = logging.getLogger(logger_name)

        try:
            sts = boto3.client(
                "sts",
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
            )
            self.cloudwatch_client: botocore.client.BaseClient = boto3.client(
                "logs",
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=aws_region,
            )
            self.s3_client: botocore.client.BaseClient = boto3.client(
                "s3",
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
            )

        except NoCredentialsError as error:
            self.log.error(
                f"Error occurred in validating access and secret keys of the aws account.\n"
                "Please verify if the correct access and secret key of root user are provided.\n"
                "Access and secret key can be passed using:\n"
                "1. Passing as variable to class object\n"
                "2. Placing keys in ~/.aws/config\n"
                "3. Placing keys in ~/.aws/credentials\n"
                "4. As environment variables\n"
                "\n"
                "Please refer to: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html\n"
                "\n"
                "Following is the error:\n"
                f"{error}"
            )
        except NoRegionError as error:
            self.log.error(f"Couldn't find region in AWS config." f"{error}")

        try:
            self.log.info("Verifying AWS credentials.")
            sts.get_caller_identity()
        except NoCredentialsError as error:
            self.log.error(f"Couldn't validate the AWS credentials." f"{error}")
