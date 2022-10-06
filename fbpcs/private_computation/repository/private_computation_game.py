#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict


from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, TypedDict

from fbpcp.entity.mpc_game_config import MPCGameArgument, MPCGameConfig
from fbpcp.repository.mpc_game_repository import MPCGameRepository
from fbpcs.onedocker_binary_names import OneDockerBinaryNames


class GameNames(Enum):
    LIFT = "lift"
    PCF2_LIFT = "pcf2_lift"
    PCF2_LIFT_METADATA_COMPACTION = "pcf2_lift_metadata_compaction"
    SHARD_AGGREGATOR = "shard_aggregator"
    PCF2_SHARD_COMBINER = "pcf2_shard_combiner"
    DECOUPLED_ATTRIBUTION = "decoupled_attribution"
    DECOUPLED_AGGREGATION = "decoupled_aggregation"
    PCF2_ATTRIBUTION = "pcf2_attribution"
    PCF2_AGGREGATION = "pcf2_aggregation"


@dataclass
class OneDockerArgument:
    name: str
    required: bool


class GameNamesValue(TypedDict):
    onedocker_package_name: str
    arguments: List[OneDockerArgument]


PRIVATE_COMPUTATION_GAME_CONFIG: Dict[str, GameNamesValue] = {
    GameNames.LIFT.value: {
        "onedocker_package_name": OneDockerBinaryNames.LIFT_COMPUTE.value,
        "arguments": [
            OneDockerArgument(name="input_base_path", required=True),
            OneDockerArgument(name="output_base_path", required=True),
            OneDockerArgument(name="file_start_index", required=False),
            OneDockerArgument(name="num_files", required=True),
            OneDockerArgument(name="concurrency", required=True),
            OneDockerArgument(name="run_id", required=False),
            OneDockerArgument(name="pc_feature_flags", required=False),
        ],
    },
    GameNames.PCF2_LIFT.value: {
        "onedocker_package_name": OneDockerBinaryNames.PCF2_LIFT.value,
        "arguments": [
            OneDockerArgument(name="input_base_path", required=True),
            OneDockerArgument(name="output_base_path", required=True),
            OneDockerArgument(name="input_global_params_path", required=False),
            OneDockerArgument(name="file_start_index", required=False),
            OneDockerArgument(name="num_files", required=True),
            OneDockerArgument(name="concurrency", required=True),
            OneDockerArgument(name="epoch", required=False),
            OneDockerArgument(name="num_conversions_per_user", required=False),
            OneDockerArgument(name="compute_publisher_breakdowns", required=False),
            OneDockerArgument(name="log_cost", required=False),
            OneDockerArgument(name="log_cost_s3_bucket", required=False),
            OneDockerArgument(name="log_cost_s3_region", required=False),
            OneDockerArgument(name="run_name", required=False),
            OneDockerArgument(name="run_id", required=False),
            OneDockerArgument(name="pc_feature_flags", required=False),
            OneDockerArgument(name="use_tls", required=False),
            OneDockerArgument(name="ca_cert_path", required=False),
            OneDockerArgument(name="server_cert_path", required=False),
            OneDockerArgument(name="private_key_path", required=False),
        ],
    },
    GameNames.PCF2_LIFT_METADATA_COMPACTION.value: {
        "onedocker_package_name": OneDockerBinaryNames.PCF2_LIFT_METADATA_COMPACTION.value,
        "arguments": [
            OneDockerArgument(name="input_path", required=True),
            OneDockerArgument(name="output_global_params_path", required=True),
            OneDockerArgument(name="output_secret_shares_path", required=True),
            OneDockerArgument(name="epoch", required=False),
            OneDockerArgument(name="num_conversions_per_user", required=False),
            OneDockerArgument(name="compute_publisher_breakdowns", required=False),
            OneDockerArgument(name="run_name", required=False),
            OneDockerArgument(name="log_cost", required=False),
            OneDockerArgument(name="log_cost_s3_bucket", required=False),
            OneDockerArgument(name="log_cost_s3_region", required=False),
            OneDockerArgument(name="pc_feature_flags", required=False),
            OneDockerArgument(name="use_tls", required=False),
            OneDockerArgument(name="ca_cert_path", required=False),
            OneDockerArgument(name="server_cert_path", required=False),
            OneDockerArgument(name="private_key_path", required=False),
        ],
    },
    GameNames.SHARD_AGGREGATOR.value: {
        "onedocker_package_name": OneDockerBinaryNames.SHARD_AGGREGATOR.value,
        "arguments": [
            OneDockerArgument(name="input_base_path", required=True),
            OneDockerArgument(name="num_shards", required=True),
            OneDockerArgument(name="output_path", required=True),
            OneDockerArgument(name="metrics_format_type", required=True),
            OneDockerArgument(name="threshold", required=True),
            OneDockerArgument(name="first_shard_index", required=False),
            OneDockerArgument(name="log_cost", required=False),
            OneDockerArgument(name="log_cost_s3_bucket", required=False),
            OneDockerArgument(name="log_cost_s3_region", required=False),
            OneDockerArgument(name="run_name", required=False),
            OneDockerArgument(name="visibility", required=False),
            OneDockerArgument(name="run_id", required=False),
            OneDockerArgument(name="pc_feature_flags", required=False),
        ],
    },
    GameNames.PCF2_SHARD_COMBINER.value: {
        "onedocker_package_name": OneDockerBinaryNames.PCF2_SHARD_COMBINER.value,
        "arguments": [
            OneDockerArgument(name="input_base_path", required=True),
            OneDockerArgument(name="num_shards", required=True),
            OneDockerArgument(name="output_path", required=True),
            OneDockerArgument(name="metrics_format_type", required=True),
            OneDockerArgument(name="threshold", required=True),
            OneDockerArgument(name="first_shard_index", required=False),
            OneDockerArgument(name="log_cost", required=False),
            OneDockerArgument(name="log_cost_s3_bucket", required=False),
            OneDockerArgument(name="log_cost_s3_region", required=False),
            OneDockerArgument(name="run_name", required=False),
            OneDockerArgument(name="visibility", required=False),
            OneDockerArgument(name="use_tls", required=False),
            OneDockerArgument(name="ca_cert_path", required=False),
            OneDockerArgument(name="server_cert_path", required=False),
            OneDockerArgument(name="private_key_path", required=False),
        ],
    },
    GameNames.DECOUPLED_ATTRIBUTION.value: {
        "onedocker_package_name": OneDockerBinaryNames.DECOUPLED_ATTRIBUTION.value,
        "arguments": [
            OneDockerArgument(name="input_base_path", required=True),
            OneDockerArgument(name="output_base_path", required=True),
            OneDockerArgument(name="attribution_rules", required=True),
            OneDockerArgument(name="aggregators", required=False),
            OneDockerArgument(name="concurrency", required=True),
            OneDockerArgument(name="num_files", required=True),
            OneDockerArgument(name="file_start_index", required=True),
            OneDockerArgument(name="use_xor_encryption", required=True),
            OneDockerArgument(name="use_postfix", required=True),
            OneDockerArgument(name="log_cost", required=False),
            OneDockerArgument(name="run_name", required=False),
        ],
    },
    GameNames.DECOUPLED_AGGREGATION.value: {
        "onedocker_package_name": OneDockerBinaryNames.DECOUPLED_AGGREGATION.value,
        "arguments": [
            OneDockerArgument(name="aggregators", required=True),
            OneDockerArgument(name="input_base_path", required=True),
            OneDockerArgument(name="input_base_path_secret_share", required=True),
            OneDockerArgument(name="output_base_path", required=True),
            OneDockerArgument(name="attribution_rules", required=False),
            OneDockerArgument(name="concurrency", required=True),
            OneDockerArgument(name="num_files", required=True),
            OneDockerArgument(name="file_start_index", required=True),
            OneDockerArgument(name="use_xor_encryption", required=True),
            OneDockerArgument(name="use_postfix", required=True),
            OneDockerArgument(name="log_cost", required=False),
            OneDockerArgument(name="run_name", required=False),
        ],
    },
    GameNames.PCF2_ATTRIBUTION.value: {
        "onedocker_package_name": OneDockerBinaryNames.PCF2_ATTRIBUTION.value,
        "arguments": [
            OneDockerArgument(name="input_base_path", required=True),
            OneDockerArgument(name="output_base_path", required=True),
            OneDockerArgument(name="attribution_rules", required=True),
            OneDockerArgument(name="aggregators", required=False),
            OneDockerArgument(name="concurrency", required=True),
            OneDockerArgument(name="num_files", required=True),
            OneDockerArgument(name="file_start_index", required=True),
            OneDockerArgument(name="use_xor_encryption", required=True),
            OneDockerArgument(name="use_postfix", required=True),
            OneDockerArgument(name="log_cost", required=False),
            OneDockerArgument(name="log_cost_s3_bucket", required=False),
            OneDockerArgument(name="log_cost_s3_region", required=False),
            OneDockerArgument(name="run_name", required=False),
            OneDockerArgument(name="use_new_output_format", required=False),
            OneDockerArgument(name="run_id", required=False),
            OneDockerArgument(name="pc_feature_flags", required=False),
            OneDockerArgument(name="use_tls", required=False),
            OneDockerArgument(name="ca_cert_path", required=False),
            OneDockerArgument(name="server_cert_path", required=False),
            OneDockerArgument(name="private_key_path", required=False),
        ],
    },
    GameNames.PCF2_AGGREGATION.value: {
        "onedocker_package_name": OneDockerBinaryNames.PCF2_AGGREGATION.value,
        "arguments": [
            OneDockerArgument(name="aggregators", required=True),
            OneDockerArgument(name="input_base_path", required=True),
            OneDockerArgument(name="input_base_path_secret_share", required=True),
            OneDockerArgument(name="output_base_path", required=True),
            OneDockerArgument(name="attribution_rules", required=False),
            OneDockerArgument(name="concurrency", required=True),
            OneDockerArgument(name="num_files", required=True),
            OneDockerArgument(name="file_start_index", required=True),
            OneDockerArgument(name="use_xor_encryption", required=True),
            OneDockerArgument(name="use_postfix", required=True),
            OneDockerArgument(name="log_cost", required=False),
            OneDockerArgument(name="log_cost_s3_bucket", required=False),
            OneDockerArgument(name="log_cost_s3_region", required=False),
            OneDockerArgument(name="run_name", required=False),
            OneDockerArgument(name="use_new_output_format", required=False),
            OneDockerArgument(name="run_id", required=False),
            OneDockerArgument(name="pc_feature_flags", required=False),
            OneDockerArgument(name="use_tls", required=False),
            OneDockerArgument(name="ca_cert_path", required=False),
            OneDockerArgument(name="server_cert_path", required=False),
            OneDockerArgument(name="private_key_path", required=False),
        ],
    },
}


class PrivateComputationGameRepository(MPCGameRepository):
    def __init__(self) -> None:
        self.private_computation_game_config: Dict[
            str, GameNamesValue
        ] = PRIVATE_COMPUTATION_GAME_CONFIG

    def get_game(self, name: str) -> MPCGameConfig:
        if name not in self.private_computation_game_config:
            raise ValueError(f"Game {name} is not supported.")

        game_config = self.private_computation_game_config[name]
        arguments: List[MPCGameArgument] = [
            MPCGameArgument(name=argument.name, required=argument.required)
            for argument in game_config["arguments"]
        ]

        return MPCGameConfig(
            game_name=name,
            onedocker_package_name=game_config["onedocker_package_name"],
            arguments=arguments,
        )
