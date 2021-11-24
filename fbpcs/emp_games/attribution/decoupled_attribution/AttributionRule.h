/*
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#pragma once

#include <stdexcept>

#include <fmt/format.h>

#include "fbpcs/emp_games/attribution/decoupled_attribution/Conversion.h"
#include "fbpcs/emp_games/attribution/decoupled_attribution/Touchpoint.h"

namespace aggregation::private_attribution {

struct AttributionRule {
  // Integer that should uniquely identify this attribution rule. Used
  // to synchronize between the publisher and partner
  const int64_t id;

  // Human readable name for the this attribution rule. The publisher will
  // pass in a list of names, and the output json will be keyed by names
  const std::string name;

  // time window for attribution, in seconds
  const int64_t window_in_sec;

  // Should return true if the given touchpoint is eligible to be attributed
  // to the given conversion
  const std::function<
      const emp::Bit(const PrivateTouchpoint&, const PrivateConversion&)>
      isAttributable;

  // Should return true if the new touchpoint is preferred over the old
  // touchpoint. Because whether or not newTp and oldTp is attributable is
  // private, this function will be called for all potentially attributable
  // touchpoint pairs. However, in practice, this function can assume that
  // both the new and old touchpoint are attributable as the caller will
  // ensure that the result of this is properly & with the result of
  // isAttributable for both oldTp and newTp.
  const std::function<const emp::Bit(
      const PrivateTouchpoint& newTp,
      const PrivateTouchpoint& oldTp)>
      isNewTouchpointPreferred;

  // Constructors for attribution rules, which can be found in
  // AttributionRule.cpp
  static const AttributionRule fromNameOrThrow(const std::string& name);
  static const AttributionRule fromIdOrThrow(int64_t id);
};

} // namespace aggregation::private_attribution
