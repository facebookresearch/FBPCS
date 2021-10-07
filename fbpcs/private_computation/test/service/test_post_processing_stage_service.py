#!/usr/bin/env python3
# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from fbpcs.post_processing_handler.post_processing_handler import (
    PostProcessingHandlerStatus,
)
from fbpcs.post_processing_handler.post_processing_instance import (
    PostProcessingInstance,
    PostProcessingInstanceStatus,
)
from fbpcs.post_processing_handler.tests.dummy_handler import PostProcessingDummyHandler
from fbpcs.private_computation.entity.private_computation_instance import (
    PrivateComputationGameType,
    PrivateComputationInstance,
    PrivateComputationRole,
)
from fbpcs.private_computation.entity.private_computation_instance import (
    PrivateComputationInstanceStatus,
)
from fbpcs.private_computation.service.constants import (
    NUM_NEW_SHARDS_PER_FILE,
)
from fbpcs.private_computation.service.post_processing_stage_service import (
    PostProcessingStageService,
)


class TestPostProcessingStageService(IsolatedAsyncioTestCase):
    @patch("fbpcp.service.storage_s3.S3StorageService")
    def setUp(self, mock_storage_svc):
        self.mock_storage_svc = mock_storage_svc

    async def test_post_processing_all_succeed(self):
        # create two handlers that never fail
        handlers = {
            f"handler{i}": PostProcessingDummyHandler(probability_of_failure=0)
            for i in range(2)
        }
        stage_svc = PostProcessingStageService(self.mock_storage_svc, handlers)

        private_computation_instance = self._create_pc_instance()
        await stage_svc.run_async(private_computation_instance)

        post_processing_instance = private_computation_instance.instances[0]
        self.assertIsInstance(post_processing_instance, PostProcessingInstance)

        # post processing instance should have status COMPLETED
        self.assertEqual(
            post_processing_instance.status, PostProcessingInstanceStatus.COMPLETED
        )

        # all handlers should have status COMPLETED
        expected_handler_statuses = {
            handler_name: PostProcessingHandlerStatus.COMPLETED
            for handler_name in handlers.keys()
        }
        self.assertEqual(
            post_processing_instance.handler_statuses, expected_handler_statuses
        )

    async def test_post_processing_all_fail(self):
        # create two handlers that always fail
        handlers = {
            f"handler{i}": PostProcessingDummyHandler(probability_of_failure=1)
            for i in range(2)
        }
        stage_svc = PostProcessingStageService(self.mock_storage_svc, handlers)

        private_computation_instance = self._create_pc_instance()
        await stage_svc.run_async(private_computation_instance)

        post_processing_instance = private_computation_instance.instances[0]
        self.assertIsInstance(post_processing_instance, PostProcessingInstance)

        # post processing instance should have status FAILED
        self.assertEqual(
            post_processing_instance.status, PostProcessingInstanceStatus.FAILED
        )

        # all handlers should have status FAILED
        expected_handler_statuses = {
            handler_name: PostProcessingHandlerStatus.FAILED
            for handler_name in handlers.keys()
        }
        self.assertEqual(
            post_processing_instance.handler_statuses, expected_handler_statuses
        )

    async def test_post_processing_one_fail(self):
        # create two handlers, one that fails, one that succeeds
        handlers = {
            f"handler{i}": PostProcessingDummyHandler(probability_of_failure=i)
            for i in range(2)
        }
        stage_svc = PostProcessingStageService(self.mock_storage_svc, handlers)

        private_computation_instance = self._create_pc_instance()
        await stage_svc.run_async(private_computation_instance)

        post_processing_instance = private_computation_instance.instances[0]
        self.assertIsInstance(post_processing_instance, PostProcessingInstance)

        # post processing instance should have status FAILED
        self.assertEqual(
            post_processing_instance.status, PostProcessingInstanceStatus.FAILED
        )

        # first handler has status completed, second handler has status failed
        expected_handler_statuses = dict(
            zip(
                handlers.keys(),
                (
                    PostProcessingHandlerStatus.COMPLETED,
                    PostProcessingHandlerStatus.FAILED,
                ),
            )
        )
        self.assertEqual(
            post_processing_instance.handler_statuses, expected_handler_statuses
        )

    def _create_pc_instance(self) -> PrivateComputationInstance:
        return PrivateComputationInstance(
            instance_id="test_instance_123",
            role=PrivateComputationRole.PUBLISHER,
            instances=[],
            status=PrivateComputationInstanceStatus.AGGREGATION_COMPLETED,
            status_update_ts=1600000000,
            num_pid_containers=2,
            num_mpc_containers=2,
            num_files_per_mpc_container=NUM_NEW_SHARDS_PER_FILE,
            game_type=PrivateComputationGameType.LIFT,
            input_path="456",
            output_dir="789",
        )
