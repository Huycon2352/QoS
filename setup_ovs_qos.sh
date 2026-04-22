#!/bin/bash

for port in s1-eth1 s1-eth2 s1-eth3 s1-eth4
do
  ovs-vsctl set port $port qos=@qos \
  -- --id=@qos create qos type=linux-htb \
  other-config:max-rate=100000000 \
  queues:1=@q1 \
  queues:2=@q2 \
  queues:3=@q3 \
  queues:4=@q4 \
  -- --id=@q1 create queue other-config:max-rate=100000000 \
  -- --id=@q2 create queue other-config:max-rate=60000000 \
  -- --id=@q3 create queue other-config:max-rate=20000000 \
  -- --id=@q4 create queue other-config:max-rate=5000000
done
