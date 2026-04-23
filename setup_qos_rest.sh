#!/bin/bash
set -euo pipefail

RYU_API=${RYU_API:-http://127.0.0.1:8080}
DPID=${1:-0000000000000001}
PORT_NAME=${2:-s1-eth4}
OVSDB_ADDR=${3:-tcp:127.0.0.1:6640}

echo "[INFO] Configure OVSDB for switch $DPID via $RYU_API"
curl -sS -X POST "${RYU_API}/v1.0/conf/switches/${DPID}/ovsdb_addr" \
  -d "\"${OVSDB_ADDR}\"" \
  -H "Content-Type: application/json" > /dev/null

echo "[INFO] Create QoS queues on ${PORT_NAME}"
curl -sS -X POST "${RYU_API}/qos/queue/${DPID}" \
  -H "Content-Type: application/json" \
  -d "{
    \"port_name\": \"${PORT_NAME}\",
    \"type\": \"linux-htb\",
    \"max_rate\": \"10000000\",
    \"queues\": [
      {\"min_rate\": \"5000000\", \"max_rate\": \"10000000\"},
      {\"min_rate\": \"3000000\", \"max_rate\": \"6000000\"},
      {\"min_rate\": \"1000000\", \"max_rate\": \"3000000\"},
      {\"min_rate\": \"200000\", \"max_rate\": \"1000000\"}
    ]
  }" | cat

echo
echo "[INFO] Queue setup completed for ${DPID}:${PORT_NAME}"
