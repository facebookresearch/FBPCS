#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock, patch

from fbpcs.common.entity.stage_state_instance import StageStateInstance
from fbpcs.infra.certificate.null_certificate_provider import NullCertificateProvider
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
from fbpcs.private_computation.service.constants import NUM_NEW_SHARDS_PER_FILE
from fbpcs.private_computation.service.pid_mr_stage_service import (
    PID_RUN_CONFIGS,
    PID_WORKFLOW_CONFIGS,
    PIDMR,
    PIDMRStageService,
)
from fbpcs.private_computation.stage_flows.private_computation_mr_stage_flow import (
    PrivateComputationMRStageFlow,
)
from fbpcs.service.workflow import WorkflowStatus
from fbpcs.service.workflow_sfn import SfnWorkflowService


class TestPIDMRStageService(IsolatedAsyncioTestCase):
    @patch("fbpcp.service.onedocker.OneDockerService")
    def setUp(self, onedocker_service) -> None:
        self.test_num_containers = 2

    @patch("fbpcs.private_computation.service.pid_mr_stage_service.PIDMRStageService")
    async def test_run_async(self, pid_mr_svc_mock) -> None:
        for test_run_id in (None, "2621fda2-0eca-11ed-861d-0242ac120002"):
            with self.subTest(test_run_id=test_run_id):
                flow = PrivateComputationMRStageFlow
                infra_config: InfraConfig = InfraConfig(
                    instance_id="publisher_123",
                    role=PrivateComputationRole.PUBLISHER,
                    status=PrivateComputationInstanceStatus.PID_MR_STARTED,
                    status_update_ts=1600000000,
                    instances=[],
                    game_type=PrivateComputationGameType.LIFT,
                    num_pid_containers=1,
                    num_mpc_containers=1,
                    num_files_per_mpc_container=1,
                    status_updates=[],
                    _stage_flow_cls_name=flow.get_cls_name(),
                    run_id=test_run_id,
                )
                common: CommonProductConfig = CommonProductConfig(
                    input_path="https://mpc-aem-exp-platform-input.s3.us-west-2.amazonaws.com/pid_test_data/stress_test/input.csv",
                    output_dir="https://mpc-aem-exp-platform-input.s3.us-west-2.amazonaws.com/pid_test/output",
                    pid_configs={
                        PIDMR: {
                            PID_WORKFLOW_CONFIGS: {
                                "stateMachineArn": "arn:aws:states:us-west-2:119557546360:stateMachine:pid-mr-e2e-adv-sfn"
                            },
                            PID_RUN_CONFIGS: {
                                "pidMrMultikeyJarPath": "s3://one-docker-repository-prod/pid/private-id-mr/latest/pid-mr-multikey.jar"
                            },
                        }
                    },
                )
                product_config: ProductConfig = LiftConfig(
                    common=common,
                )

                pc_instance = PrivateComputationInstance(
                    infra_config=infra_config,
                    product_config=product_config,
                )

                service = SfnWorkflowService(
                    "us-west-2",
                    "access_key",
                    "access_data",
                    session_token="session_token",
                )
                service.start_workflow = MagicMock(return_value="execution_arn")
                service.get_workflow_status = MagicMock(
                    return_value=WorkflowStatus.COMPLETED
                )
                stage_svc = PIDMRStageService(
                    service,
                )
                await stage_svc.run_async(
                    pc_instance, NullCertificateProvider(), NullCertificateProvider()
                )

                self.assertEqual(
                    stage_svc.get_status(pc_instance),
                    PrivateComputationInstanceStatus.PID_MR_COMPLETED,
                )
                self.assertEqual(
                    pc_instance.pid_mr_stage_output_spine_path,
                    "https://mpc-aem-exp-platform-input.s3.us-west-2.amazonaws.com/pid_test/output/publisher_123_out_dir/pid_mr/matched_output/out.csv_publisher_mr_pid_matched",
                )
                self.assertEqual(
                    pc_instance.infra_config.instances[0].instance_id, "execution_arn"
                )
                self.assertIsInstance(
                    pc_instance.infra_config.instances[0], StageStateInstance
                )

    def create_sample_instance(self) -> PrivateComputationInstance:
        infra_config: InfraConfig = InfraConfig(
            instance_id="test_instance_123",
            role=PrivateComputationRole.PARTNER,
            status=PrivateComputationInstanceStatus.ID_MATCHING_COMPLETED,
            status_update_ts=1600000000,
            instances=[],
            game_type=PrivateComputationGameType.LIFT,
            num_pid_containers=self.test_num_containers,
            num_mpc_containers=self.test_num_containers,
            num_files_per_mpc_container=NUM_NEW_SHARDS_PER_FILE,
            status_updates=[],
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

    def test_mr_pid_output(self) -> None:
        pc_instance = self.create_sample_instance()
        expected_str = "789/test_instance_123_out_dir/pid_mr/matched_output/out.csv_advertiser_mr_pid_matched"
        self.assertEqual(
            pc_instance.pid_mr_stage_output_spine_path,
            expected_str,
        )
