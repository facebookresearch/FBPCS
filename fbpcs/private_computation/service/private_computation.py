#!/usr/bin/env python3
# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

import asyncio
import json
import logging
import math
from datetime import datetime, timezone
from typing import DefaultDict, Dict, List, Optional, Any, TypeVar

from fbpcp.entity.mpc_instance import MPCInstance, MPCInstanceStatus
from fbpcp.service.mpc import MPCService
from fbpcp.service.onedocker import OneDockerService
from fbpcp.service.storage import StorageService
from fbpcp.util.typing import checked_cast
from fbpcs.common.entity.pcs_mpc_instance import PCSMPCInstance
from fbpcs.data_processing.attribution_id_combiner.attribution_id_spine_combiner_cpp import (
    CppAttributionIdSpineCombinerService,
)
from fbpcs.data_processing.lift_id_combiner.lift_id_spine_combiner_cpp import (
    CppLiftIdSpineCombinerService,
)
from fbpcs.data_processing.sharding.sharding import ShardType
from fbpcs.data_processing.sharding.sharding_cpp import CppShardingService
from fbpcs.onedocker_binary_config import OneDockerBinaryConfig
from fbpcs.onedocker_binary_names import OneDockerBinaryNames
from fbpcs.pid.entity.pid_instance import PIDInstance, PIDInstanceStatus
from fbpcs.pid.service.pid_service.pid import PIDService
from fbpcs.pid.service.pid_service.pid_stage import PIDStage
from fbpcs.post_processing_handler.post_processing_handler import PostProcessingHandler
from fbpcs.post_processing_handler.post_processing_instance import (
    PostProcessingInstance,
    PostProcessingInstanceStatus,
)
from fbpcs.private_computation.entity.breakdown_key import BreakdownKey
from fbpcs.private_computation.entity.pce_config import PCEConfig
from fbpcs.private_computation.entity.private_computation_base_stage_flow import (
    PrivateComputationBaseStageFlow,
)
from fbpcs.private_computation.entity.private_computation_instance import (
    AggregationType,
    AttributionRule,
    PrivateComputationGameType,
    PrivateComputationInstance,
    PrivateComputationInstanceStatus,
    PrivateComputationRole,
    UnionedPCInstance,
    UnionedPCInstanceStatus,
)
from fbpcs.private_computation.entity.private_computation_stage_flow import (
    PrivateComputationStageFlow,
)
from fbpcs.private_computation.repository.private_computation_game import GameNames
from fbpcs.private_computation.repository.private_computation_instance import (
    PrivateComputationInstanceRepository,
)
from fbpcs.private_computation.service.aggregate_shards_stage_service import (
    AggregateShardsStageService,
)
from fbpcs.private_computation.service.compute_metrics_stage_service import (
    ComputeMetricsStageService,
)
from fbpcs.private_computation.service.constants import (
    NUM_NEW_SHARDS_PER_FILE,
    STAGE_STARTED_STATUSES,
    STAGE_FAILED_STATUSES,
    DEFAULT_K_ANONYMITY_THRESHOLD,
    DEFAULT_PADDING_SIZE,
    DEFAULT_PID_PROTOCOL,
)
from fbpcs.private_computation.service.errors import (
    PrivateComputationServiceValidationError,
)
from fbpcs.private_computation.service.id_match_stage_service import IdMatchStageService
from fbpcs.private_computation.service.post_processing_stage_service import (
    PostProcessingStageService,
)
from fbpcs.private_computation.service.private_computation_service_data import (
    PrivateComputationServiceData,
)
from fbpcs.private_computation.service.private_computation_stage_service import (
    PrivateComputationStageService,
)
from fbpcs.private_computation.service.utils import (
    ready_for_partial_container_retry,
)

T = TypeVar("T")


class PrivateComputationService:
    def __init__(
        self,
        instance_repository: PrivateComputationInstanceRepository,
        storage_svc: StorageService,
        mpc_svc: MPCService,
        pid_svc: PIDService,
        onedocker_svc: OneDockerService,
        onedocker_binary_config_map: DefaultDict[str, OneDockerBinaryConfig],
    ) -> None:
        """Constructor of PrivateComputationService
        instance_repository -- repository to CRUD PrivateComputationInstance
        """
        self.instance_repository = instance_repository
        self.storage_svc = storage_svc
        self.mpc_svc = mpc_svc
        self.pid_svc = pid_svc
        self.onedocker_svc = onedocker_svc
        self.onedocker_binary_config_map = onedocker_binary_config_map
        self.logger: logging.Logger = logging.getLogger(__name__)

    # TODO T88759390: make an async version of this function
    def create_instance(
        self,
        instance_id: str,
        role: PrivateComputationRole,
        game_type: PrivateComputationGameType,
        input_path: str,
        output_dir: str,
        num_pid_containers: int,
        num_mpc_containers: int,
        concurrency: int,
        attribution_rule: Optional[AttributionRule] = None,
        aggregation_type: Optional[AggregationType] = None,
        num_files_per_mpc_container: Optional[int] = None,
        is_validating: Optional[bool] = False,
        synthetic_shard_path: Optional[str] = None,
        breakdown_key: Optional[BreakdownKey] = None,
        pce_config: Optional[PCEConfig] = None,
        is_test: Optional[bool] = False,
        hmac_key: Optional[str] = None,
        padding_size: int = DEFAULT_PADDING_SIZE,
        k_anonymity_threshold: int = DEFAULT_K_ANONYMITY_THRESHOLD,
        fail_fast: bool = False,
    ) -> PrivateComputationInstance:
        self.logger.info(f"Creating instance: {instance_id}")

        instance = PrivateComputationInstance(
            instance_id=instance_id,
            role=role,
            instances=[],
            status=PrivateComputationInstanceStatus.CREATED,
            status_update_ts=PrivateComputationService.get_ts_now(),
            num_files_per_mpc_container=num_files_per_mpc_container
            or NUM_NEW_SHARDS_PER_FILE,
            game_type=game_type,
            is_validating=is_validating,
            synthetic_shard_path=synthetic_shard_path,
            num_pid_containers=num_pid_containers,
            num_mpc_containers=num_mpc_containers,
            attribution_rule=attribution_rule,
            aggregation_type=aggregation_type,
            input_path=input_path,
            output_dir=output_dir,
            breakdown_key=breakdown_key,
            pce_config=pce_config,
            is_test=is_test,
            hmac_key=hmac_key,
            padding_size=padding_size,
            concurrency=concurrency,
            k_anonymity_threshold=k_anonymity_threshold,
            fail_fast=fail_fast,
        )

        self.instance_repository.create(instance)
        return instance

    # TODO T88759390: make an async version of this function
    def get_instance(self, instance_id: str) -> PrivateComputationInstance:
        return self.instance_repository.read(instance_id=instance_id)

    # TODO T88759390: make an async version of this function
    def update_instance(self, instance_id: str) -> PrivateComputationInstance:
        private_computation_instance = self.instance_repository.read(instance_id)
        self.logger.info(f"Updating instance: {instance_id}")
        return self._update_instance(
            private_computation_instance=private_computation_instance
        )

    def _update_instance(
        self, private_computation_instance: PrivateComputationInstance
    ) -> PrivateComputationInstance:
        if private_computation_instance.instances:
            # Only need to update the last stage/instance
            last_instance = private_computation_instance.instances[-1]

            if isinstance(last_instance, PIDInstance):
                # PID service has to call update_instance to get the newest containers
                # information in case they are still running
                private_computation_instance.instances[
                    -1
                ] = self.pid_svc.update_instance(last_instance.instance_id)
            elif isinstance(last_instance, MPCInstance):
                # MPC service has to call update_instance to get the newest containers
                # information in case they are still running
                private_computation_instance.instances[
                    -1
                ] = PCSMPCInstance.from_mpc_instance(
                    self.mpc_svc.update_instance(last_instance.instance_id)
                )
            elif isinstance(last_instance, PostProcessingInstance):
                self.logger.info(
                    "PostProcessingInstance doesn't have its own instance repository and is already updated"
                )
            else:
                raise ValueError("Unknown type of instance")

            new_status = (
                self._get_status_from_stage(private_computation_instance.instances[-1])
                or private_computation_instance.status
            )
            private_computation_instance = self._update_status(
                private_computation_instance=private_computation_instance,
                new_status=new_status,
            )
            self.instance_repository.update(private_computation_instance)
            self.logger.info(
                f"Finished updating instance: {private_computation_instance.instance_id}"
            )

        return private_computation_instance

    def run_stage(
        self,
        instance_id: str,
        stage: PrivateComputationBaseStageFlow,
        stage_svc: PrivateComputationStageService,
        server_ips: Optional[List[str]] = None,
        dry_run: bool = False,
    ) -> PrivateComputationInstance:
        return asyncio.run(
            self.run_stage_async(
                instance_id, stage, stage_svc, server_ips, dry_run
            )
        )

    def _get_validated_instance(
        self,
        instance_id: str,
        stage: PrivateComputationBaseStageFlow,
        server_ips: Optional[List[str]] = None,
        dry_run: bool = False,
    ) -> PrivateComputationInstance:
        """
        Gets a private computation instance and checks that it's ready to run a given
        stage service
        """
        pc_instance = self.get_instance(instance_id)
        if (
            stage.is_joint_stage
            and pc_instance.role is PrivateComputationRole.PARTNER
            and not server_ips
        ):
            raise ValueError("Missing server_ips")

        # if the instance status is the complete status of the previous stage, then we can run the target stage
        # e.g. if status == ID_MATCH_COMPLETE, then we can run COMPUTE_METRICS
        if pc_instance.status is stage.previous_stage.completed_status:
            pc_instance.retry_counter = 0
        # if the instance status is the fail status of the target stage, then we can retry the target stage
        # e.g. if status == COMPUTE_METRICS_FAILED, then we can run COMPUTE_METRICS
        elif pc_instance.status is stage.failed_status:
            pc_instance.retry_counter += 1
        # if the instance status is a start status, it's running something already. Don't run another stage, even if dry_run=True
        elif stage.is_started_status(pc_instance.status):
            raise ValueError(
                f"Cannot start a new operation when instance {instance_id} has status {pc_instance.status}."
            )
        # if dry_run = True, then we can run the target stage. Otherwise, throw an error
        elif not dry_run:
            raise ValueError(
                f"Instance {instance_id} has status {pc_instance.status}. Not ready for {stage}."
            )

        return pc_instance

    # TODO T88759390: Make this function truly async. It is not because it calls blocking functions.
    # Make an async version of run_stage_async() so that it can be called by Thrift
    async def run_stage_async(
        self,
        instance_id: str,
        stage: PrivateComputationBaseStageFlow,
        stage_svc: PrivateComputationStageService,
        server_ips: Optional[List[str]] = None,
        dry_run: bool = False,
    ) -> PrivateComputationInstance:
        """
        Runs a stage for a given instance. If state of the instance is invalid (e.g. not ready to run a stage),
        an exception will be thrown.
        """

        pc_instance = self._get_validated_instance(
            instance_id, stage, server_ips, dry_run
        )

        self._update_status(
            private_computation_instance=pc_instance,
            new_status=stage.started_status,
        )
        self.logger.info(repr(stage))
        try:
            pc_instance = await stage_svc.run_async(pc_instance, server_ips)
        except Exception as e:
            self.logger.error(f"Caught exception when running {stage}")
            self._update_status(
                private_computation_instance=pc_instance,
                new_status=stage.failed_status,
            )
            raise e
        finally:
            pc_instance = self._update_instance(pc_instance)
        return pc_instance

    # PID stage
    def id_match(
        self,
        instance_id: str,
        pid_config: Dict[str, Any],
        is_validating: Optional[bool] = False,
        synthetic_shard_path: Optional[str] = None,
        server_ips: Optional[List[str]] = None,
        dry_run: Optional[bool] = False,
    ) -> PrivateComputationInstance:
        return asyncio.run(
            self.id_match_async(
                instance_id,
                pid_config,
                is_validating,
                synthetic_shard_path,
                server_ips,
                dry_run,
            )
        )

    # TODD T101783992: delete this function and call run_stage directly
    async def id_match_async(
        self,
        instance_id: str,
        pid_config: Dict[str, Any],
        is_validating: Optional[bool] = False,
        synthetic_shard_path: Optional[str] = None,
        server_ips: Optional[List[str]] = None,
        dry_run: Optional[bool] = False,
    ) -> PrivateComputationInstance:
        return await self.run_stage_async(
            instance_id,
            PrivateComputationStageFlow.ID_MATCH,
            IdMatchStageService(
                self.pid_svc,
                pid_config,
                DEFAULT_PID_PROTOCOL,
                is_validating or False,
                synthetic_shard_path,
            ),
            server_ips,
            dry_run or False,
        )

    def prepare_data(
        self,
        instance_id: str,
        is_validating: Optional[bool] = False,
        dry_run: Optional[bool] = None,
        log_cost_to_s3: bool = False,
    ) -> None:
        asyncio.run(
            self.prepare_data_async(
                instance_id=instance_id,
                is_validating=is_validating,
                dry_run=dry_run,
                log_cost_to_s3=log_cost_to_s3,
            )
        )

    # TODO T88759390: Make this function truly async. It is not because it calls blocking functions.
    async def prepare_data_async(
        self,
        instance_id: str,
        is_validating: Optional[bool] = False,
        dry_run: Optional[bool] = None,
        log_cost_to_s3: bool = False,
    ) -> None:
        # It's expected that the pl instance is in an updated status because:
        #   For publisher, a Chronos job is scheduled to update it every 60 seconds;
        #   for partner, PL-Coordinator should have updated it before calling this action.
        private_computation_instance = self.get_instance(instance_id)

        # Validate status of the instance
        if not dry_run and (
            private_computation_instance.status
            not in [
                PrivateComputationInstanceStatus.ID_MATCHING_COMPLETED,
                PrivateComputationInstanceStatus.COMPUTATION_FAILED,
            ]
        ):
            raise ValueError(
                f"Instance {instance_id} has status {private_computation_instance.status}. Not ready for data prep stage."
            )

        # If this request is made to recover from a previous mpc compute failure,
        #   then we skip the actual tasks running on containers. It's still necessary
        #   to run this function just because the caller needs the returned all_output_paths
        skip_tasks_on_container = (
            ready_for_partial_container_retry(private_computation_instance)
            and not dry_run
        )

        output_path = private_computation_instance.data_processing_output_path
        combine_output_path = output_path + "_combine"

        # execute combiner step
        if skip_tasks_on_container:
            self.logger.info(f"[{self}] Skipping id spine combiner service")
        else:
            self.logger.info(f"[{self}] Starting id spine combiner service")

            # TODO: we will write log_cost_to_s3 to the instance, so this function interface
            #   will get simplified
            await self._run_combiner_service(
                private_computation_instance, combine_output_path, log_cost_to_s3
            )

        self.logger.info("Finished running CombinerService, starting to reshard")

        # reshard each file into x shards
        #     note we need each file to be sharded into the same # of files
        #     because we want to keep the data of each existing file to run
        #     on the same container
        if skip_tasks_on_container:
            self.logger.info(f"[{self}] Skipping sharding on container")
        else:
            await self._run_sharder_service(
                private_computation_instance, combine_output_path
            )

    # MPC step 1
    def compute_metrics(
        self,
        instance_id: str,
        is_validating: Optional[bool] = False,
        server_ips: Optional[List[str]] = None,
        dry_run: Optional[bool] = None,
        log_cost_to_s3: bool = False,
        container_timeout: Optional[int] = None,
    ) -> PrivateComputationInstance:
        return asyncio.run(
            self.compute_metrics_async(
                instance_id,
                is_validating,
                server_ips,
                dry_run,
                log_cost_to_s3,
                container_timeout,
            )
        )

    # TODO T88759390: Make this function truly async. It is not because it calls blocking functions.
    # Make an async version of compute_metrics() so that it can be called by Thrift
    async def compute_metrics_async(
        self,
        instance_id: str,
        is_validating: Optional[bool] = False,
        server_ips: Optional[List[str]] = None,
        dry_run: Optional[bool] = None,
        log_cost_to_s3: bool = False,
        container_timeout: Optional[int] = None,
    ) -> PrivateComputationInstance:
        return await self.run_stage_async(
            instance_id,
            PrivateComputationStageFlow.COMPUTE,
            ComputeMetricsStageService(
                self.onedocker_binary_config_map,
                self.mpc_svc,
                is_validating or False,
                log_cost_to_s3,
                container_timeout,
                dry_run or False,
            ),
            server_ips,
            dry_run or False,
        )

    # MPC step 2
    def aggregate_shards(
        self,
        instance_id: str,
        is_validating: Optional[bool] = False,
        server_ips: Optional[List[str]] = None,
        dry_run: Optional[bool] = False,
        log_cost_to_s3: bool = False,
        container_timeout: Optional[int] = None,
    ) -> PrivateComputationInstance:
        return asyncio.run(
            self.aggregate_shards_async(
                instance_id,
                is_validating,
                server_ips,
                dry_run,
                log_cost_to_s3,
                container_timeout,
            )
        )

    # TODO T88759390: Make this function truly async. It is not because it calls blocking functions.
    # Make an async version of aggregate_shards() so that it can be called by Thrift
    async def aggregate_shards_async(
        self,
        instance_id: str,
        is_validating: Optional[bool] = False,
        server_ips: Optional[List[str]] = None,
        dry_run: Optional[bool] = False,
        log_cost_to_s3: bool = False,
        container_timeout: Optional[int] = None,
    ) -> PrivateComputationInstance:
        return await self.run_stage_async(
            instance_id,
            PrivateComputationStageFlow.AGGREGATE,
            AggregateShardsStageService(
                self.onedocker_binary_config_map,
                self.mpc_svc,
                is_validating or False,
                log_cost_to_s3,
                container_timeout,
            ),
            server_ips,
            dry_run or False,
        )

    # TODO T88759390: make an async version of this function
    # Optioinal stage, validate the correctness of aggregated results for injected synthetic data
    def validate_metrics(
        self,
        instance_id: str,
        expected_result_path: str,
        aggregated_result_path: Optional[str] = None,
    ) -> None:
        private_computation_instance = self.get_instance(instance_id)
        expected_results_dict = json.loads(self.storage_svc.read(expected_result_path))
        aggregated_results_dict = json.loads(
            self.storage_svc.read(
                aggregated_result_path
                or private_computation_instance.shard_aggregate_stage_output_path
            )
        )
        if expected_results_dict == aggregated_results_dict:
            self.logger.info(
                f"Aggregated results for instance {instance_id} on synthetic data is as expected."
            )
        else:
            raise PrivateComputationServiceValidationError(
                f"Aggregated results for instance {instance_id} on synthetic data is NOT as expected."
            )

    def run_post_processing_handlers(
        self,
        instance_id: str,
        post_processing_handlers: Dict[str, PostProcessingHandler],
        aggregated_result_path: Optional[str] = None,
        dry_run: Optional[bool] = False,
    ) -> PrivateComputationInstance:
        return asyncio.run(
            self.run_post_processing_handlers_async(
                instance_id,
                post_processing_handlers,
                aggregated_result_path,
                dry_run,
            )
        )

    # Make an async version of run_post_processing_handlers so that
    # it can be called by Thrift
    async def run_post_processing_handlers_async(
        self,
        instance_id: str,
        post_processing_handlers: Dict[str, PostProcessingHandler],
        aggregated_result_path: Optional[str] = None,
        dry_run: Optional[bool] = False,
    ) -> PrivateComputationInstance:
        return await self.run_stage_async(
            instance_id,
            PrivateComputationStageFlow.POST_PROCESSING_HANDLERS,
            PostProcessingStageService(
                self.storage_svc, post_processing_handlers, aggregated_result_path
            ),
            dry_run=dry_run or False,
        )

    def cancel_current_stage(
        self,
        instance_id: str,
    ) -> PrivateComputationInstance:
        private_computation_instance = self.get_instance(instance_id)

        # pre-checks to make sure it's in a cancel-able state
        if private_computation_instance.status not in STAGE_STARTED_STATUSES:
            raise ValueError(
                f"Instance {instance_id} has status {private_computation_instance.status}. Nothing to cancel."
            )

        if not private_computation_instance.instances:
            raise ValueError(
                f"Instance {instance_id} is in invalid state because no stages are registered under."
            )

        # cancel the running stage
        last_instance = private_computation_instance.instances[-1]
        if isinstance(last_instance, MPCInstance):
            self.mpc_svc.stop_instance(instance_id=last_instance.instance_id)
        else:
            self.logger.warning(
                f"Canceling the current stage of instance {instance_id} is not supported yet."
            )
            return private_computation_instance

        # post-checks to make sure the pl instance has the updated status
        private_computation_instance = self._update_instance(
            private_computation_instance=private_computation_instance
        )
        if private_computation_instance.status not in STAGE_FAILED_STATUSES:
            raise ValueError(
                f"Failed to cancel the current stage unexptectedly. Instance {instance_id} has status {private_computation_instance.status}"
            )

        self.logger.info(
            f"The current stage of instance {instance_id} has been canceled."
        )
        return private_computation_instance

    """
    Get Private Lift instance status from the given instance that represents a stage.
    Return None when no status returned from the mapper, indicating that we do not want
    the current status of the given stage to decide the status of Private Lift instance.
    """

    def _get_status_from_stage(
        self, instance: UnionedPCInstance
    ) -> Optional[PrivateComputationInstanceStatus]:
        MPC_GAME_TO_STAGE_MAPPER: Dict[str, str] = {
            GameNames.LIFT.value: "computation",
            GameNames.ATTRIBUTION_COMPUTE.value: "computation",
            GameNames.SHARD_AGGREGATOR.value: "aggregation",
        }

        STAGE_TO_STATUS_MAPPER: Dict[
            str,
            Dict[UnionedPCInstanceStatus, PrivateComputationInstanceStatus],
        ] = {
            "computation": {
                MPCInstanceStatus.STARTED: PrivateComputationInstanceStatus.COMPUTATION_STARTED,
                MPCInstanceStatus.COMPLETED: PrivateComputationInstanceStatus.COMPUTATION_COMPLETED,
                MPCInstanceStatus.FAILED: PrivateComputationInstanceStatus.COMPUTATION_FAILED,
                MPCInstanceStatus.CANCELED: PrivateComputationInstanceStatus.COMPUTATION_FAILED,
            },
            "aggregation": {
                MPCInstanceStatus.STARTED: PrivateComputationInstanceStatus.AGGREGATION_STARTED,
                MPCInstanceStatus.COMPLETED: PrivateComputationInstanceStatus.AGGREGATION_COMPLETED,
                MPCInstanceStatus.FAILED: PrivateComputationInstanceStatus.AGGREGATION_FAILED,
                MPCInstanceStatus.CANCELED: PrivateComputationInstanceStatus.AGGREGATION_FAILED,
            },
            "PID": {
                PIDInstanceStatus.STARTED: PrivateComputationInstanceStatus.ID_MATCHING_STARTED,
                PIDInstanceStatus.COMPLETED: PrivateComputationInstanceStatus.ID_MATCHING_COMPLETED,
                PIDInstanceStatus.FAILED: PrivateComputationInstanceStatus.ID_MATCHING_FAILED,
            },
            "post_processing": {
                PostProcessingInstanceStatus.STARTED: PrivateComputationInstanceStatus.POST_PROCESSING_HANDLERS_STARTED,
                PostProcessingInstanceStatus.COMPLETED: PrivateComputationInstanceStatus.POST_PROCESSING_HANDLERS_COMPLETED,
                PostProcessingInstanceStatus.FAILED: PrivateComputationInstanceStatus.POST_PROCESSING_HANDLERS_FAILED,
            },
        }

        stage: str
        if isinstance(instance, MPCInstance):
            stage = MPC_GAME_TO_STAGE_MAPPER[instance.game_name]
        elif isinstance(instance, PIDInstance):
            stage = "PID"
        elif isinstance(instance, PostProcessingInstance):
            stage = "post_processing"
        else:
            raise ValueError(f"Unknown stage in instance: {instance}")

        status = STAGE_TO_STATUS_MAPPER[stage].get(instance.status)

        return status

    @staticmethod
    def get_ts_now() -> int:
        return int(datetime.now(tz=timezone.utc).timestamp())

    def _update_status(
        self,
        private_computation_instance: PrivateComputationInstance,
        new_status: PrivateComputationInstanceStatus,
    ) -> PrivateComputationInstance:
        old_status = private_computation_instance.status
        private_computation_instance.status = new_status
        if old_status != new_status:
            private_computation_instance.status_update_ts = (
                PrivateComputationService.get_ts_now()
            )
            self.logger.info(
                f"Updating status of {private_computation_instance.instance_id} from {old_status} to {private_computation_instance.status} at time {private_computation_instance.status_update_ts}"
            )
        return private_computation_instance

    def _get_param(
        self, param_name: str, instance_param: Optional[T], override_param: Optional[T]
    ) -> T:
        res = override_param
        if override_param is not None:
            if instance_param is not None and instance_param != override_param:
                self.logger.warning(
                    f"{param_name}={override_param} is given and will be used, "
                    f"but it is inconsistent with {instance_param} recorded in the PrivateComputationInstance"
                )
        else:
            res = instance_param
        if res is None:
            raise ValueError(f"Missing value for parameter {param_name}")

        return res

    async def _run_combiner_service(
        self,
        pl_instance: PrivateComputationInstance,
        combine_output_path: str,
        log_cost_to_s3: bool,
    ) -> None:
        stage_data = PrivateComputationServiceData.get(
            pl_instance.game_type
        ).combiner_stage

        binary_name = stage_data.binary_name
        binary_config = self.onedocker_binary_config_map[binary_name]

        common_combiner_args = {
            "spine_path": pl_instance.pid_stage_output_spine_path,
            "data_path": pl_instance.pid_stage_output_data_path,
            "output_path": combine_output_path,
            "num_shards": pl_instance.num_pid_containers + 1
            if pl_instance.is_validating
            else pl_instance.num_pid_containers,
            "onedocker_svc": self.onedocker_svc,
            "binary_version": binary_config.binary_version,
            "tmp_directory": binary_config.tmp_directory,
        }

        # TODO T100977304: the if-else will be removed after the two combiners are consolidated
        if pl_instance.game_type is PrivateComputationGameType.LIFT:
            combiner_service = checked_cast(
                CppLiftIdSpineCombinerService,
                stage_data.service,
            )
            await combiner_service.combine_on_container_async(
                # pyre-ignore [6] Incompatible parameter type
                **common_combiner_args
            )
        elif pl_instance.game_type is PrivateComputationGameType.ATTRIBUTION:
            combiner_service = checked_cast(
                CppAttributionIdSpineCombinerService,
                stage_data.service,
            )
            common_combiner_args["run_name"] = (
                pl_instance.instance_id if log_cost_to_s3 else ""
            )
            common_combiner_args["padding_size"] = checked_cast(
                int, pl_instance.padding_size
            )
            await combiner_service.combine_on_container_async(
                # pyre-ignore [6] Incompatible parameter type
                **common_combiner_args
            )

    async def _run_sharder_service(
        self, pl_instance: PrivateComputationInstance, combine_output_path: str
    ) -> None:
        sharder = CppShardingService()
        self.logger.info("Instantiated sharder")

        coros = []
        for shard_index in range(
            pl_instance.num_pid_containers + 1
            if pl_instance.is_validating
            else pl_instance.num_pid_containers
        ):
            path_to_shard = PIDStage.get_sharded_filepath(
                combine_output_path, shard_index
            )
            self.logger.info(f"Input path to sharder: {path_to_shard}")

            shards_per_file = math.ceil(
                (pl_instance.num_mpc_containers / pl_instance.num_pid_containers)
                * pl_instance.num_files_per_mpc_container
            )
            shard_index_offset = shard_index * shards_per_file
            self.logger.info(
                f"Output base path to sharder: {pl_instance.data_processing_output_path}, {shard_index_offset=}"
            )

            binary_config = self.onedocker_binary_config_map[
                OneDockerBinaryNames.SHARDER.value
            ]
            coro = sharder.shard_on_container_async(
                shard_type=ShardType.ROUND_ROBIN,
                filepath=path_to_shard,
                output_base_path=pl_instance.data_processing_output_path,
                file_start_index=shard_index_offset,
                num_output_files=shards_per_file,
                onedocker_svc=self.onedocker_svc,
                binary_version=binary_config.binary_version,
                tmp_directory=binary_config.tmp_directory,
            )
            coros.append(coro)

        # Wait for all coroutines to finish
        await asyncio.gather(*coros)
        self.logger.info("All sharding coroutines finished")
