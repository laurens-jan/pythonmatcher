# Shared services go here (dependency injection)
import settings
from environment import SimulationEnvironment
import datetime

environment = SimulationEnvironment(stop_time=datetime.datetime.now() + datetime.timedelta(days=2))