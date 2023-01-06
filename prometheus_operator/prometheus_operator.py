import argparse
import traceback
import sys
from typing import List
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

console = Console()

class HostPortConfig:
    def __init__(self) -> None:
        self.enabled = False
        self.name = ""
        self.hostname = ""
        self.job_name = ""
        self.hostnames = []
        self.port = ""

    def __str__(self):
        return f"{self.__class__.__name__}[enabled: {self.enabled}, name: {self.name}, hostname: {self.hostname}, job_name: {self.job_name}, hostnames: {self.hostnames}, port: {self.port}, ]"


class AWSTag:
    def __init__(self, tag) -> None:
        self.key = tag.Key
        self.val = tag.Value


class OperatedConfig:
    def __init__(self) -> None:
        self.config = None
        self.scrape_configs:List[HostPortConfig] = []

    def LoadFromFile(self, config_file):
        try:
            with open(config_file) as file:
                self.config = GetWrappedJson(yaml.load(file, Loader=yaml.FullLoader))
                self.scrape_configs = self.config.scrape_configs
                # print(self.config)
        except Exception as e:
            print(e)

        return self

    def LoadFromDict(self, dict_config):
        # print("dict_config:", dict_config)
        self.config = GetWrappedJson(copy.deepcopy(dict_config.__dict__["_data"]))
        self.scrape_configs = self.config.scrape_configs
        return self

    def __str__(self):
        return f"{self.__class__.__name__}[scrape_configs: {self.scrape_configs}]"


class OperatorConfig:
    def __init__(self) -> None:
        self.aws_block = ""
        self.credentials = ""
        self.region = ""
        self.output_file = ""
        self.container_name = ""
        self.aws_access_key_id = ""
        self.aws_secret_access_key = ""
        self.config = None

    def load(self):
        config = None
        with open(("test-" if args.dev else "")+'config.yml') as file:
            config = GetWrappedJson(yaml.load(file, Loader=yaml.FullLoader))
            print("config:", config)
            file.close()

        self.config = config

        aws_block = config.aws
        self.aws_block = aws_block

        credentials = aws_block.credentials
        self.credentials = credentials

        region = aws_block.region

        if not region:
            region = os.getenv("REGION")

        self.region = region

        output_file = config.prometheus.output_file
        self.output_file = output_file

        container_name = config.docker.container_name
        self.container_name = container_name

        aws_access_key_id = credentials.aws_access_key_id
        if not aws_access_key_id:
            aws_access_key_id = os.getenv("aws_access_key_id")

        self.aws_access_key_id = aws_access_key_id

        aws_secret_access_key = credentials.aws_secret_access_key
        if not aws_secret_access_key:
            aws_secret_access_key = os.getenv("aws_secret_access_key")

        self.aws_secret_access_key = aws_secret_access_key

        return self

    def GetCurrentOperatedConfig(self) -> OperatedConfig:
        return OperatedConfig().LoadFromFile(self.output_file)

    def GetOperatedConfigTemplate(self) -> OperatedConfig:
        return OperatedConfig().LoadFromDict(self.config.prometheus.base_config)


def ParseConfigFromAwsTags(desc, tgs_by_arn):
    token = "prometheus_operator.job."

    jobs:List[HostPortConfig] = []
    ret:List[HostPortConfig] = []

    # find clusters
    for tag in desc.Tags:
        tag = AWSTag(tag)
        key, value = tag.key, tag.val

        if key.find(token + "name.") == 0:
            job_name = key[len(token + "name."):]
            print("job_name:", job_name)

            tmp_config = HostPortConfig()

            tmp_config.job_name = tmp_config.name = job_name

            if value == "1":
                tmp_config.enabled = True

            jobs.append(tmp_config)

    # find cluster config
    for tmp_config in jobs:
        job_token = token + tmp_config.job_name + "."
        # print("cluster_token:", cluster_token)

        for tag in desc.Tags:
            tag = AWSTag(tag)
            key, value = tag.key, tag.val

            if key.find(job_token) == 0:
                prop = key[len(job_token):]
                # print("2222 prop:", prop)

                if prop == "port" and value:
                    tmp_config.port = tgs_by_arn[desc.ResourceArn].Port if value == "auto" else value
                if prop == "hostname" and value:
                    if not tmp_config.hostnames:
                        tmp_config.hostnames = []

                    tmp_config.hostname = value

    for host_port in jobs:
        if host_port.job_name and host_port.name and host_port.hostname and host_port.port:
            ret.append(host_port)

    return ret

def compare_prometheus_configs(config1:OperatedConfig, config2:OperatedConfig):
    """Returns False if there's difference"""

    if len(config1.scrape_configs) != len(config2.scrape_configs):
        return False

    config1_by_job_name = {}
    for scrape_config in config1.scrape_configs:
        config1_by_job_name[scrape_config.job_name] = scrape_config

    config2_by_job_name = {}
    for scrape_config in config2.scrape_configs:
        config2_by_job_name[scrape_config.job_name] = scrape_config

    # print("config1_by_job_name:",config1_by_job_name)
    # print("config2_by_job_name:",config2_by_job_name)
    
    config1_job_names = config1_by_job_name.keys()
    config2_job_names = config2_by_job_name.keys()

    # print("config1_job_names:", config1_job_names)
    # print("config2_job_names:", config2_job_names)

    if len(config1_job_names) != len(config2_job_names):
        return False
    
    for job_name in config1_job_names:
        scrape_config1 = config1_by_job_name.get(job_name)
        scrape_config2 = config2_by_job_name.get(job_name)

        # print("scrape_config1:", scrape_config1)
        # print("scrape_config2:", scrape_config2)

        if scrape_config1 and not scrape_config2:
            return False

        if not scrape_config1 and scrape_config2:
            return False

        if len(scrape_config1.keys()) != len(scrape_config2.keys()):
            return False

        scrape_config_targets1 = scrape_config1.static_configs[0].targets
        scrape_config_targets2 = scrape_config2.static_configs[0].targets

        # print("scrape_config_targets1:", scrape_config_targets1)
        # print("scrape_config_targets2:", scrape_config_targets2)

        if len(scrape_config_targets1) != len(scrape_config_targets2):
            return False

        for target in scrape_config_targets1:
            if target not in scrape_config_targets2:
                return False

    return True

def main(args):
    config = OperatorConfig().load()

    output_file = config.output_file
    container_name = config.container_name

    region = config.region
    aws_access_key_id = config.aws_access_key_id
    aws_secret_access_key = config.aws_secret_access_key

    # print(f"aws_access_key_id: {aws_access_key_id} aws_secret_access_key: {aws_secret_access_key}")

    session = boto3.Session(
        aws_access_key_id = aws_access_key_id,
        aws_secret_access_key = aws_secret_access_key,
        # aws_session_token=SESSION_TOKEN,
        profile_name="vcube-sg"        
    )

    def do_check():
        existing_config = config.GetCurrentOperatedConfig()

        tmp_job_config = config.GetOperatedConfigTemplate()

        # print("existing_config.scrape_configs:", existing_config.scrape_configs)
        # print("tmp_cluster_config.scrape_configs:", tmp_job_config.scrape_configs)


        elb = session.client('elbv2', region)
        ec2 = session.client('ec2', region)

        tgs = GetWrappedJson(elb.describe_target_groups())
        tgs = filter_targetgroups(tgs.TargetGroups, config.config.aws.target.resources[0].conditions[0])

        # print("tgs:",tgs)

        TargetGroupArns = []
        tgs_by_arn = {}

        for tg in tgs:
            arn = tg.TargetGroupArn
            TargetGroupArns.append(arn)
            tgs_by_arn[arn] = tg

        print("tgs_by_arn:",tgs_by_arn)

        if not TargetGroupArns:
            return

        new_config = {}

        for desc in GetWrappedJson(elb.describe_tags(ResourceArns=TargetGroupArns)).TagDescriptions:
            # print("\n\n-----------------------------")
            # print("desc:", desc)

            tag_configs = ParseConfigFromAwsTags(desc, tgs_by_arn)
            print("Found scrape_configs:", tag_configs)

            for tag_config in tag_configs:
                print(f"1111 tag_config: {tag_config}")

                # Don't process if not enabled
                if not tag_config.enabled:
                    continue

                health = GetWrappedJson(elb.describe_target_health(TargetGroupArn=desc.ResourceArn))

                # print("health:", health)

                for target in health.TargetHealthDescriptions:
                    instances = GetWrappedJson(ec2.describe_instances(InstanceIds=[target.Target.Id]))

                    for instance in instances.Reservations[0].Instances:

                        # print("instance:", instance)

                        target_host = instance.PrivateIpAddress
                        target_port = target.Target.Port if tag_config.port == "auto" else tag_config.port

                        tag_config.hostnames.append(f"{target_host}:{target_port}")

                # print("tag_config:",tag_config)

                if len(tag_config.hostnames) > 0:
                    scrape_config_job = None

                    for scrape_config in tmp_job_config.scrape_configs:
                        if scrape_config.job_name == tag_config.job_name:
                            scrape_config_job = scrape_config               
                            break

                    if not scrape_config_job:
                        scrape_config_job = GetWrappedJson({
                            "job_name": tag_config.job_name, 
                            "static_configs": [
                                {
                                    "targets": []
                                }
                            ]})

                        tmp_job_config.scrape_configs.append(scrape_config_job)

                    # print("scrape_config_job:",scrape_config_job)
                    # print("tmp_job_config:",tmp_job_config)

                    for new_hostname in tag_config.hostnames:
                        if not new_hostname in scrape_config_job.static_configs[0].targets:
                            scrape_config_job.static_configs[0].targets.append(new_hostname)

        print("Checking if there's changes in the config ...")
        has_changes = not compare_prometheus_configs(tmp_job_config, existing_config)

        # print("tmp_job_config:", tmp_job_config)

        print(f"has_changes: {has_changes}")

        if has_changes:
            sort_file = yaml.dump(tmp_job_config.config.__dict__["_data"], sort_keys=True)
            print(sort_file)

            with open(output_file, "w") as file:
                file.write(sort_file)

                file.close()
                
            with subprocess.Popen([ "docker", "restart", container_name ], stdout=subprocess.PIPE) as proc:
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

                sleep_time = config.prometheus_operator.check_interval or 300
                print(f"Sleeping for {sleep_time}s")
                sleep(sleep_time)

        the_thread = Thread(target=thread_run)

        the_thread.start()

        the_thread.join()

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
        description='Prometheus Operator',
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
