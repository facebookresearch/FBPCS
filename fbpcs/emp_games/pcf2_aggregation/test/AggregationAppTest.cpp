/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#include <math.h>
#include <filesystem>
#include <string>

#include <gtest/gtest.h>
#include "folly/Format.h"
#include "folly/Random.h"
#include "folly/logging/xlog.h"

#include <fbpcf/io/api/FileIOWrappers.h>
#include "fbpcf/engine/communication/SocketPartyCommunicationAgentFactory.h"
#include "fbpcf/engine/communication/test/SocketInTestHelper.h"
#include "fbpcf/engine/communication/test/TlsCommunicationUtils.h"
#include "fbpcs/emp_games/common/Constants.h"
#include "fbpcs/emp_games/common/TestUtil.h"
#include "fbpcs/emp_games/common/test/TestUtils.h"
#include "fbpcs/emp_games/pcf2_aggregation/AggregationApp.h"
#include "fbpcs/emp_games/pcf2_aggregation/AggregationOptions.h"
#include "fbpcs/emp_games/pcf2_aggregation/test/AggregationTestUtils.h"

namespace pcf2_aggregation {

template <
    int PARTY,
    int schedulerId,
    common::Visibility outputVisibility,
    common::InputEncryption inputEncryption>
static void runGame(
    const std::string& serverIp,
    const uint16_t port,
    const std::string& aggregationFormat,
    const std::filesystem::path& inputSecretSharePath,
    const std::filesystem::path& inputClearTextPath,
    const std::string& outputPath,
    bool useTls,
    const std::string& tlsDir,
    bool useNewOutputFormat) {
  FLAGS_use_new_output_format = useNewOutputFormat;
  std::map<
      int,
      fbpcf::engine::communication::SocketPartyCommunicationAgentFactory::
          PartyInfo>
      partyInfos({{0, {serverIp, port}}, {1, {serverIp, port}}});

  auto communicationAgentFactory = std::make_unique<
      fbpcf::engine::communication::SocketPartyCommunicationAgentFactory>(
      PARTY, partyInfos, useTls, tlsDir, "aggregation_test_traffic");

  AggregationApp<PARTY, schedulerId>(
      inputEncryption,
      outputVisibility,
      std::move(communicationAgentFactory),
      aggregationFormat,
      std::vector<std::string>{inputSecretSharePath},
      std::vector<std::string>{inputClearTextPath},
      std::vector<std::string>{outputPath})
      .run();
}

// helper function for executing MPC game and verifying corresponding output
template <
    int id,
    common::Visibility outputVisibility,
    common::InputEncryption inputEncryption>
inline void testCorrectnessAggregationAppHelper(
    int remainingFiles,
    std::string serverIpAlice,
    int16_t portAlice,
    std::vector<std::string> attributionRules,
    std::string aggregationFormat,
    std::vector<std::string> inputSecretSharePathAlice,
    std::vector<std::string> inputReformattedSecretSharePathAlice,
    std::vector<std::string> inputClearTextPathAlice,
    std::vector<std::string> outputPathAlice,
    std::string serverIpBob,
    int16_t portBob,
    std::vector<std::string> inputSecretSharePathBob,
    std::vector<std::string> inputReformattedSecretSharePathBob,
    std::vector<std::string> inputClearTextPathBob,
    std::vector<std::string> outputPathBob,
    std::vector<std::string> expectedOutputFilePaths,
    bool useTls,
    std::string& tlsDir,
    bool useNewOutputFormat) {
  FLAGS_use_new_output_format = useNewOutputFormat;
  std::string alice_secret_input;
  std::string bob_secret_input;
  if (FLAGS_use_new_output_format) {
    alice_secret_input = inputReformattedSecretSharePathAlice.at(id);
    bob_secret_input = inputReformattedSecretSharePathBob.at(id);
  } else {
    alice_secret_input = inputSecretSharePathAlice.at(id);
    bob_secret_input = inputSecretSharePathBob.at(id);
  }

  auto futureAlice = std::async(
      runGame<common::PUBLISHER, 2 * id, outputVisibility, inputEncryption>,
      serverIpAlice,
      portAlice + 100 * id,
      aggregationFormat,
      alice_secret_input,
      inputClearTextPathAlice.at(id),
      outputPathAlice.at(id),
      useTls,
      tlsDir,
      useNewOutputFormat);
  auto futureBob = std::async(
      runGame<common::PARTNER, 2 * id + 1, outputVisibility, inputEncryption>,
      serverIpBob,
      portBob + 100 * id,
      "",
      bob_secret_input,
      inputClearTextPathBob.at(id),
      outputPathBob.at(id),
      useTls,
      tlsDir,
      useNewOutputFormat);

  futureAlice.get();
  futureBob.get();

  auto resAlice = AggregationOutputMetrics::fromJson(
      fbpcf::io::FileIOWrappers::readFile(outputPathAlice.at(id)));
  auto resBob = AggregationOutputMetrics::fromJson(
      fbpcf::io::FileIOWrappers::readFile(outputPathBob.at(id)));

  if constexpr (outputVisibility == common::Visibility::Xor) {
    auto result = revealXORedResult(
        resAlice, resBob, aggregationFormat, attributionRules.at(id));

    verifyOutput(result, expectedOutputFilePaths.at(id));
  } else {
    verifyOutput(resAlice, expectedOutputFilePaths.at(id));
  }

  if constexpr (id < 16) { // 16 is an arbitrary limit on number of files to run
    if (remainingFiles > 1) {
      testCorrectnessAggregationAppHelper<
          id + 1,
          outputVisibility,
          inputEncryption>(
          remainingFiles - 1,
          serverIpAlice,
          portAlice,
          attributionRules,
          aggregationFormat,
          inputSecretSharePathAlice,
          inputReformattedSecretSharePathAlice,
          inputClearTextPathAlice,
          outputPathAlice,
          serverIpBob,
          portBob,
          inputSecretSharePathBob,
          inputReformattedSecretSharePathBob,
          inputClearTextPathBob,
          outputPathBob,
          expectedOutputFilePaths,
          useTls,
          tlsDir,
          useNewOutputFormat);
    }
  }
}

class AggregationAppTest
    : public ::testing::TestWithParam<
          std::tuple<int, common::Visibility, bool, bool>> {
 protected:
  void SetUp() override {
    tlsDir_ = fbpcf::engine::communication::setUpTlsFiles();
    port_ = fbpcf::engine::communication::SocketInTestHelper::findNextOpenPort(
        5000);

    std::string baseDir_ =
        private_measurement::test_util::getBaseDirFromPath(__FILE__);
    std::string tempDir = std::filesystem::temp_directory_path();
    serverIpAlice_ = "";
    serverIpBob_ = "127.0.0.1";
    outputPathAlice_ = folly::sformat(
        "{}/output_path_alice.json_{}_",
        tempDir,
        folly::Random::secureRand64());
    outputPathBob_ = folly::sformat(
        "{}/output_path_bob.json_{}_", tempDir, folly::Random::secureRand64());

    attributionRules_ = std::vector<std::string>{
        common::LAST_CLICK_1D,
        common::LAST_TOUCH_1D,
        common::LAST_CLICK_2_7D,
        common::LAST_TOUCH_2_7D};
    aggregationFormat_ = common::MEASUREMENT;

    for (size_t i = 0; i < attributionRules_.size(); ++i) {
      auto attributionRule = attributionRules_.at(i);
      std::string rawInputFilePrefix = baseDir_ +
          "../../pcf2_attribution/test/test_correctness/" + attributionRule +
          ".";
      std::string attributionOutputFilePrefix =
          baseDir_ + "test_correctness/" + attributionRule + ".";
      std::string attributionReformattedOutputFilePrefix = baseDir_ +
          "test_correctness/" + attributionRule + "_reformatted" + ".";
      inputSecretShareFilePathsAlice_.push_back(
          attributionOutputFilePrefix + "publisher.json");
      inputReformattedSecretShareFilePathsAlice_.push_back(
          attributionReformattedOutputFilePrefix + "publisher.json");
      inputClearTextFilePathsAlice_.push_back(
          rawInputFilePrefix + "publisher.csv");
      inputSecretShareFilePathsBob_.push_back(
          attributionOutputFilePrefix + "partner.json");
      inputReformattedSecretShareFilePathsBob_.push_back(
          attributionReformattedOutputFilePrefix + "partner.json");
      inputClearTextFilePathsBob_.push_back(rawInputFilePrefix + "partner.csv");
      outputFilePathsAlice_.push_back(outputPathAlice_ + attributionRule);
      outputFilePathsBob_.push_back(outputPathBob_ + attributionRule);
      expectedOutputFilePaths_.push_back(
          baseDir_ + "test_correctness/" + attributionRule + "." +
          aggregationFormat_ + ".json");
    }
  }

  void TearDown() override {
    std::filesystem::remove(outputPathAlice_);
    std::filesystem::remove(outputPathBob_);
    fbpcf::engine::communication::deleteTlsFiles(tlsDir_);
  }

  template <int id, common::Visibility visibility>
  void testCorrectnessAggregationAppWrapper(
      bool useTls,
      bool useNewOutputFormat) {
    testCorrectnessAggregationAppHelper<
        id,
        visibility,
        common::InputEncryption::Plaintext>(
        attributionRules_.size(),
        serverIpAlice_,
        port_,
        attributionRules_,
        aggregationFormat_,
        inputSecretShareFilePathsAlice_,
        inputReformattedSecretShareFilePathsAlice_,
        inputClearTextFilePathsAlice_,
        outputFilePathsAlice_,
        serverIpBob_,
        port_,
        inputSecretShareFilePathsBob_,
        inputReformattedSecretShareFilePathsBob_,
        inputClearTextFilePathsBob_,
        outputFilePathsBob_,
        expectedOutputFilePaths_,
        useTls,
        tlsDir_,
        useNewOutputFormat);
  }

  std::string serverIpAlice_;
  std::string serverIpBob_;
  uint16_t port_;
  std::string outputPathAlice_;
  std::string outputPathBob_;
  std::string aggregationFormat_;
  std::vector<std::string> attributionRules_;
  std::vector<std::string> inputSecretShareFilePathsAlice_;
  std::vector<std::string> inputReformattedSecretShareFilePathsAlice_;
  std::vector<std::string> inputClearTextFilePathsAlice_;
  std::vector<std::string> inputSecretShareFilePathsBob_;
  std::vector<std::string> inputReformattedSecretShareFilePathsBob_;
  std::vector<std::string> inputClearTextFilePathsBob_;
  std::vector<std::string> outputFilePathsAlice_;
  std::vector<std::string> outputFilePathsBob_;
  std::vector<std::string> expectedOutputFilePaths_;
  std::string tlsDir_;
};

TEST_P(AggregationAppTest, TestCorrectness) {
  auto [id, visibility, useTls, useNewOutputFormat] = GetParam();
  FLAGS_use_new_output_format = useNewOutputFormat;
  switch (id) {
    case 0:
      switch (visibility) {
        case common::Visibility::Publisher:
          testCorrectnessAggregationAppWrapper<
              0,
              common::Visibility::Publisher>(useTls, useNewOutputFormat);
          break;
        case common::Visibility::Xor:
          testCorrectnessAggregationAppWrapper<0, common::Visibility::Xor>(
              useTls, useNewOutputFormat);
          break;
      }
      break;
    default:
      break;
  }
}

// Test cases are iterate in https://fb.quip.com/IUHDApxKEAli
INSTANTIATE_TEST_SUITE_P(
    AggregationAppTest,
    AggregationAppTest,
    ::testing::Combine(
        ::testing::Values(0),
        ::testing::Values(
            common::Visibility::Publisher,
            common::Visibility::Xor),
        ::testing::Bool(),
        ::testing::Bool()),

    [](const testing::TestParamInfo<AggregationAppTest::ParamType>& info) {
      auto id = std::to_string(std::get<0>(info.param));
      auto visibility = common::getVisibilityString(std::get<1>(info.param));
      auto tls = std::get<2>(info.param) ? "True" : "False";
      auto reformatted = std::get<3>(info.param) ? "True" : "False";

      std::string name = "ID_" + id + "_Visibility_" + visibility + "_TLS_" +
          tls + "_Reformatted_" + reformatted;
      return name;
    });

} // namespace pcf2_aggregation
