#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict


import asyncio
import re
from typing import Dict, List, Optional

from fbpcp.entity.container_permission import ContainerPermissionConfig

from fbpcp.service.onedocker import OneDockerService
from fbpcp.service.storage import StorageService
from fbpcs.common.entity.stage_state_instance import StageStateInstanceStatus
from fbpcs.infra.certificate.certificate_provider import CertificateProvider
from fbpcs.infra.certificate.private_key import PrivateKeyReferenceProvider
from fbpcs.onedocker_binary_config import ONEDOCKER_REPOSITORY_PATH
from fbpcs.private_computation.entity.infra_config import PrivateComputationRole
from fbpcs.private_computation.entity.private_computation_instance import (
    PrivateComputationInstance,
    PrivateComputationInstanceStatus,
)
from fbpcs.private_computation.service.constants import (
    CA_CERTIFICATE_ENV_VAR,
    CA_CERTIFICATE_PATH_ENV_VAR,
    SERVER_CERTIFICATE_ENV_VAR,
    SERVER_CERTIFICATE_PATH_ENV_VAR,
    SERVER_HOSTNAME_ENV_VAR,
    SERVER_IP_ADDRESS_ENV_VAR,
    SERVER_PRIVATE_KEY_PATH_ENV_VAR,
    SERVER_PRIVATE_KEY_REF_ENV_VAR,
    SERVER_PRIVATE_KEY_REGION_ENV_VAR,
)
from fbpcs.private_computation.service.pid_utils import get_sharded_filepath


def get_pc_status_from_stage_state(
    private_computation_instance: PrivateComputationInstance,
    onedocker_svc: OneDockerService,
    stage_name: Optional[str] = None,
) -> PrivateComputationInstanceStatus:
    """Updates the StageStateInstances and gets latest PrivateComputationInstance status

    Arguments:
        private_computation_instance: The PC instance that is being updated
        onedocker_svc: Used to get latest Containers to update StageState instance status
        stage_name: if passed stage_name, will check the stage name from StageState instance

    Returns:
        The latest status for private_computation_instance
    """
    status = private_computation_instance.infra_config.status
    stage_instance = private_computation_instance.get_stage_instance()
    if stage_instance is None:
        raise ValueError(
            f"The current instance type not StageStateInstance but {type(private_computation_instance.current_stage)}"
        )

    stage_name = stage_name or stage_instance.stage_name
    assert stage_name == private_computation_instance.current_stage.name
    # calling onedocker_svc to update newest containers in StageState
    stage_state_instance_status = stage_instance.update_status(onedocker_svc)
    current_stage = private_computation_instance.current_stage
    # only update when StageStateInstanceStatus transit to Started/Completed/Failed, or remain the current status
    if stage_state_instance_status is StageStateInstanceStatus.STARTED:
        status = current_stage.started_status
    elif stage_state_instance_status is StageStateInstanceStatus.COMPLETED:
        status = current_stage.completed_status
    elif stage_state_instance_status is StageStateInstanceStatus.FAILED:
        status = current_stage.failed_status

    return status


def transform_file_path(file_path: str, aws_region: Optional[str] = None) -> str:
    """Transforms URL paths passed through the CLI to preferred access formats

    Args:
        file_path: The path to be transformed

    Returns:
        A URL in our preffered format (virtual-hosted server or local)

    Exceptions:
        ValueError:
    """

    key_pattern = "."
    region_regex_pattern = "[a-zA-Z0-9.-]"
    bucket_name_regex_pattern = "[a-z0-9.-]"

    # Check if it matches the path style access format, https://s3.Region.amazonaws.com/bucket-name/key-name
    if re.search(
        rf"https://[sS]3\.{region_regex_pattern}+\.amazonaws\.com/{bucket_name_regex_pattern}+/{key_pattern}+",
        file_path,
    ):

        # Extract Bucket, Key, and Region
        key_name_search = re.search(
            rf"https://[sS]3\.{region_regex_pattern}+\.amazonaws\.com/{bucket_name_regex_pattern}+/",
            file_path,
        )
        bucket_name_search = re.search(
            rf"https://[sS]3\.{region_regex_pattern}+\.amazonaws\.com/", file_path
        )
        region_start_search = re.search(r"https://[sS]3\.", file_path)
        region_end_search = re.search(r".amazonaws\.com/", file_path)
        bucket = ""
        key = ""

        # Check for not None rather than extracting on search, to keep pyre happy
        if (
            key_name_search
            and bucket_name_search
            and region_start_search
            and region_end_search
        ):
            aws_region = file_path[
                region_start_search.span()[1] : region_end_search.span()[0]
            ]
            bucket = file_path[
                bucket_name_search.span()[1] : key_name_search.span()[1] - 1
            ]
            key = file_path[key_name_search.span()[1] :]

        file_path = f"https://{bucket}.s3.{aws_region}.amazonaws.com/{key}"

    # Check if it matches the s3 style access format, s3://bucket-name/key-name
    if re.search(rf"[sS]3://{bucket_name_regex_pattern}+/{key_pattern}+", file_path):

        if aws_region is not None:

            # Extract Bucket, Key
            bucket_name_search = re.search(r"[sS]3://", file_path)
            key_name_search = re.search(
                rf"[sS]3://{bucket_name_regex_pattern}+/", file_path
            )
            bucket = ""
            key = ""

            # Check for not None rather than extracting on search, to keep pyre happy
            if key_name_search and bucket_name_search:

                bucket = file_path[
                    bucket_name_search.span()[1] : key_name_search.span()[1] - 1
                ]
                key = file_path[key_name_search.span()[1] :]

            file_path = f"https://{bucket}.s3.{aws_region}.amazonaws.com/{key}"

        else:
            raise ValueError(
                "Cannot be parsed to expected virtual-hosted-file format "
                f"Please check your input path that aws_region need to be specified: [{file_path}]"
            )

    if re.search(
        rf"https://{bucket_name_regex_pattern}+\.s3\.{region_regex_pattern}+\.amazonaws.com/{key_pattern}+",
        file_path,
    ):
        return file_path
    else:
        raise ValueError(
            "Error transforming into expected virtual-hosted format. Bad input? "
            f"Please check your input path: [{file_path}]"
        )


async def file_exists_async(
    storage_svc: StorageService,
    file_path: str,
) -> bool:
    """
    Check if the file on the StorageService
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, storage_svc.file_exists, file_path)


async def all_files_exist_on_cloud(
    input_path: str, num_shards: int, storage_svc: StorageService
) -> bool:
    input_paths = [
        get_sharded_filepath(input_path, shard) for shard in range(num_shards)
    ]
    # if all files exist on storage service, every element of file_exist_booleans should be True.
    tasks = await asyncio.gather(
        *[file_exists_async(storage_svc, path) for path in input_paths]
    )
    return sum(tasks) == num_shards


def stop_stage_service(
    pc_instance: PrivateComputationInstance, onedocker_svc: OneDockerService
) -> None:
    stage_instance = pc_instance.get_stage_instance()
    if stage_instance is not None:
        stage_instance.stop_containers(onedocker_svc)
    else:
        raise ValueError("Have no StageState for stop_service")


def generate_env_vars_dict(
    repository_path: Optional[str] = None,
    server_certificate_provider: Optional[CertificateProvider] = None,
    server_certificate_path: Optional[str] = None,
    ca_certificate_provider: Optional[CertificateProvider] = None,
    ca_certificate_path: Optional[str] = None,
    server_ip_address: Optional[str] = None,
    server_hostname: Optional[str] = None,
    server_private_key_ref_provider: Optional[PrivateKeyReferenceProvider] = None,
    **kwargs: Optional[str],
) -> Dict[str, str]:
    """Generate Env Vars for onedocker svc container spin up.

    Generate env_vars dictionary to pass to container svc like ECS as environment {"var_name": var_value,} variable.

    Args:
        server_private_key_ref_provider: Server Private Key reference provider to support TLS
        repository_path: package repository in OneDocker
        server_certificate_provider: Server Certificate Provider to support TLS, need to also specify server_certificate_path
        server_certificate_path: Server Certificate Path to support TLS, need to also specify server_certificate_provider
        ca_certificate_provider: CA Certificate Provider to support TLS, need to also specify ca_certificate_path
        ca_certificate_path: CA Certificate Path to support TLS, need to also specify ca_certificate_provider
        server_ip_address: The network IP address of the server to be used for connections during joint stages
        server_hostname: The network hostname of the server to be used for connections during during joint stages
        **kwargs: Arbitrary keyword arguments, will be upated in return dictionary as key-value pair.

    Returns:
        return: Dict of container enviroment name and value.
    """
    env_vars = {k: v for k, v in kwargs.items() if v is not None}
    if repository_path:
        env_vars[ONEDOCKER_REPOSITORY_PATH] = repository_path

    if server_certificate_provider is not None:
        server_cert = server_certificate_provider.get_certificate()
        if server_cert and server_certificate_path:
            env_vars[SERVER_CERTIFICATE_ENV_VAR] = server_cert
            env_vars[SERVER_CERTIFICATE_PATH_ENV_VAR] = server_certificate_path

    if server_private_key_ref_provider is not None:
        server_private_key = server_private_key_ref_provider.get_key_ref()
        if server_private_key is not None:
            env_vars[SERVER_PRIVATE_KEY_REF_ENV_VAR] = server_private_key.resource_id
            env_vars[SERVER_PRIVATE_KEY_REGION_ENV_VAR] = server_private_key.region
            env_vars[SERVER_PRIVATE_KEY_PATH_ENV_VAR] = server_private_key.install_path

    if ca_certificate_provider is not None:
        ca_cert = ca_certificate_provider.get_certificate()
        if ca_cert and ca_certificate_path:
            env_vars[CA_CERTIFICATE_ENV_VAR] = ca_cert
            env_vars[CA_CERTIFICATE_PATH_ENV_VAR] = ca_certificate_path

    if server_hostname is not None and server_ip_address is not None:
        # only set if both present, since variables are used for mapping between these values
        env_vars[SERVER_HOSTNAME_ENV_VAR] = server_hostname
        env_vars[SERVER_IP_ADDRESS_ENV_VAR] = server_ip_address

    return env_vars


def _validate_env_vars_length(
    num_containers: int, **kwargs: Optional[List[str]]
) -> bool:
    """
    Validate length of all the non null arguments is the same as num_containers.
    """
    for k, v in kwargs.items():
        if v and len(v) != num_containers:
            raise ValueError(
                f"Incorrect number of items in the env var list to match num_containers. num_contaienrs {num_containers}; {k} {len(v)};"
            )
    return True


def generate_env_vars_dicts_list(
    num_containers: int,
    repository_path: Optional[str] = None,
    server_certificate_provider: Optional[CertificateProvider] = None,
    server_certificate_path: Optional[str] = None,
    ca_certificate_provider: Optional[CertificateProvider] = None,
    ca_certificate_path: Optional[str] = None,
    server_ip_addresses: Optional[List[str]] = None,
    server_hostnames: Optional[List[str]] = None,
    server_private_key_ref_provider: Optional[PrivateKeyReferenceProvider] = None,
) -> List[Dict[str, str]]:

    _validate_env_vars_length(
        num_containers=num_containers,
        server_ip_addresses=server_ip_addresses,
        server_hostnames=server_hostnames,
    )

    return [
        generate_env_vars_dict(
            repository_path=repository_path,
            server_certificate_provider=server_certificate_provider,
            server_certificate_path=server_certificate_path,
            ca_certificate_provider=ca_certificate_provider,
            ca_certificate_path=ca_certificate_path,
            server_ip_address=server_ip_addresses[i] if server_ip_addresses else None,
            server_hostname=server_hostnames[i] if server_hostnames else None,
            server_private_key_ref_provider=server_private_key_ref_provider,
        )
        for i in range(num_containers)
    ]


# distribute number_files files into number_containers of containers evenly so that the maximum difference will be at most 1
def distribute_files_among_containers(
    number_files: int, number_containers: int
) -> List[int]:
    files_per_container = [number_files // number_containers] * number_containers
    for i in range(number_files % number_containers):
        files_per_container[i] += 1
    return files_per_container


def gen_tls_server_hostnames_for_publisher(
    server_domain: Optional[str], role: PrivateComputationRole, num_containers: int
) -> Optional[List[str]]:
    """For each container, create a unique server_uri based
    on the server_domain when the MPCParty is server.
    """
    if role is PrivateComputationRole.PARTNER or not server_domain:
        return None
    else:
        return [f"node{i}.{server_domain}" for i in range(num_containers)]


def gen_container_permission(
    pc_instance: PrivateComputationInstance,
) -> Optional[ContainerPermissionConfig]:
    """Returns a container permission configuration, when specified by the PC Instance,
    which can be used to override the default permissions during container start

    Arguments:
        pc_instance: The PC instance for which containers are being started
    """
    container_permission_id = pc_instance.infra_config.container_permission_id
    if container_permission_id is not None:
        return ContainerPermissionConfig(container_permission_id)

    return None
