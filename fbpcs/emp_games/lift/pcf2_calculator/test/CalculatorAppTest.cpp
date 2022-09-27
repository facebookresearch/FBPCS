/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#include <cmath>
#include <filesystem>
#include <memory>
#include <string>
#include <thread>
#include <unordered_map>

#include <gtest/gtest.h>
#include "folly/Random.h"

#include <fbpcf/io/api/FileIOWrappers.h>
#include "fbpcf/engine/communication/SocketPartyCommunicationAgentFactory.h"
#include "fbpcf/engine/communication/test/AgentFactoryCreationHelper.h"
#include "fbpcf/engine/communication/test/SocketInTestHelper.h"
#include "fbpcf/engine/communication/test/TlsCommunicationUtils.h"
#include "fbpcs/emp_games/common/Csv.h"
#include "fbpcs/emp_games/common/TestUtil.h"
#include "fbpcs/emp_games/common/test/TestUtils.h"
#include "fbpcs/emp_games/lift/pcf2_calculator/CalculatorApp.h"
#include "fbpcs/emp_games/lift/pcf2_calculator/test/common/GenFakeData.h"
#include "fbpcs/emp_games/lift/pcf2_calculator/test/common/LiftCalculator.h"

namespace private_lift {

template <int schedulerId>
void runCalculatorApp(
    int myId,
    const int numConversionsPerUser,
    const bool computePublisherBreakdowns,
    const int epoch,
    const std::string& inputPath,
    const std::string& outputPath,
    bool useXorEncryption,
    std::unique_ptr<
        fbpcf::engine::communication::IPartyCommunicationAgentFactory>
        communicationAgentFactory) {
  auto metricCollector =
      std::make_shared<fbpcf::util::MetricCollector>("calculator_test");

  auto app = std::make_unique<CalculatorApp<schedulerId>>(
      myId,
      std::move(communicationAgentFactory),
      numConversionsPerUser,
      computePublisherBreakdowns,
      epoch,
      std::vector<std::string>{inputPath},
      std::vector<std::string>{outputPath},
      metricCollector,
      0,
      1,
      useXorEncryption);
  app->run();
}

class CalculatorAppTestFixture
    : public ::testing::TestWithParam<std::tuple<bool, bool, bool>> {
 protected:
  std::string publisherInputPath_;
  std::string partnerInputPath_;
  std::string publisherOutputPath_;
  std::string partnerOutputPath_;
  std::string tlsDir_;

  void SetUp() override {
    std::string tempDir = std::filesystem::temp_directory_path();
    publisherInputPath_ = folly::sformat(
        "{}/publisher_{}.csv", tempDir, folly::Random::secureRand64());
    partnerInputPath_ = folly::sformat(
        "{}/partner_{}.csv", tempDir, folly::Random::secureRand64());
    publisherOutputPath_ = folly::sformat(
        "{}/res_publisher_{}", tempDir, folly::Random::secureRand64());
    partnerOutputPath_ = folly::sformat(
        "{}/res_partner_{}", tempDir, folly::Random::secureRand64());
    tlsDir_ = fbpcf::engine::communication::setUpTlsFiles();
  }

  void TearDown() override {
    std::filesystem::remove(publisherInputPath_);
    std::filesystem::remove(partnerInputPath_);
    std::filesystem::remove(publisherOutputPath_);
    std::filesystem::remove(partnerOutputPath_);
    fbpcf::engine::communication::deleteTlsFiles(tlsDir_);
  }

  GroupedLiftMetrics runTest(
      const std::string& publisherInputPath,
      const std::string& partnerInputPath,
      const std::string& publisherOutputPath,
      const std::string& partnerOutputPath,
      const int numConversionsPerUser,
      const bool computePublisherBreakdowns,
      bool useTls,
      bool useXorEncryption) {
    fbpcf::engine::communication::SocketPartyCommunicationAgent::TlsInfo
        tlsInfo;
    tlsInfo.certPath = useTls ? (tlsDir_ + "/cert.pem") : "";
    tlsInfo.keyPath = useTls ? (tlsDir_ + "/key.pem") : "";
    tlsInfo.passphrasePath = useTls ? (tlsDir_ + "/passphrase.pem") : "";
    tlsInfo.rootCaCertPath = useTls ? (tlsDir_ + "/ca_cert.pem") : "";
    tlsInfo.useTls = useTls;

    auto [communicationAgentFactoryAlice, communicationAgentFactoryBob] =
        fbpcf::engine::communication::getSocketAgentFactoryPair(tlsInfo);
    int epoch = 1546300800;
    auto future0 = std::async(
        runCalculatorApp<0>,
        0,
        numConversionsPerUser,
        computePublisherBreakdowns,
        epoch,
        publisherInputPath,
        publisherOutputPath,
        useXorEncryption,
        std::move(communicationAgentFactoryAlice));

    auto future1 = std::async(
        runCalculatorApp<1>,
        1,
        numConversionsPerUser,
        computePublisherBreakdowns,
        epoch,
        partnerInputPath,
        partnerOutputPath,
        useXorEncryption,
        std::move(communicationAgentFactoryBob));

    future0.get();
    future1.get();
    auto publisherResult = GroupedLiftMetrics::fromJson(
        fbpcf::io::FileIOWrappers::readFile(publisherOutputPath));
    auto partnerResult = GroupedLiftMetrics::fromJson(
        fbpcf::io::FileIOWrappers::readFile(partnerOutputPath));

    return useXorEncryption ? publisherResult ^ partnerResult : publisherResult;
  }
};

TEST_P(CalculatorAppTestFixture, TestCorrectness) {
  int numConversionsPerUser = 2;
  std::string baseDir =
      private_measurement::test_util::getBaseDirFromPath(__FILE__);
  std::string publisherInputPath =
      baseDir + "../sample_input/publisher_unittest3.csv";
  std::string partnerInputPath =
      baseDir + "../sample_input/partner_2_convs_unittest.csv";
  std::string expectedOutputPath =
      baseDir + "../sample_input/correctness_output.json";
  bool useTls = std::get<0>(GetParam());
  bool useXorEncryption = std::get<1>(GetParam());

  // test with and w/o computing publisher breakdowns
  bool computePublisherBreakdowns = std::get<2>(GetParam());

  auto result = runTest(
      publisherInputPath,
      partnerInputPath,
      publisherOutputPath_,
      partnerOutputPath_,
      numConversionsPerUser,
      computePublisherBreakdowns,
      useTls,
      useXorEncryption);

  auto expectedResult = GroupedLiftMetrics::fromJson(
      fbpcf::io::FileIOWrappers::readFile(expectedOutputPath));

  // No publisher breakdown computation required, remove the
  // breakdown data from the expected output before result validation
  if (!computePublisherBreakdowns) {
    expectedResult.publisherBreakdowns.clear();
  }

  EXPECT_EQ(expectedResult, result);
}

TEST_P(CalculatorAppTestFixture, TestCorrectnessRandomInput) {
  // Generate test input files with random data
  int numConversionsPerUser = 25;
  GenFakeData testDataGenerator;
  LiftFakeDataParams params;
  params.setNumRows(15)
      .setOpportunityRate(0.5)
      .setTestRate(0.5)
      .setPurchaseRate(0.5)
      .setIncrementalityRate(0.0)
      .setEpoch(1546300800);
  testDataGenerator.genFakePublisherInputFile(publisherInputPath_, params);
  params.setNumConversions(numConversionsPerUser).setOmitValuesColumn(false);
  testDataGenerator.genFakePartnerInputFile(partnerInputPath_, params);

  // Run calculator app with test input
  bool useTls = std::get<0>(GetParam());
  bool useXorEncryption = std::get<1>(GetParam());
  bool computePublisherBreakdowns = std::get<2>(GetParam());
  auto res = runTest(
      publisherInputPath_,
      partnerInputPath_,
      publisherOutputPath_,
      partnerOutputPath_,
      numConversionsPerUser,
      computePublisherBreakdowns,
      useTls,
      useXorEncryption);

  // Calculate expected results with simple lift calculator
  LiftCalculator liftCalculator(0, 0, 0);
  std::ifstream inFilePublisher{publisherInputPath_};
  std::ifstream inFilePartner{partnerInputPath_};
  int32_t tsOffset = 10;
  std::string linePublisher;
  std::string linePartner;
  getline(inFilePublisher, linePublisher);
  getline(inFilePartner, linePartner);
  auto headerPublisher =
      private_measurement::csv::splitByComma(linePublisher, false);
  auto headerPartner =
      private_measurement::csv::splitByComma(linePartner, false);
  std::unordered_map<std::string, int> colNameToIndex =
      liftCalculator.mapColToIndex(headerPublisher, headerPartner);
  GroupedLiftMetrics expectedResult = liftCalculator.compute(
      inFilePublisher, inFilePartner, colNameToIndex, tsOffset, false);

  EXPECT_EQ(expectedResult, res);
}

INSTANTIATE_TEST_SUITE_P(
    CalculatorAppTest,
    CalculatorAppTestFixture,
    ::testing::Combine(::testing::Bool(), ::testing::Bool(), ::testing::Bool()),
    [](const testing::TestParamInfo<CalculatorAppTestFixture::ParamType>&
           info) {
      std::string tls = std::get<0>(info.param) ? "True" : "False";
      std::string useXorEncryption = std::get<1>(info.param) ? "True" : "False";
      std::string computePublisherBreakdowns =
          std::get<2>(info.param) ? "True" : "False";
      std::string name = "TLS_" + tls + "_XOR_" + useXorEncryption +
          "_ComputePublisherBreakdowns_" + computePublisherBreakdowns;
      return name;
    });

} // namespace private_lift
