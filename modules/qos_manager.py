import json


class QoSManager:

    def __init__(self, config_file):

        with open(config_file) as f:
            self.config = json.load(f)

        self.profiles = self.config["profiles"]

    ########################################################

    def normalize_role(self, role):

        if isinstance(role, dict):
            return role.get("role", "guest")

        return role

    ########################################################

    def assign_queue(self, role, congested):

        role = self.normalize_role(role)

        with open("config/rbac_rules.json") as f:
            rbac = json.load(f)

        role_cfg = rbac["roles"].get(role)

        if not role_cfg:
            return 4

        q_min, q_max = role_cfg["queue_range"]

        # 🔥 logic QoS

        if congested:
            # downgrade priority (chọn queue cao hơn = thấp QoS)
            return q_max
        else:
            # normal → best queue
            return q_min
