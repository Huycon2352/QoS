# policy_engine.py
from dataclasses import dataclass, field
from typing import Dict, Optional
import time
import math

WINDOW_SECONDS = 120          # 2 phút
STABLE_CYCLES_TO_RESTORE = 2  # 2 chu kỳ ổn định mới restore

ROLE_DEFAULT_QUEUE = {
    "admin": 0,
    "employee": 1,
    "guest": 2,
}

QUEUE_NAME = {
    0: "q0-high",
    1: "q1-good",
    2: "q2-stable",
    3: "q3-minimum",
}


@dataclass
class HostTrafficWindow:
    ip: str = ""
    mac: str = ""
    role: str = "unknown"
    current_queue: int = 1
    default_queue: int = 1

    packet_count: int = 0
    last_packet_count: int = 0

    window_start_ts: float = field(default_factory=time.time)
    stable_cycles: int = 0

    variation_score: float = 0.0
    last_window_packets: int = 0
    history: list = field(default_factory=list)

    def reset_window(self):
        self.last_packet_count = self.packet_count
        self.packet_count = 0
        self.window_start_ts = time.time()

    def snapshot(self):
        self.history.append({
            "ts": time.time(),
            "ip": self.ip,
            "mac": self.mac,
            "role": self.role,
            "packets": self.last_packet_count,
            "queue": self.current_queue,
            "variation": self.variation_score,
            "stable_cycles": self.stable_cycles,
        })


class PolicyEngine:
    def __init__(self):
        self.hosts: Dict[str, HostTrafficWindow] = {}

    def register_host(self, ip: str, mac: str, role: str):
        if ip not in self.hosts:
            default_queue = ROLE_DEFAULT_QUEUE.get(role, 1)
            self.hosts[ip] = HostTrafficWindow(
                ip=ip,
                mac=mac,
                role=role,
                current_queue=default_queue,
                default_queue=default_queue,
            )
        else:
            self.hosts[ip].mac = mac
            self.hosts[ip].role = role

    def get_host(self, ip: str) -> Optional[HostTrafficWindow]:
        return self.hosts.get(ip)

    def increment_packet(self, ip: str, count: int = 1):
        host = self.hosts.get(ip)
        if not host:
            return
        host.packet_count += count

    def compute_variation(self, host: HostTrafficWindow) -> float:
        """
        Tính biến thiên packet count giữa các chu kỳ.
        variation = abs(curr - prev) / max(prev, 1)
        """
        prev = max(host.last_packet_count, 1)
        curr = host.packet_count
        return abs(curr - prev) / prev

    def decide_queue(self, host: HostTrafficWindow) -> int:
        """
        Logic queue:
        - admin: ưu tiên q0 khi ổn định
        - employee: mặc định q1
        - guest: mặc định q2
        - nếu traffic biến thiên cao: hạ xuống q3
        - nếu ổn định 2 chu kỳ: restore queue mặc định
        """
        variation = self.compute_variation(host)
        host.variation_score = variation

        # Ngưỡng có thể chỉnh
        HIGH_VARIATION_THRESHOLD = 0.80    # tăng/giảm >80%
        MEDIUM_VARIATION_THRESHOLD = 0.40  # biến thiên vừa

        # Xác định trạng thái ổn định
        stable = variation < MEDIUM_VARIATION_THRESHOLD

        if stable:
            host.stable_cycles += 1
        else:
            host.stable_cycles = 0

        # Nếu traffic bất thường cao => hạ queue
        if variation >= HIGH_VARIATION_THRESHOLD or host.packet_count > 3000:
            host.stable_cycles = 0
            return 3  # minimum

        # Nếu ổn định đủ 2 chu kỳ => restore default
        if host.stable_cycles >= STABLE_CYCLES_TO_RESTORE:
            return host.default_queue

        # Nếu chưa đủ ổn định, giữ theo role
        if host.role == "admin":
            return 0
        elif host.role == "employee":
            return 1
        elif host.role == "guest":
            return 2

        return host.default_queue

    def commit_window(self, ip: str):
        host = self.hosts.get(ip)
        if not host:
            return None

        host.snapshot()
        host.last_window_packets = host.last_packet_count
        host.last_packet_count = host.packet_count
        host.reset_window()

        return host

    def get_queue_name(self, queue_id: int) -> str:
        return QUEUE_NAME.get(queue_id, f"q{queue_id}")

    def summary(self):
        return self.hosts
