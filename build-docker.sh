#!/bin/bash
# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

set -e

UBUNTU_RELEASE="20.04"
GITHUB_PACKAGES="ghcr.io/facebookresearch"


PROG_NAME=$0
usage() {
  cat << EOF >&2
Usage: $PROG_NAME <package: emp_games|data_processing|onedocker> [-u] [-t TAG]

package:
  emp_games - builds the emp_games docker image
  data_processing - builds the data_processing docker image
  onedocker - A OneDocker docker image containing emp_games and data_processing
-u: builds the docker images against ubuntu (default)
-f: force use of latest fbpcf from ghcr.io/facebookresearch
-t TAG: tags the image with the given tag (default: latest)
EOF
  exit 1
}
AVAILABLE_PACKAGES="emp_games data_processing onedocker"
PACKAGE=$1
if [[ ! " $AVAILABLE_PACKAGES " =~ $PACKAGE ]]; then
   usage
fi
shift

IMAGE_PREFIX="ubuntu"
OS_RELEASE=${UBUNTU_RELEASE}
DOCKER_EXTENSION=".ubuntu"
TAG="latest"
FORCE_EXTERNAL=false
while getopts "u,f,t:" o; do
  case $o in
    (u) IMAGE_PREFIX="ubuntu"
        OS_RELEASE=${UBUNTU_RELEASE}
        DOCKER_EXTENSION=".ubuntu";;
    (f) FORCE_EXTERNAL=true;;
    (t) TAG=$OPTARG;;
    (*) usage
  esac
done
shift "$((OPTIND - 1))"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# Docker build must run from the root folder, so all the relative paths work inside the Dockerfile's
cd "$SCRIPT_DIR" || exit

FBPCF_IMAGE="fbpcf/${IMAGE_PREFIX}:latest"
if [ "${FORCE_EXTERNAL}" == false ] && docker image inspect "${FBPCF_IMAGE}" >/dev/null 2>&1; then
  printf "Using locally built %s docker image (this may NOT be up-to-date...)\n\n" "${FBPCF_IMAGE}"
  printf "To use latest %s from %s please \n   1. Delete this local docker image (docker image rm %s) \nor\n   2. Use the '-f' flag\n" "${FBPCF_IMAGE}" "${GITHUB_PACKAGES}" "${FBPCF_IMAGE}"
else
  printf "attempting to pull image %s from %s...\n" "${FBPCF_IMAGE}" "${GITHUB_PACKAGES}"
  if docker pull "${GITHUB_PACKAGES}/${FBPCF_IMAGE}" 2>/dev/null; then
      # Use the external ghcr.io image (if a local image doesn't exist) instead of building locally...
      FBPCF_IMAGE="${GITHUB_PACKAGES}/${FBPCF_IMAGE}"
      printf "successfully pulled image %s\n\n" "${FBPCF_IMAGE}"
    else
      # This should not happen since we build fbpcf externally
      printf "\nERROR: Unable to find docker image %s.  Please clone and run https://github.com/facebookresearch/fbpcf/blob/master/build-docker.sh " "${FBPCF_IMAGE}"
      exit 1
  fi
fi

# Local Docker Image Dependencies
if [ "$PACKAGE" = "onedocker" ]; then
 PACKAGE="emp_games data_processing onedocker"
fi

for P in $PACKAGE; do
  DOCKER_PACKAGE=${P/_/-}
  printf "\nBuilding %s %s docker image...\n" "${P}" "${IMAGE_PREFIX}"
  docker build  \
    --build-arg tag="${TAG}" \
    --build-arg os_release="${OS_RELEASE}" \
    --build-arg fbpcf_image="${FBPCF_IMAGE}" \
    --compress \
    -t "fbpcs/${DOCKER_PACKAGE}:${TAG}" -f "docker/${P}/Dockerfile${DOCKER_EXTENSION}" .
done
