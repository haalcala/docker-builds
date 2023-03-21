import argparse
import traceback
import sys
import re 
import yaml

import boto3
import json
import os
import copy

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
            elif isinstance(value, (GetWrappedJson, dict)) and 'regex' in value:
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
        config = GetWrappedJson(yaml.load(file, Loader=yaml.FullLoader))
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
                existing_config = GetWrappedJson(yaml.load(file, Loader=yaml.FullLoader))
                # print("existing_config:", existing_config)
        except Exception as e:
            print(e)

        new_config = GetWrappedJson(copy.deepcopy(config.filebeat.base_config.__dict__["_data"]))

        # print("----------------------------\nnew_config:",new_config,"\n--------------------------")
        # print("----------------------------\nnew_config['output.elasticsearch'].hosts:",new_config['output.elasticsearch'].hosts,"\n--------------------------")

        elb = session.client('elbv2', region)
        ec2 = session.client('ec2', region)

        tgs = GetWrappedJson(elb.describe_target_groups())
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
        for tags in GetWrappedJson(elb.describe_tags(ResourceArns=TargetGroupArns)).TagDescriptions:
            # print("-----------------------------")
            # print("tags:", tags)

            tmp_config = parseConfigFromAwsTags(tags.Tags, tgs_by_arn, tags)

            # print(f"tmp_config: {tmp_config}")

            # get the host and port
            if tmp_config and tmp_config.enabled:
                health = GetWrappedJson(elb.describe_target_health(TargetGroupArn=tags.ResourceArn))

                # print("health:", health)

                for target in health.TargetHealthDescriptions:
                    instances = GetWrappedJson(ec2.describe_instances(InstanceIds=[target.Target.Id]))

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

class GetWrappedJson:
    def __init__(self, data):
        self._data = data
    
    def __getattr__(self, name):
        # print(f"Getting attribute {name} {type(self._data)}")

        if isinstance(self._data, dict) and name in self._data:
            value = self._data[name]
            if isinstance(value, (dict, list)):
                return GetWrappedJson(value)
            return value
        elif isinstance(self._data, dict):
            if name in dir(dict):
                return getattr(self._data, name)
            return None
        elif isinstance(self._data, list):
            if name == "append":
                def wrapped_append(kw):
                    if isinstance(kw, GetWrappedJson):
                        self._data.append(kw._data)
                    else:
                        self._data.append(kw)
                return wrapped_append
            if name in dir(list):
                return getattr(self._data, name)
            return None
        return None

    def __getitem__(self, name):
        # print(f"Getting item {name} {type(self._data)}")
        if isinstance(self._data, list) and isinstance(name, int) and 0 <= name < len(self._data):
            value = self._data[name]
            if isinstance(value, (dict, list)):
                return GetWrappedJson(value)
            return value
        elif isinstance(self._data, dict) and name in self._data:
            value = self._data[name]
            if isinstance(value, (dict, list)):
                return GetWrappedJson(value)
            return value
        return None

    def __setattr__(self, name, value):
        if name != "_data":
            if isinstance(self._data, dict):
                if isinstance(value, GetWrappedJson):
                    self._data[name] = value._data
                else:
                    self._data[name] = value
        else:
            super().__setattr__(name, value)

    def __setitem__(self, key, value):
        if isinstance(self._data, list) and isinstance(key, int) and 0 <= key < len(self._data):
            if isinstance(value, GetWrappedJson):
                self._data[key] = value._data
            else:
                self._data[key] = value
        elif isinstance(self._data, dict):
            if isinstance(value, GetWrappedJson):
                self._data[key] = value._data
            else:
                self._data[key] = value

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        for value in self._data:
            if isinstance(value, (dict, list)):
                yield GetWrappedJson(value)
            else:
                yield value


    def __str__(self):
        return str(self._data)

    def __repr__(self):
        return repr(self._data)


    def __bool__(self):
        return bool(self._data)


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
