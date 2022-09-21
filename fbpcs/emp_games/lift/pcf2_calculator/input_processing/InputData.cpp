/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#include <glog/logging.h>
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <functional>
#include <string>

#include "fbpcs/emp_games/common/Csv.h"
#include "fbpcs/emp_games/lift/pcf2_calculator/input_processing/InputData.h"

namespace private_lift {

InputData::InputData(
    std::string filepath,
    LiftMPCType liftMpcType,
    bool computePublisherBreakdowns,
    int64_t epoch,
    int32_t numConversionsPerUser)
    : liftMpcType_{liftMpcType},
      computePublisherBreakdowns_{computePublisherBreakdowns},
      epoch_{epoch},
      numConversionsPerUser_{numConversionsPerUser} {
  auto readLine = [&](const std::vector<std::string>& header,
                      const std::vector<std::string>& parts) {
    ++numRows_;
    addFromCSV(header, parts);
  };

  if (!private_measurement::csv::readCsv(filepath, readLine)) {
    LOG(FATAL) << "Failed to read input file " << filepath;
  }
}

void InputData::setTimestamps(
    std::string& str,
    std::vector<std::vector<uint32_t>>& timestampArrays) {
  timestampArrays.emplace_back();
  // Strip the brackets [] before splitting into individual timestamp values
  auto innerString = str.substr(1, str.size() - 1);
  auto timestamps = private_measurement::csv::splitByComma(innerString, false);

  // Take up to numConversionsPerUser_ elements and ignore the rest
  for (std::size_t i = 0; i < timestamps.size() && i < numConversionsPerUser_;
       ++i) {
    std::istringstream iss{timestamps[i]};
    int64_t parsed = 0;
    iss >> parsed;
    if (iss.fail()) {
      LOG(FATAL) << "Failed to parse '" << iss.str() << "' to int64_t";
    }
    // secret-share-lift can have negative input timestamps
    if (liftMpcType_ == LiftMPCType::Standard && parsed < epoch_ &&
        parsed != 0) {
      LOG(FATAL) << "Timestamp " << parsed << " is before epoch " << epoch_
                 << ", which is unexpected.";
    }
    timestampArrays.back().push_back(parsed < epoch_ ? 0 : parsed - epoch_);
  }
}

void InputData::setValuesFields(std::string& str) {
  purchaseValueArrays_.emplace_back();
  if (liftMpcType_ == LiftMPCType::Standard) {
    purchaseValueSquaredArrays_.emplace_back();
  }
  // Strip the brackets [] before splitting into individual values
  auto innerString = str.substr(1, str.size() - 1);
  auto values = private_measurement::csv::splitByComma(innerString, false);
  // Take up to numConversionsPerUser_ elements and ignore the rest
  for (std::size_t i = 0; i < values.size() && i < numConversionsPerUser_;
       ++i) {
    int64_t parsed = 0;
    std::istringstream iss{values[i]};
    iss >> parsed;
    if (iss.fail()) {
      LOG(FATAL) << "Failed to parse '" << iss.str() << "' to int64_t";
    }
    purchaseValueArrays_.back().push_back(parsed);
    totalValue_ += parsed;
    // If this is secret_share lift, we can't pre-compute squared values
    if (liftMpcType_ == LiftMPCType::Standard) {
      purchaseValueSquaredArrays_.back().push_back(parsed * parsed);
    }
  }

  // For non-secret-share lift, we *can* use this valueSquared optimizations to
  // avoid doing addition/multiplication in MPC, though
  if (liftMpcType_ == LiftMPCType::Standard) {
    auto& valuesArr = purchaseValueArrays_.back();
    auto& valuesSquaredArr = purchaseValueSquaredArrays_.back();
    uint64_t acc = 0;
    // NOTE: Don't use `auto` here since it will give us std::size_t (which is
    // unsigned) and will underflow and cause an ASAN error.
    for (int64_t i = valuesArr.size() - 1; i >= 0; --i) {
      // 1. Add accumulation of total value seen so far iterating backwards
      acc += valuesArr.at(i);
      // 2. Set valuesSquared at this index as acc**2
      valuesSquaredArr.at(i) = acc * acc;
    }
    // Finally, update totalValueSquared with the *maximum possible* value,
    // which is what we just stored into the first value
    totalValueSquared_ += valuesSquaredArr.at(0);
  }
}

void InputData::addFromCSV(
    const std::vector<std::string>& header,
    const std::vector<std::string>& parts) {
  std::vector<std::string> featureValues;

  // These bools + int64_t allow us to create separate vectors for testPop and
  // controlPop without enforcing an ordering between oppFlag and testFlag.
  bool sawOppFlag = false;
  bool sawTestFlag = false;
  int64_t storedOpportunityFlag = 0;
  int64_t storedTestFlag = 0;

  for (std::size_t i = 0; i < header.size(); ++i) {
    auto column = header[i];
    auto value = parts[i];
    int64_t parsed = 0;
    std::istringstream iss{value};
    // Array columns and features may be parsed differently
    if (!(column == "opportunity_timestamps" || column == "event_timestamps" ||
          column == "values" || column == "id_")) {
      iss >> parsed;

      if (iss.fail()) {
        LOG(FATAL) << "Failed to parse '" << iss.str() << "' to int64_t";
      }
    }

    if (column == "opportunity") {
      sawOppFlag = true;
      if (sawTestFlag) {
        testPopulation_.push_back(parsed & storedTestFlag ? 1 : 0);
        controlPopulation_.push_back(
            (parsed & ((!storedTestFlag) ? 1 : 0)) ? 1 : 0);
      } else {
        storedOpportunityFlag = parsed;
      }
    } else if (column == "test_flag") {
      sawTestFlag = true;
      if (sawOppFlag) {
        testPopulation_.push_back(parsed & storedOpportunityFlag ? 1 : 0);
        controlPopulation_.push_back((!parsed) & storedOpportunityFlag ? 1 : 0);
      } else {
        storedTestFlag = parsed;
      }
    } else if (column == "opportunity_timestamp") {
      // secret-share-lift can have negative input timestamps
      if (liftMpcType_ == LiftMPCType::Standard && parsed < epoch_ &&
          parsed != 0) {
        LOG(FATAL) << "Timestamp " << parsed << " is before epoch " << epoch_
                   << ", which is unexpected.";
      }
      opportunityTimestamps_.push_back(parsed < epoch_ ? 0 : parsed - epoch_);
    } else if (column == "num_impressions") {
      numImpressions_.push_back(parsed);
    } else if (column == "num_clicks") {
      numClicks_.push_back(parsed);
    } else if (column == "total_spend") {
      totalSpend_.push_back(parsed);
    } else if (column == "cohort_id") {
      groupIds_.push_back(parsed);
      // We use parsed + 1 because cohorts are zero-indexed
      numGroups_ = std::max(numGroups_, static_cast<uint32_t>(parsed + 1));
    } else if (column == "breakdown_id") {
      if (computePublisherBreakdowns_) {
        breakdownIds_.push_back(parsed);

        // We use parsed + 1 because breakdowns are zero-indexed
        numGroups_ = std::max(numGroups_, static_cast<uint32_t>(parsed + 1));
      }
    } else if (column == "event_timestamp") {
      // When event_timestamp column presents (in standard Converter Lift
      // input), parse it as arrays of size 1.
      if (liftMpcType_ == LiftMPCType::Standard) {
        value = "[" + value + "]";
        setTimestamps(value, purchaseTimestampArrays_);
      } else {
        purchaseTimestamps_.push_back(parsed < epoch_ ? 0 : parsed - epoch_);
      }
    } else if (column == "event_timestamps") {
      setTimestamps(value, purchaseTimestampArrays_);
    } else if (column == "value") {
      totalValue_ += parsed;
      purchaseValues_.push_back(parsed);
      // If this is secret_share lift, we can't pre-compute squared values
      if (liftMpcType_ == LiftMPCType::Standard) {
        totalValueSquared_ += parsed * parsed;
        purchaseValuesSquared_.push_back(parsed * parsed);
      }
    } else if (column == "values") {
      setValuesFields(value);
    } else if (column == "value_squared") {
      // This column is only valid in secret_share lift
      // otherwise, we just use simple multiplication in the above condition
      if (liftMpcType_ == LiftMPCType::SecretShare) {
        totalValueSquared_ += parsed;
        purchaseValuesSquared_.push_back(parsed);
      }
    } else if (column == "opportunity_timestamps") {
      // This column is only valid in secret_share lift
      // otherwise, we just use single opportunity_timestamp
      if (liftMpcType_ == LiftMPCType::SecretShare) {
        setTimestamps(value, opportunityTimestampArrays_);
      }
    } else if (column == "purchase_flag") {
      // When purchase_flag column presents (in standard Converter Lift
      // input), parse it as arrays of size 1.
      if (liftMpcType_ == LiftMPCType::Standard) {
        value = "[" + value + "]";
        setValuesFields(value);
      } else {
        totalValue_ += parsed;
        purchaseValues_.push_back(parsed);
      }
    } else if (column != "id_") { // Do nothing with the id_ column as Lift
                                  // games assume the ids are already matched
      // We shouldn't fail if there are extra columns in the input
      LOG(WARNING) << "Warning: Unknown column in csv: " << column;
    }
  }

  // Once we've gone through every column, we need to check if we've added the
  // test/control values yet. From the input dataset, opp_flag is *optional*
  // so this can be interpreted as "this is a valid opportunity"
  if (!sawOppFlag) {
    testPopulation_.push_back(storedTestFlag);
    controlPopulation_.push_back(1 - storedTestFlag);
  }
}

std::vector<int64_t> InputData::bitmaskFor(int64_t groupId) const {
  std::vector<int64_t> res(numRows_);
  for (std::size_t i = 0; i < res.size(); ++i) {
    res[i] = groupIds_.size() > i && groupIds_.at(i) == groupId ? 1 : 0;
  }
  return res;
}

} // namespace private_lift
