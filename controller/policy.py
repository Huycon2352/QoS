RBAC_POLICY = {
    "10.0.0.1": "max",
    "10.0.0.2": "normal",
    "10.0.0.3": "least",
}

QOS_PROFILES = {
    "max": {
        "queue_id": 0,
        "min_rate": 20000000,
        "max_rate": 100000000,
    },
    "normal": {
        "queue_id": 1,
        "min_rate": 5000000,
        "max_rate": 20000000,
    },
    "least": {
        "queue_id": 2,
        "min_rate": 1000000,
        "max_rate": 5000000,
    },
}
