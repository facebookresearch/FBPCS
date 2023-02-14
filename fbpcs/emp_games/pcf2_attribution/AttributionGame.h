/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#pragma once

#include "fbpcf/frontend/mpcGame.h"
#include "fbpcs/emp_games/common/Debug.h"
#include "fbpcs/emp_games/common/Util.h"
#include "fbpcs/emp_games/pcf2_attribution/AttributionMetrics.h"
#include "fbpcs/emp_games/pcf2_attribution/AttributionOptions.h"
#include "fbpcs/emp_games/pcf2_attribution/AttributionRule.h"
#include "fbpcs/emp_games/pcf2_attribution/Constants.h"
#include "fbpcs/emp_games/pcf2_attribution/Conversion.h"
#include "fbpcs/emp_games/pcf2_attribution/Touchpoint.h"
#include "folly/logging/xlog.h"

namespace pcf2_attribution {

template <int schedulerId, common::InputEncryption inputEncryption>
class AttributionGame : public fbpcf::frontend::MpcGame<schedulerId> {
 public:
  explicit AttributionGame(
      std::unique_ptr<fbpcf::scheduler::IScheduler> scheduler)
      : fbpcf::frontend::MpcGame<schedulerId>(std::move(scheduler)) {}

  AttributionOutputMetrics computeAttributions(
      const int myRole,
      const AttributionInputMetrics<inputEncryption>& inputData);

  using PrivateTouchpointT = PrivateTouchpoint<schedulerId>;

  using PrivateConversionT = PrivateConversion<schedulerId, inputEncryption>;

  std::tuple<
      std::vector<std::vector<std::vector<SecTimestamp<schedulerId>>>>,
      std::vector<PrivateTouchpointT>,
      std::vector<PrivateConversionT>,
      std::vector<
          std::shared_ptr<const AttributionRule<schedulerId, inputEncryption>>>,
      std::vector<int64_t>>
  prepareMpcInputs(
      const int myRole,
      const AttributionInputMetrics<inputEncryption>& inputData);

  AttributionOutputMetrics computeAttributions_impl(
      std::vector<std::vector<std::vector<SecTimestamp<schedulerId>>>>&
          thresholdArraysForEachRule,
      std::vector<PrivateTouchpointT>& tpArrays,
      std::vector<PrivateConversionT>& convArrays,
      std::vector<
          std::shared_ptr<const AttributionRule<schedulerId, inputEncryption>>>&
          attributionRules,
      std::vector<int64_t>& ids);

  /**
   * Publisher shares attribution rules with partner.
   */
  std::vector<
      std::shared_ptr<const AttributionRule<schedulerId, inputEncryption>>>
  shareAttributionRules(
      const int myRole,
      const std::vector<std::string>& attributionRuleNames);

  /**
   * Publisher shares touchpoints with partner.
   */
  std::vector<PrivateTouchpointT> privatelyShareTouchpoints(
      const std::vector<Touchpoint>& touchpoints);

  /**
   * Partner shares conversions with publisher.
   */
  std::vector<PrivateConversionT> privatelyShareConversions(
      const std::vector<Conversion>& conversions);

  /**
   * Publisher shares touchpoints thresholds, to optimize attribution
   * computation.
   */
  std::vector<std::vector<SecTimestamp<schedulerId>>> privatelyShareThresholds(
      const std::vector<Touchpoint>& touchpoints,
      const std::vector<PrivateTouchpointT>& privateTouchpoints,
      const AttributionRule<schedulerId, inputEncryption>& attributionRule,
      size_t batchSize);

  /**
   * Retrieve the original Ad Ids from touchpoint data
   */
  const std::vector<uint64_t> retrieveValidOriginalAdIds(
      const int myRole,
      std::vector<Touchpoint>& touchpoints);
  /**
   * Create a compression map of the original Ad Id with the compressed Ad ID
   */

  void replaceAdIdWithCompressedAdId(
      std::vector<Touchpoint>& touchpoints,
      std::vector<uint64_t>& validOriginalAdIds);

  void putAdIdMappingJson(
      const CompressedAdIdToOriginalAdId& maps,
      std::string outputPath);

  /**
   * Helper method for computing attributions.
   */
  const std::vector<SecBit<schedulerId>> computeAttributionsHelper(
      const std::vector<PrivateTouchpoint<schedulerId>>& touchpoints,
      const std::vector<PrivateConversion<schedulerId, inputEncryption>>&
          conversions,
      const AttributionRule<schedulerId, inputEncryption>& attributionRule,
      const std::vector<std::vector<SecTimestamp<schedulerId>>>& thresholds,
      size_t batchSize);

  const std::vector<AttributionReformattedOutputFmt<schedulerId>>
  computeAttributionsHelperV2(
      const std::vector<PrivateTouchpoint<schedulerId>>& touchpoints,
      const std::vector<PrivateConversion<schedulerId, inputEncryption>>&
          conversions,
      const AttributionRule<schedulerId, inputEncryption>& attributionRule,
      const std::vector<std::vector<SecTimestamp<schedulerId>>>& thresholds,
      size_t batchSize);
};

} // namespace pcf2_attribution

#include "fbpcs/emp_games/pcf2_attribution/AttributionGame_impl.h"
