# Hướng dẫn Triển khai QoS RBAC Shaping


## Các bước triển khai (Deployment)


### Khởi chạy Ryu Controller
Mở terminal và chạy ứng dụng điều khiển:

  - ryu run ryu_app.py


### Khởi chạy Mininet Topology 

  - sudo mn --custom topo.py --topo qos_topo --controller=remote --switch ovs,protocols=OpenFlow13


### Áp dụng cấu hình QoS RBAC Shaping (Thực thi script để cấu hình giới hạn băng thông trên Switch-OVS ):

  - ./setup_ovs_qos.sh

## (Testing)


### 1. Sử dụng lệnh Ping

Kiểm tra kết nối cơ bản giữa các host:

  - mininet> h1 ping h2


### 2. Sử dụng Iperf3 

Sử dụng xterm để dễ tương tác 
  - mininet> xterm h1 h2


Tại cửa sổ của Host h? (Server):

  - iperf3 -s


Tại cửa sổ của Host h1 (Client):

  - iperf3 -c <địa_chỉ_IP_h2>
