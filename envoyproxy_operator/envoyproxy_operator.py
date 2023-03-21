import logging
import traceback
import sys
import argparse
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
        self.cluster_name = ""
        self.hostnames = []
        self.port = ""

    def __str__(self):
        return f"{self.__class__.__name__}[enabled: {self.enabled}, name: {self.name}, hostname: {self.hostname}, cluster_name: {self.cluster_name}, hostnames: {self.hostnames}, port: {self.port}, ]"


class AWSTag:
    def __init__(self, tag) -> None:
        self.key = tag["Key"]
        self.val = tag["Value"]


class OperatedConfig:
    def __init__(self) -> None:
        self.config = None
        self.clusters: List[HostPortConfig] = []

    def LoadFromFile(self, config_file):
        try:
            with open(config_file) as file:
                self.config = GetWrappedJson(yaml.load(file, Loader=yaml.FullLoader))
                self.clusters = self.config["static_resources"]["clusters"]
                # print(self.config)
        except Exception as e:
            print(e)

        return self

    def LoadFromDict(self, dict_config):
        # print("dict_config:", dict_config, "type(dict_config):", type(dict_config))
        # print("dict_config.__dict__[\"_data\"]:", dict_config.__dict__["_data"])
        self.clusters = GetWrappedJson(copy.deepcopy(dict_config.__dict__["_data"])["clusters"])
        return self

    def __str__(self):
        return f"{self.__class__.__name__}[clusters: {self.clusters}]"


class OperatorConfig:
    def __init__(self) -> None:
        self.aws_block = GetWrappedJson({})
        self.credentials = GetWrappedJson({})
        self.region = ""
        self.output_file = ""
        self.container_name = ""
        self.aws_access_key_id = ""
        self.aws_secret_access_key = ""
        self.config = GetWrappedJson({})

    def load(self, dev=False):
        config = GetWrappedJson({})
        with open(("test-" if dev else "") + 'config.yml') as file:
            config = GetWrappedJson(yaml.load(file, Loader=yaml.FullLoader))
            # print("1111 config:", config, "type(config):", type(config))

            # sort_file = yaml.dump(config["envoyproxy"]["base_cluster_config"], sort_keys=True)
            # print("sort_file:", sort_file)
            file.close()

        # print("2222 config:", config, "type(config):", type(config))
        # print("2222 config.aws:", config.aws, "type(config.aws):", type(config.aws))

        self.config = config

        aws_block = config.aws
        self.aws_block = aws_block

        # print("aws_block:", aws_block, "type(aws_block):", type(aws_block), )

        credentials = aws_block.credentials
        self.credentials = credentials

        region = aws_block.region

        if not region:
            region = os.getenv("REGION")

        self.region = region

        output_file = config.envoyproxy.output_file
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
        return OperatedConfig().LoadFromDict(self.config.envoyproxy.base_cluster_config)


def ParseConfigFromAwsTags(desc, tgs_by_arn):
    token = "envoyproxy_operator.cluster."

    clusters: List[HostPortConfig] = []
    ret: List[HostPortConfig] = []

    # find clusters
    for tag in desc["Tags"]:
        tag = AWSTag(tag)
        key, value = tag.key, tag.val

        if key.find(token + "name.") == 0:
            cluster_name = key[len(token + "name."):]
            # print("cluster_name:", cluster_name)

            tmp_config = HostPortConfig()

            tmp_config.cluster_name = tmp_config.name = cluster_name

            if value == "1":
                tmp_config.enabled = True

            clusters.append(tmp_config)

    # find cluster config
    for tmp_config in clusters:
        cluster_token = token + tmp_config.cluster_name + "."
        # print("cluster_token:", cluster_token)

        for tag in desc.Tags:
            tag = AWSTag(tag)
            key, value = tag.key, tag.val

            if key.find(cluster_token) == 0:
                prop = key[len(cluster_token):]
                # print("2222 prop:", prop)

                if prop == "port" and value:
                    tmp_config.port = tgs_by_arn[desc.ResourceArn].Port if value == "auto" else value
                if prop == "hostname" and value:
                    if not tmp_config.hostnames:
                        tmp_config.hostnames = []

                    tmp_config.hostname = value

    for host_port in clusters:
        if host_port.cluster_name and host_port.name and host_port.hostname and host_port.port:
            ret.append(host_port)

    return ret


def compare_prometheus_configs(clusters1, clusters2):
    """
    Returns False if there's difference
    """

    if len(clusters1) != len(clusters2):
        return False

    clusters1_by_cluster_name = {}
    for cluster_config in clusters1:
        clusters1_by_cluster_name[cluster_config.name] = cluster_config

    clusters2_by_cluster_name = {}
    for cluster_config in clusters2:
        clusters2_by_cluster_name[cluster_config.name] = cluster_config

    # print("config1_by_cluster_name:",clusters1_by_cluster_name)
    # print("config2_by_cluster_name:",clusters2_by_cluster_name)

    config1_cluster_names = clusters1_by_cluster_name.keys()
    config2_cluster_names = clusters2_by_cluster_name.keys()

    # print("config1_cluster_names:", config1_cluster_names)
    # print("config2_cluster_names:", config2_cluster_names)

    if len(config1_cluster_names) != len(config2_cluster_names):
        return False

    for cluster_name in config1_cluster_names:
        cluster_config1 = clusters1_by_cluster_name.get(cluster_name)
        cluster_config2 = clusters2_by_cluster_name.get(cluster_name)

        # print("cluster_config1:", cluster_config1)
        # print("cluster_config2:", cluster_config2)

        if cluster_config1 and not cluster_config2:
            return False

        if not cluster_config1 and cluster_config2:
            return False

        if len(cluster_config1.keys()) != len(cluster_config2.keys()):
            return False

        cluster_config_endpoints1 = cluster_config1.load_assignment.endpoints[0].lb_endpoints
        cluster_config_endpoints2 = cluster_config2.load_assignment.endpoints[0].lb_endpoints

        # print("cluster_config_targets1:", cluster_config_endpoints1)
        # print("cluster_config_targets2:", cluster_config_endpoints2)

        if len(cluster_config_endpoints1) != len(cluster_config_endpoints2):
            return False

        _cluster_config_endpoints2 = []
        for endpoint2 in cluster_config_endpoints2:
            hostname = endpoint2.endpoint.address.socket_address.address
            port = endpoint2.endpoint.address.socket_address.port_value

            _cluster_config_endpoints2.append(f"{hostname}:{port}")

        # print("_cluster_config_endpoints2:", _cluster_config_endpoints2)

        for target in cluster_config_endpoints1:
            # print("target:", target)

            hostname = target.endpoint.address.socket_address.address
            port = target.endpoint.address.socket_address.port_value

            _target = f"{hostname}:{port}"
            # print("_target:", _target)

            if _target not in _cluster_config_endpoints2:
                return False

    return True


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
    config = OperatorConfig().load(args.dev)

    aws_block = config.aws_block

    output_file = config.output_file
    container_name = config.container_name

    region = config.region or os.getenv("Region") or os.getenv("REGION")
    aws_access_key_id = config.aws_access_key_id
    aws_secret_access_key = config.aws_secret_access_key

    # print(f"aws_access_key_id: {aws_access_key_id} aws_secret_access_key: {aws_secret_access_key}")

    session = boto3.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        # aws_session_token=SESSION_TOKEN,
        profile_name="vcube-sg"
    )

    def do_check():
        # print("==============================================================================")
        existing_config = config.GetCurrentOperatedConfig()

        tmp_cluster_config = config.GetOperatedConfigTemplate()

        # print("existing_config.clusters:", existing_config.clusters)
        # print("tmp_cluster_config.clusters:", tmp_cluster_config.clusters)

        elb = session.client('elbv2', region)
        ec2 = session.client('ec2', region)

        tgs = GetWrappedJson(elb.describe_target_groups())
        tgs = filter_targetgroups(tgs.TargetGroups, config.config.aws.target.resources[0].conditions[0])
        # print("type(tgs.TargetGroups):", type(tgs.TargetGroups))

        TargetGroupArns = []
        tgs_by_arn = {}

        for tg in tgs:
            arn = tg.TargetGroupArn
            TargetGroupArns.append(arn)
            tgs_by_arn[arn] = tg

        print("tgs_by_arn:", tgs_by_arn)
        print("len(tgs_by_arn):", len(tgs_by_arn))

        if not TargetGroupArns:
            return

        new_config = {}

        describe_tags_ret = GetWrappedJson(
            elb.describe_tags(ResourceArns=TargetGroupArns))

        # print("describe_tags_ret:", describe_tags_ret)
        # print("describe_tags_ret.TagDescriptions:", describe_tags_ret.TagDescriptions)
        # print("type(describe_tags_ret.TagDescriptions):", type(describe_tags_ret.TagDescriptions))

        for desc in describe_tags_ret.TagDescriptions:
            # print("\n\n-----------------------------")
            # print("desc:", desc)

            clusters = ParseConfigFromAwsTags(desc, tgs_by_arn)

            # print("Found clusters:", clusters)

            for tag_config in clusters:
                # print(f"1111 tag_config: {tag_config}")

                # Don't process if not enabled
                if not tag_config.enabled:
                    continue

                health = GetWrappedJson(elb.describe_target_health(
                    TargetGroupArn=desc.ResourceArn))

                # print("health:", health)

                for target in health.TargetHealthDescriptions:
                    instances = GetWrappedJson(ec2.describe_instances(
                        InstanceIds=[target.Target.Id]))

                    for instance in instances.Reservations[0].Instances:

                        # print("instance:", instance)

                        hostname = instance.PrivateIpAddress if tag_config.hostname == "auto" else tag_config.hostname
                        port = target.Target.Port if tag_config.port == "auto" else tag_config.port

                        tag_config.hostnames.append(f"{hostname}:{port}")

                print("2222 tag_config:", tag_config)

                if len(tag_config.hostnames) > 0:
                    cluster_config_job = None

                    for cluster_config in tmp_cluster_config.clusters:
                        if cluster_config.name == tag_config.cluster_name:
                            cluster_config_job = cluster_config
                            break

                    print("cluster_config_job:", cluster_config_job)

                    if not cluster_config_job:
                        cluster_config_job = {
                            "name": tag_config.name,
                            "connect_timeout": "0.25s",
                            "type": "strict_dns",
                            "lb_policy": "round_robin",
                            "load_assignment": {
                                "cluster_name": tag_config.cluster_name,
                                "endpoints": [{"lb_endpoints": []}]
                            }
                        }

                        tmp_cluster_config.clusters.append(cluster_config_job)

                    # print("cluster_config_job:",cluster_config_job)
                    # print("tmp_cluster_config:",tmp_cluster_config)
                    # print("1111 tag_config.hostnames:", tag_config.hostnames)

                    for new_hostname in tag_config.hostnames:
                        # print("new_hostname:", new_hostname)
                        current_cluster_hostnames = ["{}:{}".format(x.endpoint.address.socket_address.address, x.endpoint.address
                                                                    .socket_address.port_value) for x in cluster_config_job.load_assignment.endpoints[0].lb_endpoints]
                        # print("current_cluster_hostnames:",  current_cluster_hostnames)
                        if not new_hostname in current_cluster_hostnames:
                            cluster_config_job.load_assignment.endpoints[0].lb_endpoints.append({
                                "endpoint": {
                                    "address": {
                                        "socket_address": {
                                            "address": new_hostname.split(":")[0],
                                            "port_value": int(new_hostname.split(":")[1])
                                        }
                                    }
                                }
                            })

                # print("cluster_config_job:",cluster_config_job)

        has_changes = not compare_prometheus_configs(
            tmp_cluster_config.clusters, existing_config.clusters)
        print(f"has_changes: {has_changes}")

        print("tmp_cluster_config.clusters:", tmp_cluster_config.clusters)

        if has_changes:
            existing_config.config.static_resources.clusters = tmp_cluster_config.clusters
            sort_file = yaml.dump(existing_config.config.__dict__["_data"], sort_keys=True)
            # print(sort_file)

            with open(output_file, "w") as file:
                file.write(sort_file)

            with subprocess.Popen(["docker", "restart", container_name], stdout=subprocess.PIPE) as proc:
                print(proc.stdout.read())

    # print("Mode: {}".format("DEV" if args.dev else "PRD"))

    if args.dev:
        do_check()
    else:
        def thread_run():
            while True:
                try:
                    do_check()
                except Exception:
                    traceback.print_exc(file=sys.stdout)

                sleep_time = config.config.envoyproxy_operator.check_interval or 300
                print(f"Sleeping for {sleep_time}s")
                sleep(sleep_time)

        the_thread = Thread(target=thread_run)

        the_thread.start()

        the_thread.join()

class GetWrappedJson:
    def __init__(self, data):
        self._data = data
    
    def __getattr__(self, name):
        # print(f"Getting attribute {name}")

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
        # print(f"Getting item {name}")
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

def test_get_wrapped_json():
    data = {
        "a": 1,
        "b": 2,
        "c": {
            "d": 3,
            "e": 4,
        },
        "f": [5, 6, 7],
    }
    wrapped = GetWrappedJson(data)

    # Test attribute access
    assert wrapped.a == 1
    assert wrapped.b == 2
    assert wrapped.c.d == 3
    assert wrapped.c.e == 4
    assert wrapped.f[0] == 5
    assert wrapped.f[1] == 6
    assert wrapped.f[2] == 7
    assert wrapped.f[3] == None
    assert wrapped.g == None
    assert wrapped.c.f == None

    # Test item access
    assert wrapped["a"] == 1
    assert wrapped["b"] == 2
    assert wrapped["c"]["d"] == 3
    assert wrapped["c"]["e"] == 4
    assert wrapped["f"][0] == 5
    assert wrapped["f"][1] == 6
    assert wrapped["f"][2] == 7
    assert wrapped["g"] == None
    assert wrapped["c"]["f"] == None

    # Test set attribute
    wrapped.a = 10
    assert wrapped.a == 10
    wrapped.g = 20
    assert wrapped.g == 20

    # Test set item
    wrapped["b"] = 20
    assert wrapped["b"] == 20
    wrapped["h"] = 30
    assert wrapped["h"] == 30

    # Test str and repr
    assert str(wrapped) == str(data)
    assert repr(wrapped) == repr(data)

    # Test len
    print("wrapped:", wrapped)
    assert len(wrapped) == 6
    assert len(wrapped.c) == 2
    assert len(wrapped.f) == 3

    # Test bool
    assert bool(wrapped) == True
    assert bool(wrapped.g) == True
    assert bool(wrapped.c) == True
    assert bool(wrapped.f)

    data = {
        "name": "John",
        "age": 30,
        "cars": [
            {"model": "Ford", "year": 2020},
            {"model": "BMW", "year": 2019}
        ]
    }

    wrapped_data = GetWrappedJson(data)

    # Accessing values using dot notation
    print(wrapped_data.name)  # Output: "John"
    print(wrapped_data.age)  # Output: 30
    print(wrapped_data.cars)  # Output: [{"model": "Ford", "year": 2020}, {"model": "BMW", "year": 2019}]

    # Accessing values using square brackets notation
    print(wrapped_data['name'])  # Output: "John"
    print(wrapped_data['age'])  # Output: 30
    print(wrapped_data['cars'])  # Output: [{"model": "Ford", "year": 2020}, {"model": "BMW", "year": 2019}]

    # Accessing values that are not present in the data
    print(wrapped_data.address)  # Output: None
    print(wrapped_data['address'])  # Output: None

    # Accessing elements of the list using index notation
    print(wrapped_data.cars[0])  # Output: {"model": "Ford", "year": 2020}
    print(wrapped_data['cars'][0])  # Output: {"model": "Ford", "year": 2020}

    # Accessing elements of the list using index notation
    print(wrapped_data.cars[0].model)  # Output: "Ford"
    print(wrapped_data['cars'][0]['model'])  # Output: "Ford"

    # Accessing elements of the list using index notation
    print(wrapped_data.cars[2])  # Output: None
    print(wrapped_data['cars'][2])  # Output: None

    # Accessing elements of the list using index notation
    print(wrapped_data.cars[0].color)  # Output: None
    print(wrapped_data['cars'][0]['color'])  # Output: None


# config = GetWrappedJson({"name": "John", "age": 30, "aws": {"region": "us-east-1", "access_key": "abcdef"}})
# print(config.aws)  # Output: {'region': 'us-east-1', 'access_key': 'abcdef'}
# print(config["aws"])  # Output: {'region': 'us-east-1', 'access_key': 'abcdef'}

# def GetWrappedJson(_json):
#     _json = {} if _json is None else _json

#     class CC:
#         def __init__(self, data):
#             self.data = data  # an iterable

#         def __iter__(self):
#             self.current_index = 0
#             if type(self.data) == dict:
#                 self.keys = list(self.data.keys())
#             return self

#         def __next__(self):
#             #  print("self.current_index:", self.current_index, "self.data:", self.data, "self.keys:", self.keys, "type(self.data):", type(self.data))
#             # print("self.current_index:", self.current_index, "self.keys:", self.keys, "type(self.data):", type(self.data))

#             if type(self.data) == dict:
#                 current_index = self.current_index

#                 if current_index < len(self.keys):
#                     self.current_index += 1
#                     x = self.data[self.keys[current_index]]
#                     return GetWrappedJson(x) if type(x) == dict else x
#                 else:
#                     raise StopIteration
#             elif self.current_index < len(self.data):
#                 x = self.data[self.current_index] if len(
#                     self.data) > self.current_index else None
#                 self.current_index += 1
#                 return GetWrappedJson(x) if type(x) == dict else x
#             raise StopIteration

#     class WrappedJson:
#         def __getitem__(self, __name):
#             # print("__getitem__:", __name, type(_json))
#             try:
#                 if type(__name) == str and __name[-(len("__json")):] == "__json":
#                     return _json

#                 if type(__name) == str and __name == "keys" and type(_json) == dict:
#                     return _json.keys

#                 if type(__name) == str and __name == "append" and type(_json) == list:
#                     return _json.append

#                 ret = None

#                 if type(_json) == list:
#                     ret = _json[__name] if type(__name) == int and len(
#                         _json) > __name else None
#                 else:
#                     ret = _json.get(__name)

#                 return GetWrappedJson(ret) if type(ret) == dict or type(ret) == list else ret
#             except Exception as e:
#                 print("ERROR: e:", e, "__name", __name, "_json", _json)
#                 logging.exception(e)
#                 raise e

#         def __getattribute__(self, __name: str):
#             # print("__getattribute__:", __name, type(_json))
#             try:
#                 if type(__name) == str and __name[-(len("__json")):] == "__json":
#                     return _json

#                 if type(__name) == str and __name == "keys" and type(_json) == dict:
#                     return _json.keys

#                 if type(__name) == str and __name == "append" and type(_json) == list:
#                     return _json.append

#                 ret = None

#                 if type(_json) == list:
#                     ret = _json[__name] if type(__name) == int and len(
#                         _json) > __name else None
#                 else:
#                     ret = _json.get(__name)

#                 return GetWrappedJson(ret) if type(ret) == dict or type(ret) == list else ret
#             except Exception as e:
#                 print("ERROR: e:", e, "__name", __name, "_json", _json)
#                 logging.exception(e)
#                 raise e

#         def __repr__(self) -> str:
#             return str(_json)

#         def __setitem__(self, __name: str, __value) -> None:
#             _json[__name] = __value

#         def __setattr__(self, __name: str, __value) -> None:
#             _json[__name] = __value

#         def __bool__(self):
#             return not not _json

#         def __delattr__(self, __name):
#             if _json.get(__name):
#                 del _json[__name]

#         def __delitem__(self, __name):
#             if _json.get(__name):
#                 del _json[__name]

#         def __iter__(self):
#             return iter(CC(_json))

#         def __len__(self):
#             return len(_json)

#     return WrappedJson()


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

    test_get_wrapped_json()

    print("args:", args)

    main(args)
