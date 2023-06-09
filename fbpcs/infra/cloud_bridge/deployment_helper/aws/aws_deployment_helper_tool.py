# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

import argparse

from fbpcs.infra.cloud_bridge.deployment_helper.aws.aws_deployment_helper import (
    AwsDeploymentHelper,
)
from fbpcs.infra.cloud_bridge.deployment_helper.aws.policy_params import PolicyParams


class AwsDeploymentHelperTool:
    def __init__(self, cli_args: argparse.Namespace) -> None:
        self.aws_deployment_helper_obj = AwsDeploymentHelper(
            cli_args.access_key,
            cli_args.secret_key,
            cli_args.account_id,
            cli_args.region,
        )
        self.cli_args = cli_args

    def create(self) -> None:
        if self.cli_args.add_iam_user:
            if self.cli_args.user_name is None:
                raise Exception(
                    "Need username to add user. Please add username using"
                    " --user_name argument in cli.py"
                )
            self.aws_deployment_helper_obj.create_user_workflow(
                user_name=self.cli_args.user_name
            )

        if self.cli_args.add_iam_policy:
            if self.cli_args.policy_name is None or self.cli_args.region is None:
                raise Exception(
                    "Need policy name and region to add IAM policy. Please add policy name using"
                    " --policy_name argument in cli.py and region using --region argument"
                )
            policy_params = PolicyParams(
                firehose_stream_name=self.cli_args.firehose_stream_name,
                data_bucket_name=self.cli_args.data_bucket_name,
                config_bucket_name=self.cli_args.config_bucket_name,
                database_name=self.cli_args.database_name,
                table_name=self.cli_args.table_name,
                cluster_name=self.cli_args.cluster_name,
                ecs_task_execution_role_name=self.cli_args.ecs_task_execution_role_name,
                data_ingestion_lambda_name=self.cli_args.data_ingestion_lambda_name,
                kia_lambda_name=self.cli_args.kia_lambda_name,
                events_data_crawler_arn=self.cli_args.events_data_crawler_arn,
                semi_automated_glue_job_arn=self.cli_args.semi_automated_glue_job_arn,
            )
            self.aws_deployment_helper_obj.create_policy(
                policy_name=self.cli_args.policy_name,
                template_path=self.cli_args.template_path,
                policy_params=policy_params,
            )

        if self.cli_args.attach_iam_policy:
            if (
                self.cli_args.iam_policy_name is None
                or self.cli_args.iam_user_name is None
            ):
                raise Exception(
                    "Need username and policy_name to attach policy to user. Please use"
                    " --user_name and --policy_name arguments in cli.py"
                )
            self.aws_deployment_helper_obj.attach_user_policy(
                policy_name=self.cli_args.iam_policy_name,
                user_name=self.cli_args.iam_user_name,
            )

    def destroy(self) -> None:
        if self.cli_args.delete_iam_user:
            self.aws_deployment_helper_obj.delete_user_workflow(
                user_name=self.cli_args.user_name
            )

        if self.cli_args.delete_iam_policy:
            self.aws_deployment_helper_obj.delete_policy(
                policy_name=self.cli_args.policy_name
            )
        if self.cli_args.detach_iam_policy:
            if (
                self.cli_args.iam_policy_name is None
                or self.cli_args.iam_user_name is None
            ):
                raise Exception(
                    "Need username and policy_name to detach policy to user. Please use"
                    " --user_name and --policy_name arguments in cli.py"
                )
            self.aws_deployment_helper_obj.detach_user_policy(
                policy_name=self.cli_args.iam_policy_name,
                user_name=self.cli_args.iam_user_name,
            )
