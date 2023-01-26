import json
import pathlib

import requests
from requests.auth import HTTPBasicAuth

import argparse

from dotenv import dotenv_values

GRAFANA_URL = None
GRAFANA_USER = None
GRAFANA_PASS = None
GRAFANA_APIKEY = None


class BearerAuth(requests.auth.AuthBase):
    def __init__(self, token):
        self.token = token

    def __call__(self, r):
        r.headers["authorization"] = "Bearer " + self.token
        return r


def SendRequest(method, uri, data=None, auth_mode=None):
    request_method = None

    request_method_params = {}

    if method == 'GET':
        request_method = requests.get
    if method == 'POST':
        request_method = requests.post
    if method == 'PUT':
        request_method = requests.put
    if method == 'DELETE':
        request_method = requests.delete

    if not request_method:
        raise ValueError('Invalid request method: %s' % method)

    if data:
        request_method_params['json'] = data

    if auth_mode == "basic":
        request_method_params["auth"] = HTTPBasicAuth(
            GRAFANA_USER, GRAFANA_PASS)

    if auth_mode == "token":
        request_method_params["auth"] = BearerAuth(GRAFANA_APIKEY)

    res = request_method(GRAFANA_URL+uri, **request_method_params)

    print(res.json())

    return res.json()


def GetDashboards():
    dashboards = SendRequest("GET", "/api/dashboards", auth_mode="basic",)

    return dashboards


def GetDatasources():
    datasources = SendRequest("GET", "/api/datasources", auth_mode="basic",)

    return datasources


def GetApiKey():
    apiKey = SendRequest(
        "GET", "/api/auth/keys", auth_mode="basic",)

    return apiKey


def DeleteApiKey(apiKey):
    apiKey = SendRequest(
        "DELETE", f"/api/auth/keys/{apiKey}", auth_mode="basic",)

    return apiKey


def CreateApiKey():
    apiKey = SendRequest(
        "POST", "/api/auth/keys", {"name": "apikeycurl", "role": "Admin"}, auth_mode="basic",)

    return apiKey


def CreateDatasources():
    files = pathlib.Path("datasources").glob("*")

    for file in files:
        print("file:", file)

        data = json.load(open(file))

        print("data:", data)

        resp = SendRequest("POST", "/api/datasources", data, "token")

        print("resp:", resp)


def CreateDashboards():
    files = pathlib.Path("dashboards").glob("*")

    for file in files:
        print("file:", file)

        data = json.load(open(file))

        data = {"dashboard": data}

        print("data:", data)

        resp = SendRequest("POST", "/api/dashboards/db", data, "token")

        print("resp:", resp)


def main(args):
    global GRAFANA_URL, GRAFANA_USER, GRAFANA_PASS, GRAFANA_APIKEY
    print(args.filename)

    env = dotenv_values(args.filename)

    # GRAFANA_URL = env.get("GRAFANA_URL") or "http://grafana:8000"
    GRAFANA_URL = env.get(
        "GRAFANA_URL") or "http://grafana:3000"
    GRAFANA_USER = env.get("GRAFANA_USER") or "admin"
    GRAFANA_PASS = env.get("GRAFANA_PASS") or "admin"
    GRAFANA_APIKEY = env.get(
        "GRAFANA_APIKEY") or ""

    if not GRAFANA_APIKEY:
        apiKey = GetApiKey()

        existing_id = 0

        for key in apiKey:
            if key["name"] == "apikeycurl":
                existing_id = key["id"]
                break

        if existing_id:
            DeleteApiKey(existing_id)

        apiKey = CreateApiKey()

        print("apiKey: ", apiKey)
        GRAFANA_APIKEY = apiKey["key"]

    CreateDatasources()

    CreateDashboards()

    # datasources = GetDatasources()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        prog='ProgramName',
        description='What the program does',
        epilog='Text at the bottom of help')

    parser.add_argument('filename')           # positional argument
    parser.add_argument('-c', '--count')      # option that takes a value
    parser.add_argument('-v', '--verbose',
                        action='store_true')  # on/off flag

    args = parser.parse_args()

    print(args)

    main(args)
