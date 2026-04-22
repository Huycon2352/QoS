import time


class CongestionMonitor:

    def __init__(self, auth):

        self.auth = auth

        self.byte_counter = 0
        self.last_check = time.time()

        self.window = 10  # seconds

        self.max_bandwidth_mbps = 100  # giả lập link capacity

    ########################################################

    def update_bytes(self, byte_len):

        self.byte_counter += byte_len

    ########################################################

    def is_congested(self):

        now = time.time()

        if now - self.last_check < self.window:
            return False

        # convert bytes -> Mbps
        mbps = (self.byte_counter * 8) / (self.window * 1_000_000)

        utilization = (mbps / self.max_bandwidth_mbps) * 100

        print(
            f"[MONITOR] throughput={mbps:.2f}Mbps | "
            f"util={utilization:.2f}%"
        )

        self.byte_counter = 0
        self.last_check = now

        return utilization > 80  # threshold

    ########################################################

    def get_window(self):
        return self.byte_counter
