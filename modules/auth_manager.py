import json
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ipv4


class AuthManager:

    def __init__(self, file):

        with open(file) as f:
            data = json.load(f)

        self.roles = data.get("roles", {})
        self.users = data.get("users", {})
        self.system = data.get("system", {})

    ########################################################

    def extract_identity(self, raw):

        pkt = packet.Packet(raw)

        eth = pkt.get_protocol(ethernet.ethernet)
        ip_pkt = pkt.get_protocol(ipv4.ipv4)

        mac = eth.src if eth else None

        if ip_pkt:
            return ip_pkt.src, mac

        return None, mac

    ########################################################

    def get_role(self, ip):

        user = self.users.get(ip)

        if not user:
            return None

        return user.get("role")
