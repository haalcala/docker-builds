#!/bin/bash

python3 -m pip install -r requirements.txt

python3 filebeat_operator.py 2>&1 >> filebeat_operator.log