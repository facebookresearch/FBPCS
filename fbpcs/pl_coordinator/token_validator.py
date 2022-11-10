#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

import json
from typing import Optional, Tuple

from fbpcs.pl_coordinator.bolt_graphapi_client import (
    BoltGraphAPIClient,
    BoltGraphAPICreateInstanceArgs,
)
from fbpcs.pl_coordinator.exceptions import GraphAPITokenValidationError
from fbpcs.pl_coordinator.token_validation_rules import (
    DebugTokenData,
    TokenRuleException,
    TokenValidationRule,
    TokenValidationRuleType,
)


COMMON_RULES: Tuple[TokenValidationRule, ...] = (
    TokenValidationRule.TOKEN_USER_TYPE,
    TokenValidationRule.TOKEN_VALID,
    TokenValidationRule.TOKEN_EXPIRY,
    TokenValidationRule.TOKEN_DATA_ACCESS_EXPIRY,
    TokenValidationRule.TOKEN_PERMISSIONS,
)


class TokenValidator:
    def __init__(
        self, client: BoltGraphAPIClient[BoltGraphAPICreateInstanceArgs]
    ) -> None:
        self.client = client
        self.debug_token_data: Optional[DebugTokenData] = None

    def _load_data(self, rule: TokenValidationRule) -> None:
        if (
            rule.rule_type is TokenValidationRuleType.COMMON
            and self.debug_token_data is None
        ):
            _debug_token_data = json.loads(self.client.get_debug_token_data().text).get(
                "data"
            )
            # pyre-ignore[16]
            self.debug_token_data = DebugTokenData.from_dict(_debug_token_data)

    def validate_common_rules(self) -> None:
        for rule in COMMON_RULES:
            self.validate_rule(rule)

    def validate_rule(self, rule: TokenValidationRule) -> None:
        ## prepare data
        self._load_data(rule=rule)
        if rule.rule_type is TokenValidationRuleType.COMMON:
            if self.debug_token_data is None:
                raise GraphAPITokenValidationError.make_error(rule=rule)

            try:
                rule.rule_checker(self.debug_token_data)
            except TokenRuleException as e:
                raise GraphAPITokenValidationError.make_error(rule=rule, cause=str(e))

        return None
