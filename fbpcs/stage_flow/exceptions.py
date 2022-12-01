#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict


class StageFlowException(Exception):
    pass


class StageFlowStageNotFoundError(KeyError, StageFlowException):
    pass


class StageFlowDuplicateStatusError(ValueError, StageFlowException):
    pass
