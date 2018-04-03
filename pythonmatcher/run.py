import ext # import dependencies first
import logging
from powermatcher import Auctioneer
from agents import PVAgent, BatteryAgent, LoadAgent, ImbalanceAgent
import settings

# Initialize logging, see also https://docs.python.org/3/howto/logging-cookbook.html
logger = logging.getLogger(settings.app_name)

# Create console handler
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG) # Log all messages to console
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger.addHandler(ch)


if __name__ == '__main__':
    auctioneer = Auctioneer(id='Sim')
    load_agent = LoadAgent(auctioneer, id='SimLoadAgent')
    pv_agent = PVAgent(auctioneer, id='SimPVAgent')
    imbalance_agent = ImbalanceAgent(auctioneer, id="SimImbalanceAgent")
    battery_agent = BatteryAgent(auctioneer, id='SimBatteryAgent',
                                 capacity=50)

    ext.environment.register_auctioneer(auctioneer)
    ext.environment.start() # Blocks until finished