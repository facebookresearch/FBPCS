# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Dict, Set
import re

INTEGER_REGEX = re.compile(r"^[0-9]+$")
TIMESTAMP_REGEX = re.compile(r"^[0-9]{10}$")
BASE64_REGEX = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")

UNFILTERED_ALL_REQUIRED_FIELDS: Set[str] = {
    'action_source',
    'conversion_value',
    'currency_type',
    'event_type',
    'timestamp',
}
UNFILTERED_ONE_OR_MORE_REQUIRED_FIELDS: Set[str] = {'email','device_id'}
UNFILTERED_FORMAT_VALIDATION_FOR_FIELD: Dict[str, re.Pattern] = {
    'email': re.compile(r"^[a-f0-9]{64}$"),
    'device_id': re.compile(r"^([a-f0-9]{32}|[a-f0-9-]{36})$"),
    'timestamp': TIMESTAMP_REGEX,
    'currency_type': re.compile(r"^[a-z]+$"),
    'conversion_value': INTEGER_REGEX,
    'action_source': re.compile(r"^(email|website|phone_call|chat|physical_store|system_generated|other)$"),
    'event_type': re.compile(r"^.+$"),
}

PA_ALL_REQUIRED_FIELDS: Set[str] = {
    'id_',
    'conversion_timestamp',
    'conversion_value',
    'conversion_metadata'
}

PA_FORMAT_VALIDATION_FOR_FIELD: Dict[str, re.Pattern] = {
    'id_': BASE64_REGEX,
    'conversion_timestamp': TIMESTAMP_REGEX,
    'conversion_value': INTEGER_REGEX,
    'conversion_metadata': INTEGER_REGEX,
}

PL_ALL_REQUIRED_FIELDS: Set[str] = {
    'id_',
    'event_timestamp',
    'value',
}

PL_FORMAT_VALIDATION_FOR_FIELD: Dict[str, re.Pattern] = {
    'id_': BASE64_REGEX,
    'event_timestamp': TIMESTAMP_REGEX,
    'value': INTEGER_REGEX,
}
