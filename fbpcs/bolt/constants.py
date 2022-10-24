#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

from typing import Dict, List, Type

from fbpcs.private_computation.entity.infra_config import PrivateComputationGameType

from fbpcs.private_computation.entity.private_computation_status import (
    PrivateComputationInstanceStatus,
)
from fbpcs.private_computation.stage_flows.private_computation_base_stage_flow import (
    PrivateComputationBaseStageFlow,
)
from fbpcs.private_computation.stage_flows.private_computation_pcf2_stage_flow import (
    PrivateComputationPCF2StageFlow,
)
from fbpcs.private_computation.stage_flows.private_computation_private_id_dfca_stage_flow import (
    PrivateComputationPrivateIdDfcaStageFlow,
)
from fbpcs.private_computation.stage_flows.private_computation_stage_flow import (
    PrivateComputationStageFlow,
)

DEFAULT_POLL_INTERVAL_SEC = 5
DEFAULT_STAGE_FLOW: Dict[
    PrivateComputationGameType, Type[PrivateComputationBaseStageFlow]
] = {
    PrivateComputationGameType.ATTRIBUTION: PrivateComputationPCF2StageFlow,
    PrivateComputationGameType.LIFT: PrivateComputationStageFlow,
    PrivateComputationGameType.PRIVATE_ID_DFCA: PrivateComputationPrivateIdDfcaStageFlow,
}
DEFAULT_MAX_PARALLEL_RUNS = 10
DEFAULT_NUM_TRIES = 4
TIMEOUT_SEC = 1200
RETRY_INTERVAL = 60
INVALID_STATUS_LIST: List[PrivateComputationInstanceStatus] = [
    PrivateComputationInstanceStatus.TIMEOUT,
    PrivateComputationInstanceStatus.UNKNOWN,
    PrivateComputationInstanceStatus.PROCESSING_REQUEST,
]
WAIT_VALID_STATUS_TIMEOUT = 600

FBPCS_GRAPH_API_TOKEN = "FBPCS_GRAPH_API_TOKEN"
