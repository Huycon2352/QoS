import eventlet
eventlet.monkey_patch()

import logging
import time

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import (
    MAIN_DISPATCHER,
    CONFIG_DISPATCHER,
    set_ev_cls,
)
from ryu.ofproto import ofproto_v1_3

from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import arp
from ryu.lib.packet import ipv4

from modules.auth_manager import AuthManager
from modules.qos_manager import QoSManager
from modules.congestion_monitor import CongestionMonitor
from modules.redirector import Redirector


class SDNController(app_manager.RyuApp):

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    # ======================================================
    # INIT
    # ======================================================

    def __init__(self, *args, **kwargs):

        super(SDNController, self).__init__(*args, **kwargs)

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(message)s",
        )

        print("\n====================================")
        print("   SDN Controller STARTED")
        print("====================================\n")

        # modules
        self.auth = AuthManager("config/rbac_rules.json")
        self.qos = QoSManager("config/qos_profiles.json")
        self.monitor = CongestionMonitor(self.auth)
        self.redirector = Redirector(self.auth)

        # runtime state
        self.datapath = None
        self.mac_to_port = {}

        # per-user stats
        self.user_stats = {}

        # reset per user (2 minutes)
        self.RESET_INTERVAL = 120

    # ======================================================
    # FLOW ADD
    # ======================================================

    def add_flow(self, datapath, priority, match, actions):

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                actions
            )
        ]

        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=inst,
        )

        datapath.send_msg(mod)

    # ======================================================
    # LOG PER PACKET (YOU WANT THIS FORMAT)
    # ======================================================

    def log_packet(self, ip, mac, role, queue_id):

        now = time.time()

        if ip not in self.user_stats:
            self.user_stats[ip] = {
                "count": 0,
                "last_reset": now
            }

        # reset mỗi 2 phút
        if now - self.user_stats[ip]["last_reset"] >= self.RESET_INTERVAL:
            print(f"[RESET] {ip}")
            self.user_stats[ip]["count"] = 0
            self.user_stats[ip]["last_reset"] = now

        self.user_stats[ip]["count"] += 1

        total = self.user_stats[ip]["count"]

        print(
            f"ip : {ip} | "
            f"mac : {mac} | "
            f"role : {role} | "
            f"totalpacket : {total} | "
            f"q_id : {queue_id}"
        )

    # ======================================================
    # SWITCH CONNECTED
    # ======================================================

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):

        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        self.datapath = datapath

        print("\nSwitch connected")
        print("Datapath ID:", datapath.id)

        match = parser.OFPMatch()

        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER
            )
        ]

        self.add_flow(datapath, 0, match, actions)

    # ======================================================
    # PACKET IN
    # ======================================================

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):

        msg = ev.msg
        datapath = msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)

        eth = pkt.get_protocol(ethernet.ethernet)
        if not eth:
            return

        src_mac = eth.src
        dst_mac = eth.dst

        dpid = datapath.id

        # init mac table
        if dpid not in self.mac_to_port:
            self.mac_to_port[dpid] = {}

        self.mac_to_port[dpid][src_mac] = in_port

        # ==================================================
        # ARP FLOOD
        # ==================================================

        if pkt.get_protocol(arp.arp):

            actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]

            out = parser.OFPPacketOut(
                datapath=datapath,
                buffer_id=msg.buffer_id,
                in_port=in_port,
                actions=actions,
                data=msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None,
            )

            datapath.send_msg(out)
            return

        # ==================================================
        # IPv4 ONLY
        # ==================================================

        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        self.monitor.update_bytes(len(msg.data))
        if not ip_pkt:
            return

        src_ip = ip_pkt.src

        # role
        role = self.auth.get_role(src_ip)

        # unknown user
        if role is None:
            print(f"REDIRECT unknown user ip={src_ip}")
            self.redirector.redirect_to_portal(datapath, in_port)
            return

        # ==================================================
        # CONGESTION (REAL BANDWIDTH)
        # ==================================================

        self.monitor.update_bytes(len(msg.data))
        congested = self.monitor.is_congested()

        # ==================================================
        # QUEUE
        # ==================================================

        queue_id = self.qos.assign_queue(role, congested)

        # ==================================================
        # LOG
        # ==================================================

        self.log_packet(src_ip, src_mac, role, queue_id)

        # ==================================================
        # OUTPUT PORT
        # ==================================================

        if dst_mac in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst_mac]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [
            parser.OFPActionSetQueue(queue_id),
            parser.OFPActionOutput(out_port),
        ]

        # send packet
        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None,
        )

        datapath.send_msg(out)
