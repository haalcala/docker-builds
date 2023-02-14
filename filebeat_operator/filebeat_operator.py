import argparse
import traceback
import sys
import re 
import yaml

import boto3
import json
import os
import copy

import real_json

import subprocess

from time import sleep
from threading import Thread

from rich.console import Console
# from rich import print

import dotenv

dotenv.load_dotenv(override=True)

console = Console()

# print("os.environ:", os.environ)

class Config:
    def __init__(self) -> None:
        self.enabled = False
        self.hostname = ""
        self.port = ""


class AWSTag:
    def __init__(self, tag) -> None:
        self.key = tag.Key
        self.val = tag.Value


def parseConfigFromAwsTags(aws_tags, tgs_by_arn, desc):
    tmp_config = Config()

    for tag in aws_tags:
        tag = AWSTag(tag)
        key, value = tag.key, tag.val

        if key == "filebeat_operator" and value == "1":
            tmp_config.enabled = True

        if key == "filebeat_operator.es_host" and value == "auto":
            tmp_config.hostname = value

        if key == "filebeat_operator.es_port" and value:
            tmp_config.port = tgs_by_arn[desc.ResourceArn].Port if value == "auto" else value

    return tmp_config if tmp_config.enabled and tmp_config.hostname and tmp_config.port else None

def filter_targetgroups(targetgroups, filter):
    # print(f"filter: {filter} {filter.items()}")
    filtered_targetgroups = []
    for targetgroup in targetgroups:
        # print("targetgroup:",targetgroup)
        include = True
        for key, value in filter.items():
            # print(f"key: {key} value: {value} {type(value)} {isinstance(value, str)} targetgroup[\"VpcId\"]: {targetgroup['VpcId']}")
            if isinstance(value, str):
                if targetgroup[key] != value:
                    include = False
                    break
            elif isinstance(value, (real_json.ify, dict)) and 'regex' in value:
                regex = value['regex']
                if not re.match(regex, targetgroup[key]):
                    include = False
                    break
        if include:
            filtered_targetgroups.append(targetgroup)
    return filtered_targetgroups

def main(args):
    config = None
    with open(("test-" if args.dev else "") + 'config.yml') as file:
        config = real_json.ify(yaml.load(file, Loader=yaml.FullLoader))
        # print("config:", config)

        # sort_file = yaml.dump(config.filebeat.base_config, sort_keys=True)
        # print("sort_file:", sort_file)
        file.close()

    aws_block = config.aws
    credentials = aws_block.credentials

    region = aws_block.region
    if not region:
        region = os.getenv("REGION")

    output_file = config.filebeat.output_file

    container_name = config.docker.container_name

    aws_access_key_id = credentials.aws_access_key_id
    if not aws_access_key_id:
        aws_access_key_id = os.getenv("AWS_ADMIN_ACCESS_KEY")

    aws_secret_access_key = credentials.aws_secret_access_key
    if not aws_secret_access_key:
        aws_secret_access_key = os.getenv("AWS_ADMIN_SECRET_KEY")

    # print(f"aws_access_key_id: {aws_access_key_id} aws_secret_access_key: {aws_secret_access_key}")

    session = boto3.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        # aws_session_token=SESSION_TOKEN,
        profile_name="vcube-sg"
    )

    def do_check():
        existing_config = None

        try:
            with open(output_file) as file:
                existing_config = real_json.ify(yaml.load(file, Loader=yaml.FullLoader))
                # print("existing_config:", existing_config)
        except Exception as e:
            print(e)

        new_config = real_json.ify(copy.deepcopy(config.filebeat.base_config.__dict__["_data"]))

        # print("----------------------------\nnew_config:",new_config,"\n--------------------------")
        # print("----------------------------\nnew_config['output.elasticsearch'].hosts:",new_config['output.elasticsearch'].hosts,"\n--------------------------")

        elb = session.client('elbv2', region)
        ec2 = session.client('ec2', region)

        tgs = real_json.ify(elb.describe_target_groups())
        tgs = filter_targetgroups(tgs.TargetGroups, config.aws.target.resources[0].conditions[0])

        TargetGroupArns = []
        tgs_by_arn = {}

        for tg in tgs:
            arn = tg.TargetGroupArn
            TargetGroupArns.append(arn)
            tgs_by_arn[arn] = tg

        # print("tgs_by_arn:",tgs_by_arn)

        if not TargetGroupArns:
            return

        tmp_config: Config = None

        # interpret the tags
        for tags in real_json.ify(elb.describe_tags(ResourceArns=TargetGroupArns)).TagDescriptions:
            # print("-----------------------------")
            # print("tags:", tags)

            tmp_config = parseConfigFromAwsTags(tags.Tags, tgs_by_arn, tags)

            # print(f"tmp_config: {tmp_config}")

            # get the host and port
            if tmp_config and tmp_config.enabled:
                health = real_json.ify(elb.describe_target_health(TargetGroupArn=tags.ResourceArn))

                # print("health:", health)

                for target in health.TargetHealthDescriptions:
                    instances = real_json.ify(ec2.describe_instances(InstanceIds=[target.Target.Id]))

                    for instance in instances.Reservations[0].Instances:

                        # print("instance:", instance)

                        hostname = instance.PrivateIpAddress if tmp_config.hostname == "auto" else tmp_config.hostname
                        port = target.Target.Port if tmp_config.port == "auto" else tmp_config.port

                        tmp_config.hostname = hostname
                        tmp_config.port = port

                # print("tmp_config.hostname:", tmp_config.hostname)

                new_config["output.elasticsearch"].hosts = f"{tmp_config.hostname}:{tmp_config.port}"

                break

        print("existing_config:", existing_config, "new_config[\"output.elasticsearch\"][\"hosts\"]:", new_config["output.elasticsearch"].hosts)

        has_changes = existing_config["output.elasticsearch"].hosts != new_config["output.elasticsearch"].hosts
        print(f"has_changes: {has_changes}")

        print("new_config:", new_config)

        if has_changes:
            existing_config["output.elasticsearch"].hosts = new_config["output.elasticsearch"].hosts
            sort_file = yaml.dump(existing_config.__dict__["_data"], sort_keys=True)
            print(sort_file)

            with open(output_file, "w") as file:
                file.write(sort_file)

            with subprocess.Popen(["docker", "restart", container_name], stdout=subprocess.PIPE) as proc:
                print(proc.stdout.read())

    if args.dev:
        do_check()
    else:
        def thread_run():
            while True:
                try:
                    do_check()
                except Exception:
                    traceback.print_exc(file=sys.stdout)

                interval = 300
                
                if config.filebeat_operator and config.filebeat_operator.check_interval:
                    try:
                        interval = int(config.filebeat_operator.check_interval) 
                    except:
                        pass

                print(f"Sleeping for {interval}s")
                
                sleep(interval)

        the_thread = Thread(target=thread_run)

        the_thread.start()

        the_thread.join()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='ProgramName',
        description='Envoyproxy operator',
        epilog='Text at the bottom of help')

    parser.add_argument('-c', '--count')      # option that takes a value
    parser.add_argument('-v', '--verbose',
                        action='store_true')  # on/off flag
    parser.add_argument('-d', '--dev',
                        action='store_true')  # on/off flag

    args = parser.parse_args()

    if args.dev:
        print("\n" * 100)

    print(args)

    main(args)
