#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

import asyncio
import logging
from typing import Dict, List, Optional

from fbpcp.entity.container_instance import ContainerInstance, ContainerInstanceStatus
from fbpcp.error.pcp import ThrottlingError
from fbpcp.service.mpc import MPCService
from fbpcp.service.onedocker import OneDockerService
from fbpcs.common.service.retry_handler import RetryHandler
from fbpcs.private_computation.service.constants import DEFAULT_CONTAINER_TIMEOUT_IN_SEC

DEFAULT_WAIT_FOR_CONTAINER_POLL = 5


class RunBinaryBaseService:
    async def start_containers(
        self,
        cmd_args_list: List[str],
        onedocker_svc: OneDockerService,
        binary_version: str,
        binary_name: str,
        timeout: Optional[int] = None,
        wait_for_containers_to_finish: bool = False,
        env_vars: Optional[Dict[str, str]] = None,
        wait_for_containers_to_start_up: bool = True,
        existing_containers: Optional[List[ContainerInstance]] = None,
    ) -> List[ContainerInstance]:
        logger = logging.getLogger(__name__)

        timeout = timeout or DEFAULT_CONTAINER_TIMEOUT_IN_SEC

        containers_to_start = MPCService.get_containers_to_start(
            len(cmd_args_list), existing_containers
        )

        if containers_to_start:
            logger.info(f"Spinning up {len(containers_to_start)} containers")
            logger.info(f"Containers to start: {containers_to_start}")

            new_pending_containers = onedocker_svc.start_containers(
                package_name=binary_name,
                version=binary_version,
                cmd_args_list=[cmd_args_list[i] for i in containers_to_start],
                timeout=timeout,
                env_vars=env_vars,
            )

            pending_containers = MPCService.get_pending_containers(
                new_pending_containers, containers_to_start, existing_containers
            )
        else:
            logger.info(
                "No containers are in a failed state - skipping container start-up"
            )
            pending_containers = existing_containers or []

        if not wait_for_containers_to_start_up:
            logger.info("Skipped container warm up")
            return pending_containers

        with RetryHandler(
            ThrottlingError, logger=logger, backoff_seconds=30
        ) as retry_handler:
            containers = await retry_handler.execute(
                onedocker_svc.wait_for_pending_containers,
                [container.instance_id for container in pending_containers],
            )

        logger.info("Task started")
        if wait_for_containers_to_finish:
            # Busy wait until the container is finished
            containers = await self.wait_for_containers_async(onedocker_svc, containers)
            if not all(
                container.status is ContainerInstanceStatus.COMPLETED
                for container in containers
            ):
                raise RuntimeError(
                    "One or more containers failed. See the logs above to find the exact container_id"
                )
        return containers

    @staticmethod
    async def wait_for_containers_async(
        onedocker_svc: OneDockerService,
        containers: List[ContainerInstance],
        poll: int = DEFAULT_WAIT_FOR_CONTAINER_POLL,
    ) -> List[ContainerInstance]:
        updated_containers = containers.copy()
        end_states = {
            ContainerInstanceStatus.COMPLETED,
            ContainerInstanceStatus.FAILED,
        }
        for i, container in enumerate(updated_containers):
            instance_id = container.instance_id
            onedocker_svc.logger.info(
                f"Waiting for container {instance_id} to complete"
            )
            status = container.status
            while status not in end_states:
                await asyncio.sleep(poll)
                container = onedocker_svc.get_containers([instance_id])[0]
                if not container:
                    break
                status = container.status
                updated_containers[i] = container
            if status is not ContainerInstanceStatus.COMPLETED:
                onedocker_svc.logger.warning(
                    f"Container {instance_id} failed with status {status}"
                )
                return updated_containers
        return updated_containers
