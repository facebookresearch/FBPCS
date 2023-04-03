#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import dataclasses
import unittest
from unittest.mock import MagicMock, patch

from fbpcp.entity.container_instance import ContainerInstance, ContainerInstanceStatus
from fbpcs.common.entity.stage_state_instance import (
    StageStateInstance,
    StageStateInstanceStatus,
)


class TestStageStateInstance(unittest.TestCase):
    def setUp(self) -> None:
        self.stage_state_instance = StageStateInstance(
            instance_id="stage_state_instance",
            stage_name="test_stage",
            status=StageStateInstanceStatus.COMPLETED,
            containers=[
                ContainerInstance(
                    instance_id="test_container_instance_1",
                    ip_address="192.0.2.4",
                    status=ContainerInstanceStatus.COMPLETED,
                ),
                ContainerInstance(
                    instance_id="test_container_instance_2",
                    ip_address="192.0.2.5",
                    status=ContainerInstanceStatus.COMPLETED,
                ),
            ],
            creation_ts=1646642432,
            end_ts=1646642432 + 5,
        )

    def test_server_ips(self) -> None:
        self.assertEqual(len(self.stage_state_instance.containers), 2)
        self.assertEqual(
            self.stage_state_instance.server_ips, ["192.0.2.4", "192.0.2.5"]
        )

        self.stage_state_instance.status = StageStateInstanceStatus.UNKNOWN
        self.assertEqual(self.stage_state_instance.server_ips, [])

    def test_elapsed_time(self) -> None:
        self.assertEqual(self.stage_state_instance.elapsed_time, 5)

    @patch("fbpcp.service.onedocker.OneDockerService")
    def test_stop_containers(self, mock_onedocker_svc) -> None:
        for container_stoppable in (True, False):
            with self.subTest(
                "Subtest with container_stoppable: {container_stoppable}",
                container_stoppable=container_stoppable,
            ):

                mock_onedocker_svc.reset_mock()
                if container_stoppable:
                    mock_onedocker_svc.stop_containers = MagicMock(
                        return_value=[None, None]
                    )
                    self.stage_state_instance.stop_containers(mock_onedocker_svc)
                else:
                    mock_onedocker_svc.stop_containers = MagicMock(
                        return_value=[None, "Oops"]
                    )
                    with self.assertRaises(RuntimeError):
                        self.stage_state_instance.stop_containers(mock_onedocker_svc)

                mock_onedocker_svc.stop_containers.assert_called_with(
                    ["test_container_instance_1", "test_container_instance_2"]
                )

    @patch("fbpcp.service.onedocker.OneDockerService")
    @patch(
        "fbpcs.common.entity.stage_state_instance.StageStateInstance._get_updated_containers"
    )
    def test_update_status_translation(
        self, mock_update_containers, mock_onedocker_svc
    ) -> None:
        with self.subTest("test all containers started"):
            mock_update_containers.return_value = [
                ContainerInstance(
                    instance_id="test_container_instance_100",
                    status=ContainerInstanceStatus.STARTED,
                ),
                ContainerInstance(
                    instance_id="test_container_instance_101",
                    status=ContainerInstanceStatus.STARTED,
                ),
            ]

            status = self.stage_state_instance.update_status(mock_onedocker_svc)
            self.assertEqual(status, StageStateInstanceStatus.STARTED)

        with self.subTest("test some container completed"):
            mock_update_containers.return_value = [
                ContainerInstance(
                    instance_id="test_container_instance_100",
                    status=ContainerInstanceStatus.COMPLETED,
                ),
                ContainerInstance(
                    instance_id="test_container_instance_101",
                    status=ContainerInstanceStatus.STARTED,
                ),
            ]

            status = self.stage_state_instance.update_status(mock_onedocker_svc)
            self.assertEqual(status, StageStateInstanceStatus.STARTED)

        with self.subTest("test all containers completed"):
            mock_update_containers.return_value = [
                ContainerInstance(
                    instance_id="test_container_instance_100",
                    status=ContainerInstanceStatus.COMPLETED,
                ),
                ContainerInstance(
                    instance_id="test_container_instance_101",
                    status=ContainerInstanceStatus.COMPLETED,
                ),
            ]

            status = self.stage_state_instance.update_status(mock_onedocker_svc)
            self.assertEqual(status, StageStateInstanceStatus.COMPLETED)

        with self.subTest("test container had failed"):
            mock_update_containers.return_value = [
                ContainerInstance(
                    instance_id="test_container_instance_100",
                    status=ContainerInstanceStatus.FAILED,
                ),
                ContainerInstance(
                    instance_id="test_container_instance_101",
                    status=ContainerInstanceStatus.COMPLETED,
                ),
            ]

            status = self.stage_state_instance.update_status(mock_onedocker_svc)
            self.assertEqual(status, StageStateInstanceStatus.FAILED)

        with self.subTest("test container had unknown"):
            mock_update_containers.return_value = [
                ContainerInstance(
                    instance_id="test_container_instance_100",
                    status=ContainerInstanceStatus.COMPLETED,
                ),
                ContainerInstance(
                    instance_id="test_container_instance_101",
                    status=ContainerInstanceStatus.UNKNOWN,
                ),
            ]

            status = self.stage_state_instance.update_status(mock_onedocker_svc)
            self.assertEqual(status, StageStateInstanceStatus.UNKNOWN)

    @patch("fbpcp.service.onedocker.OneDockerService")
    def test_update_status(self, mock_onedocker_svc) -> None:
        self.stage_state_instance.containers[0].status = ContainerInstanceStatus.FAILED

        started_container = ContainerInstance(
            instance_id="test_container_instance_100",
            ip_address="192.0.2.100",
            status=ContainerInstanceStatus.STARTED,
        )
        unkown_container = ContainerInstance(
            instance_id="test_container_instance_101",
            ip_address="192.0.2.101",
            status=ContainerInstanceStatus.UNKNOWN,
        )
        self.stage_state_instance.containers.append(started_container)
        self.stage_state_instance.containers.append(unkown_container)
        # exsiting conatiner status: FAILED/COMPLETED/STARTED/UNKNOWN

        updated_container = dataclasses.replace(started_container)
        updated_container.status = ContainerInstanceStatus.FAILED

        mock_onedocker_svc.reset_mock()
        mock_onedocker_svc.get_containers = MagicMock(
            return_value=[updated_container, None]
        )

        # Ack
        self.assertEqual(
            self.stage_state_instance.get_running_containers(
                self.stage_state_instance.containers
            ),
            [2, 3],
        )
        self.stage_state_instance.update_status(mock_onedocker_svc)

        # Asserts
        mock_onedocker_svc.get_containers.assert_called_once_with(
            [started_container.instance_id, unkown_container.instance_id]
        )
        self.assertEqual(
            [o.status for o in self.stage_state_instance.containers],
            [
                ContainerInstanceStatus.FAILED,
                ContainerInstanceStatus.COMPLETED,
                ContainerInstanceStatus.FAILED,
                ContainerInstanceStatus.UNKNOWN,
            ],
        )
