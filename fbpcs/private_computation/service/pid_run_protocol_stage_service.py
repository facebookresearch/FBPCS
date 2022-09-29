#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.


import logging
from typing import DefaultDict, List, Optional

from fbpcp.entity.container_instance import ContainerInstance
from fbpcp.service.onedocker import OneDockerService
from fbpcp.service.storage import StorageService
from fbpcs.common.entity.stage_state_instance import StageStateInstance
from fbpcs.data_processing.service.pid_run_protocol_binary_service import (
    PIDRunProtocolBinaryService,
)
from fbpcs.onedocker_binary_config import (
    ONEDOCKER_REPOSITORY_PATH,
    OneDockerBinaryConfig,
)

from fbpcs.private_computation.entity.private_computation_instance import (
    PrivateComputationInstance,
    PrivateComputationInstanceStatus,
    PrivateComputationRole,
)
from fbpcs.private_computation.service.constants import DEFAULT_SERVER_PORT_NUMBER
from fbpcs.private_computation.service.pid_utils import (
    get_metrics_filepath,
    get_sharded_filepath,
)
from fbpcs.private_computation.service.private_computation_stage_service import (
    PrivateComputationStageService,
)
from fbpcs.private_computation.service.utils import (
    get_pc_status_from_stage_state,
    stop_stage_service,
)


class PIDRunProtocolStageService(PrivateComputationStageService):
    """Handles business logic for the PID run protocol stage

    Private attributes:
        _storage_svc: used to read/write files during private computation runs
        _onedocker_svc: used to spin up containers that run binaries in the cloud
        _onedocker_binary_config: stores OneDocker information
    """

    def __init__(
        self,
        storage_svc: StorageService,
        onedocker_svc: OneDockerService,
        onedocker_binary_config_map: DefaultDict[str, OneDockerBinaryConfig],
    ) -> None:
        self._storage_svc = storage_svc
        self._onedocker_svc = onedocker_svc
        self._onedocker_binary_config_map = onedocker_binary_config_map
        self._logger: logging.Logger = logging.getLogger(__name__)

    async def run_async(
        self,
        pc_instance: PrivateComputationInstance,
        server_ips: Optional[List[str]] = None,
    ) -> PrivateComputationInstance:
        """Runs the PID run protocol stage

        Args:
            pc_instance: the private computation instance to start pid run protocol stage service
            server_ips: only used by partner to get server hostnames
        Returns:
            An updated version of pc_instance
        """
        self._logger.info(f"[{self}] Starting PIDRunProtocolStageService")
        container_instances = await self.start_pid_run_protocol_service(
            pc_instance=pc_instance,
            server_ips=server_ips,
        )
        self._logger.info("PIDRunProtocolStageService finished")
        stage_state = StageStateInstance(
            pc_instance.infra_config.instance_id,
            pc_instance.current_stage.name,
            containers=container_instances,
        )
        pc_instance.infra_config.instances.append(stage_state)
        return pc_instance

    def get_status(
        self,
        pc_instance: PrivateComputationInstance,
    ) -> PrivateComputationInstanceStatus:
        """Gets the latest PrivateComputationInstance status.

        Arguments:
            pc_instance: The private computation instance that is being updated

        Returns:
            The latest status for private computation instance
        """
        return get_pc_status_from_stage_state(pc_instance, self._onedocker_svc)

    async def start_pid_run_protocol_service(
        self,
        pc_instance: PrivateComputationInstance,
        server_ips: Optional[List[str]],
        port: int = DEFAULT_SERVER_PORT_NUMBER,
    ) -> List[ContainerInstance]:
        """start pid run protocol service and spine up the container instances"""
        pid_run_protocol_binary_service = PIDRunProtocolBinaryService()
        logging.info("Instantiated PID run protocol stage")
        num_shards = pc_instance.infra_config.num_pid_containers
        # input_path is the output_path from PIDPrepareStage
        input_path = pc_instance.pid_stage_output_prepare_path
        output_path = pc_instance.pid_stage_output_spine_path
        pc_role = pc_instance.infra_config.role
        pid_protocol = pc_instance.product_config.common.pid_protocol
        metric_paths = self.get_metric_paths(pc_role, output_path, num_shards)
        server_hostnames = self.get_server_hostnames(pc_role, server_ips, num_shards)
        use_row_numbers = pc_instance.product_config.common.pid_use_row_numbers
        if use_row_numbers:
            logging.info("use-row-numbers is enabled for Private ID")
        # generate the list of command args for publisher or partner
        args_list = []
        for shard in range(num_shards):
            args_per_shard = pid_run_protocol_binary_service.build_args(
                input_path=get_sharded_filepath(input_path, shard),
                output_path=get_sharded_filepath(output_path, shard),
                port=port,
                metric_path=metric_paths[shard] if metric_paths else None,
                use_row_numbers=use_row_numbers,
                server_hostname=server_hostnames[shard] if server_hostnames else None,
                run_id=pc_instance.infra_config.run_id,
            )
            args_list.append(args_per_shard)
        # start containers
        logging.info(f"{pc_role} spinning up containers")
        binary_name = pid_run_protocol_binary_service.get_binary_name(
            pid_protocol, pc_role
        )
        onedocker_binary_config = self._onedocker_binary_config_map[binary_name]
        env_vars = {
            "RUST_LOG": "info",
        }
        if onedocker_binary_config.repository_path:
            env_vars[
                ONEDOCKER_REPOSITORY_PATH
            ] = onedocker_binary_config.repository_path

        should_wait_spin_up: bool = (
            pc_instance.infra_config.role is PrivateComputationRole.PARTNER
        )
        return await pid_run_protocol_binary_service.start_containers(
            cmd_args_list=args_list,
            onedocker_svc=self._onedocker_svc,
            binary_version=onedocker_binary_config.binary_version,
            binary_name=binary_name,
            env_vars=env_vars,
            wait_for_containers_to_start_up=should_wait_spin_up,
            existing_containers=pc_instance.get_existing_containers_for_retry(),
        )

    @classmethod
    def get_metric_paths(
        cls, pc_role: PrivateComputationRole, output_path: str, num_shards: int
    ) -> Optional[List[str]]:
        # only publisher needs metric_paths
        if pc_role is PrivateComputationRole.PARTNER:
            return None
        return [get_metrics_filepath(output_path, shard) for shard in range(num_shards)]

    @classmethod
    def get_server_hostnames(
        cls,
        pc_role: PrivateComputationRole,
        server_ips: Optional[List[str]],
        num_shards: int,
    ) -> Optional[List[str]]:
        # only partner needs server_hostnames
        if pc_role is PrivateComputationRole.PUBLISHER:
            return None
        if not server_ips:
            raise ValueError("Partner missing server_ips")
        if len(server_ips) != num_shards:
            raise ValueError(
                f"Supplied {len(server_ips)} server_hostnames, but num_shards == {num_shards} (these should agree)"
            )
        return [f"http://{ip}" for ip in server_ips]

    def stop_service(
        self,
        pc_instance: PrivateComputationInstance,
    ) -> None:
        stop_stage_service(pc_instance, self._onedocker_svc)
