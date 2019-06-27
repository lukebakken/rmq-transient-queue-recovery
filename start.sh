#!/bin/bash

for i in `seq 3` ; do
    docker-compose up -d "rmq$i"
    sleep 20
done
