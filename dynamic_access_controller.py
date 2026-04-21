# dynamic_access_controller.py
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.lib import hub
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ipv4, arp

import logging
import time

from policy_engine import PolicyEngine, WINDOW_SECONDS


class DynamicAccessController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(DynamicAccessController, self).__init__(*args, **kwargs)

        self.logger.setLevel(logging.INFO)

        self.mac_to_port = {}   # dpid -> {mac: port}
        self.datapaths = {}
        self.policy = PolicyEngine()

        # role mapping theo host bạn yêu cầu
        self.role_by_ip = {
            "10.0.0.1": "guest",     # h1
            "10.0.0.2": "admin",     # h2
            "10.0.0.3": "employee",  # h3
            "10.0.0.4": "server",    # h4
        }

        # theo dõi packet/2 phút
        self.monitor_thread = hub.spawn(self._monitor_loop)

        # lưu queue áp dụng gần nhất
        self.last_queue_by_ip = {}

        self.logger.info("DynamicAccessController initialized")

    def _monitor_loop(self):
        while True:
            try:
                for ip, host in list(self.policy.summary().items()):
                    elapsed = time.time() - host.window_start_ts
                    if elapsed >= WINDOW_SECONDS:
                        new_queue = self.policy.decide_queue(host)
                        old_queue = host.current_queue

                        host.current_queue = new_queue

                        self.logger.info(
                            "[WINDOW] host=%s role=%s ip=%s mac=%s packets/2m=%s variation=%.3f stable_cycles=%s queue=%s -> %s",
                            ip,
                            host.role,
                            host.ip,
                            host.mac,
                            host.last_packet_count,
                            host.variation_score,
                            host.stable_cycles,
                            self.policy.get_queue_name(old_queue),
                            self.policy.get_queue_name(new_queue),
                        )

                        # reset buffer riêng host sau 2 phút
                        self.policy.commit_window(ip)

                        # nếu có datapath thì update flow / queue
                        self._apply_host_queue_policy(ip, host.current_queue)
            except Exception as e:
                self.logger.exception("monitor loop error: %s", e)

            hub.sleep(1)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        self.datapaths[datapath.id] = datapath
        self.mac_to_port.setdefault(datapath.id, {})

        # table-miss -> controller
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

        self.logger.info("Switch connected: dpid=%s", datapath.id)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        dpid = datapath.id
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        eth_type = eth.ethertype

        # bỏ qua LLDP
        if eth_type == 0x88cc:
            return

        src = eth.src
        dst = eth.dst

        ip_src = None
        ip_dst = None

        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        if ip_pkt:
            ip_src = ip_pkt.src
            ip_dst = ip_pkt.dst

        arp_pkt = pkt.get_protocol(arp.arp)
        if arp_pkt:
            ip_src = arp_pkt.src_ip
            ip_dst = arp_pkt.dst_ip

        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port

        # học MAC/IP/role
        if ip_src and ip_src in self.role_by_ip:
            role = self.role_by_ip[ip_src]
            self.policy.register_host(ip_src, src, role)
            self.policy.increment_packet(ip_src, 1)

            host = self.policy.get_host(ip_src)
            self.logger.info(
                "[PKT] ip=%s mac=%s role=%s packets_in_window=%s current_queue=%s",
                ip_src,
                src,
                role,
                host.packet_count if host else 0,
                self.policy.get_queue_name(host.current_queue) if host else "n/a",
            )

            # áp policy queue ngay nếu cần
            if host:
                desired_queue = self.policy.decide_queue(host)
                if desired_queue != host.current_queue:
                    old_q = host.current_queue
                    host.current_queue = desired_queue
                    self.logger.info(
                        "[QUEUE-CHANGE] ip=%s role=%s %s -> %s",
                        ip_src,
                        role,
                        self.policy.get_queue_name(old_q),
                        self.policy.get_queue_name(desired_queue),
                    )
                    self._apply_host_queue_policy(ip_src, desired_queue)

        # learning switch behavior
        out_port = ofproto.OFPP_FLOOD
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]

        actions = []

        # Nếu là host có policy, gán queue egress bằng action set_queue
        if ip_src and ip_src in self.policy.hosts:
            host = self.policy.get_host(ip_src)
            if host:
                actions.append(parser.OFPActionSetQueue(host.current_queue))
                self.logger.debug("SetQueue ip=%s queue=%s", ip_src, host.current_queue)

        actions.append(parser.OFPActionOutput(out_port))

        # cài flow nếu không flood
        if out_port != ofproto.OFPP_FLOOD:
            match_fields = {"in_port": in_port, "eth_src": src, "eth_dst": dst}
            if ip_src:
                match_fields["ipv4_src"] = ip_src
            if ip_dst:
                match_fields["ipv4_dst"] = ip_dst

            match = parser.OFPMatch(**match_fields)
            self.add_flow(datapath, 1, match, actions)

        # gửi packet tiếp
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        datapath.send_msg(out)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        if buffer_id is not None:
            mod = parser.OFPFlowMod(
                datapath=datapath,
                buffer_id=buffer_id,
                priority=priority,
                match=match,
                instructions=inst,
            )
        else:
            mod = parser.OFPFlowMod(
                datapath=datapath,
                priority=priority,
                match=match,
                instructions=inst,
            )
        datapath.send_msg(mod)

    def _apply_host_queue_policy(self, ip, queue_id):
        """
        Hook để sau này bạn có thể gắn:
        - meter
        - queue mapping
        - flow delete / reinstall
        - proactive rules
        """
        host = self.policy.get_host(ip)
        if not host:
            return

        self.last_queue_by_ip[ip] = queue_id
        self.logger.info(
            "[POLICY] apply ip=%s mac=%s role=%s queue=%s",
            host.ip,
            host.mac,
            host.role,
            self.policy.get_queue_name(queue_id),
        )
