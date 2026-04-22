Hướng dẫn Triển khai QoS RBAC Shaping

Dự án này hướng dẫn cách thiết lập kiểm soát chất lượng dịch vụ (QoS) dựa trên vai trò (RBAC) sử dụng bộ điều khiển Ryu và môi trường mô phỏng mạng Mininet.

📋 Các bước triển khai (Deployment)

Để triển khai hệ thống, bạn cần thực hiện theo thứ tự 3 bước sau đây:

Khởi chạy Ryu Controller
Mở terminal và chạy ứng dụng điều khiển:

ryu run ryu_app.py


Khởi chạy Mininet Topology
Mở một terminal khác và thiết lập sơ đồ mạng tùy chỉnh với giao thức OpenFlow 1.3:

sudo mn --custom topo.py --topo qos_topo --controller=remote --switch ovs,protocols=OpenFlow13


Áp dụng cấu hình QoS RBAC Shaping
Thực thi script để cấu hình giới hạn băng thông trên các Switch:

./setup_ovs_qos.sh


🧪 Hướng dẫn Kiểm thử (Testing)

Bạn có thể sử dụng các công cụ sau để kiểm tra hiệu quả của việc giới hạn băng thông:

1. Sử dụng lệnh Ping

Kiểm tra kết nối cơ bản giữa các host:

mininet> h1 ping h2


2. Sử dụng Iperf3 (Khuyên dùng)

Để quan sát rõ nhất sự thay đổi về băng thông, nên sử dụng công cụ iperf3 kết hợp với xterm.

Mở cửa sổ terminal cho các host:

mininet> xterm h1 h2


Tại cửa sổ của Host h2 (Server):

iperf3 -s


Tại cửa sổ của Host h1 (Client):

iperf3 -c <địa_chỉ_IP_h2>
