# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

import logging
import os
from typing import Any, Dict, List, Optional

import boto3
import botocore
from botocore.exceptions import ClientError, NoCredentialsError, NoRegionError

from fbpcs.infra.logging_service.download_logs.cloud.cloud_baseclass import (
    CloudBaseClass,
)
from fbpcs.infra.logging_service.download_logs.cloud_error.cloud_error import (
    AwsCloudwatchLogGroupFetchException,
    AwsCloudwatchLogsFetchException,
    AwsCloudwatchLogStreamFetchException,
    AwsInvalidCredentials,
    AwsKinesisFirehoseDeliveryStreamFetchException,
    AwsRegionNotFound,
    AwsS3BucketVerificationException,
    AwsS3FolderContentFetchException,
    AwsS3FolderCreationException,
    AwsS3UploadFailedException,
)
from fbpcs.infra.logging_service.download_logs.utils.utils import Utils
from tqdm import tqdm


# TODO: Convert this to factory
class AwsCloud(CloudBaseClass):
    """
    Class AwsCloud verifies the credentials needed to call the boto3 APIs
    """

    DEFAULT_RETRIES_LIMIT = 3
    DEFAULT_AWS_REGION = "us-east-1"

    def __init__(
        self,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
        logger_name: Optional[str] = None,
        s3_bucket_name: Optional[str] = None,
    ) -> None:
        aws_access_key_id = aws_access_key_id or os.environ.get("AWS_ACCESS_KEY_ID")
        aws_secret_access_key = aws_secret_access_key or os.environ.get(
            "AWS_SECRET_ACCESS_KEY"
        )
        aws_session_token = aws_session_token or os.environ.get("AWS_SESSION_TOKEN")
        bucket_name = s3_bucket_name or ""
        self.log: logging.Logger = logging.getLogger(logger_name or __name__)
        self.utils = Utils()

        self.s3_client: botocore.client.BaseClient = self.get_boto3_object(
            "s3",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
        )
        aws_region = self.get_aws_region(s3_bucket_name=bucket_name)

        sts = self.get_boto3_object(
            "sts",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            region_name=aws_region,
        )

        # Verify if the aws credentials are correct
        try:
            self.log.info("Verifying AWS credentials.")
            sts.get_caller_identity()
        except NoCredentialsError as error:
            error_message = f"Couldn't validate the AWS credentials: {error}"
            self.log.error(f"{error_message}")
            raise AwsInvalidCredentials(f"{error_message}")

        self.cloudwatch_client: botocore.client.BaseClient = self.get_boto3_object(
            "logs",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            region_name=aws_region,
        )
        self.s3_client: botocore.client.BaseClient = self.get_boto3_object(
            "s3",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            region_name=aws_region,
        )
        self.kinesis_client: botocore.client.BaseClient = self.get_boto3_object(
            "firehose",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            region_name=aws_region,
        )
        self.glue_client: botocore.client.BaseClient = self.get_boto3_object(
            "glue",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            region_name=aws_region,
        )
        self.athena_client: botocore.client.BaseClient = self.get_boto3_object(
            "athena",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            region_name=aws_region,
        )

    def get_boto3_object(
        self,
        service_name: str,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
        region_name: Optional[str] = None,
    ) -> botocore.client.BaseClient:
        return_value = None
        try:
            return_value = boto3.client(
                service_name,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                aws_session_token=aws_session_token,
                region_name=region_name,
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
        return return_value

    def get_aws_region(
        self, s3_bucket_name: str, aws_region: Optional[str] = None
    ) -> str:
        """
        Returns the aws region to be used in the boto3 objects
        Supports 2 paths:
            1. If the region is passed to the class AwsCloud, return the same
            2. Derive the AWS region from the S3 bucket.

        For path #2, boto3 API `get_bucket_location` is used, which returns `LocationConstraint`
        with the bucket region. For the region `us-east-1` None is returned by this API.
        In this function, we handle this case explicitly.

         https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.get_bucket_location
        """
        response = {}
        if aws_region is not None:
            return aws_region

        self.verify_s3_bucket(s3_bucket_name=s3_bucket_name)

        for attempt in range(self.DEFAULT_RETRIES_LIMIT):
            try:
                response = self.s3_client.get_bucket_location(Bucket=s3_bucket_name)
            except ClientError as error:
                if attempt < self.DEFAULT_RETRIES_LIMIT - 1:
                    continue
                else:
                    raise AwsRegionNotFound(f"AWS Region not found: {error}")
            break
        return response.get("LocationConstraint") or self.DEFAULT_AWS_REGION

    def get_cloudwatch_logs(
        self,
        log_group_name: str,
        log_stream_name: str,
        container_arn: Optional[str] = None,
    ) -> List[str]:
        """
        Fetches cloudwatch logs from the AWS account for a given log group and log stream
        Args:
            log_group_name (string): Name of the log group
            log_stream_name (string): Name of the log stream
            container_arn (string): Container arn to get log group and log stream names
        Returns:
            List[string]
        """
        messages = []
        message_events = []

        if not log_group_name or not log_stream_name:
            return messages

        try:
            self.log.info(
                f"Getting logs from cloudwatch for log group {log_group_name} and stream name {log_stream_name}"
            )

            response = self.cloudwatch_client.get_log_events(
                logGroupName=log_group_name,
                logStreamName=log_stream_name,
                startFromHead=True,
            )
            message_events = response["events"]

            # Loop through to get the all the logs

            while True:
                prev_token = response["nextForwardToken"]
                response = self.cloudwatch_client.get_log_events(
                    logGroupName=log_group_name,
                    logStreamName=log_stream_name,
                    nextToken=prev_token,
                )
                # same token then break
                if response["nextForwardToken"] == prev_token:
                    break
                message_events.extend(response["events"])

            messages = self._parse_log_events(message_events)

        except ClientError as error:
            error_code = error.response.get("Error", {}).get("Code")
            if error_code == "InvalidParameterException":
                error_message = (
                    f"Couldn't fetch the log events for log group {log_group_name} and log stream {log_stream_name}.\n"
                    f"Please check if the container arn {container_arn} is correct.\n"
                    f"{error}\n"
                )
            elif error_code == "ResourceNotFoundException":
                error_message = (
                    f"Couldn't find log group name {log_group_name} and log stream {log_stream_name} in AWS account.\n"
                    f"Please check if the container arn {container_arn} is correct.\n"
                    f"{error}\n"
                )
            else:
                error_message = (
                    f"Unexpected error occured in fetching the log event log group {log_group_name} and log stream {log_stream_name}\n"
                    f"{error}\n"
                )
            raise AwsCloudwatchLogsFetchException(f"{error_message}")

        return messages

    def create_s3_folder(self, bucket_name: str, folder_name: str) -> None:
        """
        Creates a folder (Key in boto3 terms) inside the s3 bucket
        Args:
            bucket_name (string): Name of the s3 bucket where logs will be stored
            folder_name (string): Name of folder for which is to be created
        Returns:
            None
        """

        if self.ensure_folder_exists(bucket_name=bucket_name, folder_name=folder_name):
            self.log.info(
                f"Folder {folder_name} in S3 bucket {bucket_name} already exists."
            )
            self.log.info("Skipping creating a new folder.")
            return

        response = self.s3_client.put_object(Bucket=bucket_name, Key=folder_name)

        if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
            self.log.info(
                f"Successfully created folder {folder_name} in S3 bucket {bucket_name}"
            )
        else:
            error_message = (
                f"Failed to create folder {folder_name} in S3 bucket {bucket_name}\n"
            )
            raise AwsS3FolderCreationException(f"{error_message}")

    def _parse_log_events(self, log_events: List[Dict[str, Any]]) -> List[str]:
        """
        AWS returns events metadata with other fields like logStreamName, timestamp etc.
        Following is the sample events returned:
        {'logStreamName': 'ecs/fake-container/123456789abcdef',
        'timestamp': 123456789,
        'message': 'INFO:This is a fake message',
        'ingestionTime': 123456789,
        'eventId': '12345678901234567890'}

        Args:
            log_events (list): List of dict contains the log messages

        Returns: list
        """

        return [event["message"] for event in log_events]

    def get_s3_folder_contents(
        self,
        bucket_name: str,
        folder_name: str,
        max_items: int = 1,
        next_continuation_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetches folders in a given S3 bucket and folders information

        Args:
            bucket_name (string): Name of the s3 bucket where logs will be stored
            folder_name (string): Name of folder for fetching the contents
            NextContinuationToken (string): Token to get all the logs in case of pagination
        Returns:
            Dict
        """

        response = {}
        kwargs = {}

        if next_continuation_token == "":
            next_continuation_token = None

        if next_continuation_token:
            kwargs = {"ContinuationToken": next_continuation_token}

        try:
            response = self.s3_client.list_objects_v2(
                Bucket=bucket_name, Prefix=folder_name, MaxKeys=max_items, **kwargs
            )
        except ClientError as error:
            error_message = f"Couldn't find folder. Please check if S3 bucket name {bucket_name} and folder name {folder_name} are correct"
            if error.response.get("Error", {}).get("Code") == "NoSuchBucket":
                error_message = f"Couldn't find folder {folder_name} in S3 bucket {bucket_name}\n{error}"
            raise AwsS3FolderContentFetchException(f"{error_message}")

        return response

    def upload_file_to_s3(
        self,
        s3_bucket_name: str,
        s3_file_path: str,
        file_name: str,
        retries: int = DEFAULT_RETRIES_LIMIT,
    ) -> None:
        """
        Function to upload a file to S3 bucket
        Args:
            s3_bucket_name (str): Name of the s3 bucket where logs will be uploaded
            s3_file_path (str): Name of folder in S3 bucket where logs will be uploaded
            file_name (str): Full path of the file location Eg: /tmp/xyz.txt
        Returns:
            None
        """

        while True:
            try:
                self.log.info("Uploading log folder to AWS S3")
                file_size = os.stat(file_name).st_size
                with tqdm(
                    total=file_size, unit="B", unit_scale=True, desc=file_name
                ) as pbar:
                    self.s3_client.upload_file(
                        Filename=file_name,
                        Bucket=s3_bucket_name,
                        Key=s3_file_path,
                        Callback=lambda bytes_transferred: pbar.update(
                            bytes_transferred
                        ),
                    )
                self.log.info("Uploaded log folder to AWS S3")
                break
            except ClientError as error:
                retries -= 1
                if retries <= 0:
                    raise AwsS3UploadFailedException(
                        f"Couldn't upload file {file_name} to bucket {s3_bucket_name}."
                        f"Please check if right S3 bucket name and file path in S3 bucket {s3_file_path}."
                        f"{error}"
                    )

    def _verify_log_group(self, log_group_name: str) -> bool:
        """
        Verifies if the log group is present in the AWS account
        Args:
            log_group_name (String): Log group name that needs to be checked

        Returns: Boolean
        """
        response = {}

        try:
            self.log.info("Checking for log group name in the AWS account")
            response = self.cloudwatch_client.describe_log_groups(
                logGroupNamePrefix=log_group_name
            )
        except ClientError as error:
            error_code = error.response.get("Error", {}).get("Code")
            if error_code == "InvalidParameterException":
                error_message = (
                    f"Wrong parameters passed to the API. Please check container arn.\n"
                    f"Couldn't find log group {log_group_name}\n"
                    f"{error}\n"
                )
            elif error_code == "ResourceNotFoundException":
                error_message = (
                    f"Couldn't find log group name {log_group_name} in AWS account.\n"
                    f"{error}\n"
                )
            else:
                error_message = (
                    f"Unexpected error occurred in fetching log group name {log_group_name}.\n"
                    f"{error}\n"
                )
            raise AwsCloudwatchLogGroupFetchException(f"{error_message}")

        return len(response.get("logGroups", [])) == 1

    def _verify_log_stream(self, log_group_name: str, log_stream_name: str) -> bool:
        """
        Verifies log stream name in AWS account.

        Args:
            log_group_name (string): Log group name in the AWS account
            log_stream_name (string): Log stream name in the AWS account

        Returns: Boolean
        """
        response = {}

        try:
            self.log.info("Checking for log stream name in the AWS account")
            response = self.cloudwatch_client.describe_log_streams(
                logGroupName=log_group_name, logStreamNamePrefix=log_stream_name
            )
        except ClientError as error:
            error_code = error.response.get("Error", {}).get("Code")
            if error_code == "InvalidParameterException":
                error_message = (
                    f"Wrong parameters passed to the API. Please check container arn.\n"
                    f"Couldn't find log stream name {log_stream_name} in log group {log_group_name}\n"
                    f"{error}\n"
                )
            elif error_code == "ResourceNotFoundException":
                error_message = (
                    f"Couldn't find log group name {log_group_name} or log stream {log_stream_name} in AWS account\n"
                    f"{error}\n"
                )
            else:
                error_message = (
                    f"Unexpected error occurred in finding log stream name {log_stream_name} in log grpup {log_group_name}\n"
                    f"{error}\n"
                )
            raise AwsCloudwatchLogStreamFetchException(f"{error_message}")

        return len(response.get("logStreams", [])) == 1

    def verify_s3_bucket(self, s3_bucket_name: str) -> None:
        """
        Verify if S3 bucket is present
        Boto3 function head_bucket returns None if the bucket is present

        Args:
            s3_bucket_name (str): name of the S3 bucket to check if it's present

        Returns:
            None

        Raises:
            AwsS3BucketVerificationException if the S3 bucket is not present in AWS accout
        """
        try:
            self.s3_client.head_bucket(Bucket=s3_bucket_name)
        except ClientError as error:
            error_message = f"Failed to fetch S3 bucket {s3_bucket_name}: {error}"
            raise AwsS3BucketVerificationException(f"{error_message}")

    def ensure_folder_exists(self, bucket_name: str, folder_name: str) -> bool:
        """
        Verify if the folder is present in s3 bucket
        Args:
            bucket_name (string): Name of the s3 bucket where logs will be stored
            folder_name (string): Name of folder for which verification is needed
        Returns:
            Boolean
        """

        response = self.get_s3_folder_contents(
            bucket_name=bucket_name, folder_name=folder_name
        )

        return "Contents" in response

    def get_kinesis_firehose_streams(
        self, kinesis_firehose_stream_name: str
    ) -> Dict[str, Any]:
        try:
            response = self.kinesis_client.describe_delivery_stream(
                DeliveryStreamName=kinesis_firehose_stream_name, Limit=1
            )
        except ClientError as error:
            error_message = f"Failed to get Kinesis firehose stream {kinesis_firehose_stream_name}: {error}"
            raise AwsKinesisFirehoseDeliveryStreamFetchException(f"{error_message}")

        return response

    def get_kinesis_firehose_config(self, response: Dict[str, Any]) -> Dict[str, Any]:
        return_dict = {"Enabled": False}
        try:
            response_dict = response["DeliveryStreamDescription"]["Destinations"][0][
                "S3DestinationDescription"
            ]["CloudWatchLoggingOptions"]
        except KeyError:
            self.log.error("Coudln't find the Cloudwatch configs.")
            self.log.error("Returning Cloudwatch logging disabled config")
            return return_dict
        return response_dict

    def get_latest_cloudwatch_log(self, log_group_name: str) -> str:
        """
        Returns the latest log stream on a given log group
        """
        stream_name = ""
        response = {}
        try:
            self.log.info("Checking for log stream name in the AWS account")
            response = self.cloudwatch_client.describe_log_streams(
                logGroupName=log_group_name,
                orderBy="LastEventTime",
                descending=True,
                limit=1,
            )
        except ClientError as error:
            error_message = (
                f"Couldn't fetch log streams for log group {log_group_name}: {error}"
            )
            self.log.error(f"{error_message}")

        # Since only one entry is fetched, number of log_streams will be 1
        for log_streams in response.get("logStreams", []):
            stream_name = log_streams.get("logStreamName", "")
            break

        return stream_name

    def get_glue_crawler_config(self, glue_crawler_name: str) -> Dict[str, Any]:
        """
        Returns glue crawler config which included status of crawler and last crawler status
        """
        response = {}
        if not glue_crawler_name:
            self.log.error(
                "Glue crawler name not found. Failed to fetch Glue Crawler configs."
            )
            return response
        try:
            response = self.glue_client.get_crawler(Name=glue_crawler_name)
        except ClientError as error:
            error_message = f"Couldn't fetch glue crawler {glue_crawler_name}: {error}"
            self.log.error(f"{error_message}")
            response = {"Get_Crawler_Error": error_message}
        return response

    def get_glue_crawler_metrics(self, glue_crawler_name: str) -> Dict[str, Any]:
        """
        Returns glue crawler metrics which includes number of rows updated in a database, run time etc
        """
        response = {}
        if not glue_crawler_name:
            return response
        try:
            response = self.glue_client.get_crawler_metrics(
                CrawlerNameList=[glue_crawler_name], MaxResults=1
            )
        except ClientError as error:
            error_message = (
                f"Couldn't fetch glue crawler metrics {glue_crawler_name}: {error}"
            )
            self.log.error(f"{error_message}")
            response = {"Get_Crawler_Metrics_Error": error_message}
        return response

    def get_glue_etl_job_details(self, glue_etl_name: str) -> Dict[str, Any]:
        """
        Returns glue ETL job details
        """
        response = {}
        if not glue_etl_name:
            return response

        try:
            response = self.glue_client.get_job(JobName=glue_etl_name)
        except ClientError as error:
            error_message = f"Couldn't fetch glue ETL job {glue_etl_name}: {error}"
            self.log.error(f"{error_message}")
            response = {"Get_Job_Error": error_message}
        return response

    def get_glue_etl_job_run_details(self, glue_etl_name: str) -> Dict[str, Any]:
        """
        Returns run details of a glue ETL job
        """
        response = {}
        if not glue_etl_name:
            return response

        try:
            response = self.glue_client.get_job_runs(
                JobName=glue_etl_name, MaxResults=10
            )
        except ClientError as error:
            error_message = (
                f"Couldn't fetch glue ETL job run details {glue_etl_name}: {error}"
            )
            self.log.error(f"{error_message}")
            response = {"Get_Job_Runs_Error": error_message}
        return response

    def get_athena_database_list(self, data_catalog_name: str) -> Dict[str, Any]:
        """
        Returns list of databases for a given data catalog
        """
        response = {}
        if not data_catalog_name:
            self.log.error("Catalog name not passed to fetch database config.")
            return response

        try:
            response = self.athena_client.list_databases(
                CatalogName=data_catalog_name, MaxResults=10
            )
        except ClientError as error:
            error_message = f"Couldn't fetch databases for data catalog {data_catalog_name}: {error}"
            self.log.error(f"{error_message}")
            response = {"List_Databases_Error": error_message}
        return response

    def get_athena_database_config(
        self, catalog_name: str, database_name: str
    ) -> Dict[str, Any]:
        """
        Checks the database config for a given catalog and returns the api response
        """
        response = {}
        if not catalog_name:
            self.log.error("Catalog name not provided to fetch database config.")
            return response

        if not database_name:
            self.log.error("Database name not provided to fetch database config.")
            return response

        try:
            response = self.athena_client.get_database(
                CatalogName=catalog_name, DatabaseName=database_name
            )
        except ClientError as error:
            error_message = f"Failed to fetch database config in Athena for catalog {catalog_name} and database {database_name}: {error}"
            self.log.error(f"{error_message}")
            response = {"Get_Database_Error": error_message}
        return response

    def get_athena_query_executions(self) -> List[str]:
        """
        List Athena execution IDs.
        Which can be used to get more information about the query execution
        """
        response = {}
        try:
            response = self.athena_client.list_query_executions()
        except ClientError as error:
            error_message = f"Failed to fetch athena query exectuction ID: {error}"
            self.log.error(f"{error_message}")
        return response.get("QueryExecutionIds", [])

    def get_athena_query_execution_details(
        self, query_execution_id: str
    ) -> Dict[str, Any]:
        """
        Returns Athena query execution details
        """
        response = {}
        if not query_execution_id:
            self.log.error("Query execution ID not provided to fetch query details.")
            return response
        try:
            response = self.athena_client.get_query_execution(
                QueryExecutionId=query_execution_id
            )
        except ClientError as error:
            error_message = f"Failed to fetch query details with execution ID {query_execution_id}: {error}"
            self.log.error(f"{error_message}")
            response = {"Get_Query_Execution_Error": error_message}
        return response
