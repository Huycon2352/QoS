#!/bin/bash
set -e

PORT=${1:-s1-eth4}

echo "[INFO] Setting up QoS on $PORT"

# Xóa QoS cũ nếu có
ovs-vsctl --if-exists clear Port "$PORT" qos || true

# Tạo QoS + Queue trong 1 transaction
ovs-vsctl \
  -- --id=@q0 create Queue other-config:min-rate=5000000 other-config:max-rate=10000000 \
  -- --id=@q1 create Queue other-config:min-rate=3000000 other-config:max-rate=6000000 \
  -- --id=@q2 create Queue other-config:min-rate=1000000 other-config:max-rate=3000000 \
  -- --id=@q3 create Queue other-config:min-rate=200000 other-config:max-rate=1000000 \
  -- --id=@qos create QoS type=linux-htb other-config:max-rate=10000000 \
     queues:0=@q0 queues:1=@q1 queues:2=@q2 queues:3=@q3 \
  -- set Port "$PORT" qos=@qos

echo "[INFO] QoS configured on $PORT"
ovs-vsctl list Port "$PORT"
