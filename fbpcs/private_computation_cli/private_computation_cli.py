#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.


"""
CLI for running a Private Lift study


Usage:
    pc-cli create_instance <instance_id> --config=<config_file> --role=<pl_role> --game_type=<game_type> --input_path=<input_path> --output_dir=<output_dir> --num_pid_containers=<num_pid_containers> --num_mpc_containers=<num_mpc_containers> [--attribution_rule=<attribution_rule> --aggregation_type=<aggregation_type> --concurrency=<concurrency> --num_files_per_mpc_container=<num_files_per_mpc_container> --padding_size=<padding_size> --k_anonymity_threshold=<k_anonymity_threshold> --hmac_key=<base64_key> --stage_flow=<stage_flow> --result_visibility=<result_visibility> --run_id=<run_id>] [options]
    pc-cli validate <instance_id> --config=<config_file> --expected_result_path=<expected_result_path> [--aggregated_result_path=<aggregated_result_path>] [options]
    pc-cli run_next <instance_id> --config=<config_file> [--server_ips=<server_ips>] [options]
    pc-cli run_stage <instance_id> --stage=<stage> --config=<config_file> [--server_ips=<server_ips> --dry_run] [options]
    pc-cli get_instance <instance_id> --config=<config_file> [options]
    pc-cli get_server_ips <instance_id> --config=<config_file> [options]
    pc-cli run_study <study_id> --config=<config_file> --objective_ids=<objective_ids> --input_paths=<input_paths> [--output_dir=<output_dir> --tries_per_stage=<tries_per_stage> --result_visibility=<result_visibility> --run_id=<run_id> --graphapi_version=<graphapi_version> --graphapi_domain=<graphapi_domain> --dry_run] [options]
    pc-cli pre_validate [<study_id>] --config=<config_file> [--objective_ids=<objective_ids>] --input_paths=<input_paths> [--tries_per_stage=<tries_per_stage> --dry_run] [options]
    pc-cli cancel_current_stage <instance_id> --config=<config_file> [options]
    pc-cli print_instance <instance_id> --config=<config_file> [options]
    pc-cli print_current_status <instance_id> --config=<config_file> [options]
    pc-cli print_log_urls <instance_id> --config=<config_file> [options]
    pc-cli get_attribution_dataset_info --dataset_id=<dataset_id> --config=<config_file> [options]
    pc-cli run_attribution --config=<config_file> --dataset_id=<dataset_id> --input_path=<input_path> --timestamp=<timestamp> --attribution_rule=<attribution_rule> --aggregation_type=<aggregation_type> --concurrency=<concurrency> --num_files_per_mpc_container=<num_files_per_mpc_container> --k_anonymity_threshold=<k_anonymity_threshold> [--run_id=<run_id> --graphapi_version=<graphapi_version> --graphapi_domain=<graphapi_domain>] [options]
    pc-cli pre_validate --config=<config_file> [--dataset_id=<dataset_id>] --input_path=<input_path> [--timestamp=<timestamp> --attribution_rule=<attribution_rule> --aggregation_type=<aggregation_type> --concurrency=<concurrency> --num_files_per_mpc_container=<num_files_per_mpc_container> --k_anonymity_threshold=<k_anonymity_threshold>] [options]
    pc-cli bolt_e2e --bolt_config=<bolt_config_file> [options]
    pc-cli secret_scrubber <secret_input_path> <scrubbed_output_path> [options]


Options:
    -h --help                       Show this help
    --log_path=<path>               Override the default path where logs are saved
    --logging_service=<host:port>   Server host and port for enabling the logging service client
    --verbose                       Set logging level to DEBUG
"""

import asyncio
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path, PurePath
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import schema
from docopt import docopt
from fbpcs.bolt.read_config import parse_bolt_config
from fbpcs.common.service.graphapi_trace_logging_service import (
    GraphApiTraceLoggingService,
)
from fbpcs.common.service.secret_scrubber import LoggingSecretScrubber, SecretScrubber
from fbpcs.common.service.trace_logging_service import TraceLoggingService
from fbpcs.infra.logging_service.client.meta.client_manager import ClientManager
from fbpcs.infra.logging_service.client.meta.data_model.lift_run_info import LiftRunInfo
from fbpcs.pl_coordinator.bolt_graphapi_client import BoltGraphAPIClient
from fbpcs.pl_coordinator.exceptions import sys_exit_after
from fbpcs.pl_coordinator.pl_study_runner import run_study
from fbpcs.pl_coordinator.token_validator import TokenValidator
from fbpcs.private_computation.entity.infra_config import PrivateComputationGameType
from fbpcs.private_computation.entity.private_computation_instance import (
    PrivateComputationRole,
)
from fbpcs.private_computation.entity.product_config import (
    AggregationType,
    AttributionRule,
    ResultVisibility,
)
from fbpcs.private_computation.pc_attribution_runner import (
    get_attribution_dataset_info,
    run_attribution,
)
from fbpcs.private_computation.service.constants import FBPCS_BUNDLE_ID
from fbpcs.private_computation.service.pre_validate_service import PreValidateService
from fbpcs.private_computation.service.utils import transform_file_path
from fbpcs.private_computation.stage_flows.private_computation_base_stage_flow import (
    PrivateComputationBaseStageFlow,
)
from fbpcs.private_computation.stage_flows.private_computation_pcf2_stage_flow import (
    PrivateComputationPCF2StageFlow,
)
from fbpcs.private_computation.stage_flows.private_computation_stage_flow import (
    PrivateComputationStageFlow,
)
from fbpcs.private_computation_cli.private_computation_service_wrapper import (
    cancel_current_stage,
    create_instance,
    get_instance,
    get_server_ips,
    get_trace_logging_service,
    print_current_status,
    print_instance,
    print_log_urls,
    run_next,
    run_stage,
    validate,
)
from fbpcs.utils.config_yaml.config_yaml_dict import ConfigYamlDict


def transform_path(path_to_check: str) -> str:
    """
    Checks that a path is a valid file or a valid S3 path.
    If necessary, S3 path will be re-formated into the  “virtual-hosted-style access” format

    Arg:
        path_to_check: string containing file or S3 path

    Returns:
        a string valid file path or a valid S3 path
    """
    # If the file exists on the local system,
    # the path is good and nothing else to do
    # Short term fix for checking if the GCS path is valid.
    if os.path.exists(path_to_check) or "storage.cloud.google.com" in path_to_check:
        return path_to_check
    # Otherwise, check if the path is an S3 path and
    # carry out any necessary transformation into virtual-hosted format
    s3_path = transform_file_path(path_to_check)
    return s3_path


def transform_many_paths(paths_to_check: Union[str, Iterable[str]]) -> List[str]:
    """
    Similar to calling `transform_path` multiple times on a list of paths
    """
    if isinstance(paths_to_check, str):
        paths_to_check = paths_to_check.split(",")

    paths = [transform_path(path) for path in paths_to_check if path]
    return paths


def put_log_metadata(
    logging_service_client: ClientManager,
    game_type: str,
    launch_type: str,
) -> None:
    logger = logging.getLogger(__name__)
    # timestamp is like "20220510T070725.116207Z"
    ts = f"{datetime.utcnow().isoformat().replace('-', '').replace(':', '')}Z"
    # mock data of instances and objectives. Also "partner1" ID below.
    instance_objectives = {"instance1": "objective1", "instance2": "objective2"}
    lift_run_info = LiftRunInfo(
        "v1",
        "LiftRunInfo",
        ts,
        game_type,
        launch_type,
        {"cell_id1": instance_objectives},
    )
    key = f"run/inf/{ts}/{game_type}/{launch_type}/"
    result = logging_service_client.put_metadata(
        "partner1",
        key,
        # pyre-ignore
        lift_run_info.to_json(),
    )
    logger.info(f"logging_service_client.put_metadata: response: {result}.")


def parse_host_port(
    host_port: str,
) -> Tuple[str, int]:
    """
    Parse the host and port in the input string, which is like "host.domain:9090".
    Returns ("", 0) when the input string is empty or has invalid value.
    """
    host_port = host_port or ""
    found = re.search("([^:]+):([0-9]+)", host_port)
    if not found:
        return ("", 0)
    return (found.group(1), int(found.group(2)))


@sys_exit_after
def main(argv: Optional[List[str]] = None) -> None:
    s = schema.Schema(
        {
            "create_instance": bool,
            "validate": bool,
            "run_next": bool,
            "run_stage": bool,
            "get_instance": bool,
            "get_server_ips": bool,
            "run_study": bool,
            "pre_validate": bool,
            "run_attribution": bool,
            "cancel_current_stage": bool,
            "print_instance": bool,
            "print_current_status": bool,
            "print_log_urls": bool,
            "get_attribution_dataset_info": bool,
            "bolt_e2e": bool,
            "secret_scrubber": bool,
            "<instance_id>": schema.Or(None, str),
            "<study_id>": schema.Or(None, str),
            "<secret_input_path>": schema.Or(
                None, schema.And(schema.Use(PurePath), os.path.exists)
            ),
            "<scrubbed_output_path>": schema.Or(None, str),
            "--config": schema.Or(
                None, schema.And(schema.Use(PurePath), os.path.exists)
            ),
            "--bolt_config": schema.Or(
                None, schema.And(schema.Use(PurePath), os.path.exists)
            ),
            "--role": schema.Or(
                None,
                schema.And(
                    schema.Use(str.upper),
                    lambda s: s in ("PUBLISHER", "PARTNER"),
                    schema.Use(PrivateComputationRole),
                ),
            ),
            "--game_type": schema.Or(
                None,
                schema.And(
                    schema.Use(str.upper),
                    lambda s: s in ("LIFT", "ATTRIBUTION", "PRIVATE_ID_DFCA"),
                    schema.Use(PrivateComputationGameType),
                ),
            ),
            "--objective_ids": schema.Or(None, schema.Use(lambda arg: arg.split(","))),
            "--dataset_id": schema.Or(None, str),
            "--input_path": schema.Or(None, transform_path),
            "--input_paths": schema.Or(None, schema.Use(transform_many_paths)),
            "--output_dir": schema.Or(None, transform_path),
            "--aggregated_result_path": schema.Or(None, str),
            "--expected_result_path": schema.Or(None, str),
            "--num_pid_containers": schema.Or(None, schema.Use(int)),
            "--num_mpc_containers": schema.Or(None, schema.Use(int)),
            "--aggregation_type": schema.Or(None, schema.Use(AggregationType)),
            "--attribution_rule": schema.Or(None, schema.Use(AttributionRule)),
            "--timestamp": schema.Or(None, str),
            "--num_files_per_mpc_container": schema.Or(None, schema.Use(int)),
            "--server_ips": schema.Or(None, schema.Use(lambda arg: arg.split(","))),
            "--concurrency": schema.Or(None, schema.Use(int)),
            "--padding_size": schema.Or(None, schema.Use(int)),
            "--k_anonymity_threshold": schema.Or(None, schema.Use(int)),
            "--hmac_key": schema.Or(None, str),
            "--tries_per_stage": schema.Or(None, schema.Use(int)),
            "--dry_run": bool,
            "--logging_service": schema.Or(
                None,
                schema.And(
                    schema.Use(str),
                    lambda arg: parse_host_port(arg)[1] > 0,
                ),
            ),
            "--log_path": schema.Or(None, schema.Use(Path)),
            "--stage_flow": schema.Or(
                None,
                schema.Use(
                    lambda arg: PrivateComputationBaseStageFlow.cls_name_to_cls(arg)
                ),
            ),
            "--result_visibility": schema.Or(
                None,
                schema.Use(lambda arg: ResultVisibility[arg.upper()]),
            ),
            "--run_id": schema.Or(None, str),
            "--graphapi_version": schema.Or(None, str),
            "--graphapi_domain": schema.Or(None, str),
            "--stage": schema.Or(None, str),
            "--verbose": bool,
            "--help": bool,
        }
    )
    arguments = s.validate(docopt(__doc__, argv))

    config = {}
    if arguments["--config"]:
        config = ConfigYamlDict.from_file(arguments["--config"])
    # if no --config given and endpoint isn't bolt_e2e or secret_scrubber, raise
    # exception. All other endpoints need --config.
    elif not arguments["bolt_e2e"] and not arguments["secret_scrubber"]:
        raise ValueError("--config is a required argument")

    log_path = arguments["--log_path"]
    instance_id = arguments["<instance_id>"]

    # if log_path specified, logging using FileHandler, or console StreamHandler
    log_handler = logging.FileHandler(log_path) if log_path else logging.StreamHandler()
    logging.Formatter.converter = time.gmtime
    logging.basicConfig(
        # Root log level must be INFO or up, to avoid logging debug data which might
        # contain PII.
        level=logging.INFO,
        handlers=[log_handler],
    )

    log_format = "%(asctime)sZ %(levelname)s t:%(threadName)s n:%(name)s ! %(message)s"
    log_scrubber = LoggingSecretScrubber(log_format)
    for handler in logging.root.handlers:
        handler.setFormatter(log_scrubber)

    logger = logging.getLogger(__name__)
    log_level = logging.DEBUG if arguments["--verbose"] else logging.INFO
    logger.setLevel(log_level)

    logger.info(f"FBPCS_BUNDLE_ID: {os.getenv(FBPCS_BUNDLE_ID)}")
    # Concatenate all arguments to a string, with every argument wrapped by quotes.
    all_options = f"{sys.argv[1:]}"[1:-1].replace("', '", "' '")
    # E.g. Command line: private_computation_cli 'create_instance' 'partner_15464380' '--config=/tmp/tmp21ari0i6/config_local.yml' ...
    logging.info(f"Command line: {Path(__file__).stem} {all_options}")

    # When the logging service argument is specified, its value is like "localhost:9090".
    # When the argument is missing, logging service client will be disabled, i.e. no-op.
    (logging_service_host, logging_service_port) = parse_host_port(
        arguments["--logging_service"]
    )
    logger.info(
        f"Client using logging service host: {logging_service_host}, port: {logging_service_port}."
    )
    logging_service_client = ClientManager(logging_service_host, logging_service_port)

    # validate token before run study/attribution
    if arguments["run_attribution"] or arguments["run_study"]:
        graph_client = BoltGraphAPIClient(
            config=config,
            logger=logger,
            graphapi_version=arguments["--graphapi_version"],
            graphapi_domain=arguments["--graphapi_domain"],
        )

        study_id_or_dataset_id = arguments["<study_id>"] or arguments["--dataset_id"]
        trace_logging_svc = _get_trace_logging_service(
            config=config,
            client=graph_client,
            study_id_or_dataset_id=study_id_or_dataset_id,
        )
        token_validator = TokenValidator(
            client=graph_client, trace_logging_svc=trace_logging_svc
        )
        token_validator.validate_common_rules()

    if arguments["create_instance"]:
        logger.info(f"Create instance: {instance_id}")
        put_log_metadata(
            logging_service_client, arguments["--game_type"], "create_instance"
        )
        create_instance(
            config=config,
            instance_id=instance_id,
            role=arguments["--role"],
            game_type=arguments["--game_type"],
            logger=logger,
            input_path=arguments["--input_path"],
            output_dir=arguments["--output_dir"],
            num_pid_containers=arguments["--num_pid_containers"],
            num_mpc_containers=arguments["--num_mpc_containers"],
            attribution_rule=arguments["--attribution_rule"],
            aggregation_type=arguments["--aggregation_type"],
            concurrency=arguments["--concurrency"],
            num_files_per_mpc_container=arguments["--num_files_per_mpc_container"],
            hmac_key=arguments["--hmac_key"],
            padding_size=arguments["--padding_size"],
            k_anonymity_threshold=arguments["--k_anonymity_threshold"],
            stage_flow_cls=arguments["--stage_flow"],
            result_visibility=arguments["--result_visibility"],
            run_id=arguments["--run_id"],
        )
    elif arguments["run_next"]:
        logger.info(f"run_next instance: {instance_id}")
        run_next(
            config=config,
            instance_id=instance_id,
            logger=logger,
            server_ips=arguments["--server_ips"],
        )
    elif arguments["run_stage"]:
        stage_name = arguments["--stage"]
        logger.info(f"run_stage: {instance_id=}, {stage_name=}")
        instance = get_instance(config, instance_id, logger)
        stage = instance.stage_flow.get_stage_from_str(stage_name)
        run_stage(
            config=config,
            instance_id=instance_id,
            stage=stage,
            logger=logger,
            server_ips=arguments["--server_ips"],
            dry_run=arguments["--dry_run"],
        )
    elif arguments["get_instance"]:
        logger.info(f"Get instance: {instance_id}")
        instance = get_instance(config, instance_id, logger)
        logger.info(instance)
    elif arguments["get_server_ips"]:
        get_server_ips(config, instance_id, logger)
    elif arguments["validate"]:
        logger.info(f"Validate instance: {instance_id}")
        validate(
            config=config,
            instance_id=instance_id,
            aggregated_result_path=arguments["--aggregated_result_path"],
            expected_result_path=arguments["--expected_result_path"],
            logger=logger,
        )
    elif arguments["run_study"]:
        stage_flow = PrivateComputationStageFlow
        run_study(
            config=config,
            study_id=arguments["<study_id>"],
            objective_ids=arguments["--objective_ids"],
            input_paths=arguments["--input_paths"],
            logger=logger,
            stage_flow=stage_flow,
            num_tries=arguments["--tries_per_stage"],
            dry_run=arguments["--dry_run"],
            result_visibility=arguments["--result_visibility"],
            run_id=arguments["--run_id"],
            graphapi_version=arguments["--graphapi_version"],
            graphapi_domain=arguments["--graphapi_domain"],
            final_stage=PrivateComputationStageFlow.AGGREGATE,
            output_dir=arguments["--output_dir"],
        )
    elif arguments["run_attribution"]:
        stage_flow = PrivateComputationPCF2StageFlow
        run_attribution(
            config=config,
            dataset_id=arguments["--dataset_id"],
            input_path=arguments["--input_path"],
            timestamp=arguments["--timestamp"],
            attribution_rule=arguments["--attribution_rule"],
            aggregation_type=arguments["--aggregation_type"],
            concurrency=arguments["--concurrency"],
            num_files_per_mpc_container=arguments["--num_files_per_mpc_container"],
            k_anonymity_threshold=arguments["--k_anonymity_threshold"],
            logger=logger,
            stage_flow=stage_flow,
            final_stage=PrivateComputationPCF2StageFlow.AGGREGATE,
            run_id=arguments["--run_id"],
            graphapi_version=arguments["--graphapi_version"],
            graphapi_domain=arguments["--graphapi_domain"],
        )

    elif arguments["cancel_current_stage"]:
        logger.info(f"Canceling the current running stage of instance: {instance_id}")
        cancel_current_stage(
            config=config,
            instance_id=instance_id,
            logger=logger,
        )
    elif arguments["print_instance"]:
        print_instance(
            config=config,
            instance_id=instance_id,
            logger=logger,
        )
    elif arguments["print_current_status"]:
        print("print_current_status")
        print_current_status(
            config=config,
            instance_id=instance_id,
            logger=logger,
        )
    elif arguments["print_log_urls"]:
        print_log_urls(
            config=config,
            instance_id=instance_id,
            logger=logger,
        )
    elif arguments["get_attribution_dataset_info"]:
        print(
            get_attribution_dataset_info(
                config=config, dataset_id=arguments["--dataset_id"], logger=logger
            )
        )
    elif arguments["pre_validate"]:
        input_paths = (
            [arguments["--input_path"]]
            if arguments["--input_path"]
            else arguments["--input_paths"]
        )
        PreValidateService.pre_validate(
            config=config,
            input_paths=input_paths,
            logger=logger,
        )
    elif arguments["bolt_e2e"]:
        bolt_config = ConfigYamlDict.from_file(arguments["--bolt_config"])
        bolt_runner, jobs = parse_bolt_config(config=bolt_config, logger=logger)
        bolt_summary = asyncio.run(bolt_runner.run_async(jobs))
        if bolt_summary.is_failure:
            raise RuntimeError(f"Jobs failed: {bolt_summary.failed_job_names}")
        else:
            print("Jobs succeeded")
    elif arguments["secret_scrubber"]:
        with open(arguments["<secret_input_path>"]) as f:
            file_content = f.read()

        secret_scrubber = SecretScrubber()
        scrub_summary = secret_scrubber.scrub(file_content)
        scrubbed_output_path = arguments["<scrubbed_output_path>"]
        with open(scrubbed_output_path, "w") as f:
            f.write(scrub_summary.scrubbed_output)
        print(scrub_summary.get_report())


def _get_trace_logging_service(
    config: Dict[str, Any],
    client: BoltGraphAPIClient,
    study_id_or_dataset_id: Optional[str],
) -> Optional[TraceLoggingService]:

    if study_id_or_dataset_id is None:
        return None

    try:
        endpoint_url = f"{client.graphapi_url}/{study_id_or_dataset_id}/checkpoint"
        default_trace_logger = GraphApiTraceLoggingService(
            access_token=client.access_token,
            endpoint_url=endpoint_url,
        )

        return get_trace_logging_service(
            config, default_trace_logger=default_trace_logger
        )
    except Exception:
        logging.getLogger(__name__).exception(f"Creating trace logger failed")
        return None


if __name__ == "__main__":
    main()
