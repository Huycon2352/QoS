
from mininet.topo import Topo


class QoSTopo(Topo):

    def build(self):

        s1 = self.addSwitch("s1")

        h1 = self.addHost(
            "h1",
            ip="10.0.0.1/24"
        )

        h2 = self.addHost(
            "h2",
            ip="10.0.0.2/24"
        )

        h3 = self.addHost(
            "h3",
            ip="10.0.0.3/24"
        )

        portal = self.addHost(
            "portal",
            ip="10.0.0.254/24"
        )

        self.addLink(h1, s1)
        self.addLink(h2, s1)
        self.addLink(h3, s1)
        self.addLink(portal, s1)


topos = {
    "qos_topo": QoSTopo
}


