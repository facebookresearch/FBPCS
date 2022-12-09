# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
PrivateComputationBaseStageFlow has a mapping from subclass name -> subclass.
This only works if the subclass is imported somewhere in the global namespace.
This logic will import all of the modules in the directory, which will guarantee
that each subclass is imported whenever PrivateComputationBaseStageFlow is imported.
"""

# TODO(T107598106): Create StageFlowSelector class and delete custom __init__.py logic

__all__ = [  # noqa: ignore=F405
    "private_computation_base_stage_flow",
    "private_computation_local_test_stage_flow",
    "private_computation_pcf2_lift_stage_flow",
    "private_computation_pcf2_lift_udp_stage_flow",
    "private_computation_pcf2_local_test_stage_flow",
    "private_computation_pcf2_stage_flow",
    "private_computation_stage_flow",
    "private_computation_mr_stage_flow",
    "private_computation_mr_pid_pcf2_lift_stage_flow",
    "private_computation_pid_only_test_stage_flow",
    "private_computation_mrpid_only_test_stage_flow",
    "private_computation_private_id_dfca_local_test_stage_flow",
    "private_computation_private_id_dfca_stage_flow",
]

from . import *  # noqa: ignore=F403
