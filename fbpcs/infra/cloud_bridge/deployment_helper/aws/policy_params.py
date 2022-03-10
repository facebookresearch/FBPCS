# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from dataclasses import dataclass


@dataclass
class PolicyParams:
    firehose_stream_name: str
    data_bucket_name: str
    config_bucket_name: str
    database_name: str
    table_name: str
    cluster_name: str
    ecs_task_execution_role_name: str
