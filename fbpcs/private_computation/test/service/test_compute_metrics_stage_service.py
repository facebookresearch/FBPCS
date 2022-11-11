#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

from collections import defaultdict
from typing import Set
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from fbpcs.common.entity.pcs_mpc_instance import PCSMPCInstance
from fbpcs.infra.certificate.null_certificate_provider import NullCertificateProvider
from fbpcs.onedocker_binary_config import OneDockerBinaryConfig
from fbpcs.private_computation.entity.infra_config import (
    InfraConfig,
    PrivateComputationGameType,
)
from fbpcs.private_computation.entity.pcs_feature import PCSFeature
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
from fbpcs.private_computation.service.compute_metrics_stage_service import (
    ComputeMetricsStageService,
)
from fbpcs.private_computation.service.constants import NUM_NEW_SHARDS_PER_FILE

from fbpcs.private_computation.service.mpc.entity.mpc_instance import MPCParty
from fbpcs.private_computation.service.mpc.mpc import MPCService


class TestComputeMetricsStageService(IsolatedAsyncioTestCase):
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
        self.stage_svc = ComputeMetricsStageService(
            onedocker_binary_config_map, self.mock_mpc_svc
        )

    async def test_compute_metrics(self) -> None:
        for stage_service_name, pcs_feature_set in (
            (
                "compute_metrics",
                {PCSFeature.PCS_DUMMY},
            ),
            (
                "pcf2_lift",
                {PCSFeature.PRIVATE_LIFT_PCF2_RELEASE},
            ),
        ):
            with self.subTest(
                stage_service_name=stage_service_name, pcs_feature_set=pcs_feature_set
            ):
                private_computation_instance = self._create_pc_instance(pcs_feature_set)
                mpc_instance = PCSMPCInstance.create_instance(
                    instance_id=private_computation_instance.infra_config.instance_id
                    + "_{stage_service_name}0",
                    game_name=GameNames.LIFT.value,
                    mpc_party=MPCParty.CLIENT,
                    num_workers=private_computation_instance.infra_config.num_mpc_containers,
                )

                self.mock_mpc_svc.start_instance_async = AsyncMock(
                    return_value=mpc_instance
                )

                test_server_ips = [
                    f"192.0.2.{i}"
                    for i in range(
                        private_computation_instance.infra_config.num_mpc_containers
                    )
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
        pcs_feature = {PCSFeature.PCS_DUMMY}
        private_computation_instance = self._create_pc_instance(pcs_feature)
        test_game_args = [
            {
                "input_base_path": private_computation_instance.data_processing_output_path,
                "output_base_path": private_computation_instance.compute_stage_output_base_path,
                "file_start_index": 0,
                "num_files": private_computation_instance.infra_config.num_files_per_mpc_container,
                "concurrency": private_computation_instance.infra_config.mpc_compute_concurrency,
                "run_id": self.run_id,
                "pc_feature_flags": PCSFeature.PCS_DUMMY.value,
            },
            {
                "input_base_path": private_computation_instance.data_processing_output_path,
                "output_base_path": private_computation_instance.compute_stage_output_base_path,
                "file_start_index": private_computation_instance.infra_config.num_files_per_mpc_container,
                "num_files": private_computation_instance.infra_config.num_files_per_mpc_container,
                "concurrency": private_computation_instance.infra_config.mpc_compute_concurrency,
                "run_id": self.run_id,
                "pc_feature_flags": PCSFeature.PCS_DUMMY.value,
            },
        ]

        self.assertEqual(
            test_game_args,
            self.stage_svc._get_compute_metrics_game_args(private_computation_instance),
        )

    def _create_pc_instance(
        self, pcs_features: Set[PCSFeature]
    ) -> PrivateComputationInstance:
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
            pcs_features=pcs_features,
            run_id=self.run_id,
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
