# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Set, Union

from dataclasses_json import DataClassJsonMixin
from fbpcs.common.entity.dataclasses_hooks import DataclassHookMixin, HookEventType
from fbpcs.common.entity.generic_hook import GenericHook
from fbpcs.common.entity.pcs_mpc_instance import PCSMPCInstance
from fbpcs.common.entity.stage_state_instance import StageStateInstance
from fbpcs.pid.entity.pid_instance import PIDInstance
from fbpcs.post_processing_handler.post_processing_instance import (
    PostProcessingInstance,
)
from fbpcs.private_computation.entity.pce_config import PCEConfig
from fbpcs.private_computation.entity.pcs_feature import PCSFeature
from fbpcs.private_computation.entity.private_computation_status import (
    PrivateComputationInstanceStatus,
)


class PrivateComputationRole(Enum):
    PUBLISHER = "PUBLISHER"
    PARTNER = "PARTNER"


class PrivateComputationGameType(Enum):
    LIFT = "LIFT"
    ATTRIBUTION = "ATTRIBUTION"


UnionedPCInstance = Union[
    PIDInstance, PCSMPCInstance, PostProcessingInstance, StageStateInstance
]


# called in num_pid_mpc_containers_hook
def raise_containers_error(obj: "InfraConfig") -> None:
    raise ValueError(
        f"num_pid_containers must be less than or equal to num_mpc_containers. Received num_pid_containers = {obj.num_pid_containers} and num_mpc_containers = {obj.num_mpc_containers}"
    )


# called in num_pid_mpc_containers_hook
def not_valid_containers(obj: "InfraConfig") -> bool:
    if hasattr(obj, "num_pid_containers") and hasattr(obj, "num_mpc_containers"):
        return obj.num_pid_containers > obj.num_mpc_containers
    # one or both not initialized yet
    return False


# create generic_hook for num_pid_containers > num_mpc_containers check
# if num_pid_containers < num_mpc_containers => raise an error
num_pid_mpc_containers_hook: GenericHook["InfraConfig"] = GenericHook(
    hook_function=raise_containers_error,
    triggers=[HookEventType.POST_INIT, HookEventType.POST_UPDATE],
    hook_condition=not_valid_containers,
)


@dataclass
class InfraConfig(DataClassJsonMixin, DataclassHookMixin):
    """Stores metadata of infra config in a private computation instance

    Public attributes:
        instance_id: this is unique for each PrivateComputationInstance.
                        It is used to find and generate PCInstance in json repo.
        role: an Enum indicating if this PrivateComputationInstance is a publisher object or partner object
        status: an Enum indecating what stage and status the PCInstance is currently in
        status_update_ts: the time of last status update
        instances: during the whole computation run, all the instances created will be sotred here.
        game_type: an Enum indicating if this PrivateComputationInstance is for private lift or private attribution
        num_pid_containers: the number of containers used in pid
        num_mpc_containers: the number of containers used in mpc
        num_files_per_mpc_container: the number of files for each container
        tier: an string indicating the release binary tier to run (rc, canary, latest)
        retry_counter: the number times a stage has been retried
        creation_ts: the time of the creation of this PrivateComputationInstance
        end_ts: the time of the the end when finishing a computation run
        mpc_compute_concurrency: number of threads to run per container at the MPC compute metrics stage

    Private attributes:
        _stage_flow_cls_name: the name of a PrivateComputationBaseStageFlow subclass (cls.__name__)
    """

    instance_id: str
    role: PrivateComputationRole
    status: PrivateComputationInstanceStatus
    status_update_ts: int
    instances: List[UnionedPCInstance]
    game_type: PrivateComputationGameType
    num_pid_containers: int = field(
        metadata=DataclassHookMixin.get_metadata(num_pid_mpc_containers_hook)
    )
    num_mpc_containers: int = field(
        metadata=DataclassHookMixin.get_metadata(num_pid_mpc_containers_hook)
    )
    num_files_per_mpc_container: int

    tier: Optional[str] = None
    pcs_features: Set[PCSFeature] = field(default_factory=set)
    pce_config: Optional[PCEConfig] = None

    # stored as a string because the enum was refusing to serialize to json, no matter what I tried.
    # TODO(T103299005): [BE] Figure out how to serialize StageFlow objects to json instead of using their class name
    _stage_flow_cls_name: str = "PrivateComputationStageFlow"

    retry_counter: int = 0
    creation_ts: int = field(default_factory=lambda: int(time.time()))
    end_ts: int = 0
    mpc_compute_concurrency: int = 1
