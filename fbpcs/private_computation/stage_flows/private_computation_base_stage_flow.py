#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

from abc import abstractmethod
from dataclasses import dataclass
from typing import Type, TypeVar

from fbpcs.private_computation.entity.private_computation_status import (
    PrivateComputationInstanceStatus,
)

from fbpcs.private_computation.service.private_computation_stage_service import (
    PrivateComputationStageService,
    PrivateComputationStageServiceArgs,
)

from fbpcs.private_computation.stage_flows.exceptions import (
    PCStageFlowNotFoundException,
)

from fbpcs.private_computation.stage_flows.stage_selector import StageSelector

from fbpcs.stage_flow.stage_flow import StageFlow, StageFlowData

C = TypeVar("C", bound="PrivateComputationBaseStageFlow")
DEFAULT_STAGE_TIMEOUT_IN_SEC: int = 60 * 60  # 1 hour


@dataclass(frozen=True)
class PrivateComputationStageFlowData(StageFlowData[PrivateComputationInstanceStatus]):
    is_joint_stage: bool
    timeout: int = DEFAULT_STAGE_TIMEOUT_IN_SEC
    is_retryable: bool = True


class PrivateComputationBaseStageFlow(StageFlow):
    def __init__(self, data: PrivateComputationStageFlowData) -> None:
        super().__init__()
        self.initialized_status: PrivateComputationInstanceStatus = (
            data.initialized_status
        )
        self.started_status: PrivateComputationInstanceStatus = data.started_status
        self.failed_status: PrivateComputationInstanceStatus = data.failed_status
        self.completed_status: PrivateComputationInstanceStatus = data.completed_status
        self.is_joint_stage: bool = data.is_joint_stage
        self.timeout: int = data.timeout
        self.is_retryable: bool = data.is_retryable

    @classmethod
    def cls_name_to_cls(cls: Type[C], name: str) -> Type[C]:
        """
        Converts the name of an existing stage flow subclass into the subclass object

        Arguments:
            name: The name of a PrivateComputationBaseStageFlow subclass

        Returns:
            A subclass of PrivateComputationBaseStageFlow

        Raises:
            PCStageFlowNotFoundException: raises when no subclass with the name 'name' is found
        """
        for subclass in cls.__subclasses__():
            if name == subclass.__name__:
                return subclass
        raise PCStageFlowNotFoundException(
            f"Could not find subclass with {name=}. Make sure it has been imported in stage_flows/__init__.py"
        )

    @classmethod
    def get_cls_name(cls: Type[C]) -> str:
        """Convenience wrapper around cls.__name__"""
        return cls.__name__

    @abstractmethod
    def get_stage_service(
        self, args: "PrivateComputationStageServiceArgs"
    ) -> "PrivateComputationStageService":
        """
        Maps StageFlow instances to StageService instances

        Arguments:
            args: Common arguments initialized in PrivateComputationService that are consumed by stage services

        Returns:
            An instantiated StageService object corresponding to the StageFlow enum member caller.

        Raises:
            NotImplementedError: The subclass doesn't implement a stage service for a given StageFlow enum member
        """
        raise NotImplementedError(
            f"get_stage_service not implemented for {self.__class__}"
        )

    def get_default_stage_service(
        self,
        args: PrivateComputationStageServiceArgs,
    ) -> PrivateComputationStageService:
        stage = StageSelector.get_stage_service(self, args)
        if stage is None:
            raise NotImplementedError(f"No stage service configured for {self}")
        return stage
