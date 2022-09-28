/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#pragma once
#include <folly/logging/xlog.h>
#include <filesystem>
#include <fstream>
#include <ostream>
#include <string>
#include <vector>

#include "fbpcf/io/api/BufferedReader.h"
#include "fbpcs/data_processing/id_combiner/AddPaddingToCols.h"
#include "fbpcs/data_processing/id_combiner/DataPreparationHelpers.h"
#include "fbpcs/data_processing/private_id_dfca_id_combiner/PrivateIdDfcaIdSpineCombinerOptions.h"
#include "fbpcs/data_processing/private_id_dfca_id_combiner/PrivateIdDfcaStrategy.h"

namespace pid::combiner {
struct FileMetaData {
  std::string headerLine;
  bool isPublisherDataset;
  std::vector<std::string> aggregatedCols;
};

/*
PrivateIdDfcaStrategy is an base class which has process functions for ID
combiner.
*/
class PrivateIdDfcaStrategy {
 public:
  const std::vector<std::string> publisherCols = {"user_id_publisher"};
  const std::vector<std::string> partnerCols = {"user_id_partner"};
  /**
   * aggregate() will aggreagte the file if the pid is the same.
   *
   * @param idSwapOutFile the file from the idSwap() which has the pid colums
   * @param meta header line, file type and aggregated columns
   * @param outputPath the file path that stores aggreaged result
   * @return idSwapOutFile output stream of private-id file
   **/
  virtual void aggregate(
      std::stringstream& idSwapOutFile,
      FileMetaData& meta,
      std::string outputPath);
  /**
   * getFileType() will return the type of file. Publisher or Partner
   * If the file format is wrong, rasise the excption
   *
   * @param headerLine the file header
   * @return the file type. If the file type is publisher, return true.
   *Otherwise return false.
   **/
  virtual bool getFileType(std::string headerLine);
  /**
   * processHeader() will extract the header of the file, check the tpye of the
   * file and get meta data
   *
   * @param file data file generated by the ID_MATCHING stage
   * @return FileMetaData: header line, file type and aggregated columns
   **/
  virtual FileMetaData processHeader(
      const std::shared_ptr<fbpcf::io::BufferedReader>& file);
  virtual ~PrivateIdDfcaStrategy() {}
  /**
   * run() will execute different steps according to differnt id_combiner
   **/
  virtual void run() = 0;
};

} // namespace pid::combiner
