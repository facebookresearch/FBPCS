# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Set, Type, TYPE_CHECKING, Union

from dataclasses_json import config, dataclass_json, DataClassJsonMixin

# this import statument can avoid circular import
if TYPE_CHECKING:

    from fbpcs.private_computation.stage_flows.private_computation_base_stage_flow import (
        PrivateComputationBaseStageFlow,
    )

import os

from fbpcs.common.entity.dataclasses_hooks import DataclassHookMixin, HookEventType
from fbpcs.common.entity.dataclasses_mutability import (
    DataclassMutabilityMixin,
    immutable_field,
    MutabilityMetadata,
)
from fbpcs.common.entity.frozen_field_hook import FrozenFieldHook
from fbpcs.common.entity.stage_state_instance import StageStateInstance
from fbpcs.common.entity.update_generic_hook import UpdateGenericHook
from fbpcs.post_processing_handler.post_processing_instance import (
    PostProcessingInstance,
)
from fbpcs.private_computation.entity.pce_config import PCEConfig
from fbpcs.private_computation.entity.pcs_feature import PCSFeature
from fbpcs.private_computation.entity.private_computation_status import (
    PrivateComputationInstanceStatus,
)
from marshmallow import fields
from marshmallow_enum import EnumField


class PrivateComputationRole(Enum):
    PUBLISHER = "PUBLISHER"
    PARTNER = "PARTNER"


class PrivateComputationGameType(Enum):
    LIFT = "LIFT"
    ATTRIBUTION = "ATTRIBUTION"
    PRIVATE_ID_DFCA = "PRIVATE_ID_DFCA"
    ANONYMIZER = "ANONYMIZER"


TLS_SUPPORTED_GAME_TYPES: Set[PrivateComputationGameType] = {
    PrivateComputationGameType.LIFT
}


UnionedPCInstance = Union[PostProcessingInstance, StageStateInstance]


@dataclass_json
@dataclass
class StatusUpdate:
    status: PrivateComputationInstanceStatus
    status_update_ts: int
    status_update_ts_delta: int = 0


# called in post_status_hook
# happens whenever status is updated
def post_update_status(obj: "InfraConfig") -> None:
    obj.status_update_ts = int(time.time())
    append_status_updates(obj)
    if obj.is_stage_flow_completed():
        obj.end_ts = int(time.time())


# called in post_status_hook
def append_status_updates(obj: "InfraConfig") -> None:
    ts_delta = 0
    if obj.status_updates:
        ts_delta = obj.status_update_ts - obj.status_updates[-1].status_update_ts

    update_entity = StatusUpdate(
        status=obj.status,
        status_update_ts=obj.status_update_ts,
        status_update_ts_delta=ts_delta,
    )
    obj.status_updates.append(update_entity)


# create update_generic_hook for status
post_status_hook: UpdateGenericHook["InfraConfig"] = UpdateGenericHook(
    triggers=[HookEventType.POST_UPDATE],
    update_function=post_update_status,
)


# create FrozenFieldHook: set end_ts immutable after initialized
set_end_ts_immutable_hook: FrozenFieldHook = FrozenFieldHook(
    other_field="end_ts",
    freeze_when=lambda obj: obj.end_ts != 0,
)


@dataclass
class InfraConfig(DataClassJsonMixin, DataclassMutabilityMixin):
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
        fbpcs_bundle_id: an string indicating the fbpcs bundle id to run.
        tier: an string indicating the release binary tier to run (rc, canary, latest)
        retry_counter: the number times a stage has been retried
        creation_ts: the time of the creation of this PrivateComputationInstance
        end_ts: the time of the the end when finishing a computation run
        mpc_compute_concurrency: number of threads to run per container at the MPC compute metrics stage
        run_id: field that can be used to identify all the logs for a run.
        num_secure_random_shards: total number of shards in secure random sharding stage, which is also the total number of files in following lift-udp stages
        num_udp_containers: the number of containers used in udp
        num_lift_containers: the number of containers used in lift with udp
    Private attributes:
        _stage_flow_cls_name: the name of a PrivateComputationBaseStageFlow subclass (cls.__name__)
    """

    instance_id: str = immutable_field()
    role: PrivateComputationRole = immutable_field()
    status: PrivateComputationInstanceStatus = field(
        metadata=DataclassHookMixin.get_metadata(post_status_hook)
    )
    status_update_ts: int
    instances: List[UnionedPCInstance]
    game_type: PrivateComputationGameType = immutable_field()

    num_pid_containers: int
    num_mpc_containers: int
    num_files_per_mpc_container: int

    # status_updates will be update in status hook
    status_updates: List[StatusUpdate]

    fbpcs_bundle_id: Optional[str] = immutable_field(init=False)
    tier: Optional[str] = immutable_field(default=None)
    pcs_features: Set[PCSFeature] = field(
        default_factory=set,
        metadata={
            # this makes type warning away when serialize this field
            **config(mm_field=fields.List(EnumField(enum=PCSFeature, by_value=True))),
            **MutabilityMetadata.IMMUTABLE.value,
        },
    )
    pce_config: Optional[PCEConfig] = None
    run_id: Optional[str] = immutable_field(default=None)
    log_cost_bucket: Optional[str] = immutable_field(default=None)

    # stored as a string because the enum was refusing to serialize to json, no matter what I tried.
    # TODO(T103299005): [BE] Figure out how to serialize StageFlow objects to json instead of using their class name
    _stage_flow_cls_name: str = immutable_field(default="PrivateComputationStageFlow")

    retry_counter: int = 0
    creation_ts: int = immutable_field(default_factory=lambda: int(time.time()))

    end_ts: int = field(
        default=0, metadata=DataclassHookMixin.get_metadata(set_end_ts_immutable_hook)
    )

    # TODO: concurrency should be immutable eventually
    mpc_compute_concurrency: int = 1

    server_certificate: Optional[str] = immutable_field(default=None)
    ca_certificate: Optional[str] = immutable_field(default=None)
    server_key_ref: Optional[str] = immutable_field(default=None)
    server_domain: Optional[str] = immutable_field(default=None)
    container_permission_id: Optional[str] = immutable_field(default=None)

    num_secure_random_shards: int = 1
    num_udp_containers: int = 1
    num_lift_containers: int = 1

    @property
    def stage_flow(self) -> Type["PrivateComputationBaseStageFlow"]:
        # this inner-function import allow us to call PrivateComputationBaseStageFlow.cls_name_to_cls
        # TODO: [BE] create a safe way to avoid inner-function import
        from fbpcs.private_computation.stage_flows.private_computation_base_stage_flow import (
            PrivateComputationBaseStageFlow,
        )

        return PrivateComputationBaseStageFlow.cls_name_to_cls(
            self._stage_flow_cls_name
        )

    @property
    def is_tls_enabled(self) -> bool:
        """Returns true if the TLS feature is enabled; otherwise, false."""
        return (
            PCSFeature.PCF_TLS in self.pcs_features
            and self.game_type in TLS_SUPPORTED_GAME_TYPES
        )

    def is_stage_flow_completed(self) -> bool:
        return self.status is self.stage_flow.get_last_stage().completed_status

    def __post_init__(self):
        # ensure mutability before override __post_init__
        super().__post_init__()
        # note: The reason can't make it fbpcs_bundle_id = immutable_field(default=os.getenv(FBPCS_BUNDLE_ID)),
        # is because that will happend in static varible when module been loaded, moved it to __post_init__ for better init control
        # TODO: T135712075 Use constant from fbpcs.private_computation.service.constants, fix circular import
        self.fbpcs_bundle_id = os.getenv("FBPCS_BUNDLE_ID")
