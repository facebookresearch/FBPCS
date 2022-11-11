#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

from collections import defaultdict
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from fbpcs.common.entity.pcs_mpc_instance import PCSMPCInstance
from fbpcs.infra.certificate.null_certificate_provider import NullCertificateProvider
from fbpcs.onedocker_binary_config import OneDockerBinaryConfig
from fbpcs.private_computation.entity.infra_config import (
    InfraConfig,
    PrivateComputationGameType,
)
from fbpcs.private_computation.entity.private_computation_instance import (
    PrivateComputationInstance,
    PrivateComputationInstanceStatus,
    PrivateComputationRole,
)
from fbpcs.private_computation.entity.product_config import (
    CommonProductConfig,
    LiftConfig,
    ProductConfig,
)
from fbpcs.private_computation.repository.private_computation_game import GameNames
from fbpcs.private_computation.service.constants import NUM_NEW_SHARDS_PER_FILE

from fbpcs.private_computation.service.mpc.entity.mpc_instance import MPCParty
from fbpcs.private_computation.service.mpc.mpc import MPCService

from fbpcs.private_computation.service.pcf2_lift_stage_service import (
    PCF2LiftStageService,
)


class TestPCF2LiftStageService(IsolatedAsyncioTestCase):
    @patch("fbpcs.private_computation.service.mpc.mpc.MPCService")
    def setUp(self, mock_mpc_svc: MPCService) -> None:
        self.mock_mpc_svc = mock_mpc_svc
        self.mock_mpc_svc.create_instance = MagicMock()
        self.run_id = "681ba82c-16d9-11ed-861d-0242ac120002"

        onedocker_binary_config_map = defaultdict(
            lambda: OneDockerBinaryConfig(
                tmp_directory="/test_tmp_directory/",
                binary_version="latest",
                repository_path="test_path/",
            )
        )
        self.stage_svc = PCF2LiftStageService(
            onedocker_binary_config_map,
            self.mock_mpc_svc,
        )

    async def test_compute_metrics(self) -> None:
        private_computation_instance = self._create_pc_instance()
        mpc_instance = PCSMPCInstance.create_instance(
            instance_id=private_computation_instance.infra_config.instance_id
            + "_pcf2_lift0",
            game_name=GameNames.PCF2_LIFT.value,
            mpc_party=MPCParty.CLIENT,
            num_workers=private_computation_instance.infra_config.num_mpc_containers,
        )

        self.mock_mpc_svc.start_instance_async = AsyncMock(return_value=mpc_instance)

        test_server_ips = [
            f"192.0.2.{i}"
            for i in range(private_computation_instance.infra_config.num_mpc_containers)
        ]
        await self.stage_svc.run_async(
            private_computation_instance,
            NullCertificateProvider(),
            NullCertificateProvider(),
            "",
            "",
            test_server_ips,
        )

        self.assertEqual(
            mpc_instance, private_computation_instance.infra_config.instances[0]
        )

    def test_get_game_args(self) -> None:
        # TODO: add game args test for attribution args
        private_computation_instance = self._create_pc_instance()
        run_name = (
            private_computation_instance.infra_config.instance_id
            + "_"
            + GameNames.PCF2_LIFT.value
            if self.stage_svc._log_cost_to_s3
            else ""
        )
        common_game_args = {
            "input_base_path": private_computation_instance.data_processing_output_path,
            "output_base_path": private_computation_instance.pcf2_lift_stage_output_base_path,
            "num_files": private_computation_instance.infra_config.num_files_per_mpc_container,
            "concurrency": private_computation_instance.infra_config.mpc_compute_concurrency,
            "num_conversions_per_user": private_computation_instance.product_config.common.padding_size,
            "run_name": run_name,
            "log_cost": True,
            "run_id": self.run_id,
            "use_tls": False,
            "ca_cert_path": "",
            "server_cert_path": "",
            "private_key_path": "",
            "log_cost_s3_bucket": private_computation_instance.infra_config.log_cost_bucket,
        }
        test_game_args = [
            {
                **common_game_args,
                "file_start_index": 0,
            },
            {
                **common_game_args,
                "file_start_index": private_computation_instance.infra_config.num_files_per_mpc_container,
            },
        ]

        self.assertEqual(
            test_game_args,
            self.stage_svc._get_compute_metrics_game_args(
                private_computation_instance,
                "",
                "",
            ),
        )

    def _create_pc_instance(self) -> PrivateComputationInstance:
        infra_config: InfraConfig = InfraConfig(
            instance_id="test_instance_123",
            role=PrivateComputationRole.PARTNER,
            status=PrivateComputationInstanceStatus.ID_MATCHING_COMPLETED,
            status_update_ts=1600000000,
            instances=[],
            game_type=PrivateComputationGameType.LIFT,
            num_pid_containers=2,
            num_mpc_containers=2,
            num_files_per_mpc_container=NUM_NEW_SHARDS_PER_FILE,
            status_updates=[],
            run_id=self.run_id,
            log_cost_bucket="test_log_cost_bucket",
        )
        common: CommonProductConfig = CommonProductConfig(
            input_path="456",
            output_dir="789",
        )
        product_config: ProductConfig = LiftConfig(
            common=common,
        )
        return PrivateComputationInstance(
            infra_config=infra_config,
            product_config=product_config,
        )
