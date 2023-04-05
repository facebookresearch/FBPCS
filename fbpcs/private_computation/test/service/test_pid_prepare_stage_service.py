#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import itertools
from typing import List, Optional
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from fbpcp.entity.container_instance import ContainerInstance, ContainerInstanceStatus
from fbpcs.common.entity.stage_state_instance import StageStateInstance
from fbpcs.infra.certificate.null_certificate_provider import NullCertificateProvider
from fbpcs.onedocker_binary_config import OneDockerBinaryConfig

from fbpcs.pid.entity.pid_instance import PIDProtocol
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
from fbpcs.private_computation.service.constants import (
    DEFAULT_MULTIKEY_PROTOCOL_MAX_COLUMN_COUNT,
)
from fbpcs.private_computation.service.pid_prepare_stage_service import (
    PIDPrepareStageService,
)
from fbpcs.private_computation.service.utils import generate_env_vars_dict


class TestPIDPrepareStageService(IsolatedAsyncioTestCase):
    @patch("fbpcp.service.storage.StorageService")
    @patch("fbpcp.service.onedocker.OneDockerService")
    def setUp(self, mock_onedocker_svc, mock_storage_svc) -> None:
        self.mock_onedocker_svc = mock_onedocker_svc
        self.mock_storage_svc = mock_storage_svc
        self.onedocker_binary_config = OneDockerBinaryConfig(
            tmp_directory="/tmp",
            binary_version="latest",
            repository_path="test_path/",
        )
        self.binary_name = "data_processing/pid_preparer"
        self.onedocker_binary_config_map = {
            self.binary_name: self.onedocker_binary_config
        }
        self.input_path = "in"
        self.output_path = "out"
        self.pc_instance_id = "test_instance_123"
        self.container_timeout = 86400

    async def test_pid_prepare_stage_service(self) -> None:
        async def _run_sub_test(
            pc_role: PrivateComputationRole,
            multikey_enabled: bool,
            test_num_containers: int,
            test_run_id: Optional[str] = None,
        ) -> None:
            pid_protocol = (
                PIDProtocol.UNION_PID_MULTIKEY
                if test_num_containers == 1 and multikey_enabled
                else PIDProtocol.UNION_PID
            )
            max_col_cnt_expect = (
                DEFAULT_MULTIKEY_PROTOCOL_MAX_COLUMN_COUNT
                if pid_protocol is PIDProtocol.UNION_PID_MULTIKEY
                else 1
            )
            id_filter_thresh_expect = -1
            pc_instance = self.create_sample_pc_instance(
                pc_role=pc_role,
                test_num_containers=test_num_containers,
                multikey_enabled=multikey_enabled,
                pid_max_column_count=max_col_cnt_expect,
                run_id=test_run_id,
            )
            stage_svc = PIDPrepareStageService(
                storage_svc=self.mock_storage_svc,
                onedocker_svc=self.mock_onedocker_svc,
                onedocker_binary_config_map=self.onedocker_binary_config_map,
            )
            containers = [
                self.create_container_instance(i) for i in range(test_num_containers)
            ]
            self.mock_onedocker_svc.start_containers = MagicMock(
                return_value=containers
            )
            self.mock_onedocker_svc.wait_for_pending_containers = AsyncMock(
                return_value=containers
            )
            updated_pc_instance = await stage_svc.run_async(
                pc_instance=pc_instance,
                server_certificate_provider=NullCertificateProvider(),
                ca_certificate_provider=NullCertificateProvider(),
                server_certificate_path="",
                ca_certificate_path="",
            )
            env_vars = generate_env_vars_dict(
                repository_path=self.onedocker_binary_config.repository_path
            )
            args_ls_expect = self.get_args_expected(
                pc_role,
                test_num_containers,
                max_col_cnt_expect,
                id_filter_thresh_expect,
                test_run_id,
            )
            # test the start_containers is called with expected parameters
            self.mock_onedocker_svc.start_containers.assert_called_with(
                package_name=self.binary_name,
                version=self.onedocker_binary_config.binary_version,
                cmd_args_list=args_ls_expect,
                timeout=self.container_timeout,
                env_vars=env_vars,
                container_type=None,
                certificate_request=None,
                opa_workflow_path=None,
                permission=None,
            )
            # test the return value is as expected
            self.assertEqual(
                len(updated_pc_instance.infra_config.instances),
                1,
                "Failed to add the StageStateInstance into pc_instance",
            )
            stage_state_expect = StageStateInstance(
                pc_instance.infra_config.instance_id,
                pc_instance.current_stage.name,
                containers=containers,
            )
            stage_state_actual = updated_pc_instance.infra_config.instances[0]
            self.assertEqual(
                stage_state_actual,
                stage_state_expect,
                "Appended StageStateInstance is not as expected",
            )

        data_tests = itertools.product(
            [PrivateComputationRole.PUBLISHER, PrivateComputationRole.PARTNER],
            [True, False],
            [1, 2],
            [None, "2621fda2-0eca-11ed-861d-0242ac120002"],
        )
        for pc_role, multikey_enabled, test_num_containers, test_run_id in data_tests:
            with self.subTest(
                pc_role=pc_role,
                multikey_enabled=multikey_enabled,
                test_num_containers=test_num_containers,
                test_run_id=test_run_id,
            ):
                await _run_sub_test(
                    pc_role=pc_role,
                    multikey_enabled=multikey_enabled,
                    test_num_containers=test_num_containers,
                    test_run_id=test_run_id,
                )

    def create_sample_pc_instance(
        self,
        pc_role: PrivateComputationRole = PrivateComputationRole.PUBLISHER,
        test_num_containers: int = 1,
        pid_max_column_count: int = 1,
        multikey_enabled: bool = False,
        status: PrivateComputationInstanceStatus = PrivateComputationInstanceStatus.PID_SHARD_COMPLETED,
        run_id: Optional[str] = None,
    ) -> PrivateComputationInstance:
        infra_config: InfraConfig = InfraConfig(
            instance_id=self.pc_instance_id,
            role=pc_role,
            instances=[],
            status=status,
            status_update_ts=1600000000,
            game_type=PrivateComputationGameType.LIFT,
            num_pid_containers=test_num_containers,
            num_mpc_containers=test_num_containers,
            num_files_per_mpc_container=test_num_containers,
            status_updates=[],
            run_id=run_id,
        )
        common: CommonProductConfig = CommonProductConfig(
            input_path=self.input_path,
            output_dir=self.output_path,
            pid_use_row_numbers=True,
            pid_max_column_count=pid_max_column_count,
            multikey_enabled=multikey_enabled,
        )
        product_config: ProductConfig = LiftConfig(
            common=common,
        )
        return PrivateComputationInstance(
            infra_config=infra_config,
            product_config=product_config,
        )

    def create_container_instance(
        self,
        id: int,
        container_status: ContainerInstanceStatus = ContainerInstanceStatus.COMPLETED,
    ) -> ContainerInstance:
        return ContainerInstance(
            instance_id=f"test_container_instance_{id}",
            ip_address=f"127.0.0.{id}",
            status=container_status,
        )

    def get_args_expected(
        self,
        pc_role: PrivateComputationRole,
        test_num_containers: int,
        max_col_cnt_expected: int,
        id_filter_thresh_expect: int,
        test_run_id: Optional[str] = None,
    ) -> List[str]:
        arg_ls = []
        if pc_role is PrivateComputationRole.PUBLISHER:
            arg_ls = [
                f"--input_path=out/test_instance_123_out_dir/pid_stage/out.csv_publisher_sharded_{i} --output_path=out/test_instance_123_out_dir/pid_stage/out.csv_publisher_prepared_{i} --tmp_directory=/tmp --max_column_cnt={max_col_cnt_expected} --id_filter_thresh={id_filter_thresh_expect}"
                for i in range(test_num_containers)
            ]
        elif pc_role is PrivateComputationRole.PARTNER:
            arg_ls = [
                f"--input_path=out/test_instance_123_out_dir/pid_stage/out.csv_advertiser_sharded_{i} --output_path=out/test_instance_123_out_dir/pid_stage/out.csv_advertiser_prepared_{i} --tmp_directory=/tmp --max_column_cnt={max_col_cnt_expected} --id_filter_thresh={id_filter_thresh_expect}"
                for i in range(test_num_containers)
            ]

        modified_arg_ls = []
        for arg in arg_ls:
            modified_arg = arg
            if test_run_id is not None:
                modified_arg = " ".join(
                    [
                        arg,
                        f"--run_id={test_run_id}",
                    ]
                )
            else:
                modified_arg = arg
            modified_arg_ls.append(modified_arg)
        return modified_arg_ls
