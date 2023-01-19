#!/bin/bash



kill -9 $(lsof -t -i$1) ; go run ./src -b $1 -s $2