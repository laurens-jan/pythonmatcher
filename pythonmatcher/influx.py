import logging
from concurrent.futures import ThreadPoolExecutor

import settings
import traceback
from influxdb import InfluxDBClient

logger = logging.getLogger(settings.app_name + '.' + __name__)
# logger.setLevel(logging.DEBUG)

# Create variable that holds all the connections to influxdb
influxClients = {}

# Threadpool for async writing to database
executor = ThreadPoolExecutor(max_workers=2)

def write_points(points, database):
    # Write the points to the InfluxDB

    if settings.influxdb_enabled:
        logger.debug('Writing to db: {}'.format(points))
        try:
            # Create connection to influxdb for specified database if it doesn't exist yet
            if not database in influxClients:
                influxClients[database] = InfluxDBClient(host=settings.influxdb_host, database=database)

                # Empty database in case it isn't empty (setting)
                if settings.influxdb_empty:
                    influxClients[database].drop_database(database)

                influxClients[database].create_database(database)

            if settings.influxdb_write_async:
                executor.submit(influxClients[database].write_points, points)
            else:
                influxClients[database].write_points(points)
        except Exception as e:
            logger.error("Error while writing points to database: {}".format(points))
            traceback.print_exc() # Print stacktrace, since we are using threading this error will not be caught by the main tread
            raise e