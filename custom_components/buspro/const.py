DOMAIN = "buspro"
CONF_HOST = "host"
CONF_PORT = "port"
PLATFORMS = ["binary_sensor", "climate", "cover", "light", "sensor", "switch"]
# Dispatcher signal per platform, sent with a list of EntitySpec to create.
SIGNAL_ENTITIES_ADDED = "buspro_entities_added_{}"
