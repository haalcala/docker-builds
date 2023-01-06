#!/bin/bash

pip install -r requirements.txt

python3 envoyproxy_operator.py 2>&1 >> envoyproxy_operator.log