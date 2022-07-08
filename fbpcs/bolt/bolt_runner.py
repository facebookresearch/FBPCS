#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from time import time
from typing import List, Optional

from fbpcs.bolt.bolt_job import BoltCreateInstanceArgs, BoltJob
from fbpcs.bolt.constants import DEFAULT_POLL_INTERVAL_SEC
from fbpcs.bolt.exceptions import (
    NoServerIpsException,
    StageFailedException,
    StageTimeoutException,
)
from fbpcs.private_computation.entity.private_computation_status import (
    PrivateComputationInstanceStatus,
)

from fbpcs.private_computation.stage_flows.private_computation_base_stage_flow import (
    PrivateComputationBaseStageFlow,
)


@dataclass
class BoltState:
    pc_instance_status: PrivateComputationInstanceStatus
    server_ips: Optional[List[str]] = None


class BoltClient(ABC):
    """
    Exposes async methods for creating instances, running stages, updating instances, and validating the correctness of a computation
    """

    @abstractmethod
    async def create_instance(self, instance_args: BoltCreateInstanceArgs) -> str:
        pass

    @abstractmethod
    async def run_stage(
        self,
        instance_id: str,
        stage: PrivateComputationBaseStageFlow,
        server_ips: Optional[List[str]] = None,
    ) -> None:
        pass

    @abstractmethod
    async def update_instance(self, instance_id: str) -> BoltState:
        pass

    @abstractmethod
    async def validate_results(
        self, instance_id: str, expected_result_path: Optional[str] = None
    ) -> bool:
        pass


class BoltRunner:
    def __init__(
        self,
        publisher_client: BoltClient,
        partner_client: BoltClient,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.publisher_client = publisher_client
        self.partner_client = partner_client
        self.logger: logging.Logger = (
            logging.getLogger(__name__) if logger is None else logger
        )

    async def run_async(
        self,
        jobs: List[BoltJob],
    ) -> List[bool]:
        return list(await asyncio.gather(*[self.run_one(job=job) for job in jobs]))

    async def run_one(self, job: BoltJob) -> bool:
        try:
            self.logger.info(f"[{job.job_name}] Creating instances...")
            publisher_id, partner_id = await asyncio.gather(
                self.publisher_client.create_instance(
                    instance_args=job.publisher_bolt_args.create_instance_args
                ),
                self.partner_client.create_instance(
                    instance_args=job.partner_bolt_args.create_instance_args
                ),
            )
            for stage in list(job.stage_flow)[1:]:
                await self.run_next_stage(
                    publisher_id=publisher_id, partner_id=partner_id, stage=stage
                )
                await self.wait_stage_complete(
                    publisher_id=publisher_id, partner_id=partner_id, stage=stage
                )
            results = await asyncio.gather(
                *[
                    self.publisher_client.validate_results(
                        instance_id=publisher_id,
                        expected_result_path=job.publisher_bolt_args.expected_result_path,
                    ),
                    self.partner_client.validate_results(
                        instance_id=partner_id,
                        expected_result_path=job.partner_bolt_args.expected_result_path,
                    ),
                ]
            )
            return all(results)
        except Exception as e:
            self.logger.exception(e)
            return False

    async def run_next_stage(
        self, publisher_id: str, partner_id: str, stage: PrivateComputationBaseStageFlow
    ) -> None:
        self.logger.info(f"Publisher {publisher_id} starting stage {stage.name}.")
        await self.publisher_client.run_stage(instance_id=publisher_id, stage=stage)
        server_ips = None
        if stage.is_joint_stage:
            server_ips = await self.get_server_ips_after_start(
                instance_id=publisher_id, stage=stage, timeout=stage.timeout
            )
            if server_ips is None:
                raise NoServerIpsException(
                    f"{stage.name} requires server ips but got none."
                )
        self.logger.info(f"Partner {partner_id} starting stage {stage.name}.")
        await self.partner_client.run_stage(
            instance_id=partner_id, stage=stage, server_ips=server_ips
        )

    async def get_server_ips_after_start(
        self, instance_id: str, stage: PrivateComputationBaseStageFlow, timeout: int
    ) -> Optional[List[str]]:
        # Waits until stage has started status then updates stage and returns server ips
        start_time = time()
        while time() < start_time + timeout:
            state = await self.publisher_client.update_instance(instance_id)
            status = state.pc_instance_status
            if status is stage.started_status:
                return state.server_ips
            if status is stage.failed_status:
                raise StageFailedException(
                    f"{instance_id} waiting for status {stage.started_status}, got {status} instead.",
                )
            self.logger.info(
                f"{instance_id} current status is {status}, waiting for {stage.started_status}."
            )
            await asyncio.sleep(DEFAULT_POLL_INTERVAL_SEC)
        raise StageTimeoutException(
            f"Poll {instance_id} status timed out after {timeout}s expecting status {stage.started_status}."
        )

    async def wait_stage_complete(
        self, publisher_id: str, partner_id: str, stage: PrivateComputationBaseStageFlow
    ) -> None:
        fail_status = stage.failed_status
        complete_status = stage.completed_status
        timeout = stage.timeout

        start_time = time()
        while time() < start_time + timeout:
            publisher_state, partner_state = await asyncio.gather(
                self.publisher_client.update_instance(instance_id=publisher_id),
                self.partner_client.update_instance(instance_id=partner_id),
            )
            if (
                publisher_state.pc_instance_status is complete_status
                and partner_state.pc_instance_status is complete_status
            ):
                return
            if (
                publisher_state.pc_instance_status is fail_status
                or partner_state.pc_instance_status is fail_status
            ):
                raise StageFailedException(
                    f"Stage {stage.name} failed. Publisher status: {publisher_state.pc_instance_status}. Partner status: {partner_state.pc_instance_status}."
                )
            self.logger.info(
                f"Publisher {publisher_id} status is {publisher_state.pc_instance_status}, Partner {partner_id} status is {partner_state.pc_instance_status}. Waiting for status {complete_status}."
            )
            await asyncio.sleep(DEFAULT_POLL_INTERVAL_SEC)
        raise StageTimeoutException(
            f"Stage {stage.name} timed out after {timeout}s. Publisher status: {publisher_state.pc_instance_status}. Partner status: {partner_state.pc_instance_status}."
        )
