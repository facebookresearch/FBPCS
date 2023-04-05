#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import itertools
from collections import defaultdict
from typing import List, Optional
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from fbpcp.entity.container_instance import ContainerInstance, ContainerInstanceStatus
from fbpcs.common.entity.stage_state_instance import StageStateInstance

from fbpcs.data_processing.service.pid_run_protocol_binary_service import (
    PIDRunProtocolBinaryService,
)
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
from fbpcs.private_computation.service.constants import (
    DEFAULT_CONTAINER_TIMEOUT_IN_SEC,
    DEFAULT_PID_PROTOCOL,
    TLS_OPA_WORKFLOW_PATH,
)
from fbpcs.private_computation.service.pid_run_protocol_stage_service import (
    PIDRunProtocolStageService,
)
from fbpcs.private_computation.service.pid_utils import (
    pid_should_use_row_numbers,
    PIDProtocol,
)
from fbpcs.private_computation.service.utils import (
    gen_tls_server_hostnames_for_publisher,
    generate_env_vars_dict,
)


class TestPIDRunProtocolStageService(IsolatedAsyncioTestCase):
    @patch("fbpcp.service.storage.StorageService")
    @patch("fbpcp.service.onedocker.OneDockerService")
    def setUp(self, mock_onedocker_service, mock_storage_service) -> None:
        self.mock_onedocker_svc = mock_onedocker_service
        self.mock_storage_svc = mock_storage_service
        self.test_num_containers = 1
        self.onedocker_binary_config_map = defaultdict(
            lambda: OneDockerBinaryConfig(
                tmp_directory="/test_tmp_directory/",
                binary_version="latest",
                repository_path="test_path/",
            )
        )
        self.server_ips = [f"192.0.2.{i}" for i in range(self.test_num_containers)]
        self.input_path = "in"
        self.output_path = "out"
        self.pc_instance_id = "test_instance_123"
        self.port = 15200
        self.use_row_numbers = True

    async def test_pid_run_protocol_stage(self) -> None:
        async def _run_sub_test(
            pc_role: PrivateComputationRole,
            multikey_enabled: bool,
            run_id: Optional[str] = None,
        ) -> None:
            pid_protocol = (
                PIDProtocol.UNION_PID_MULTIKEY
                if self.test_num_containers == 1 and multikey_enabled
                else PIDProtocol.UNION_PID
            )
            use_row_number = pid_should_use_row_numbers(
                self.use_row_numbers, pid_protocol
            )
            pc_instance = self.create_sample_pc_instance(
                pc_role,
                pid_use_row_numbers=use_row_number,
                pid_protocol=pid_protocol,
                multikey_enabled=multikey_enabled,
                run_id=run_id,
            )
            stage_svc = PIDRunProtocolStageService(
                storage_svc=self.mock_storage_svc,
                onedocker_svc=self.mock_onedocker_svc,
                onedocker_binary_config_map=self.onedocker_binary_config_map,
            )
            containers = [
                self.create_container_instance(i)
                for i in range(self.test_num_containers)
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
                server_ips=self.server_ips,
            )

            binary_name = PIDRunProtocolBinaryService.get_binary_name(
                pid_protocol, pc_role
            )
            binary_config = self.onedocker_binary_config_map[binary_name]
            env_vars = generate_env_vars_dict(
                repository_path=binary_config.repository_path,
                RUST_LOG="info",
            )
            args_str_expect = self.get_args_expect(
                pc_role,
                pid_protocol,
                self.use_row_numbers,
                run_id,
            )
            # test the start_containers is called with expected parameters
            self.mock_onedocker_svc.start_containers.assert_called_with(
                package_name=binary_name,
                version=binary_config.binary_version,
                cmd_args_list=args_str_expect,
                timeout=DEFAULT_CONTAINER_TIMEOUT_IN_SEC,
                env_vars=env_vars,
                container_type=None,
                certificate_request=None,
                opa_workflow_path=None,
                permission=None,
            )
            # test the return value is as expected
            self.assertEqual(
                len(updated_pc_instance.infra_config.instances),
                self.test_num_containers,
                "Failed to add the StageStageInstance into pc_instance",
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
                "Appended StageStageInstance is not as expected",
            )

        data_tests = itertools.product(
            [PrivateComputationRole.PUBLISHER, PrivateComputationRole.PARTNER],
            [True, False],
            [None, "2621fda2-0eca-11ed-861d-0242ac120002"],
        )
        for pc_role, multikey_enabled, test_run_id in data_tests:
            with self.subTest(
                pc_role=pc_role,
                multikey_enabled=multikey_enabled,
                test_run_id=test_run_id,
            ):
                await _run_sub_test(
                    pc_role=pc_role,
                    multikey_enabled=multikey_enabled,
                    run_id=test_run_id,
                )

    async def test_pid_run_protocol_stage_tls_enabled_publisher(self) -> None:
        # Arrange
        pc_role = PrivateComputationRole.PUBLISHER
        pc_instance = self.create_sample_pc_instance(
            pc_role, server_domain="test_domain"
        )
        stage_svc = PIDRunProtocolStageService(
            storage_svc=self.mock_storage_svc,
            onedocker_svc=self.mock_onedocker_svc,
            onedocker_binary_config_map=self.onedocker_binary_config_map,
        )
        containers = [
            self.create_container_instance(i) for i in range(self.test_num_containers)
        ]
        self.mock_onedocker_svc.start_containers = MagicMock(return_value=containers)
        self.mock_onedocker_svc.wait_for_pending_containers = AsyncMock(
            return_value=containers
        )
        server_hostnames = gen_tls_server_hostnames_for_publisher(
            pc_instance.infra_config.server_domain,
            pc_role,
            self.test_num_containers,
        )
        stage_state_expect = StageStateInstance(
            pc_instance.infra_config.instance_id,
            pc_instance.current_stage.name,
            containers=containers,
            server_uris=server_hostnames,
        )

        # Act
        updated_pc_instance = await stage_svc.run_async(
            pc_instance=pc_instance,
            server_certificate_provider=NullCertificateProvider(),
            ca_certificate_provider=NullCertificateProvider(),
            server_certificate_path="",
            ca_certificate_path="",
        )

        # Assert
        self.assertEqual(
            len(updated_pc_instance.infra_config.instances),
            self.test_num_containers,
            "Failed to add the StageStageInstance into pc_instance",
        )
        stage_state_actual = updated_pc_instance.infra_config.instances[0]
        self.assertEqual(
            stage_state_actual,
            stage_state_expect,
            "Appended StageStageInstance is not as expected",
        )

    async def test_pid_run_protocol_stage_with_tls(self) -> None:
        async def _run_sub_test(
            pc_role: PrivateComputationRole,
            multikey_enabled: bool,
            run_id: Optional[str] = None,
        ) -> None:
            pid_protocol = (
                PIDProtocol.UNION_PID_MULTIKEY
                if self.test_num_containers == 1 and multikey_enabled
                else PIDProtocol.UNION_PID
            )
            use_row_number = pid_should_use_row_numbers(
                self.use_row_numbers, pid_protocol
            )
            pc_instance = self.create_sample_pc_instance(
                pc_role,
                pid_use_row_numbers=use_row_number,
                pid_protocol=pid_protocol,
                multikey_enabled=multikey_enabled,
                run_id=run_id,
                use_tls=True,
            )
            stage_svc = PIDRunProtocolStageService(
                storage_svc=self.mock_storage_svc,
                onedocker_svc=self.mock_onedocker_svc,
                onedocker_binary_config_map=self.onedocker_binary_config_map,
            )
            containers = [
                self.create_container_instance(i)
                for i in range(self.test_num_containers)
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
                server_certificate_path="tls/server_certificate.pem",
                ca_certificate_path="tls/ca_certificate.pem",
                server_ips=self.server_ips,
                server_hostnames=["node0.meta.com"]
                if pc_role is PrivateComputationRole.PARTNER
                else None,
            )
            binary_name = PIDRunProtocolBinaryService.get_binary_name(
                pid_protocol, pc_role
            )
            binary_config = self.onedocker_binary_config_map[binary_name]
            if pc_role is PrivateComputationRole.PUBLISHER:
                expected_env_vars = generate_env_vars_dict(
                    repository_path=binary_config.repository_path,
                    RUST_LOG="info",
                )
            else:
                expected_env_vars = generate_env_vars_dict(
                    repository_path=binary_config.repository_path,
                    RUST_LOG="info",
                    SERVER_HOSTNAME="node0.meta.com",
                    IP_ADDRESS="192.0.2.0",
                )
            args_str_expect = self.get_args_expect(
                pc_role,
                pid_protocol,
                self.use_row_numbers,
                run_id,
                use_tls=True,
            )
            # test the start_containers is called with expected parameters
            self.mock_onedocker_svc.start_containers.assert_called_with(
                package_name=binary_name,
                version=binary_config.binary_version,
                cmd_args_list=args_str_expect,
                timeout=DEFAULT_CONTAINER_TIMEOUT_IN_SEC,
                env_vars=[expected_env_vars],
                container_type=None,
                certificate_request=None,
                opa_workflow_path=TLS_OPA_WORKFLOW_PATH,
                permission=None,
            )
            # test the return value is as expected
            self.assertEqual(
                len(updated_pc_instance.infra_config.instances),
                self.test_num_containers,
                "Failed to add the StageStageInstance into pc_instance",
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
                "Appended StageStageInstance is not as expected",
            )

        data_tests = itertools.product(
            [PrivateComputationRole.PUBLISHER, PrivateComputationRole.PARTNER],
            [True, False],
            [None, "2621fda2-0eca-11ed-861d-0242ac120002"],
        )
        for pc_role, multikey_enabled, test_run_id in data_tests:
            with self.subTest(
                pc_role=pc_role,
                multikey_enabled=multikey_enabled,
                test_run_id=test_run_id,
            ):
                await _run_sub_test(
                    pc_role=pc_role,
                    multikey_enabled=multikey_enabled,
                    run_id=test_run_id,
                )

    def create_sample_pc_instance(
        self,
        pc_role: PrivateComputationRole = PrivateComputationRole.PARTNER,
        status: PrivateComputationInstanceStatus = PrivateComputationInstanceStatus.PID_PREPARE_COMPLETED,
        multikey_enabled: bool = False,
        pid_use_row_numbers: bool = True,
        pid_protocol: PIDProtocol = DEFAULT_PID_PROTOCOL,
        run_id: Optional[str] = None,
        server_domain: Optional[str] = None,
        use_tls: Optional[bool] = False,
    ) -> PrivateComputationInstance:
        infra_config: InfraConfig = InfraConfig(
            instance_id=self.pc_instance_id,
            role=pc_role,
            status=status,
            status_update_ts=1600000000,
            instances=[],
            game_type=PrivateComputationGameType.LIFT,
            num_pid_containers=self.test_num_containers,
            num_mpc_containers=self.test_num_containers,
            num_files_per_mpc_container=self.test_num_containers,
            status_updates=[],
            run_id=run_id,
            server_domain=server_domain,
            pcs_features=set() if not use_tls else {PCSFeature.PCF_TLS},
        )
        common: CommonProductConfig = CommonProductConfig(
            input_path=self.input_path,
            output_dir=self.output_path,
            pid_use_row_numbers=pid_use_row_numbers,
            multikey_enabled=multikey_enabled,
            pid_protocol=pid_protocol,
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

    def get_args_expect(
        self,
        pc_role: PrivateComputationRole,
        protocol: PIDProtocol,
        use_row_numbers: bool,
        test_run_id: Optional[str] = None,
        use_tls: Optional[bool] = False,
    ) -> List[str]:
        arg_ls = []
        if (
            pc_role is PrivateComputationRole.PUBLISHER
            and protocol is PIDProtocol.UNION_PID
            and not use_tls
        ):
            arg_ls.append(
                "--host 0.0.0.0:15200 --input out/test_instance_123_out_dir/pid_stage/out.csv_publisher_prepared_0 --output out/test_instance_123_out_dir/pid_stage/out.csv_publisher_pid_matched_0 --metric-path out/test_instance_123_out_dir/pid_stage/out.csv_publisher_pid_matched_0_metrics --no-tls --use-row-numbers"
            )
        elif (
            pc_role is PrivateComputationRole.PUBLISHER
            and protocol is PIDProtocol.UNION_PID
            and use_tls
        ):
            arg_ls.append(
                "--host 0.0.0.0:15200 --input out/test_instance_123_out_dir/pid_stage/out.csv_publisher_prepared_0 --output out/test_instance_123_out_dir/pid_stage/out.csv_publisher_pid_matched_0 --metric-path out/test_instance_123_out_dir/pid_stage/out.csv_publisher_pid_matched_0_metrics --use-row-numbers --tls-cert tls/server_certificate.pem --tls-key tls/private_key.pem"
            )
        elif (
            pc_role is PrivateComputationRole.PUBLISHER
            and protocol is PIDProtocol.UNION_PID_MULTIKEY
            and not use_tls
        ):
            arg_ls.append(
                "--host 0.0.0.0:15200 --input out/test_instance_123_out_dir/pid_stage/out.csv_publisher_prepared_0 --output out/test_instance_123_out_dir/pid_stage/out.csv_publisher_pid_matched_0 --metric-path out/test_instance_123_out_dir/pid_stage/out.csv_publisher_pid_matched_0_metrics --no-tls"
            )
        elif (
            pc_role is PrivateComputationRole.PUBLISHER
            and protocol is PIDProtocol.UNION_PID_MULTIKEY
            and use_tls
        ):
            arg_ls.append(
                "--host 0.0.0.0:15200 --input out/test_instance_123_out_dir/pid_stage/out.csv_publisher_prepared_0 --output out/test_instance_123_out_dir/pid_stage/out.csv_publisher_pid_matched_0 --metric-path out/test_instance_123_out_dir/pid_stage/out.csv_publisher_pid_matched_0_metrics --tls-cert tls/server_certificate.pem --tls-key tls/private_key.pem"
            )
        elif (
            pc_role is PrivateComputationRole.PARTNER
            and protocol is PIDProtocol.UNION_PID
            and not use_tls
        ):
            arg_ls.append(
                "--company http://192.0.2.0:15200 --input out/test_instance_123_out_dir/pid_stage/out.csv_advertiser_prepared_0 --output out/test_instance_123_out_dir/pid_stage/out.csv_advertiser_pid_matched_0 --no-tls --use-row-numbers"
            )
        elif (
            pc_role is PrivateComputationRole.PARTNER
            and protocol is PIDProtocol.UNION_PID
            and use_tls
        ):
            arg_ls.append(
                "--company https://node0.meta.com:15200 --input out/test_instance_123_out_dir/pid_stage/out.csv_advertiser_prepared_0 --output out/test_instance_123_out_dir/pid_stage/out.csv_advertiser_pid_matched_0 --use-row-numbers --tls-ca tls/ca_certificate.pem"
            )
        elif (
            pc_role is PrivateComputationRole.PARTNER
            and protocol is PIDProtocol.UNION_PID_MULTIKEY
            and not use_tls
        ):
            arg_ls.append(
                "--company http://192.0.2.0:15200 --input out/test_instance_123_out_dir/pid_stage/out.csv_advertiser_prepared_0 --output out/test_instance_123_out_dir/pid_stage/out.csv_advertiser_pid_matched_0 --no-tls"
            )
        elif (
            pc_role is PrivateComputationRole.PARTNER
            and protocol is PIDProtocol.UNION_PID_MULTIKEY
            and use_tls
        ):
            arg_ls.append(
                "--company https://node0.meta.com:15200 --input out/test_instance_123_out_dir/pid_stage/out.csv_advertiser_prepared_0 --output out/test_instance_123_out_dir/pid_stage/out.csv_advertiser_pid_matched_0 --tls-ca tls/ca_certificate.pem"
            )

        modified_arg_ls = []
        for arg in arg_ls:
            modified_arg = arg
            if test_run_id is not None:
                modified_arg = " ".join(
                    [
                        arg,
                        f"--run_id {test_run_id}",
                    ]
                )
            else:
                modified_arg = arg
            modified_arg_ls.append(modified_arg)
        return modified_arg_ls

        return arg_ls
