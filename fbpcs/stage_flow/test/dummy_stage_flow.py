#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

from enum import auto, Enum

from fbpcs.stage_flow.stage_flow import StageFlow, StageFlowData


class DummyStageFlowStatus(Enum):
    STAGE_1_STARTED = auto()
    STAGE_1_COMPLETED = auto()
    STAGE_1_FAILED = auto()
    STAGE_2_STARTED = auto()
    STAGE_2_COMPLETED = auto()
    STAGE_2_FAILED = auto()
    STAGE_3_STARTED = auto()
    STAGE_3_COMPLETED = auto()
    STAGE_3_FAILED = auto()


DummyStageFlowData = StageFlowData[DummyStageFlowStatus]


class DummyStageFlow(StageFlow):
    STAGE_1 = DummyStageFlowData(
        started_status=DummyStageFlowStatus.STAGE_1_STARTED,
        completed_status=DummyStageFlowStatus.STAGE_1_COMPLETED,
        failed_status=DummyStageFlowStatus.STAGE_1_FAILED,
    )
    STAGE_2 = DummyStageFlowData(
        started_status=DummyStageFlowStatus.STAGE_2_STARTED,
        completed_status=DummyStageFlowStatus.STAGE_2_COMPLETED,
        failed_status=DummyStageFlowStatus.STAGE_2_FAILED,
    )
    STAGE_3 = DummyStageFlowData(
        started_status=DummyStageFlowStatus.STAGE_3_STARTED,
        completed_status=DummyStageFlowStatus.STAGE_3_COMPLETED,
        failed_status=DummyStageFlowStatus.STAGE_3_FAILED,
    )
