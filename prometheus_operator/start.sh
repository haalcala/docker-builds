#!/bin/bash

python3 -m pip install -r requirements.txt

python3 prometheus_operator.py 2>&1 >> prometheus_operator.log