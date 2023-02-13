/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#include <filesystem>

#include <gflags/gflags.h>
#include <signal.h>

#include "folly/init/Init.h"

// TODO: Rewrite for OSS?
#include "fbpcf/aws/AwsSdk.h"

#include "UnionPIDDataPreparer.h"

DEFINE_string(input_path, "", "Path to input CSV (with header)");
DEFINE_string(output_path, "", "Path where list of IDs should be output");
DEFINE_string(
    tmp_directory,
    "/tmp/",
    "Directory where temporary files should be saved before final write");
DEFINE_int32(max_column_cnt, 1, "Number of columns to write");

DEFINE_string(
    run_id,
    "",
    "A run_id used to identify all the logs in a PL/PA run.");
DEFINE_int32(log_every_n, 1'000'000, "How frequently to log updates");
DEFINE_int32(
    id_filter_thresh,
    -1,
    "A threshold for number of times identifier can appear");

int main(int argc, char** argv) {
  folly::init(&argc, &argv);
  gflags::ParseCommandLineFlags(&argc, &argv, true);
  fbpcf::AwsSdk::aquire();

  signal(SIGPIPE, SIG_IGN);

  std::filesystem::path tmpDirectory{FLAGS_tmp_directory};
  measurement::pid::UnionPIDDataPreparer preparer{
      FLAGS_input_path,
      FLAGS_output_path,
      tmpDirectory,
      FLAGS_max_column_cnt,
      FLAGS_id_filter_thresh,
      FLAGS_log_every_n};

  preparer.prepare();
  return 0;
}
