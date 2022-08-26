#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import logging

from fbpcs.private_computation.entity.pid_mr_config import Protocol

from fbpcs.private_computation.entity.private_computation_status import (
    PrivateComputationInstanceStatus,
)
from fbpcs.private_computation.service.id_spine_combiner_stage_service import (
    IdSpineCombinerStageService,
)
from fbpcs.private_computation.service.pcf2_aggregation_stage_service import (
    PCF2AggregationStageService,
)
from fbpcs.private_computation.service.pcf2_attribution_stage_service import (
    PCF2AttributionStageService,
)
from fbpcs.private_computation.service.pid_mr_stage_service import PIDMRStageService
from fbpcs.private_computation.service.private_computation_stage_service import (
    PrivateComputationStageService,
    PrivateComputationStageServiceArgs,
)
from fbpcs.private_computation.stage_flows.private_computation_base_stage_flow import (
    PrivateComputationBaseStageFlow,
    PrivateComputationStageFlowData,
)


class PrivateComputationMRStageFlow(PrivateComputationBaseStageFlow):
    """
    - Private Lift Stage Flow with UNION_PID_MR_MULTIKEY -
    This enum lists all of the supported stage types and maps to their possible statuses.
    It also provides methods to get information about the next or previous stage.

    NOTE: The order in which the enum members appear is the order in which the stages are intended
    to run. The _order_ variable is used to ensure member order is consistent (class attribute, removed during class creation).
    An exception is raised at runtime if _order_ is inconsistent with the actual member order.
    """

    # Specifies the order of the stages. Don't change this unless you know what you are doing.
    # pyre-fixme[15]: `_order_` overrides attribute defined in `Enum` inconsistently.
    _order_ = "CREATED PC_PRE_VALIDATION UNION_PID_MR_MULTIKEY ID_SPINE_COMBINER RESHARD PCF2_ATTRIBUTION PCF2_AGGREGATION AGGREGATE POST_PROCESSING_HANDLERS"
    # Regarding typing fixme above, Pyre appears to be wrong on this one. _order_ only appears in the EnumMeta metaclass __new__ method
    # and is not actually added as a variable on the enum class. I think this is why pyre gets confused.

    CREATED = PrivateComputationStageFlowData(
        PrivateComputationInstanceStatus.CREATION_STARTED,
        PrivateComputationInstanceStatus.CREATED,
        PrivateComputationInstanceStatus.CREATION_FAILED,
        False,
    )
    PC_PRE_VALIDATION = PrivateComputationStageFlowData(
        PrivateComputationInstanceStatus.PC_PRE_VALIDATION_STARTED,
        PrivateComputationInstanceStatus.PC_PRE_VALIDATION_COMPLETED,
        PrivateComputationInstanceStatus.PC_PRE_VALIDATION_FAILED,
        False,
    )
    UNION_PID_MR_MULTIKEY = PrivateComputationStageFlowData(
        PrivateComputationInstanceStatus.PID_MR_STARTED,
        PrivateComputationInstanceStatus.PID_MR_COMPLETED,
        PrivateComputationInstanceStatus.PID_MR_FAILED,
        False,
    )
    ID_SPINE_COMBINER = PrivateComputationStageFlowData(
        PrivateComputationInstanceStatus.ID_SPINE_COMBINER_STARTED,
        PrivateComputationInstanceStatus.ID_SPINE_COMBINER_COMPLETED,
        PrivateComputationInstanceStatus.ID_SPINE_COMBINER_FAILED,
        False,
    )
    RESHARD = PrivateComputationStageFlowData(
        PrivateComputationInstanceStatus.RESHARD_STARTED,
        PrivateComputationInstanceStatus.RESHARD_COMPLETED,
        PrivateComputationInstanceStatus.RESHARD_FAILED,
        False,
    )
    PCF2_ATTRIBUTION = PrivateComputationStageFlowData(
        PrivateComputationInstanceStatus.PCF2_ATTRIBUTION_STARTED,
        PrivateComputationInstanceStatus.PCF2_ATTRIBUTION_COMPLETED,
        PrivateComputationInstanceStatus.PCF2_ATTRIBUTION_FAILED,
        True,
    )
    PCF2_AGGREGATION = PrivateComputationStageFlowData(
        PrivateComputationInstanceStatus.PCF2_AGGREGATION_STARTED,
        PrivateComputationInstanceStatus.PCF2_AGGREGATION_COMPLETED,
        PrivateComputationInstanceStatus.PCF2_AGGREGATION_FAILED,
        True,
    )
    AGGREGATE = PrivateComputationStageFlowData(
        PrivateComputationInstanceStatus.AGGREGATION_STARTED,
        PrivateComputationInstanceStatus.AGGREGATION_COMPLETED,
        PrivateComputationInstanceStatus.AGGREGATION_FAILED,
        True,
    )
    POST_PROCESSING_HANDLERS = PrivateComputationStageFlowData(
        PrivateComputationInstanceStatus.POST_PROCESSING_HANDLERS_STARTED,
        PrivateComputationInstanceStatus.POST_PROCESSING_HANDLERS_COMPLETED,
        PrivateComputationInstanceStatus.POST_PROCESSING_HANDLERS_FAILED,
        False,
    )

    def get_stage_service(
        self, args: PrivateComputationStageServiceArgs
    ) -> PrivateComputationStageService:
        """
        Maps PrivateComputationMRStageFlow instances to StageService instances

        Arguments:
            args: Common arguments initialized in PrivateComputationService that are consumed by stage services

        Returns:
            An instantiated StageService object corresponding to the StageFlow enum member caller.

        Raises:
            NotImplementedError: The subclass doesn't implement a stage service for a given StageFlow enum member
        """
        logging.info("Start MR stage flow")
        if self is self.UNION_PID_MR_MULTIKEY:
            if args.workflow_svc is None:
                raise NotImplementedError("workflow_svc is None")

            return PIDMRStageService(args.workflow_svc)
        elif self is self.ID_SPINE_COMBINER:
            return IdSpineCombinerStageService(
                args.onedocker_svc,
                args.onedocker_binary_config_map,
                protocol_type=Protocol.MR_PID_PROTOCOL.value,
            )
        elif self is self.PCF2_ATTRIBUTION:
            return PCF2AttributionStageService(
                args.onedocker_binary_config_map,
                args.mpc_svc,
            )
        elif self is self.PCF2_AGGREGATION:
            return PCF2AggregationStageService(
                args.onedocker_binary_config_map,
                args.mpc_svc,
            )
        # TODO (pnethagani): enable the other stages after test
        # elif self is self.COMPUTE:
        #     return ComputeMetricsStageService(
        #         args.onedocker_binary_config_map,
        #         args.mpc_svc,
        #     )

        # elif self is self.ID_MATCH_POST_PROCESS:
        #     return PostProcessingStageService(
        #         args.storage_svc, args.pid_post_processing_handlers
        #     )
        else:
            return self.get_default_stage_service(args)
