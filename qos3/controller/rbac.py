class RBACManager:
    def __init__(self, policy):
        self.policy = policy

    def get_role(self, src_ip):
        return self.policy.get(src_ip, "least")
