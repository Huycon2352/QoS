class Redirector:

    def __init__(self, auth):
        self.auth = auth

    def redirect_to_portal(self, datapath, in_port):

        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        actions = [
            parser.OFPActionOutput(ofproto.OFPP_CONTROLLER)
        ]

        match = parser.OFPMatch(in_port=in_port)

        inst = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                actions
            )
        ]

        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=20,
            match=match,
            instructions=inst,
        )

        datapath.send_msg(mod)
