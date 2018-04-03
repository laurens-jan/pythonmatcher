# SimulationEnvironment is put in seperate file to prohibit circular import. See if this needs refactoring

import datetime

class SimulationEnvironment(object):
    """ The environment is responsible for calling handle_state_update of the agents in case of an update in state """
    # Currently it only contains the (simulated) time

    def __init__(self, start_time = datetime.datetime.now(), stop_time = datetime.datetime.now() + datetime.timedelta(days=365), simulation_interval = datetime.timedelta(minutes=1)):
        self.start_time = start_time
        self.stop_time = stop_time
        self.simulation_interval = simulation_interval
        self.running = False
        self.auctioneers = []

        self.current_time = start_time

    def register_auctioneer(self, auctioneer):
        self.auctioneers.append(auctioneer)

    def unregister_auctioneer(self, auctioneer):
        self.auctioneers.remove(auctioneer)

    def start(self):
        self.running = True

        while self.running:
            for auctioneer in self.auctioneers:
                for agent in auctioneer.agents:
                    agent.handle_state_update()

            self.current_time += self.simulation_interval
            if self.current_time > self.stop_time:
                self.running = False

    def stop(self):
        self.running = False
