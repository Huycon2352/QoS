# Dynamic Access Control + QoS (Ryu, OpenFlow 1.3)

## 1) Architecture

This repository implements a modular Ryu-based dynamic access-control and QoS/RBAC pipeline:

- `dynamic_access_controller.py`  
  OpenFlow 1.3 controller app, PacketIn handling, queue-aware flow install (`set_queue` + `output`), and policy re-apply.
- `policy_engine.py`  
  RBAC queue decision engine with dynamic congestion assessment based on aggregate packet load per time window.
- `rbac_qos_config.py` + `rbac_qos_policy.json`  
  Configurable RBAC model, queue mapping, identity mapping (IP/MAC/port), and flow/congestion parameters.
- `setup_qos.sh`  
  OVS-native queue setup with `ovs-vsctl`.
- `setup_qos_rest.sh`  
  Ryu Book `rest_qos` style helper using REST API for OVSDB + queue configuration.

## 2) RBAC model (least/max queue)

Configured in `rbac_qos_policy.json`:

- each role has:
  - `least_queue_id` (degraded queue under congestion)
  - `max_queue_id` (normal-condition queue)

Default role mapping:

- admin: max=0, least=1
- employee: max=1, least=2
- server: max=1, least=2
- guest: max=2, least=3

Queue IDs are configurable (`queue_ids: [0,1,2,3]`).

## 3) Dynamic access control behavior

On every PacketIn:

1. Controller identifies source (`src_ip` / `src_mac` / `in_port`)
2. Resolves role via RBAC identity mapping
3. Selects queue from role policy + network state
4. Installs flow with OpenFlow actions:
   - `set_queue(queue_id)`
   - `output(port)`

Periodic adaptation:

- Policy engine checks aggregate packets every `window_seconds`
- If normal: role uses `max_queue_id`
- If congested (`total_packets >= threshold_packets_per_window`): role downgraded to `least_queue_id`
- Existing host flows are deleted and re-installed automatically on next packets (clean policy switch)

## 4) Run guide (Mininet + Ryu + QoS)

Requirements:

- Python3, Ryu, Mininet, Open vSwitch

Start controller (includes REST QoS modules):

```bash
sudo ./run.sh
```

Or manually:

```bash
ryu-manager ryu.app.rest_qos ryu.app.rest_conf_switch ryu.app.rest_topology dynamic_access_controller.py
```

Start Mininet topology:

```bash
sudo mn --custom topology.py --topo dynamicaccesstopo --controller=remote --switch ovsk,protocols=OpenFlow13 --mac
```

Configure queues on switch egress port (OVS native):

```bash
sudo ./setup_qos.sh s1-eth4
```

Or configure via REST (`rest_qos` style):

```bash
sudo ./setup_qos_rest.sh 0000000000000001 s1-eth4 tcp:127.0.0.1:6640
```

## 5) Quick verification

In Mininet CLI:

```bash
h1 ping h4
xterm h1 h4
```

In xterm:

- `h4`: `iperf3 -s`
- `h1`: `iperf3 -c 10.0.0.4 -u -b 10M`

Controller logs will show role, selected queue, and state transitions (`normal`/`congested`).
