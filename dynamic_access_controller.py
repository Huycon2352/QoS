# dynamic_access_controller.py
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.lib import hub
from ryu.ofproto import ether
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ipv4, arp

import logging

from policy_engine import PolicyEngine
from rbac_qos_config import RbacQosConfig, default_config_path, normalize_mac


class DynamicAccessController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(DynamicAccessController, self).__init__(*args, **kwargs)

        self.logger.setLevel(logging.INFO)

        self.mac_to_port = {}
        self.datapaths = {}
        self.config = RbacQosConfig.from_file(default_config_path())
        self.policy = PolicyEngine(
            role_policies=self.config.role_policies,
            congestion=self.config.congestion,
            fallback_role=self.config.fallback_role,
        )

        self.monitor_thread = hub.spawn(self._monitor_loop)
        self.classifier_table = 0
        self.forward_table = 1
        self._packet_in_seen_dpids = set()

        self.logger.info(
            "DynamicAccessController initialized, queues=%s, roles=%s",
            self.config.queue_ids,
            list(self.config.role_policies.keys()),
        )

    def _monitor_loop(self):
        while True:
            try:
                if self.policy.window_elapsed():
                    changed = self.policy.evaluate_and_rotate_window()
                    state = "congested" if self.policy.congested else "normal"
                    self.logger.info(
                        "[WINDOW] state=%s total_packets=%s changed_hosts=%s",
                        state,
                        self.policy.last_window_total_packets,
                        len(changed),
                    )
                    for host_key, queue_id in changed.items():
                        self._apply_host_policy(host_key, queue_id)
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

        # Table 0: keep classification/QoS hooks and send packets to forwarding table.
        miss_match = parser.OFPMatch()
        goto_forward = [parser.OFPInstructionGotoTable(self.forward_table)]
        self.add_flow(
            datapath,
            priority=0,
            match=miss_match,
            actions=[],
            instructions=goto_forward,
            table_id=self.classifier_table,
        )

        # Table 1: learning-switch logic receives packet-in on misses.
        controller_actions = [
            parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)
        ]
        self.add_flow(
            datapath,
            priority=0,
            match=miss_match,
            actions=controller_actions,
            table_id=self.forward_table,
        )

        self.logger.info("Switch connected: dpid=%s", datapath.id)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        dpid = datapath.id
        in_port = msg.match["in_port"]
        table_id = getattr(msg, "table_id", None)
        if dpid not in self._packet_in_seen_dpids:
            self._packet_in_seen_dpids.add(dpid)
            self.logger.info("[PACKET_IN] handler active for dpid=%s", dpid)
        self.logger.debug(
            "[PACKET_IN] dpid=%s table=%s in_port=%s buffer_id=%s",
            dpid,
            table_id,
            in_port,
            msg.buffer_id,
        )

        pkt = packet.Packet(msg.data)
        eth_list = pkt.get_protocols(ethernet.ethernet)
        if not eth_list:
            # Learning switch logic only handles Ethernet frames.
            return
        eth = eth_list[0]
        eth_type = eth.ethertype

        if eth_type == 0x88cc:
            return

        src = eth.src
        dst = eth.dst

        ip_src = None
        ip_dst = None

        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        is_ipv4 = ip_pkt is not None
        if ip_pkt:
            ip_src = ip_pkt.src
            ip_dst = ip_pkt.dst

        arp_pkt = pkt.get_protocol(arp.arp)
        if arp_pkt:
            ip_src = arp_pkt.src_ip
            ip_dst = arp_pkt.dst_ip

        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port

        role = self.config.identity.resolve_role(ip_src, src, in_port)
        if role:
            src_host_key = self._host_key(ip_src, src)
            host = self.policy.register_or_update_host(
                src_host_key,
                role,
                ip=ip_src,
                mac=src,
                in_port=in_port,
            )
            self.policy.note_packet(src_host_key, 1)
            self.logger.info(
                "[PKT] key=%s ip=%s mac=%s role=%s packets=%s queue=%s state=%s",
                src_host_key,
                ip_src,
                src,
                role,
                host.packet_count,
                host.current_queue,
                "congested" if self.policy.congested else "normal",
            )

            desired_queue = self.policy.decide_queue_for_role(role)
            if desired_queue != host.current_queue:
                host.current_queue = desired_queue
                self._apply_host_policy(src_host_key, desired_queue)

        out_port = ofproto.OFPP_FLOOD
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]

        actions = []

        if role:
            host = self.policy.get_host(src_host_key)
            if host:
                actions.append(parser.OFPActionSetQueue(host.current_queue))

        actions.append(parser.OFPActionOutput(out_port))

        if out_port != ofproto.OFPP_FLOOD:
            match_fields = {"in_port": in_port, "eth_src": src, "eth_dst": dst}
            if is_ipv4:
                match_fields["eth_type"] = ether.ETH_TYPE_IP
                if ip_src:
                    match_fields["ipv4_src"] = ip_src
                if ip_dst:
                    match_fields["ipv4_dst"] = ip_dst

            match = parser.OFPMatch(**match_fields)
            self.add_flow(
                datapath,
                self.config.flow.priority,
                match,
                actions,
                idle_timeout=self.config.flow.idle_timeout,
                hard_timeout=self.config.flow.hard_timeout,
                table_id=self.forward_table,
            )

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

    def add_flow(
        self,
        datapath,
        priority,
        match,
        actions,
        buffer_id=None,
        idle_timeout=0,
        hard_timeout=0,
        table_id=0,
        instructions=None,
    ):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = list(instructions) if instructions is not None else []
        if actions:
            apply_actions = parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS, actions
            )
            goto_index = next(
                (
                    idx
                    for idx, instruction in enumerate(inst)
                    if getattr(instruction, "type", None) == ofproto.OFPIT_GOTO_TABLE
                ),
                len(inst),
            )
            inst.insert(goto_index, apply_actions)

        if buffer_id is not None:
            mod = parser.OFPFlowMod(
                datapath=datapath,
                buffer_id=buffer_id,
                priority=priority,
                match=match,
                instructions=inst,
                idle_timeout=idle_timeout,
                hard_timeout=hard_timeout,
                table_id=table_id,
            )
        else:
            mod = parser.OFPFlowMod(
                datapath=datapath,
                priority=priority,
                match=match,
                instructions=inst,
                idle_timeout=idle_timeout,
                hard_timeout=hard_timeout,
                table_id=table_id,
            )
        datapath.send_msg(mod)

    def _host_key(self, ip_src, mac_src):
        """Use IP as host key when available, otherwise normalized string MAC."""
        if ip_src:
            return ip_src
        return normalize_mac(mac_src) or "unknown-host"

    def _delete_host_flows(self, datapath, host):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        if host.ip:
            match = parser.OFPMatch(eth_type=ether.ETH_TYPE_IP, ipv4_src=host.ip)
        elif host.mac:
            match = parser.OFPMatch(eth_src=host.mac)
        else:
            return
        mod = parser.OFPFlowMod(
            datapath=datapath,
            command=ofproto.OFPFC_DELETE,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY,
            match=match,
            priority=self.config.flow.priority,
            table_id=self.forward_table,
        )
        datapath.send_msg(mod)

    def _apply_host_policy(self, host_key, queue_id):
        host = self.policy.get_host(host_key)
        if not host:
            return
        self.logger.info(
            "[POLICY] key=%s ip=%s mac=%s role=%s queue=q%s state=%s",
            host.key,
            host.ip or "n/a",
            host.mac,
            host.role,
            queue_id,
            "congested" if self.policy.congested else "normal",
        )
        for datapath in self.datapaths.values():
            self._delete_host_flows(datapath, host)
