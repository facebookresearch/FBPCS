#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

from dataclasses import dataclass
from typing import Optional

from dataclasses_json import dataclass_json

ONEDOCKER_REPOSITORY_PATH = "ONEDOCKER_REPOSITORY_PATH"
DEFAULT_BINARY_REPOSITORY = (
    "https://one-docker-repository-prod.s3.us-west-2.amazonaws.com/"
)


@dataclass_json
@dataclass
class OneDockerBinaryConfig:
    tmp_directory: str
    binary_version: str
    repository_path: Optional[str] = None
