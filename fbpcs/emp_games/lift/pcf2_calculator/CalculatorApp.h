/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#pragma once

#include <cstdlib>
#include <filesystem>
#include <string>
#include "folly/logging/xlog.h"

#include "fbpcf/engine/communication/IPartyCommunicationAgentFactory.h"
#include "fbpcf/scheduler/SchedulerHelper.h"
#include "fbpcs/emp_games/common/SchedulerStatistics.h"
#include "fbpcs/emp_games/lift/pcf2_calculator/CalculatorGame.h"
#include "fbpcs/emp_games/lift/pcf2_calculator/CalculatorGameConfig.h"
#include "fbpcs/emp_games/lift/pcf2_calculator/input_processing/InputData.h"

namespace private_lift {

template <int schedulerId>
class CalculatorApp {
 public:
  CalculatorApp(
      const int party,
      std::unique_ptr<
          fbpcf::engine::communication::IPartyCommunicationAgentFactory>
          communicationAgentFactory,
      const int numConversionsPerUser,
      const bool computePublisherBreakdowns,
      const int epoch,
      const std::vector<std::string>& inputPaths,
      const std::vector<std::string>& outputPaths,
      std::shared_ptr<fbpcf::util::MetricCollector> metricCollector,
      const int startFileIndex = 0,
      const int numFiles = 1,
      const bool useXorEncryption = true)
      : party_{party},
        communicationAgentFactory_{std::move(communicationAgentFactory)},
        numConversionsPerUser_(numConversionsPerUser),
        computePublisherBreakdowns_(computePublisherBreakdowns),
        epoch_(epoch),
        inputPaths_(inputPaths),
        outputPaths_(outputPaths),
        metricCollector_(metricCollector),
        startFileIndex_(startFileIndex),
        numFiles_(numFiles),
        useXorEncryption_(useXorEncryption) {}

  void run();

  common::SchedulerStatistics getSchedulerStatistics() {
    return schedulerStatistics_;
  }

 protected:
  CalculatorGameConfig getInputData(const std::string& inputPath);

  void putOutputData(const std::string& output, const std::string& outputPath);

  std::unique_ptr<fbpcf::scheduler::IScheduler> createScheduler();

 private:
  int party_;
  std::unique_ptr<fbpcf::engine::communication::IPartyCommunicationAgentFactory>
      communicationAgentFactory_;
  int numConversionsPerUser_;
  bool computePublisherBreakdowns_;
  int epoch_;
  std::vector<std::string> inputPaths_;
  std::vector<std::string> outputPaths_;
  std::shared_ptr<fbpcf::util::MetricCollector> metricCollector_;
  int startFileIndex_;
  int numFiles_;
  bool useXorEncryption_;
  common::SchedulerStatistics schedulerStatistics_;
};

} // namespace private_lift

#include "fbpcs/emp_games/lift/pcf2_calculator/CalculatorApp_impl.h"
