#!/bin/bash
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

set -e

PROG_NAME=$0
usage() {
  cat << EOF >&2
Usage: $PROG_NAME <emp_games|data_processing|pid|validation|smart_agent> [-t TAG] [-d DOCKER_IMAGE_NAME]

package:
  emp_games - extracts the binaries from fbpcs/emp-games docker image
  data_processing - extracts the binaries from fbpcs/data-processing docker image
  pid - extracts the binaries from private-id docker image
  validation - extracts the binaries from the onedocker docker image
  smart_agent - extracts the binaries from the onedocker docker image
-t TAG: uses the image with the given tag (default: latest)
-d DOCKER_IMAGE_NAME: defines the image name to extract from
EOF
  exit 1
}

PACKAGES="emp_games data_processing pid validation smart_agent"
PACKAGE=$1
if [[ ! " $PACKAGES " =~ $PACKAGE ]]; then
   usage
fi
shift

TAG="latest"
while getopts "t:d:" o; do
  case $o in
    t) TAG=$OPTARG;;
    d) DOCKER_IMAGE_NAME=$OPTARG;;
    *) usage
  esac
done
shift "$((OPTIND - 1))"

# ensure docker image name does not contain a : (since we apply that below)
if [[ "$DOCKER_IMAGE_NAME" == *":"* ]]; then
   echo "Invalid docker image name. Should not include ':' and a tag."
   exit 1
fi

# determine what docker image name and tag to use
if [ -z "$DOCKER_IMAGE_NAME" ]; then
  case $PACKAGE in
    emp_games) DOCKER_IMAGE_NAME="fbpcs/emp-games";;
    data_processing) DOCKER_IMAGE_NAME="fbpcs/data-processing";;
    pid) DOCKER_IMAGE_NAME="fbpcs/onedocker/test";;
    validation) DOCKER_IMAGE_NAME="fbpcs/onedocker/test";;
    smart_agent) DOCKER_IMAGE_NAME="fbpcs/onedocker/test";;
  esac
fi
DOCKER_IMAGE_PATH="${DOCKER_IMAGE_NAME}:${TAG}"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
    # Run from the root dir of so the binaries paths exist
    cd "$SCRIPT_DIR" || exit
    mkdir -p binaries_out

TEMP_CONTAINER_NAME="temp_container_$TAG"

clean_up_container() {
  docker rm -f "$TEMP_CONTAINER_NAME"
}

trap "clean_up_container" EXIT
if [ "$PACKAGE" = "emp_games" ]; then
docker create -ti --name "$TEMP_CONTAINER_NAME" "${DOCKER_IMAGE_PATH}"
docker cp "$TEMP_CONTAINER_NAME":/usr/local/bin/lift_calculator "$SCRIPT_DIR/binaries_out/."
docker cp "$TEMP_CONTAINER_NAME":/usr/local/bin/pcf2_lift_calculator "$SCRIPT_DIR/binaries_out/."
docker cp "$TEMP_CONTAINER_NAME":/usr/local/bin/pcf2_lift_metadata_compaction "$SCRIPT_DIR/binaries_out/."
docker cp "$TEMP_CONTAINER_NAME":/usr/local/bin/udp_encryptor "$SCRIPT_DIR/binaries_out/."
docker cp "$TEMP_CONTAINER_NAME":/usr/local/bin/decoupled_attribution_calculator "$SCRIPT_DIR/binaries_out/."
docker cp "$TEMP_CONTAINER_NAME":/usr/local/bin/decoupled_aggregation_calculator "$SCRIPT_DIR/binaries_out/."
docker cp "$TEMP_CONTAINER_NAME":/usr/local/bin/pcf2_attribution_calculator "$SCRIPT_DIR/binaries_out/."
docker cp "$TEMP_CONTAINER_NAME":/usr/local/bin/pcf2_aggregation_calculator "$SCRIPT_DIR/binaries_out/."
docker cp "$TEMP_CONTAINER_NAME":/usr/local/bin/shard_aggregator "$SCRIPT_DIR/binaries_out/."
docker cp "$TEMP_CONTAINER_NAME":/usr/local/bin/pcf2_shard_combiner "$SCRIPT_DIR/binaries_out/."
docker cp "$TEMP_CONTAINER_NAME":/usr/local/bin/private_id_dfca_aggregator "$SCRIPT_DIR/binaries_out/."
fi

if [ "$PACKAGE" = "data_processing" ]; then
docker create -ti --name "$TEMP_CONTAINER_NAME" "${DOCKER_IMAGE_PATH}"
docker cp "$TEMP_CONTAINER_NAME":/usr/local/bin/sharder "$SCRIPT_DIR/binaries_out/."
docker cp "$TEMP_CONTAINER_NAME":/usr/local/bin/sharder_hashed_for_pid "$SCRIPT_DIR/binaries_out/."
docker cp "$TEMP_CONTAINER_NAME":/usr/local/bin/secure_random_sharder "$SCRIPT_DIR/binaries_out/."
docker cp "$TEMP_CONTAINER_NAME":/usr/local/bin/pid_preparer "$SCRIPT_DIR/binaries_out/."
docker cp "$TEMP_CONTAINER_NAME":/usr/local/bin/lift_id_combiner "$SCRIPT_DIR/binaries_out/."
docker cp "$TEMP_CONTAINER_NAME":/usr/local/bin/attribution_id_combiner "$SCRIPT_DIR/binaries_out/."
docker cp "$TEMP_CONTAINER_NAME":/usr/local/bin/private_id_dfca_id_combiner "$SCRIPT_DIR/binaries_out/."
fi

if [ "$PACKAGE" = "pid" ]; then
docker create -ti --name "$TEMP_CONTAINER_NAME" "${DOCKER_IMAGE_PATH}"
docker cp "$TEMP_CONTAINER_NAME":/usr/local/bin/private-id-server "$SCRIPT_DIR/binaries_out/."
docker cp "$TEMP_CONTAINER_NAME":/usr/local/bin/private-id-client "$SCRIPT_DIR/binaries_out/."
docker cp "$TEMP_CONTAINER_NAME":/usr/local/bin/private-id-multi-key-server "$SCRIPT_DIR/binaries_out/."
docker cp "$TEMP_CONTAINER_NAME":/usr/local/bin/private-id-multi-key-client "$SCRIPT_DIR/binaries_out/."
fi

if [ "$PACKAGE" = "validation" ]; then
docker create -ti --name "$TEMP_CONTAINER_NAME" "${DOCKER_IMAGE_PATH}"
docker cp "$TEMP_CONTAINER_NAME":/usr/local/bin/pc_pre_validation_cli "$SCRIPT_DIR/binaries_out/."
fi

if [ "$PACKAGE" = "smart_agent" ]; then
docker create -ti --name "$TEMP_CONTAINER_NAME" "${DOCKER_IMAGE_PATH}"
docker cp "$TEMP_CONTAINER_NAME":/usr/local/bin/smart_agent_server "$SCRIPT_DIR/binaries_out/."
fi
