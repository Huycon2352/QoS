#!/bin/bash
set -e

# Run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root: sudo ./run.sh"
  exit 1
fi

echo "[INFO] Starting Ryu controller..."
ryu-manager \
  ryu.app.rest_qos \
  ryu.app.rest_conf_switch \
  ryu.app.rest_topology \
  dynamic_access_controller.py &
RYU_PID=$!

sleep 2

echo "[INFO] Starting Mininet..."
sudo mn --custom topology.py --topo dynamicaccesstopo --controller=remote --switch ovsk,protocols=OpenFlow13 --mac

# cleanup
kill $RYU_PID || true
