/*
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <map>
#include <string>

#include <re2/re2.h>

#include "folly/json.h"
#include "folly/logging/xlog.h"

#include "../common/Csv.h"

#include "AttributionMetrics.h"
#include "fbpcs/emp_games/attribution/AttributionOptions.h"

namespace measurement::private_attribution {

static const std::vector<int64_t> getInnerArray(std::string& str) {
  // Strip the brackets [] before splitting into individual timestamp values
  auto innerString = str;
  innerString.erase(
      std::remove(innerString.begin(), innerString.end(), '['),
      innerString.end());
  innerString.erase(
      std::remove(innerString.begin(), innerString.end(), ']'),
      innerString.end());
  auto innerVals = private_measurement::csv::splitByComma(innerString, false);

  std::vector<int64_t> out;

  for (const auto& innerVal : innerVals) {
    if (!innerVal.empty()) {
      int64_t parsed = 0;
      std::istringstream iss{innerVal};
      iss >> parsed;
      out.push_back(parsed);
    }
  }

  return out;
}


static const std::vector<Touchpoint> parseTouchpoints(
    const int lineNo,
    const std::vector<std::string>& header,
    const std::vector<std::string>& parts) {
  std::vector<int64_t> adIds;
  std::vector<int64_t> timestamps;
  std::vector<int64_t> isClicks;
  std::vector<int64_t> campaignMetadata;
  for (std::vector<std::string>::size_type i = 0; i < header.size(); ++i) {
    auto column = header[i];
    auto value = parts[i];
    if (column == "ad_ids") {
      adIds = getInnerArray(value);
    } else if (column == "timestamps") {
      timestamps = getInnerArray(value);
    } else if (column == "is_click") {
      isClicks = getInnerArray(value);
    } else if (column == "campaign_metadata") {
      campaignMetadata = getInnerArray(value);
    }
  }

  CHECK_EQ(adIds.size(), timestamps.size())
      << "Ad ids and timestamps arrays are not the same length.";
  CHECK_EQ(adIds.size(), isClicks.size())
      << "Ad ids and is_click arrays are not the same length.";
  CHECK_LE(adIds.size(), FLAGS_max_num_touchpoints)
      << "Number of touchpoints exceeds the maximum allowed value.";
  CHECK_EQ(adIds.size(), campaignMetadata.size())
      << "Ad ids and campaign_metadata arrays are not the same length.";

  // TODO: right now we use 0,1,2,.... as impression id. In future,
  // we either get rid of the id altogether or use some kind of
  // (ad_id, ts) tuple, or some kind of id that is synchronized
  // with the caller. Id is unique per row only.
  std::vector<int64_t> unique_ids;
  for (std::vector<int64_t>::size_type i=0; i<timestamps.size(); i++){
      unique_ids.push_back(static_cast<int64_t>(i));
  }

  const std::unordered_set<int64_t> idSet{unique_ids.begin(), unique_ids.end()};
  CHECK_EQ(idSet.size(), timestamps.size())
      << "Found non-unique id for line " << lineNo << ". "
      << "This implementation currently only supports unique touchpoint ids per user.";

  std::vector<Touchpoint> tps;
  for (std::vector<int64_t>::size_type i = 0; i < adIds.size(); i++) {
    tps.push_back(Touchpoint{
        /* id */ unique_ids.at(i),
        /* isClick */ isClicks.at(i) == 1,
        /* adId */ adIds.at(i),
        /* ts */ timestamps.at(i),
        /* campaignMetadata */ campaignMetadata.at(i)});
  }

  return tps;
}

static const std::vector<Conversion> parseConversions(
    const std::vector<std::string>& header,
    const std::vector<std::string>& parts) {
  std::vector<int64_t> convTimestamps;
  std::vector<int64_t> convValues;
  std::vector<int64_t> convMetadata;

  for (std::vector<std::string>::size_type i = 0; i < header.size(); ++i) {
    auto column = header[i];
    auto value = parts[i];

    if (column == "conversion_timestamps") {
      convTimestamps = getInnerArray(value);
    } else if (column == "conversion_values") {
      convValues = getInnerArray(value);
    } else if (column == "conversion_metadata") {
      convMetadata = getInnerArray(value);
    }
  }

  CHECK_EQ(convTimestamps.size(), convValues.size())
      << "Conversion timetamps and conversion value arrays are not the same length.";
  CHECK_EQ(convTimestamps.size(), convMetadata.size())
      << "Conversion timetamps and  arrays are not the same length.";
  CHECK_LE(convTimestamps.size(), FLAGS_max_num_conversions)
      << "Number of conversions exceeds the maximum allowed value.";

  std::vector<Conversion> convs;
  for (std::vector<int64_t>::size_type i = 0; i < convTimestamps.size(); i++) {
    convs.push_back(Conversion{
        /* ts */ convTimestamps.at(i),
        /* value */ convValues.at(i),
        /* metadata */ convMetadata.at(i)});
  }

  return convs;
}

AttributionInputMetrics::AttributionInputMetrics(
    int myRole,
    std::string attributionRulesStr,
    std::string aggregationFormatNamesStr,
    std::filesystem::path filepath) {
  XLOGF(INFO, "Reading CSV {}", filepath.string());

  // Parse the passed attribution rules
  if (myRole == PUBLISHER) {
    auto attributionRuleNames =
        private_measurement::csv::splitByComma(attributionRulesStr, false);
    CHECK_GT(attributionRuleNames.size(), 0) << "No attribution rules found";

    for (auto name : attributionRuleNames) {
      attributionRules_.push_back(AttributionRule::fromNameOrThrow(name));
    }
  }

  // Parse the passed aggregation formats
  if (myRole == PUBLISHER) {
    auto aggregationFormatNames = private_measurement::csv::splitByComma(
        aggregationFormatNamesStr, false);
    CHECK_GT(aggregationFormatNames.size(), 0)
        << "No aggregation formats found";

    for (auto name : aggregationFormatNames) {
      aggregationFormats_.push_back(getAggregationFormatFromNameOrThrow(name));
    }
  }

  // Parse the input CSV
  auto lineNo = 0;
  bool success = private_measurement::csv::readCsv(
      filepath,
      [&](const std::vector<std::string>& header,
          const std::vector<std::string>& parts) {
        if (lineNo == 0) {
          XLOGF(DBG, "{}", private_measurement::vecToString(header));
        }
        XLOGF(DBG, "{}: {}", lineNo, private_measurement::vecToString(parts));

        for (std::vector<std::string>::size_type i = 0; i < header.size(); ++i) {
          auto column = header[i];
          auto value = parts[i];

          if (column == "id_") {
            int64_t parsed = 0;
            std::istringstream iss{value};
            iss >> parsed;
            ids_.push_back(parsed);
          }
        }

        if (myRole == PUBLISHER) {
          tpArrays_.push_back(parseTouchpoints(lineNo, header, parts));
        } else {
          convArrays_.push_back(parseConversions(header, parts));
        }

        lineNo++;
      });

  if (!success) {
    XLOGF(FATAL, "Failed to read input file {},", filepath.string());
  }
}
} // namespace measurement::private_attribution
