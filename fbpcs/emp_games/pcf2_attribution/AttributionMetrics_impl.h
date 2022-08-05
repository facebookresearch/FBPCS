/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#include <re2/re2.h>
#include <filesystem>
#include <fstream>
#include <map>
#include <unordered_set>

#include "fbpcs/emp_games/common/Constants.h"
#include "fbpcs/emp_games/common/Util.h"
#include "fbpcs/emp_games/pcf2_attribution/AttributionOptions.h"

namespace pcf2_attribution {

template <bool usingBatch, common::InputEncryption inputEncryption>
const std::vector<ParsedTouchpoint>
AttributionInputMetrics<usingBatch, inputEncryption>::parseTouchpoints(
    const int myRole,
    const int lineNo,
    const std::vector<std::string>& header,
    const std::vector<std::string>& parts) {
  std::vector<uint64_t> timestamps;
  std::vector<bool> isClicks;
  std::vector<uint64_t> targetId;
  std::vector<uint64_t> actionType;
  std::vector<uint64_t> adIds;
  bool targetIdPresent = false;
  bool actionTypePresent = false;

  for (auto i = 0U; i < header.size(); ++i) {
    const auto& column = header[i];
    const auto& value = parts[i];
    if (column == "timestamps") {
      timestamps = common::getInnerArray<uint64_t>(value);
    } else if (column == "is_click") {
      if constexpr (inputEncryption == common::InputEncryption::Xor) {
        // input is 64-bit secret shares
        std::vector<uint64_t> isClickShares =
            common::getInnerArray<uint64_t>(value);
        for (auto isClickShare : isClickShares) {
          // suffices to read last bit
          isClicks.push_back(isClickShare & 1);
        }
      } else {
        isClicks = common::getInnerArray<bool>(value);
      }
    } else if (column == "target_id") {
      targetIdPresent = true;
      targetId = common::getInnerArray<uint64_t>(value);
    } else if (column == "action_type") {
      actionTypePresent = true;
      actionType = common::getInnerArray<uint64_t>(value);
    } else if (column == "ad_ids") {
      adIds = common::getInnerArray<uint64_t>(value);
    }
  }

  CHECK_EQ(timestamps.size(), isClicks.size())
      << "timestamps arrays and is_click arrays are not the same length.";
  CHECK_LE(timestamps.size(), FLAGS_max_num_touchpoints)
      << "Number of touchpoints exceeds the maximum allowed value.";
  CHECK_EQ(timestamps.size(), adIds.size())
      << "timestamps arrays and original ad ID arrays are not the same length.";

  if (!timestamps.empty()) {
    if (targetIdPresent) {
      CHECK_EQ(timestamps.size(), targetId.size())
          << "timestamps arrays and target_id arrays are not the same length.";
    }
    if (actionTypePresent) {
      CHECK_EQ(timestamps.size(), actionType.size())
          << "timestamps arrays and action_type arrays are not the same length.";
    }
  }

  std::vector<ParsedTouchpoint> tps;
  tps.reserve(static_cast<std::size_t>(FLAGS_max_num_touchpoints));

  for (size_t i = 0U; i < timestamps.size(); ++i) {
    tps.push_back(ParsedTouchpoint{
        /* id */ static_cast<std::int64_t>(i),
        /* isClick */ isClicks.at(i) == 1,
        /* ts */ timestamps.at(i),
        /* targetId */ !targetId.empty() ? targetId.at(i) : 0ULL,
        /* actionType */ !actionType.empty() ? actionType.at(i) : 0ULL,
        /* original adId */ adIds.at(i),
        /* compressed adId */ 0});
  }

  // The input received by attribution game from data processing is sorted by
  // rows, but in each row the internal columns are not sorted. Thus sorting the
  // touchpoints based on timestamp, where views come before clicks.
  // If the input is encrypted, the sorting has to be done in the data
  // processing step.
  if constexpr (inputEncryption != common::InputEncryption::Xor) {
    std::sort(tps.begin(), tps.end());
  }

  // Add padding at the end of the input data for publisher; partner data
  // consists only of padded data
  if (tps.size() < static_cast<std::size_t>(FLAGS_max_num_touchpoints)) {
    tps.resize(static_cast<std::size_t>(FLAGS_max_num_touchpoints));
  }
  return tps;
}

template <bool usingBatch, common::InputEncryption inputEncryption>
const std::vector<ParsedConversion>
AttributionInputMetrics<usingBatch, inputEncryption>::parseConversions(
    const int myRole,
    const std::vector<std::string>& header,
    const std::vector<std::string>& parts) {
  std::vector<uint64_t> convTimestamps;
  std::vector<uint64_t> targetId;
  std::vector<uint64_t> actionType;
  std::vector<uint64_t> convValue;
  bool targetIdPresent = false;
  bool actionTypePresent = false;

  for (auto i = 0; i < header.size(); ++i) {
    const auto& column = header[i];
    const auto& value = parts[i];

    if (column == "conversion_timestamps") {
      convTimestamps = common::getInnerArray<uint64_t>(value);
    } else if (column == "conversion_target_id") {
      targetIdPresent = true;
      targetId = common::getInnerArray<uint64_t>(value);
    } else if (column == "conversion_action_type") {
      actionTypePresent = true;
      actionType = common::getInnerArray<uint64_t>(value);
    } else if (column == "conversion_values") {
      convValue = common::getInnerArray<uint64_t>(value);
    }
  }

  CHECK_LE(convTimestamps.size(), FLAGS_max_num_conversions)
      << "Number of conversions exceeds the maximum allowed value.";
  CHECK_EQ(convTimestamps.size(), convValue.size())
      << "Conversion timestamps arrays and converison value arrays are not the same length.";

  if (convTimestamps.size() != 0) {
    if (targetIdPresent) {
      CHECK_EQ(convTimestamps.size(), targetId.size())
          << "Conversion timestamps arrays and target_id arrays are not the same length.";
    }
    if (actionTypePresent) {
      CHECK_EQ(convTimestamps.size(), actionType.size())
          << "Conversion timestamps arrays and action_type arrays are not the same length.";
    }
  }

  std::vector<ParsedConversion> convs;
  for (auto i = 0U; i < convTimestamps.size(); ++i) {
    convs.push_back(ParsedConversion{
        /* ts */ convTimestamps.at(i),
        /* targetId */ !targetId.empty() ? targetId.at(i) : 0ULL,
        /* actionType */ !actionType.empty() ? actionType.at(i) : 0ULL,
        /* convValue */ convValue.at(i)});
  }

  // Sorting conversions based on timestamp. If the input is encrypted, this has
  // to be done in the data processing step.
  if constexpr (inputEncryption == common::InputEncryption::Plaintext) {
    std::sort(convs.begin(), convs.end());
  }

  // Add padding at the end of the input data for partner; publisher data
  // consists only of padded data
  if (convs.size() < static_cast<std::size_t>(FLAGS_max_num_conversions)) {
    convs.resize(static_cast<std::size_t>(FLAGS_max_num_conversions));
  }
  return convs;
}

template <bool usingBatch, common::InputEncryption inputEncryption>
const std::vector<TouchpointT<usingBatch>>
AttributionInputMetrics<usingBatch, inputEncryption>::
    convertParsedTouchpointsToTouchpoints(
        const std::vector<std::vector<ParsedTouchpoint>>& parsedTouchpoints) {
  std::vector<TouchpointT<usingBatch>> touchpoints;

  if constexpr (usingBatch) {
    std::vector<std::vector<int64_t>> ids(
        FLAGS_max_num_touchpoints, std::vector<int64_t>{});
    std::vector<std::vector<bool>> isClicks(
        FLAGS_max_num_touchpoints, std::vector<bool>{});
    std::vector<std::vector<uint64_t>> timestamps(
        FLAGS_max_num_touchpoints, std::vector<uint64_t>{});
    std::vector<std::vector<uint64_t>> targetIds(
        FLAGS_max_num_touchpoints, std::vector<uint64_t>{});
    std::vector<std::vector<uint64_t>> actionTypes(
        FLAGS_max_num_touchpoints, std::vector<uint64_t>{});
    std::vector<std::vector<uint64_t>> originalAdIds(
        FLAGS_max_num_touchpoints, std::vector<uint64_t>{});
    std::vector<std::vector<uint64_t>> adIds(
        FLAGS_max_num_touchpoints, std::vector<uint64_t>{});

    // The touchpoints are parsed row by row, whereas the batches are across
    // rows.
    for (size_t i = 0; i < parsedTouchpoints.size(); ++i) {
      for (size_t j = 0; j < FLAGS_max_num_touchpoints; ++j) {
        auto parsedTouchpoint = parsedTouchpoints.at(i).at(j);
        ids.at(j).push_back(parsedTouchpoint.id);
        isClicks.at(j).push_back(parsedTouchpoint.isClick);
        timestamps.at(j).push_back(parsedTouchpoint.ts);
        targetIds.at(j).push_back(parsedTouchpoint.targetId);
        actionTypes.at(j).push_back(parsedTouchpoint.actionType);
        originalAdIds.at(j).push_back(parsedTouchpoint.originalAdId);
        adIds.at(j).push_back(parsedTouchpoint.adId);
      }
    }
    for (size_t i = 0; i < FLAGS_max_num_touchpoints; ++i) {
      touchpoints.push_back(Touchpoint<true>{
          ids.at(i),
          isClicks.at(i),
          timestamps.at(i),
          targetIds.at(i),
          actionTypes.at(i),
          originalAdIds.at(i),
          adIds.at(i)});
    }
  } else {
    for (size_t i = 0; i < parsedTouchpoints.size(); ++i) {
      std::vector<Touchpoint<false>> touchpointRow;
      for (auto& parsedTouchpoint : parsedTouchpoints.at(i)) {
        touchpointRow.push_back(Touchpoint<false>{
            parsedTouchpoint.id,
            parsedTouchpoint.isClick,
            parsedTouchpoint.ts,
            parsedTouchpoint.targetId,
            parsedTouchpoint.actionType,
            parsedTouchpoint.originalAdId,
            parsedTouchpoint.adId});
      }
      touchpoints.push_back(std::move(touchpointRow));
    }
  }
  return touchpoints;
}

template <bool usingBatch, common::InputEncryption inputEncryption>
const std::vector<ConversionT<usingBatch>>
AttributionInputMetrics<usingBatch, inputEncryption>::
    convertParsedConversionsToConversions(
        const std::vector<std::vector<ParsedConversion>>& parsedConversions) {
  std::vector<ConversionT<usingBatch>> conversions;

  if constexpr (usingBatch) {
    std::vector<std::vector<uint64_t>> timestamps(
        FLAGS_max_num_conversions, std::vector<uint64_t>{});
    std::vector<std::vector<uint64_t>> targetIds(
        FLAGS_max_num_touchpoints, std::vector<uint64_t>{});
    std::vector<std::vector<uint64_t>> actionTypes(
        FLAGS_max_num_touchpoints, std::vector<uint64_t>{});
    std::vector<std::vector<uint64_t>> values(
        FLAGS_max_num_touchpoints, std::vector<uint64_t>{});

    // The conversions are parsed row by row, whereas the batches are across
    // rows.
    for (const auto& oneBatchedParsedConversions : parsedConversions) {
      for (size_t j = 0; j < oneBatchedParsedConversions.size(); ++j) {
        timestamps.at(j).push_back(oneBatchedParsedConversions.at(j).ts);
        targetIds.at(j).push_back(oneBatchedParsedConversions.at(j).targetId);
        actionTypes.at(j).push_back(
            oneBatchedParsedConversions.at(j).actionType);
        values.at(j).push_back(oneBatchedParsedConversions.at(j).convValue);
      }
    }
    for (size_t i = 0; i < timestamps.size(); ++i) {
      conversions.push_back(Conversion<true>{
          timestamps.at(i), targetIds.at(i), actionTypes.at(i), values.at(i)});
    }
  } else {
    for (const auto& parsedRow : parsedConversions) {
      std::vector<Conversion<false>> conversionRow;
      for (const auto& parsedConversion : parsedRow) {
        conversionRow.push_back(Conversion<false>{
            parsedConversion.ts,
            parsedConversion.targetId,
            parsedConversion.actionType,
            parsedConversion.convValue});
      }
      conversions.push_back(std::move(conversionRow));
    }
  }
  return conversions;
}

template <bool usingBatch, common::InputEncryption inputEncryption>
AttributionInputMetrics<usingBatch, inputEncryption>::AttributionInputMetrics(
    int myRole,
    std::string attributionRulesStr,
    std::filesystem::path filepath) {
  XLOGF(INFO, "Reading CSV {}", filepath.string());

  // Parse the passed attribution rules
  if (myRole == common::PUBLISHER) {
    attributionRules_ =
        private_measurement::csv::splitByComma(attributionRulesStr, false);
  }

  // Parse the input CSV
  std::vector<std::vector<ParsedTouchpoint>> parsedTouchpoints;
  std::vector<std::vector<ParsedConversion>> parsedConversions;
  auto lineNo = 0;
  bool success = private_measurement::csv::readCsv(
      filepath,
      [&](const std::vector<std::string>& header,
          const std::vector<std::string>& parts) {
        if (lineNo == 0) {
          XLOGF(DBG, "{}", common::vecToString(header));
        }
        XLOGF(DBG, "{}: {}", lineNo, common::vecToString(parts));
        ids_.push_back(lineNo);

        parsedTouchpoints.push_back(
            parseTouchpoints(myRole, lineNo, header, parts));
        parsedConversions.push_back(parseConversions(myRole, header, parts));

        lineNo++;
      });

  if (!success) {
    XLOGF(FATAL, "Failed to read input file {},", filepath.string());
  }

  // Convert from parsed touchpoints and conversions to touchpoints and
  // conversions
  tpArrays_ = convertParsedTouchpointsToTouchpoints(parsedTouchpoints);
  convArrays_ = convertParsedConversionsToConversions(parsedConversions);
}

} // namespace pcf2_attribution
