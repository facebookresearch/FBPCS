#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

from dataclasses import dataclass

from typing import Dict, Optional

from fbpcs.data_processing.service.id_spine_combiner import IdSpineCombinerService
from fbpcs.onedocker_binary_names import OneDockerBinaryNames
from fbpcs.private_computation.entity.infra_config import PrivateComputationGameType
from fbpcs.private_computation.repository.private_computation_game import (
    PRIVATE_COMPUTATION_GAME_CONFIG,
)
from fbpcs.private_computation.service.run_binary_base_service import (
    RunBinaryBaseService,
)


""" This is to get a mapping from onedocker_package_name to game name
{
    "private_attribution/compute":"attribution_compute",
    "private_lift/lift":"lift",
    ...
}
"""
BINARY_NAME_TO_GAME_NAME: Dict[str, str] = {
    v["onedocker_package_name"]: k for k, v in PRIVATE_COMPUTATION_GAME_CONFIG.items()
}


@dataclass
class StageData:
    binary_name: str
    game_name: Optional[str] = None
    service: Optional[RunBinaryBaseService] = None


@dataclass
class PrivateComputationServiceData:
    """
    This class groups data necessary to run each stage for all supported stages
    by the service. The service needs to provide the type of game (lift, attribution, etc.)
    because each game_type requires different data to run.

    Currently, this get function is directly used by PrivateComputationService.
    We plan to implement a PrivateComputationStageService which abstracts the
    business logic of each stage so that PrivateComputationService is not bloated with it.
    PrivateComputationStageService will be calling this function in the future to
    get data from each stage.
    """

    combiner_stage: StageData
    compute_stage: StageData

    LIFT_COMBINER_STAGE_DATA: StageData = StageData(
        binary_name=OneDockerBinaryNames.LIFT_ID_SPINE_COMBINER.value,
        game_name=None,
        service=IdSpineCombinerService(),
    )

    LIFT_COMPUTE_STAGE_DATA: StageData = StageData(
        binary_name=OneDockerBinaryNames.LIFT_COMPUTE.value,
        game_name=BINARY_NAME_TO_GAME_NAME[OneDockerBinaryNames.LIFT_COMPUTE.value],
        service=None,
    )

    ATTRIBUTION_COMBINER_STAGE_DATA: StageData = StageData(
        binary_name=OneDockerBinaryNames.ATTRIBUTION_ID_SPINE_COMBINER.value,
        game_name=None,
        service=IdSpineCombinerService(),
    )

    DECOUPLED_ATTRIBUTION_STAGE_DATA: StageData = StageData(
        binary_name=OneDockerBinaryNames.DECOUPLED_ATTRIBUTION.value,
        game_name=BINARY_NAME_TO_GAME_NAME[
            OneDockerBinaryNames.DECOUPLED_ATTRIBUTION.value
        ],
        service=None,
    )

    DECOUPLED_AGGREGATION_STAGE_DATA: StageData = StageData(
        binary_name=OneDockerBinaryNames.DECOUPLED_AGGREGATION.value,
        game_name=BINARY_NAME_TO_GAME_NAME[
            OneDockerBinaryNames.DECOUPLED_AGGREGATION.value
        ],
        service=None,
    )

    PCF2_ATTRIBUTION_STAGE_DATA: StageData = StageData(
        binary_name=OneDockerBinaryNames.PCF2_ATTRIBUTION.value,
        game_name=BINARY_NAME_TO_GAME_NAME[OneDockerBinaryNames.PCF2_ATTRIBUTION.value],
        service=None,
    )

    PCF2_AGGREGATION_STAGE_DATA: StageData = StageData(
        binary_name=OneDockerBinaryNames.PCF2_AGGREGATION.value,
        game_name=BINARY_NAME_TO_GAME_NAME[OneDockerBinaryNames.PCF2_AGGREGATION.value],
        service=None,
    )

    PCF2_LIFT_STAGE_DATA: StageData = StageData(
        binary_name=OneDockerBinaryNames.PCF2_LIFT.value,
        game_name=BINARY_NAME_TO_GAME_NAME[OneDockerBinaryNames.PCF2_LIFT.value],
        service=None,
    )

    PCF2_LIFT_METADATA_COMPACTION_DATA: StageData = StageData(
        binary_name=OneDockerBinaryNames.PCF2_LIFT_METADATA_COMPACTION.value,
        game_name=BINARY_NAME_TO_GAME_NAME[
            OneDockerBinaryNames.PCF2_LIFT_METADATA_COMPACTION.value
        ],
        service=None,
    )

    PCF2_SHARD_COMBINE_STAGE_DATA: StageData = StageData(
        binary_name=OneDockerBinaryNames.PCF2_SHARD_COMBINER.value,
        game_name=BINARY_NAME_TO_GAME_NAME[
            OneDockerBinaryNames.PCF2_SHARD_COMBINER.value
        ],
        service=None,
    )

    PRIVATE_ID_DFCA_COMBINER_STAGE_DATA: StageData = StageData(
        binary_name=OneDockerBinaryNames.PRIVATE_ID_DFCA_SPINE_COMBINER.value,
        game_name=None,
        service=IdSpineCombinerService(),
    )

    @classmethod
    def get(
        cls, game_type: PrivateComputationGameType
    ) -> "PrivateComputationServiceData":
        if game_type is PrivateComputationGameType.LIFT:
            return cls(
                combiner_stage=PrivateComputationServiceData.LIFT_COMBINER_STAGE_DATA,
                compute_stage=PrivateComputationServiceData.LIFT_COMPUTE_STAGE_DATA,
            )
        elif game_type is PrivateComputationGameType.ATTRIBUTION:
            return cls(
                combiner_stage=PrivateComputationServiceData.ATTRIBUTION_COMBINER_STAGE_DATA,
                compute_stage=PrivateComputationServiceData.DECOUPLED_ATTRIBUTION_STAGE_DATA,
            )
        elif game_type is PrivateComputationGameType.PRIVATE_ID_DFCA:
            return cls(
                combiner_stage=PrivateComputationServiceData.PRIVATE_ID_DFCA_COMBINER_STAGE_DATA,
                compute_stage=StageData(""),
            )
        else:
            raise ValueError("Unknown game type")
