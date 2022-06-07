# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.amazon.aws.operators.emr_add_steps import EmrAddStepsOperator
from airflow.providers.amazon.aws.operators.emr_create_job_flow import (
    EmrCreateJobFlowOperator,
)
from airflow.providers.amazon.aws.sensors.emr_step import EmrStepSensor
from airflow.providers.amazon.aws.sensors.s3_key import S3KeySensor


dag = DAG(
    dag_id="meta_mr_pid_dag",
    description="Task to run Meta side Private Identity Map Reduce job on AWS EMR",
    dagrun_timeout=timedelta(hours=10),
    start_date=datetime(2022, 5, 12),
    schedule_interval=None,
    catchup=False,
)

JOB_FLOW_OVERRIDES = {
    "Name": "meta-mr-pid-airflow",
    "ReleaseLabel": "emr-6.4.0",
    "Applications": [
        {"Name": "Hadoop"},
        {"Name": "Spark"},
    ],
    "Instances": {
        "InstanceGroups": [
            {
                "Name": "Master nodes",
                "Market": "ON_DEMAND",
                "InstanceRole": "MASTER",
                "InstanceType": "m5.4xlarge",
                "InstanceCount": 1,
            },
            {
                "Name": "Core instances",
                "Market": "ON_DEMAND",
                "InstanceRole": "CORE",
                "InstanceType": "m5.4xlarge",
                "InstanceCount": 5,
            },
        ],
        "KeepJobFlowAliveWhenNoSteps": False,
        "TerminationProtected": False,
    },
    "VisibleToAllUsers": True,
    "JobFlowRole": "EMR_EC2_DefaultRole",
    "ServiceRole": "EMR_DefaultRole",
    "Tags": [
        {"Key": "Environment", "Value": "Development"},
        {"Key": "Name", "Value": "Meta MR PID Airflow Project"},
    ],
}

cluster_creator = EmrCreateJobFlowOperator(
    task_id="create_emr_cluster",
    aws_conn_id="aws_default",
    emr_conn_id="emr_default",
    job_flow_overrides=JOB_FLOW_OVERRIDES,
    dag=dag,
)

SPARK_STEP_1 = [
    {
        "Name": "meta-mr-pid-stage1",
        "ActionOnFailure": "TERMINATE_JOB_FLOW",
        "HadoopJarStep": {
            "Jar": "command-runner.jar",
            "Args": [
                "spark-submit",
                "--deploy-mode",
                "cluster",
                "--master",
                "yarn",
                "--jars",
                "{{ dag_run.conf['pidMrMultikeyJarPath'] }}",
                "--num-executors",
                "15",
                "--executor-cores",
                "8",
                "--executor-memory",
                "30G",
                "--conf",
                "spark.driver.memory=40G",
                "--conf",
                "spark.sql.shuffle.partitions=30",
                "--conf",
                "spark.yarn.maxAppAttempts=1",
                "--class",
                "com.meta.mr.multikey.publisher.PubStageOne",
                "{{ dag_run.conf['pidMrMultikeyJarPath'] }}",
                "s3://{{ dag_run.conf['metaBucketName'] }}/{{ dag_run.conf['instanceId'] }}",
                "{{ dag_run.conf['outputPath'] }}",
                "{{ dag_run.conf['inputPath'] }}",
            ],
        },
    }
]

stage1_adder = EmrAddStepsOperator(
    task_id="add_stage_1",
    job_flow_id="{{ task_instance.xcom_pull(task_ids='create_emr_cluster', key='return_value') }}",
    aws_conn_id="aws_default",
    steps=SPARK_STEP_1,
    dag=dag,
)

stage1_checker = EmrStepSensor(
    task_id="watch_stage1",
    job_flow_id="{{ task_instance.xcom_pull(task_ids='create_emr_cluster', key='return_value') }}",
    step_id="{{ task_instance.xcom_pull(task_ids='add_stage_1', key='return_value')[0] }}",
    aws_conn_id="aws_default",
    dag=dag,
)

sensor_stage2_key = S3KeySensor(
    task_id="s3_sensor_stage2_key",
    bucket_name="{{ dag_run.conf['advBucketName'] }}",
    bucket_key="{{ dag_run.conf['instanceId'] }}/step_1_meta_enc_kc_kp/_SUCCESS",
)

SPARK_STEP_2 = [
    {
        "Name": "meta-mr-pid-stage2",
        "ActionOnFailure": "TERMINATE_JOB_FLOW",
        "HadoopJarStep": {
            "Jar": "command-runner.jar",
            "Args": [
                "spark-submit",
                "--deploy-mode",
                "cluster",
                "--master",
                "yarn",
                "--jars",
                "{{ dag_run.conf['pidMrMultikeyJarPath'] }}",
                "--num-executors",
                "15",
                "--executor-cores",
                "8",
                "--executor-memory",
                "30G",
                "--conf",
                "spark.driver.memory=40G",
                "--conf",
                "spark.sql.shuffle.partitions=30",
                "--conf",
                "spark.yarn.maxAppAttempts=1",
                "--class",
                "com.meta.mr.multikey.publisher.PubStageTwo",
                "{{ dag_run.conf['pidMrMultikeyJarPath'] }}",
                "s3://{{ dag_run.conf['metaBucketName'] }}/{{ dag_run.conf['instanceId'] }}",
                "{{ dag_run.conf['outputPath'] }}",
                "s3://{{ dag_run.conf['advBucketName'] }}/{{ dag_run.conf['instanceId'] }}",
            ],
        },
    }
]

stage2_adder = EmrAddStepsOperator(
    task_id="add_stage_2",
    job_flow_id="{{ task_instance.xcom_pull(task_ids='create_emr_cluster', key='return_value') }}",
    aws_conn_id="aws_default",
    steps=SPARK_STEP_2,
    dag=dag,
)

stage2_checker = EmrStepSensor(
    task_id="watch_stage2",
    job_flow_id="{{ task_instance.xcom_pull(task_ids='create_emr_cluster', key='return_value') }}",
    step_id="{{ task_instance.xcom_pull(task_ids='add_stage_2', key='return_value')[0] }}",
    aws_conn_id="aws_default",
    dag=dag,
)

sensor_stage3_key = S3KeySensor(
    task_id="s3_sensor_stage3_key",
    bucket_name="{{ dag_run.conf['advBucketName'] }}",
    bucket_key="{{ dag_run.conf['instanceId'] }}/step_3_meta_all_enc_kc_kp_rc_rp/_SUCCESS",
)

SPARK_STEP_3 = [
    {
        "Name": "meta-mr-pid-stage3",
        "ActionOnFailure": "TERMINATE_JOB_FLOW",
        "HadoopJarStep": {
            "Jar": "command-runner.jar",
            "Args": [
                "spark-submit",
                "--deploy-mode",
                "cluster",
                "--master",
                "yarn",
                "--jars",
                "{{ dag_run.conf['pidMrMultikeyJarPath'] }}",
                "--num-executors",
                "15",
                "--executor-cores",
                "8",
                "--executor-memory",
                "30G",
                "--conf",
                "spark.driver.memory=40G",
                "--conf",
                "spark.sql.shuffle.partitions=30",
                "--conf",
                "spark.yarn.maxAppAttempts=1",
                "--class",
                "com.meta.mr.multikey.publisher.PubStageThree",
                "{{ dag_run.conf['pidMrMultikeyJarPath'] }}",
                "{{ dag_run.conf['outputPath'] }}",
                "s3://{{ dag_run.conf['advBucketName'] }}/{{ dag_run.conf['instanceId'] }}",
            ],
        },
    }
]

stage3_adder = EmrAddStepsOperator(
    task_id="add_stage_3",
    job_flow_id="{{ task_instance.xcom_pull(task_ids='create_emr_cluster', key='return_value') }}",
    aws_conn_id="aws_default",
    steps=SPARK_STEP_3,
    dag=dag,
)

stage3_checker = EmrStepSensor(
    task_id="watch_stage3",
    job_flow_id="{{ task_instance.xcom_pull(task_ids='create_emr_cluster', key='return_value') }}",
    step_id="{{ task_instance.xcom_pull(task_ids='add_stage_3', key='return_value')[0] }}",
    aws_conn_id="aws_default",
    dag=dag,
)


(
    cluster_creator
    >> stage1_adder
    >> stage1_checker
    >> sensor_stage2_key
    >> stage2_adder
    >> stage2_checker
    >> sensor_stage3_key
    >> stage3_adder
    >> stage3_checker
)
