#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

from fbpcs.pid.entity.pid_instance import PIDProtocol

"""
43200 s = 12 hrs

We want to be conservative on this timeout just in case:
1) partner side is not able to connect in time. This is possible because it's a manual process
to run partner containers and humans can be slow;
2) during development, we add logic or complexity to the binaries running inside the containers
so that they take more than a few hours to run.
"""

DEFAULT_CONTAINER_TIMEOUT_IN_SEC = 43200
DEFAULT_SERVER_PORT_NUMBER = 15200
MAX_ROWS_PER_PID_CONTAINER = 10_000_000
TARGET_ROWS_PER_MPC_CONTAINER = 250_000
NUM_NEW_SHARDS_PER_FILE: int = round(
    MAX_ROWS_PER_PID_CONTAINER / TARGET_ROWS_PER_MPC_CONTAINER
)

DEFAULT_K_ANONYMITY_THRESHOLD_PL = 100
DEFAULT_K_ANONYMITY_THRESHOLD_PA = 0
DEFAULT_PID_PROTOCOL: PIDProtocol = PIDProtocol.UNION_PID
DEFAULT_HMAC_KEY: str = ""
DEFAULT_CONCURRENCY = 4
ATTRIBUTION_TEST_CONCURRENCY = 1
LIFT_DEFAULT_PADDING_SIZE = 25
ATTRIBUTION_DEFAULT_PADDING_SIZE = 4
DEFAULT_LOG_COST_TO_S3 = True
DEFAULT_SORT_STRATEGY = "sort"
DEFAULT_MULTIKEY_PROTOCOL_MAX_COLUMN_COUNT = 6
FBPCS_BUNDLE_ID = "FBPCS_BUNDLE_ID"
