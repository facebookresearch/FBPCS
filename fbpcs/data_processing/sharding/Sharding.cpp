/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#include "fbpcs/data_processing/sharding/Sharding.h"

#include <folly/String.h>
#include <folly/logging/xlog.h>

#include "fbpcs/data_processing/sharding/HashBasedSharder.h"
#include "fbpcs/data_processing/sharding/RoundRobinBasedSharder.h"

#include "fbpcf/engine/util/AesPrgFactory.h"
#include "fbpcf/mpc_std_lib/util/secureSamplePublicSeed.h"
#include "fbpcs/data_processing/sharding/SecureRandomSharder.h"

namespace data_processing::sharder {
void runShard(
    const std::string& inputFilename,
    const std::string& outputFilenames,
    const std::string& outputBasePath,
    int32_t fileStartIndex,
    int32_t numOutputFiles,
    int32_t logEveryN) {
  if (!outputFilenames.empty()) {
    std::vector<std::string> outputFilepaths;
    folly::split(',', outputFilenames, outputFilepaths);
    RoundRobinBasedSharder sharder{inputFilename, outputFilepaths, logEveryN};
    sharder.shard();
  } else if (!outputBasePath.empty() && numOutputFiles > 0) {
    std::size_t startIndex = static_cast<std::size_t>(fileStartIndex);
    std::size_t endIndex = startIndex + numOutputFiles;
    RoundRobinBasedSharder sharder{
        inputFilename, outputBasePath, startIndex, endIndex, logEveryN};
    sharder.shard();
  } else {
    XLOG(FATAL) << "Error: specify --output_filenames or --output_base_path, "
                   "--file_start_index, and --num_output_files";
  }
}

void runShardPid(
    const std::string& inputFilename,
    const std::string& outputFilenames,
    const std::string& outputBasePath,
    int32_t fileStartIndex,
    int32_t numOutputFiles,
    int32_t logEveryN,
    const std::string& hmacBase64Key) {
  if (!outputFilenames.empty()) {
    std::vector<std::string> outputFilepaths;
    folly::split(',', outputFilenames, outputFilepaths);
    HashBasedSharder sharder{
        inputFilename, outputFilepaths, logEveryN, hmacBase64Key};
    sharder.shard();
  } else if (!outputBasePath.empty() && numOutputFiles > 0) {
    std::size_t startIndex = static_cast<std::size_t>(fileStartIndex);
    std::size_t endIndex = startIndex + numOutputFiles;
    HashBasedSharder sharder{
        inputFilename,
        outputBasePath,
        startIndex,
        endIndex,
        logEveryN,
        hmacBase64Key};
    sharder.shard();
  } else {
    XLOG(FATAL) << "Error: specify --output_filenames or --output_base_path, "
                   "--file_start_index, and --num_output_files";
  }
}

void runSecureRandomShard(
    const std::string& inputFilename,
    const std::string& outputFilenames,
    const std::string& outputBasePath,
    int32_t fileStartIndex,
    int32_t numOutputFiles,
    int32_t logEveryN,
    bool amISendingFirst,
    std::unique_ptr<fbpcf::engine::communication::IPartyCommunicationAgent>
        agent) {
  auto prgKey =
      fbpcf::mpc_std_lib::util::secureSamplePublicSeed(amISendingFirst, *agent);

  char keyMessage[100];
  alignas(16) uint32_t v[4];
  _mm_store_si128((__m128i*)v, prgKey);
  sprintf(keyMessage, "%04x%04x%04x%04x", v[0], v[1], v[2], v[3]);
  XLOG(INFO) << "Public prg key is: " << keyMessage;

  agent = nullptr; // release the agent as it is not needed anymore.

  fbpcf::engine::util::AesPrgFactory aesPrgFactory;
  auto prg = aesPrgFactory.create(prgKey);

  if (!outputFilenames.empty()) {
    std::vector<std::string> outputFilepaths;
    folly::split(',', outputFilenames, outputFilepaths);
    SecureRandomSharder sharder{
        inputFilename, outputFilepaths, logEveryN, std::move(prg)};
    sharder.shard();
  } else if (!outputBasePath.empty() && numOutputFiles > 0) {
    std::size_t startIndex = static_cast<std::size_t>(fileStartIndex);
    std::size_t endIndex = startIndex + numOutputFiles;
    SecureRandomSharder sharder{
        inputFilename,
        outputBasePath,
        startIndex,
        endIndex,
        logEveryN,
        std::move(prg)};
    sharder.shard();
  } else {
    XLOG(FATAL) << "Error: specify --output_filenames or --output_base_path, "
                   "--file_start_index, and --num_output_files";
  }
}

} // namespace data_processing::sharder
