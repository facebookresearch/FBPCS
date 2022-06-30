#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Dict, List, Optional, Union

from fbpcp.entity.container_instance import ContainerInstance
from fbpcs.common.entity.instance_base import InstanceBase
from fbpcs.common.entity.pcs_container_instance import PCSContainerInstance
from fbpcs.pid.entity.pid_stages import UnionPIDStage


class PIDRole(IntEnum):
    PUBLISHER = 0
    PARTNER = 1

    @classmethod
    def from_str(cls, s: str) -> "PIDRole":
        if s.upper() == "PUBLISHER":
            return cls.PUBLISHER
        elif s.upper() == "PARTNER":
            return cls.PARTNER
        else:
            raise ValueError(f"Unknown role: {s}")


class PIDStageStatus(Enum):
    UNKNOWN = "UNKNOWN"
    READY = "READY"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PIDProtocol(IntEnum):
    UNION_PID = 0
    PS3I_M_TO_M = 1
    UNION_PID_MULTIKEY = 2


class PIDInstanceStatus(Enum):
    UNKNOWN = "UNKNOWN"
    CREATED = "CREATED"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


@dataclass
class PIDInstance(InstanceBase):
    instance_id: str
    protocol: PIDProtocol
    pid_role: PIDRole
    num_shards: int
    input_path: str
    output_path: str
    data_path: Optional[str] = None
    spine_path: Optional[str] = None
    hmac_key: Optional[str] = None
    stages_containers: Dict[
        UnionPIDStage, List[Union[PCSContainerInstance, ContainerInstance]]
    ] = field(default_factory=dict)
    stages_status: Dict[UnionPIDStage, PIDStageStatus] = field(default_factory=dict)
    status: PIDInstanceStatus = PIDInstanceStatus.UNKNOWN
    current_stage: Optional[UnionPIDStage] = None
    server_ips: List[str] = field(default_factory=list)
    pid_use_row_numbers: bool = False

    def get_instance_id(self) -> str:
        return self.instance_id
