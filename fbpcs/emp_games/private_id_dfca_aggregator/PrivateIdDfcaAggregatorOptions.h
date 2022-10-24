/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#pragma once

#include <gflags/gflags_declare.h>

DECLARE_int32(party);
DECLARE_string(server_ip);
DECLARE_int32(port);
DECLARE_string(input_path);
DECLARE_string(output_path);
DECLARE_string(run_name);
DECLARE_bool(log_cost);
DECLARE_string(log_cost_s3_bucket);
DECLARE_string(log_cost_s3_region);
DECLARE_bool(use_tls);
DECLARE_string(ca_cert_path);
DECLARE_string(server_cert_path);
DECLARE_string(private_key_path);
