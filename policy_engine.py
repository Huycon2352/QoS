# policy_engine.py
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import time


@dataclass(frozen=True)
class RolePolicy:
    least_queue_id: int
    max_queue_id: int


@dataclass
class HostState:
    key: str
    role: str
    ip: Optional[str] = None
    mac: Optional[str] = None
    in_port: Optional[int] = None
    packet_count: int = 0
    current_queue: int = 0


@dataclass
class CongestionConfig:
    window_seconds: int
    threshold_packets_per_window: int


class PolicyEngine:
    def __init__(
        self,
        role_policies: Dict[str, RolePolicy],
        congestion: CongestionConfig,
        fallback_role: str = "guest",
    ):
        self.hosts: Dict[str, HostState] = {}
        self.role_policies = role_policies
        self.congestion = congestion
        self.fallback_role = fallback_role
        self.window_start = time.time()
        self.window_total_packets = 0
        self.congested = False
        self.last_window_total_packets = 0

    def _role_policy(self, role: str) -> RolePolicy:
        return self.role_policies.get(role, self.role_policies[self.fallback_role])

    def decide_queue_for_role(self, role: str) -> int:
        policy = self._role_policy(role)
        return policy.least_queue_id if self.congested else policy.max_queue_id

    def register_or_update_host(
        self,
        host_key: str,
        role: str,
        ip: Optional[str] = None,
        mac: Optional[str] = None,
        in_port: Optional[int] = None,
    ) -> HostState:
        if host_key not in self.hosts:
            queue_id = self.decide_queue_for_role(role)
            self.hosts[host_key] = HostState(
                key=host_key,
                role=role,
                ip=ip,
                mac=mac,
                in_port=in_port,
                current_queue=queue_id,
            )
        host = self.hosts[host_key]
        host.role = role
        host.ip = ip or host.ip
        host.mac = mac or host.mac
        host.in_port = in_port if in_port is not None else host.in_port
        return host

    def get_host(self, host_key: str) -> Optional[HostState]:
        return self.hosts.get(host_key)

    def note_packet(self, host_key: str, count: int = 1) -> None:
        host = self.hosts.get(host_key)
        if not host:
            return
        host.packet_count += count
        self.window_total_packets += count

    def window_elapsed(self) -> bool:
        return (time.time() - self.window_start) >= self.congestion.window_seconds

    def evaluate_and_rotate_window(self) -> Dict[str, int]:
        self.last_window_total_packets = self.window_total_packets
        next_congested = (
            self.window_total_packets >= self.congestion.threshold_packets_per_window
        )
        state_changed = next_congested != self.congested
        self.congested = next_congested

        changed_hosts: Dict[str, int] = {}
        for host in self.hosts.values():
            desired = self.decide_queue_for_role(host.role)
            if host.current_queue != desired:
                host.current_queue = desired
                changed_hosts[host.key] = desired
            host.packet_count = 0

        self.window_start = time.time()
        self.window_total_packets = 0
        if not state_changed:
            return changed_hosts
        return changed_hosts

    def all_hosts(self) -> List[HostState]:
        return list(self.hosts.values())
