#!/usr/bin/env python3
# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.


"""
CLI for running a Private Lift study


Usage:
    pl-coordinator create_instance <instance_id> --config=<config_file> --role=<pl_role> --input_path=<input_path> --output_dir=<output_dir> --num_pid_containers=<num_pid_containers> --num_mpc_containers=<num_mpc_containers> [--concurrency=<concurrency> --game_type=<game_type> --num_files_per_mpc_container=<num_files_per_mpc_container> --hmac_key=<base64_key> --fail_fast] [options]
    pl-coordinator id_match <instance_id> --config=<config_file> [--server_ips=<server_ips> --dry_run] [options]
    pl-coordinator compute <instance_id> --config=<config_file> [--server_ips=<server_ips> --dry_run] [options]
    pl-coordinator aggregate <instance_id> --config=<config_file> [--server_ips=<server_ips> --dry_run] [options]
    pl-coordinator validate <instance_id> --config=<config_file> --aggregated_result_path=<aggregated_result_path> --expected_result_path=<expected_result_path> [options]
    pl-coordinator run_post_processing_handlers <instance_id> --config=<config_file> [--aggregated_result_path=<aggregated_result_path> --dry_run] [options]
    pl-coordinator run_next <instance_id> --config=<config_file> [--server_ips=<server_ips>] [options]
    pl-coordinator get <instance_id> --config=<config_file> [options]
    pl-coordinator get_server_ips <instance_id> --config=<config_file> [options]
    pl-coordinator get_pid <instance_id> --config=<config_file> [options]
    pl-coordinator get_mpc <instance_id> --config=<config_file> [options]
    pl-coordinator run_instance <instance_id> --config=<config_file> --input_path=<input_path> --num_shards=<num_shards> [--tries_per_stage=<tries_per_stage> --dry_run] [options]
    pl-coordinator run_instances <instance_ids> --config=<config_file> --input_paths=<input_paths> --num_shards_list=<num_shards_list> [--tries_per_stage=<tries_per_stage> --dry_run] [options]
    pl-coordinator run_study <study_id> --config=<config_file> --objective_ids=<objective_ids> --input_paths=<input_paths> [--tries_per_stage=<tries_per_stage> --dry_run] [options]
    pl-coordinator cancel_current_stage <instance_id> --config=<config_file> [options]

Options:
    -h --help                Show this help
    --log_path=<path>        Override the default path where logs are saved
    --verbose                Set logging level to DEBUG
"""

import logging
import os
from pathlib import Path, PurePath

import schema
from docopt import docopt
from fbpcp.util import yaml
from fbpcs.pl_coordinator.pl_instance_runner import run_instance, run_instances
from fbpcs.pl_coordinator.pl_study_runner import run_study
from fbpcs.private_computation.entity.private_computation_instance import (
    PrivateComputationRole,
    PrivateComputationGameType,
)
from fbpcs.private_computation_cli.private_computation_service_wrapper import (
    aggregate_shards,
    compute,
    create_instance,
    get_instance,
    get_mpc,
    get_pid,
    get_server_ips,
    id_match,
    run_post_processing_handlers,
    validate,
    cancel_current_stage,
    run_next
)


def main():
    s = schema.Schema(
        {
            "create_instance": bool,
            "id_match": bool,
            "compute": bool,
            "aggregate": bool,
            "validate": bool,
            "run_post_processing_handlers": bool,
            "get": bool,
            "run_next": bool,
            "get_server_ips": bool,
            "get_pid": bool,
            "get_mpc": bool,
            "run_instance": bool,
            "run_instances": bool,
            "run_study": bool,
            "cancel_current_stage": bool,
            "<instance_id>": schema.Or(None, str),
            "<instance_ids>": schema.Or(None, schema.Use(lambda arg: arg.split(","))),
            "<study_id>": schema.Or(None, str),
            "--config": schema.And(schema.Use(PurePath), os.path.exists),
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
                    lambda s: s in ("LIFT", "ATTRIBUTION"),
                    schema.Use(PrivateComputationGameType),
                ),
            ),
            "--objective_ids": schema.Or(None, schema.Use(lambda arg: arg.split(","))),
            "--input_path": schema.Or(None, str),
            "--input_paths": schema.Or(None, schema.Use(lambda arg: arg.split(","))),
            "--output_dir": schema.Or(None, str),
            "--aggregated_result_path": schema.Or(None, str),
            "--expected_result_path": schema.Or(None, str),
            "--num_pid_containers": schema.Or(None, schema.Use(int)),
            "--num_mpc_containers": schema.Or(None, schema.Use(int)),
            "--num_files_per_mpc_container": schema.Or(None, schema.Use(int)),
            "--num_shards": schema.Or(None, schema.Use(int)),
            "--num_shards_list": schema.Or(
                None, schema.Use(lambda arg: arg.split(","))
            ),
            "--server_ips": schema.Or(None, schema.Use(lambda arg: arg.split(","))),
            "--concurrency": schema.Or(None, schema.Use(int)),
            "--hmac_key": schema.Or(None, str),
            "--tries_per_stage": schema.Or(None, schema.Use(int)),
            "--fail_fast": bool,
            "--dry_run": bool,
            "--log_path": schema.Or(None, schema.Use(Path)),
            "--verbose": bool,
            "--help": bool,
        }
    )

    arguments = s.validate(docopt(__doc__))
    config = yaml.load(Path(arguments["--config"]))

    log_path = arguments["--log_path"]
    log_level = logging.DEBUG if arguments["--verbose"] else logging.INFO
    instance_id = arguments["<instance_id>"]

    logging.basicConfig(filename=log_path, level=log_level)
    logger = logging.getLogger(__name__)

    if arguments["create_instance"]:
        logger.info(f"Create instance: {instance_id}")
        create_instance(
            config=config,
            instance_id=instance_id,
            role=arguments["--role"],
            logger=logger,
            input_path=arguments["--input_path"],
            output_dir=arguments["--output_dir"],
            num_pid_containers=arguments["--num_pid_containers"],
            num_mpc_containers=arguments["--num_mpc_containers"],
            concurrency=arguments["--concurrency"],
            num_files_per_mpc_container=arguments["--num_files_per_mpc_container"],
            game_type=arguments["--game_type"],
            hmac_key=arguments["--hmac_key"],
            fail_fast=arguments["--fail_fast"],
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
    elif arguments["compute"]:
        logger.info(f"Compute instance: {instance_id}")
        compute(
            config=config,
            instance_id=instance_id,
            logger=logger,
            server_ips=arguments["--server_ips"],
            dry_run=arguments["--dry_run"],
        )
    elif arguments["run_post_processing_handlers"]:
        logger.info(f"post processing handlers instance: {instance_id}")
        run_post_processing_handlers(
            config=config,
            instance_id=instance_id,
            logger=logger,
            aggregated_result_path=arguments["--aggregated_result_path"],
            dry_run=arguments["--dry_run"],
        )
    elif arguments["run_next"]:
        logger.info(f"run_next instance: {instance_id}")
        run_next(
            config=config,
            instance_id=instance_id,
            logger=logger,
            server_ips=arguments["--server_ips"],
        )
    elif arguments["get"]:
        logger.info(f"Get instance: {instance_id}")
        get_instance(config, instance_id, logger)
    elif arguments["get_server_ips"]:
        get_server_ips(config, instance_id, logger)
    elif arguments["get_pid"]:
        logger.info(f"Get PID instance: {instance_id}")
        get_pid(config, instance_id, logger)
    elif arguments["get_mpc"]:
        logger.info(f"Get MPC instance: {instance_id}")
        get_mpc(config, instance_id, logger)
    elif arguments["aggregate"]:
        logger.info(f"Aggregate instance: {instance_id}")
        aggregate_shards(
            config=config,
            instance_id=instance_id,
            logger=logger,
            server_ips=arguments["--server_ips"],
            dry_run=arguments["--dry_run"],
        )
    elif arguments["validate"]:
        logger.info(f"Vallidate instance: {instance_id}")
        validate(
            config=config,
            instance_id=instance_id,
            aggregated_result_path=arguments["--aggregated_result_path"],
            expected_result_path=arguments["--expected_result_path"],
            logger=logger,
        )
    elif arguments["run_instance"]:
        logger.info(f"Running instance: {instance_id}")
        run_instance(
            config=config,
            instance_id=instance_id,
            input_path=arguments["--input_path"],
            num_shards=["--num_shards"],
            logger=logger,
            num_tries=arguments["--tries_per_stage"],
            dry_run=arguments["--dry_run"],
        )
    elif arguments["run_instances"]:
        run_instances(
            config=config,
            instance_ids=arguments["<instance_ids>"],
            input_paths=arguments["--input_paths"],
            num_shards_list=arguments["--num_shards_list"],
            logger=logger,
            num_tries=arguments["--tries_per_stage"],
            dry_run=arguments["--dry_run"],
        )
    elif arguments["run_study"]:
        run_study(
            config=config,
            study_id=arguments["<study_id>"],
            objective_ids=arguments["--objective_ids"],
            input_paths=arguments["--input_paths"],
            logger=logger,
            num_tries=arguments["--tries_per_stage"],
            dry_run=arguments["--dry_run"],
        )
    elif arguments["cancel_current_stage"]:
        logger.info(f"Canceling the current running stage of instance: {instance_id}")
        cancel_current_stage(
            config=config,
            instance_id=instance_id,
            logger=logger,
        )


if __name__ == "__main__":
    main()
