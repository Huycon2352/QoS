class QoSManager:
    def __init__(self, qos_profiles):
        self.qos_profiles = qos_profiles

    def get_queue_id(self, role):
        profile = self.qos_profiles.get(role)
        if profile is None:
            return 2
        return profile["queue_id"]
