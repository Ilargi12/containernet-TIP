#!/bin/sh

sudo docker rm -f mn.broker mn.zookeeper mn.generator

sudo python3 demo.py 30 1024 50 10 5
