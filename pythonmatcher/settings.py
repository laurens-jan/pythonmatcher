from os import environ

# Used for logging name
app_name = "pythonmatcher"

# Default values are defined here
# Overrides may be injected in the environment
influxdb_host = environ.get("INFLUXDB_HOST", "influxdb")
influxdb_database = environ.get("INFLUXDB_DATABASE", "exe-dqn-agent")
influxdb_enabled = environ.get("INFLUXDB_ENABLED", "True").lower() == 'true'
influxdb_empty = environ.get("INFLUXDB_EMPTY", "False").lower() == 'true'
influxdb_write_async = environ.get("INFLUXDB_WRITE_ASYNC", "False").lower() == 'true'

log_level = environ.get("LOG_LEVEL", "INFO")

storage_dir = "temp"