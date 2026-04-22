QoS RBAC Shaping Deployment Guide
Dự án này hướng dẫn triển khai kiểm soát chất lượng dịch vụ (QoS) kết hợp với RBAC Shaping sử dụng Ryu Controller và Mininet.

📋 Yêu cầu hệ thống
Hệ điều hành: Linux (Ưu tiên Ubuntu 20.04+)

Công cụ: Mininet, Open vSwitch (OVS), Ryu SDN Framework, iperf3.

🚀 Các bước triển khai
1. Khởi chạy Ryu Controller
Đầu tiên, bạn cần khởi chạy ứng dụng Ryu để điều khiển các switch trong mạng.

Bash
ryu run ryu_app.py
2. Khởi tạo cấu trúc mạng (Topology)
Sử dụng Mininet để tạo topology tùy chỉnh và kết nối với controller từ xa qua giao thức OpenFlow 1.3.

Bash
sudo mn --custom topo.py --topo qos_topo --controller=remote --switch ovs,protocols=OpenFlow13
3. Cấu hình QoS RBAC Shaping
Sau khi mạng đã sẵn sàng, thực thi script để thiết lập các hàng đợi (queues) và quy tắc giới hạn băng thông trên Open vSwitch.

Bash
chmod +x setup_ovs_qos.sh
./setup_ovs_qos.sh
🧪 Kiểm thử (Testing)
Bạn có thể sử dụng các phương pháp sau để xác minh cấu hình QoS đã hoạt động chính xác hay chưa:

Cách 1: Sử dụng Ping (Kiểm tra độ trễ/Kết nối)
Bash
mininet> h1 ping h2
Cách 2: Sử dụng iperf3 (Kiểm tra băng thông)
Để thấy rõ hiệu quả của việc giới hạn băng thông (Shaping), hãy thực hiện:

Mở terminal của các host bằng xterm:

Bash
mininet> xterm h1 h2
Tại node nhận (h2), chạy server:

Bash
iperf3 -s
Tại node gửi (h1), chạy client để đo tốc độ:

Bash
iperf3 -c [IP_của_h2]
Lưu ý: Việc sử dụng xterm giúp bạn theo dõi trực quan hơn các luồng dữ liệu riêng biệt khi chạy nhiều kịch bản kiểm thử cùng lúc.

🛠 Xử lý sự cố
Nếu gặp lỗi cổng đã bị chiếm dụng, hãy dọn dẹp Mininet trước khi chạy lại:

Bash
sudo mn -c
