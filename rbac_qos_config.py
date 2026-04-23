import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from policy_engine import CongestionConfig, RolePolicy


@dataclass
class FlowConfig:
    priority: int = 10
    idle_timeout: int = 20
    hard_timeout: int = 0


@dataclass
class IdentityConfig:
    by_ip: Dict[str, str]
    by_mac: Dict[str, str]
    by_port: Dict[str, str]

    def resolve_role(
        self,
        ip_src: Optional[str],
        mac_src: Optional[str],
        in_port: Optional[int],
    ) -> Optional[str]:
        if ip_src and ip_src in self.by_ip:
            return self.by_ip[ip_src]
        if mac_src and mac_src in self.by_mac:
            return self.by_mac[mac_src.lower()]
        if in_port is not None and str(in_port) in self.by_port:
            return self.by_port[str(in_port)]
        return None


@dataclass
class RbacQosConfig:
    queue_ids: list
    role_policies: Dict[str, RolePolicy]
    identity: IdentityConfig
    congestion: CongestionConfig
    flow: FlowConfig
    fallback_role: str = "guest"

    @classmethod
    def from_file(cls, file_path: str) -> "RbacQosConfig":
        with open(file_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        role_policies = {
            role: RolePolicy(
                least_queue_id=int(item["least_queue_id"]),
                max_queue_id=int(item["max_queue_id"]),
            )
            for role, item in raw["roles"].items()
        }
        if "guest" not in role_policies:
            raise ValueError("roles must define a 'guest' fallback role")

        identity = raw.get("identity", {})
        by_mac = {
            mac.lower(): role for mac, role in identity.get("by_mac", {}).items()
        }
        return cls(
            queue_ids=[int(q) for q in raw.get("queue_ids", [0, 1, 2, 3])],
            role_policies=role_policies,
            identity=IdentityConfig(
                by_ip=identity.get("by_ip", {}),
                by_mac=by_mac,
                by_port={str(k): v for k, v in identity.get("by_port", {}).items()},
            ),
            congestion=CongestionConfig(
                window_seconds=int(
                    raw.get("congestion", {}).get("window_seconds", 10)
                ),
                threshold_packets_per_window=int(
                    raw.get("congestion", {}).get("threshold_packets_per_window", 200)
                ),
            ),
            flow=FlowConfig(
                priority=int(raw.get("flow", {}).get("priority", 10)),
                idle_timeout=int(raw.get("flow", {}).get("idle_timeout", 20)),
                hard_timeout=int(raw.get("flow", {}).get("hard_timeout", 0)),
            ),
            fallback_role="guest",
        )


def default_config_path() -> str:
    return str(Path(__file__).resolve().parent / "rbac_qos_policy.json")
