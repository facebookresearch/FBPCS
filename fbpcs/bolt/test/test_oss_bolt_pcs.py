#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.


import unittest
from collections import defaultdict
from unittest import mock
from unittest.mock import patch

from fbpcp.entity.container_instance import ContainerInstance, ContainerInstanceStatus

from fbpcp.service.mpc import MPCService

from fbpcp.service.onedocker import OneDockerService
from fbpcs.bolt.bolt_client import BoltState

from fbpcs.bolt.oss_bolt_pcs import BoltPCSClient, BoltPCSCreateInstanceArgs
from fbpcs.common.entity.stage_state_instance import (
    StageStateInstance,
    StageStateInstanceStatus,
)
from fbpcs.onedocker_binary_config import OneDockerBinaryConfig
from fbpcs.onedocker_service_config import OneDockerServiceConfig
from fbpcs.private_computation.entity.infra_config import (
    InfraConfig,
    PrivateComputationGameType,
    PrivateComputationRole,
)
from fbpcs.private_computation.entity.pc_validator_config import PCValidatorConfig
from fbpcs.private_computation.entity.private_computation_instance import (
    PrivateComputationInstance,
)

from fbpcs.private_computation.entity.private_computation_status import (
    PrivateComputationInstanceStatus,
)
from fbpcs.private_computation.entity.product_config import (
    AggregationType,
    AttributionConfig,
    AttributionRule,
    CommonProductConfig,
    LiftConfig,
    ProductConfig,
)
from fbpcs.private_computation.service.errors import (
    PrivateComputationServiceValidationError,
)
from fbpcs.private_computation.service.private_computation import (
    NUM_NEW_SHARDS_PER_FILE,
    PrivateComputationService,
)
from fbpcs.private_computation.stage_flows.private_computation_stage_flow import (
    PrivateComputationStageFlow,
)


class TestBoltPCSClient(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        container_svc_patcher = patch("fbpcp.service.container_aws.AWSContainerService")
        storage_svc_patcher = patch("fbpcp.service.storage_s3.S3StorageService")
        mpc_instance_repo_patcher = patch(
            "fbpcs.common.repository.mpc_instance_local.LocalMPCInstanceRepository"
        )
        private_computation_instance_repo_patcher = patch(
            "fbpcs.private_computation.repository.private_computation_instance_local.LocalPrivateComputationInstanceRepository"
        )
        mpc_game_svc_patcher = patch("fbpcp.service.mpc_game.MPCGameService")
        container_svc = container_svc_patcher.start()
        storage_svc = storage_svc_patcher.start()
        mpc_instance_repository = mpc_instance_repo_patcher.start()
        private_computation_instance_repository = (
            private_computation_instance_repo_patcher.start()
        )
        mpc_game_svc = mpc_game_svc_patcher.start()

        for patcher in (
            container_svc_patcher,
            storage_svc_patcher,
            mpc_instance_repo_patcher,
            private_computation_instance_repo_patcher,
            mpc_game_svc_patcher,
        ):
            self.addCleanup(patcher.stop)

        self.onedocker_service_config = OneDockerServiceConfig(
            task_definition="test_task_definition",
        )

        self.onedocker_binary_config_map = defaultdict(
            lambda: OneDockerBinaryConfig(
                tmp_directory="/test_tmp_directory/",
                binary_version="latest",
                repository_path="test_path/",
            )
        )

        self.onedocker_service = OneDockerService(
            container_svc, self.onedocker_service_config.task_definition
        )

        self.mpc_service = MPCService(
            container_svc=container_svc,
            instance_repository=mpc_instance_repository,
            task_definition="test_task_definition",
            mpc_game_svc=mpc_game_svc,
        )

        self.pc_validator_config = PCValidatorConfig(
            region="us-west-2",
        )

        self.private_computation_service = PrivateComputationService(
            instance_repository=private_computation_instance_repository,
            storage_svc=storage_svc,
            mpc_svc=self.mpc_service,
            onedocker_svc=self.onedocker_service,
            onedocker_binary_config_map=self.onedocker_binary_config_map,
            pc_validator_config=self.pc_validator_config,
        )

        self.bolt_pcs_client = BoltPCSClient(self.private_computation_service)

        self.test_instance_id = "test_id"
        self.test_role = PrivateComputationRole.PUBLISHER
        self.test_game_type = PrivateComputationGameType.LIFT
        self.test_input_path = "in_path"
        self.test_output_path = "out_path"
        self.test_num_containers = 2
        self.test_concurrency = 1
        self.test_hmac_key = "CoXbp7BOEvAN9L1CB2DAORHHr3hB7wE7tpxMYm07tc0="

    async def test_create_instance(self) -> None:
        bolt_instance_args = BoltPCSCreateInstanceArgs(
            instance_id=self.test_instance_id,
            role=self.test_role,
            game_type=self.test_game_type,
            input_path=self.test_input_path,
            output_dir=self.test_output_path,
            num_pid_containers=self.test_num_containers,
            num_mpc_containers=self.test_num_containers,
            concurrency=self.test_concurrency,
            num_files_per_mpc_container=NUM_NEW_SHARDS_PER_FILE,
            hmac_key=self.test_hmac_key,
        )
        return_id = await self.bolt_pcs_client.create_instance(bolt_instance_args)
        self.assertEqual(return_id, self.test_instance_id)

    @mock.patch(
        "fbpcs.private_computation.service.private_computation.PrivateComputationService.update_instance"
    )
    async def test_update_instance(self, mock_update) -> None:
        # mock pc update_instance to return a pc instance with specific test status and instances
        stage_state_instance = StageStateInstance(
            instance_id="stage_state_instance",
            stage_name="test_stage",
            status=StageStateInstanceStatus.COMPLETED,
            containers=[
                ContainerInstance(
                    instance_id="test_container_instance",
                    ip_address="10.0.10.242",
                    status=ContainerInstanceStatus.COMPLETED,
                )
            ],
        )
        infra_config: InfraConfig = InfraConfig(
            instance_id=self.test_instance_id,
            role=self.test_role,
            status=PrivateComputationInstanceStatus.CREATED,
            status_update_ts=0,
            instances=[stage_state_instance],
            game_type=self.test_game_type,
            num_pid_containers=self.test_num_containers,
            num_mpc_containers=self.test_num_containers,
            num_files_per_mpc_container=NUM_NEW_SHARDS_PER_FILE,
            status_updates=[],
        )
        common: CommonProductConfig = CommonProductConfig(
            input_path=self.test_input_path,
            output_dir=self.test_output_path,
        )
        product_config: ProductConfig
        if self.test_game_type is PrivateComputationGameType.ATTRIBUTION:
            product_config = AttributionConfig(
                common=common,
                attribution_rule=AttributionRule.LAST_CLICK_1D,
                aggregation_type=AggregationType.MEASUREMENT,
            )
        elif self.test_game_type is PrivateComputationGameType.LIFT:
            product_config = LiftConfig(common=common)
        test_instance = PrivateComputationInstance(
            infra_config=infra_config,
            product_config=product_config,
        )
        mock_update.return_value = test_instance
        return_state = await self.bolt_pcs_client.update_instance(
            instance_id=self.test_instance_id,
        )
        self.assertEqual(
            return_state.pc_instance_status, PrivateComputationInstanceStatus.CREATED
        )

        self.assertEqual(["10.0.10.242"], return_state.server_ips)

    @mock.patch(
        "fbpcs.private_computation.service.private_computation.PrivateComputationService.validate_metrics"
    )
    async def test_validate_results(self, mock_validate) -> None:
        # Confirm that validate_results returns False when an exception is raised
        mock_validate.side_effect = PrivateComputationServiceValidationError()
        result = await self.bolt_pcs_client.validate_results(
            self.test_instance_id, expected_result_path="test/path"
        )
        self.assertFalse(result)

        # Confirm that validate_results returns True when private_computation.validate_metrics runs successfully
        mock_validate.side_effect = None
        mock_validate.return_value = None
        result = await self.bolt_pcs_client.validate_results(
            self.test_instance_id, expected_result_path="test/path"
        )
        self.assertTrue(result)

    async def test_get_valid_stage(self) -> None:
        stage = PrivateComputationStageFlow.ID_MATCH
        for status, expected_stage in [
            # pyre-fixme: Undefined attribute [16]: Optional type has no attribute `completed_status`.
            (stage.previous_stage.completed_status, stage),
            (stage.started_status, stage),
            (stage.completed_status, stage.next_stage),
            (stage.failed_status, stage),
            (PrivateComputationStageFlow.get_last_stage().completed_status, None),
        ]:
            with self.subTest(status=status, expected_stage=expected_stage):
                self.bolt_pcs_client.update_instance = mock.AsyncMock(
                    return_value=BoltState(status)
                )
                valid_stage = await self.bolt_pcs_client.get_valid_stage(
                    "test_id", PrivateComputationStageFlow
                )
                self.assertEqual(valid_stage, expected_stage)

    @mock.patch("fbpcs.bolt.bolt_job.BoltCreateInstanceArgs")
    @mock.patch("fbpcs.bolt.bolt_client.BoltState")
    async def test_is_existing_instance(self, mock_state, mock_instance_args) -> None:
        self.bolt_pcs_client.update_instance = mock.AsyncMock(
            side_effect=[mock_state, Exception()]
        )
        for expected_result in (True, False):
            with self.subTest(expected_result=expected_result):
                actual_result = await self.bolt_pcs_client.is_existing_instance(
                    instance_args=mock_instance_args
                )
                self.assertEqual(actual_result, expected_result)
