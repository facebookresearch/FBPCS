#!/usr/bin/env python3
# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

"""
CLI for running a Private Attribute study


Usage:
    pa-coordinator create_instance <instance_id> --config=<config_file> --input_path=<input_path> --output_dir=<output_dir> --role=<pa_role> --num_pid_containers=<num_pid_containers> --num_mpc_containers=<num_mpc_containers> --num_files_per_mpc_container=<num_files_per_mpc_container> --concurrency=<concurrency>  --attribution_rule=<attribution_rule> --aggregation_type=<aggregation_type> [--padding_size=<padding_size> --k_anonymity_threshold=<k_anonymity_threshold> --hmac_key=<base64_key> --fail_fast] [options]
    pa-coordinator id_match <instance_id> --config=<config_file> [--server_ips=<server_ips> --dry_run] [options]
    pa-coordinator prepare_compute_input <instance_id> --config=<config_file> [--dry_run --log_cost_to_s3] [options]
    pa-coordinator compute_attribution <instance_id> --config=<config_file> [--server_ips=<server_ips> --dry_run --log_cost_to_s3] [options]
    pa-coordinator aggregate_shards <instance_id> --config=<config_file> [--server_ips=<server_ips> --dry_run --log_cost_to_s3] [options]
    pa-coordinator run_next <instance_id> --config=<config_file> [--server_ips=<server_ips>] [options]
    pa-coordinator get_server_ips  <instance_id> --config=<config_file> [options]
    pa-coordinator get_instance <instance_id> --config=<config_file> [options]
    pa-coordinator print_instance <instance_id> --config=<config_file> [options]


Options:
    -h --help                Show this help
    --log_path=<path>        Override the default path where logs are saved
    --verbose                Set logging level to DEBUG
"""
import logging
import os
from pathlib import Path, PurePath
from typing import Optional

import schema
from docopt import docopt
from fbpcp.util import yaml
from fbpcs.private_computation.entity.private_computation_instance import (
    AggregationType,
    AttributionRule,
    PrivateComputationRole,
)
from fbpcs.private_computation.entity.private_computation_instance import (
    PrivateComputationGameType,
)
from fbpcs.private_computation_cli.private_computation_service_wrapper import (
    aggregate_shards,
    compute_metrics,
    create_instance,
    get_instance,
    get_server_ips,
    id_match,
    prepare_compute_input,
    print_instance,
    run_next,
)
from fbpcs.utils.config_yaml.config_yaml_dict import ConfigYamlDict

def main() -> None:
    s = schema.Schema(
        {
            "create_instance": bool,
            "get_instance": bool,
            "print_instance": bool,
            "id_match": bool,
            "prepare_compute_input": bool,
            "compute_attribution": bool,
            "aggregate_shards": bool,
            "run_next": bool,
            "get_server_ips": bool,
            "<instance_id>": schema.Or(None, str),
            "--config": schema.And(schema.Use(PurePath), os.path.exists),
            "--input_path": schema.Or(None, str),
            "--output_dir": schema.Or(None, str),
            "--aggregation_type": schema.Or(None, schema.Use(AggregationType)),
            "--attribution_rule": schema.Or(None, schema.Use(AttributionRule)),
            "--num_pid_containers": schema.Or(None, schema.Use(int)),
            "--num_mpc_containers": schema.Or(None, schema.Use(int)),
            "--num_files_per_mpc_container": schema.Or(None, schema.Use(int)),
            "--padding_size": schema.Or(None, schema.Use(int)),
            "--role": schema.Or(
                None,
                schema.And(
                    schema.Use(str.upper),
                    lambda s: s in ("PUBLISHER", "PARTNER"),
                    schema.Use(PrivateComputationRole),
                ),
            ),
            "--k_anonymity_threshold": schema.Or(None, schema.Use(int)),
            "--server_ips": schema.Or(None, schema.Use(lambda arg: arg.split(","))),
            "--concurrency": schema.Or(None, schema.Use(int)),
            "--hmac_key": schema.Or(None, str),
            "--fail_fast": bool,
            "--dry_run": bool,
            "--log_path": schema.Or(None, schema.Use(Path)),
            "--log_cost_to_s3": schema.Or(None, schema.Use(bool)),
            "--verbose": bool,
            "--help": bool,
        }
    )

    arguments = s.validate(docopt(__doc__))
    config = ConfigYamlDict.from_dict(yaml.load(Path(arguments["--config"])))

    log_path = arguments["--log_path"]
    log_level = logging.DEBUG if arguments["--verbose"] else logging.INFO
    logging.basicConfig(
        filename=log_path,
        level=log_level,
        format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
    )
    logger = logging.getLogger(__name__)

    instance_id = arguments["<instance_id>"]

    if arguments["create_instance"]:
        logger.info(f"Create instance: {instance_id}")

        # Optional arguments
        hmac_key: Optional[str] = arguments["--hmac_key"]
        padding_size: Optional[int] = arguments["--padding_size"]
        k_anonymity_threshold: Optional[int] = arguments["--k_anonymity_threshold"]

        create_instance(
            instance_id=instance_id,
            config=config,
            input_path=arguments["--input_path"],
            output_dir=arguments["--output_dir"],
            role=arguments["--role"],
            game_type=PrivateComputationGameType.ATTRIBUTION,
            hmac_key=hmac_key,
            num_pid_containers=arguments["--num_pid_containers"],
            num_mpc_containers=arguments["--num_mpc_containers"],
            num_files_per_mpc_container=arguments["--num_files_per_mpc_container"],
            attribution_rule=arguments["--attribution_rule"],
            aggregation_type=arguments["--aggregation_type"],
            padding_size=padding_size,
            concurrency=arguments["--concurrency"],
            k_anonymity_threshold=k_anonymity_threshold,
            logger=logger,
            fail_fast=arguments["--fail_fast"],
        )
    elif arguments["get_instance"]:
        logger.info(f"Get instance: {instance_id}")
        get_instance(
            config=config,
            instance_id=instance_id,
            logger=logger,
        )
    elif arguments["id_match"]:
        logger.info(f"Run id match on instance: {instance_id}")
        id_match(
            config=config,
            instance_id=instance_id,
            logger=logger,
            server_ips=arguments["--server_ips"],
            dry_run=arguments["--dry_run"],
        )
    elif arguments["prepare_compute_input"]:
        logger.info(f"Run id match on instance: {instance_id}")
        prepare_compute_input(
            config=config,
            instance_id=instance_id,
            logger=logger,
            dry_run=arguments["--dry_run"],
            log_cost_to_s3=arguments["--log_cost_to_s3"],
        )
    elif arguments["compute_attribution"]:
        logger.info(f"Compute instance: {instance_id}")
        compute_metrics(
            config=config,
            instance_id=instance_id,
            server_ips=arguments["--server_ips"],
            logger=logger,
            dry_run=arguments["--dry_run"],
            log_cost_to_s3=arguments["--log_cost_to_s3"],
        )
    elif arguments["aggregate_shards"]:
        aggregate_shards(
            config=config,
            instance_id=instance_id,
            server_ips=arguments["--server_ips"],
            logger=logger,
            dry_run=arguments["--dry_run"],
            log_cost_to_s3=arguments["--log_cost_to_s3"],
        )
    elif arguments["run_next"]:
        logger.info(f"run_next instance: {instance_id}")
        run_next(
            config=config,
            instance_id=instance_id,
            logger=logger,
            server_ips=arguments["--server_ips"],
        )
    elif arguments["get_server_ips"]:
        get_server_ips(
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


if __name__ == "__main__":
    main()
