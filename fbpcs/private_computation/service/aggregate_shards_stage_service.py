#!/usr/bin/env python3
# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict


from typing import DefaultDict, List, Optional

from fbpcp.service.mpc import MPCService
from fbpcs.common.entity.pcs_mpc_instance import PCSMPCInstance
from fbpcs.onedocker_binary_config import OneDockerBinaryConfig
from fbpcs.onedocker_binary_names import OneDockerBinaryNames
from fbpcs.private_computation.entity.private_computation_instance import (
    PrivateComputationGameType,
)
from fbpcs.private_computation.entity.private_computation_instance import (
    PrivateComputationInstance,
)
from fbpcs.private_computation.repository.private_computation_game import GameNames
from fbpcs.private_computation.service.private_computation_stage_service import (
    PrivateComputationStageService,
)
from fbpcs.private_computation.service.utils import (
    create_and_start_mpc_instance,
    map_private_computation_role_to_mpc_party,
)


class AggregateShardsStageService(PrivateComputationStageService):
    """Handles business logic for the private computation aggregate metrics stage

    Private attributes:
        _onedocker_binary_config_map: Stores a mapping from mpc game to OneDockerBinaryConfig (binary version and tmp directory)
        _mpc_svc: creates and runs MPC instances
        _is_validating: TODO
        _log_cost_to_s3: TODO
        _container_timeout: optional duration in seconds before cloud containers timeout
    """

    def __init__(
        self,
        onedocker_binary_config_map: DefaultDict[str, OneDockerBinaryConfig],
        mpc_service: MPCService,
        is_validating: bool = False,
        log_cost_to_s3: bool = False,
        container_timeout: Optional[int] = None,
    ) -> None:
        self._onedocker_binary_config_map = onedocker_binary_config_map
        self._mpc_service = mpc_service
        self._is_validating = is_validating
        self._log_cost_to_s3 = log_cost_to_s3
        self._container_timeout = container_timeout

    # TODO T88759390: Make this function truly async. It is not because it calls blocking functions.
    # Make an async version of run_async() so that it can be called by Thrift
    async def run_async(
        self,
        pc_instance: PrivateComputationInstance,
        server_ips: Optional[List[str]] = None,
    ) -> PrivateComputationInstance:
        """Runs the private computation aggregate metrics stage

        Args:
            pc_instance: the private computation instance to run aggregate metrics with
            server_ips: only used by the partner role. These are the ip addresses of the publisher's containers.

        Returns:
            An updated version of pc_instance that stores an MPCInstance
        """

        num_shards = (
            pc_instance.num_mpc_containers * pc_instance.num_files_per_mpc_container
        )

        # TODO T101225989: map aggregation_type from the compute stage to metrics_format_type
        metrics_format_type = (
            "lift"
            if pc_instance.game_type is PrivateComputationGameType.LIFT
            else "ad_object"
        )

        binary_name = OneDockerBinaryNames.SHARD_AGGREGATOR.value
        binary_config = self._onedocker_binary_config_map[binary_name]

        if self._is_validating:
            # num_containers_real_data is the number of containers processing real data
            # synthetic data is processed by a dedicated extra container, and this container is always the last container,
            # hence synthetic_data_shard_start_index = num_real_data_shards
            # each of the containers, processing real or synthetic data, processes the same number of shards due to our resharding mechanism
            # num_shards representing the total number of shards which is equal to num_real_data_shards + num_synthetic_data_shards
            # hence, when num_containers_real_data and num_shards are given, num_synthetic_data_shards = num_shards / (num_containers_real_data + 1)
            num_containers_real_data = pc_instance.num_pid_containers
            if num_containers_real_data is None:
                raise ValueError("num_containers_real_data is None")
            num_synthetic_data_shards = num_shards // (num_containers_real_data + 1)
            num_real_data_shards = num_shards - num_synthetic_data_shards
            synthetic_data_shard_start_index = num_real_data_shards

            # Create and start MPC instance for real data shards and synthetic data shards
            game_args = [
                {
                    "input_base_path": pc_instance.compute_stage_output_base_path,
                    "num_shards": num_real_data_shards,
                    "metrics_format_type": metrics_format_type,
                    "output_path": pc_instance.shard_aggregate_stage_output_path,
                    "first_shard_index": 0,
                    "threshold": pc_instance.k_anonymity_threshold,
                    "run_name": pc_instance.instance_id if self._log_cost_to_s3 else "",
                },
                {
                    "input_base_path": pc_instance.compute_stage_output_base_path,
                    "num_shards": num_synthetic_data_shards,
                    "metrics_format_type": metrics_format_type,
                    "output_path": pc_instance.shard_aggregate_stage_output_path
                    + "_synthetic_data_shards",
                    "first_shard_index": synthetic_data_shard_start_index,
                    "threshold": pc_instance.k_anonymity_threshold,
                    "run_name": pc_instance.instance_id if self._log_cost_to_s3 else "",
                },
            ]

            mpc_instance = await create_and_start_mpc_instance(
                mpc_svc=self._mpc_service,
                instance_id=pc_instance.instance_id + "_aggregate_shards" + str(pc_instance.retry_counter),
                game_name=GameNames.SHARD_AGGREGATOR.value,
                mpc_party=map_private_computation_role_to_mpc_party(pc_instance.role),
                num_containers=2,
                binary_version=binary_config.binary_version,
                server_ips=server_ips,
                game_args=game_args,
                container_timeout=self._container_timeout,
            )
        else:
            # Create and start MPC instance
            game_args = [
                {
                    "input_base_path": pc_instance.compute_stage_output_base_path,
                    "metrics_format_type": metrics_format_type,
                    "num_shards": num_shards,
                    "output_path": pc_instance.shard_aggregate_stage_output_path,
                    "threshold": pc_instance.k_anonymity_threshold,
                    "run_name": pc_instance.instance_id if self._log_cost_to_s3 else "",
                },
            ]
            mpc_instance = await create_and_start_mpc_instance(
                mpc_svc=self._mpc_service,
                instance_id=pc_instance.instance_id + "_aggregate_shards" + str(pc_instance.retry_counter),
                game_name=GameNames.SHARD_AGGREGATOR.value,
                mpc_party=map_private_computation_role_to_mpc_party(pc_instance.role),
                num_containers=1,
                binary_version=binary_config.binary_version,
                server_ips=server_ips,
                game_args=game_args,
                container_timeout=self._container_timeout,
            )
        # Push MPC instance to PrivateComputationInstance.instances and update PL Instance status
        pc_instance.instances.append(PCSMPCInstance.from_mpc_instance(mpc_instance))
        return pc_instance

