/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#pragma once

#include <cmath>
#include <filesystem>
#include <fstream>
#include <map>
#include <string>
#include <unordered_map>
#include <vector>

namespace private_lift {

/*
 * This class represents input data for a Private Lift computation.
 * It processes an input csv and generates the std::vectors for each column
 * It also has the ability to generate bitmasks for cohort metrics.
 */
class InputData {
 public:
  enum class LiftMPCType { SecretShare, Standard };

  // Constructor -- input is a path to a CSV along with the new epoch to use
  explicit InputData(
      std::string filepath,
      LiftMPCType liftMpcType,
      bool computePublisherBreakdowns,
      int64_t epoch = 0,
      int32_t numConversionsPerUser = INT32_MAX);

  InputData() {}

  // Create a bitmask for the given groupId
  // Note that although the return value is a vector of int64_t, the real
  // values are just 0/1
  std::vector<int64_t> bitmaskFor(int64_t groupId) const;

  const std::vector<bool>& getTestPopulation() const {
    return testPopulation_;
  }

  const std::vector<bool>& getControlPopulation() const {
    return controlPopulation_;
  }

  const std::vector<uint32_t>& getOpportunityTimestamps() const {
    return opportunityTimestamps_;
  }

  const std::vector<int64_t>& getNumImpressions() const {
    return numImpressions_;
  }

  const std::vector<int64_t>& getNumClicks() const {
    return numClicks_;
  }

  const std::vector<int64_t>& getTotalSpend() const {
    return totalSpend_;
  }

  const std::vector<std::vector<uint32_t>>& getOpportunityTimestampArrays()
      const {
    return opportunityTimestampArrays_;
  }

  const std::vector<uint32_t>& getPurchaseTimestamps() const {
    return purchaseTimestamps_;
  }

  const std::vector<std::vector<uint32_t>>& getPurchaseTimestampArrays() const {
    return purchaseTimestampArrays_;
  }

  const std::vector<int64_t>& getPurchaseValues() const {
    return purchaseValues_;
  }

  const std::vector<int64_t>& getPurchaseValuesSquared() const {
    return purchaseValuesSquared_;
  }

  const std::vector<std::vector<int64_t>>& getPurchaseValueArrays() const {
    return purchaseValueArrays_;
  }

  const std::vector<std::vector<int64_t>>& getPurchaseValueSquaredArrays()
      const {
    return purchaseValueSquaredArrays_;
  }

  const std::vector<uint32_t>& getGroupIds() const {
    return groupIds_;
  }

  const std::vector<uint32_t>& getBreakdownIds() const {
    return breakdownIds_;
  }

  int64_t getNumGroups() const {
    return numGroups_;
  }

  int64_t getNumBitsForValue() const {
    return std::ceil(std::log2(totalValue_ + 1));
  }

  int64_t getNumBitsForValueSquared() const {
    return std::ceil(std::log2(totalValueSquared_ + 1));
  }

  int64_t getNumRows() const {
    return numRows_;
  }

 private:
  // Set the features header (only matters for partner, not publisher)
  void setFeaturesHeader(const std::vector<std::string>& header);

  /*
   * Append timestamps values from str to timestampArrays, adding offset to each
   * value
   *
   * str = input data in the format of a comma-separated list surrounded by
   * brackets
   * timestampArrays = an array to which input data from str append
   * offset = add offset to each value from str before append
   */
  void setTimestamps(
      std::string& str,
      std::vector<std::vector<uint32_t>>& timestampArrays);

  /*
   * Append values from str to valueArrays and add to totalValue.
   * If not secret_share lift, then also append squared values to
   * valuesSquaredArrays and add to totalValueSquared.
   *
   * str = input data in the format of a comma-separated list surrounded by
   * brackets
   * valueArrays = an array to which input data from str append
   * valuesSquaredArrays = an array to which the squares of input data from str
   * append
   */
  void setValuesFields(std::string& str);

  // Helper to add a line from a CSV into the component column vectors
  void addFromCSV(
      const std::vector<std::string>& header,
      const std::vector<std::string>& parts);

  LiftMPCType liftMpcType_;
  bool computePublisherBreakdowns_;
  int64_t epoch_;
  std::vector<bool> testPopulation_;
  std::vector<bool> controlPopulation_;
  std::vector<uint32_t> opportunityTimestamps_;
  std::vector<int64_t> numImpressions_;
  std::vector<int64_t> numClicks_;
  std::vector<int64_t> totalSpend_;
  std::vector<uint32_t> purchaseTimestamps_;
  std::vector<int64_t> purchaseValues_;
  std::vector<int64_t> purchaseValuesSquared_;
  std::vector<uint32_t> groupIds_;
  std::vector<uint32_t> breakdownIds_;
  std::vector<std::vector<uint32_t>> opportunityTimestampArrays_;
  std::vector<std::vector<uint32_t>> purchaseTimestampArrays_;
  std::vector<std::vector<int64_t>> purchaseValueArrays_;
  std::vector<std::vector<int64_t>> purchaseValueSquaredArrays_;

  int64_t totalValue_ = 0;
  int64_t totalValueSquared_ = 0;
  uint32_t numGroups_ = 0;
  int32_t numConversionsPerUser_;

  bool firstLineParsedAlready_ = false;
  int64_t numRows_ = 0;
};

} // namespace private_lift
