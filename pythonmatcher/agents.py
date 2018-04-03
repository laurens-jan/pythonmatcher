from powermatcher import BaseAgent, Bid
from decimal import Decimal
from enum import Enum
from ext import environment
import random
import logging
import math
import influx
import settings

logger = logging.getLogger(settings.app_name + '.' + __name__)

class LoadAgent(BaseAgent):

    def __init__(self, auctioneer, id=None, load=Decimal(1000), noise_factor=Decimal(0.1)):

        self.load = load
        self.noise_factor = noise_factor

        super(LoadAgent, self).__init__(auctioneer, id=id)

    def handle_state_update(self):

        new_power = self.load * (1 + self.noise_factor * Decimal(random.random()))
        bid = Bid(self.auctioneer, new_power)
        self.do_bid_update(bid)

        self.do_runlevel_update()


class ImbalanceAgent(BaseAgent):
    """ Produces and consumes at high/low price points"""

    def __init__(self, auctioneer, id=None,
                 production_price=None, consumption_price=None,
                 production_power=Decimal(5000), consumption_power=Decimal(5000)):

        if not consumption_price:
            # Set at 10% of price range from auctioneer
            consumption_price = auctioneer.min_price + Decimal(0.1) * (auctioneer.max_price - auctioneer.min_price)
        if not production_price:
            # Set at 90% of price range from auctioneer
            production_price = auctioneer.min_price + Decimal(0.9) * (auctioneer.max_price - auctioneer.min_price)

        self.production_price = production_price
        self.consumption_price = consumption_price
        self.production_power = production_power
        self.consumption_power = consumption_power

        # Only needs initial bid, is not going to change
        q = (self.consumption_power, Decimal(0), -self.production_power)
        p = (self.consumption_price, self.production_price)
        bid = Bid(auctioneer, q, p)

        super(ImbalanceAgent, self).__init__(auctioneer, id=id, initial_bid=bid)

    def handle_state_update(self):
        # Technically not necessary to call do_runlevel_update, since state update will not lead to new power
        self.do_runlevel_update()


class PVAgent(BaseAgent):

    def __init__(self, auctioneer, id=None, peak_power = Decimal(3000), noise_factor = Decimal(.1)):
        # self._current_power = Decimal(0)
        self.peak_power = peak_power
        self.noise_factor = noise_factor

        super(PVAgent, self).__init__(auctioneer, id=id)

    def handle_state_update(self):
        # Calculate new bidding ladder
        # Period of day (range 0 - 2*pi)
        day_period = (environment.current_time - environment.current_time.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()\
                     * 2 * math.pi / (3600*24)
        new_power = - self.peak_power * Decimal(max(math.sin(day_period - math.pi/2), 0)) * \
                           (1 + self.noise_factor * Decimal(random.random()))

        bid = Bid(self.auctioneer, new_power)
        self.do_bid_update(bid)

        self.do_runlevel_update()


class ChargeState(Enum):
    IDLE, CHARGING, DISCHARGING = range(3)


class BatteryAgent(BaseAgent):

    def __init__(self, auctioneer, id=None, soc=0.5, capacity=10,
                 max_charge_power = Decimal(4000), max_discharge_power = Decimal(3000),
                 bidding_ladder_steps = 10):

        self._soc = None
        self.capacity = capacity # in kWh
        self.charge_state = ChargeState.IDLE
        self.max_charge_power = max_charge_power
        self.max_discharge_power = max_discharge_power
        self.bidding_ladder_steps = bidding_ladder_steps

        super(BatteryAgent, self).__init__(auctioneer, id=id)

        self.current_power = Decimal(0)
        self.soc = soc

    @property
    def soc(self):
        return self._soc

    @soc.setter
    def soc(self, soc):
        if soc != self._soc:

            if soc < 0:
                soc = 0
            if soc > 1:
                soc = 1

            self._soc = soc

            # Write to influx
            points = [
                {
                    "measurement": "deviceagent_soc",
                    "tags": {
                        "agent_id": self.id,
                        "auctioneer_id": self.auctioneer.id
                    },
                    "fields": {
                        'power': float(soc)
                    },
                    "time": environment.current_time
                }
            ]
            influx.write_points(points, settings.influxdb_database)

    def handle_state_update(self):
        # Update state of charge depending on what happened
        capacity_in_joules = self.capacity * 3600 * 1000
        self.soc += float(self.current_power) * environment.simulation_interval.total_seconds() / capacity_in_joules

        bid = self.calculate_bid()
        self.do_bid_update(bid)
        logger.debug("Updated BatteryAgent with SOC: {}, Bid: {}".format(self.soc, bid))

        self.do_runlevel_update()

    def do_runlevel_update(self):
        """ Called whenever the runlevel might need changing, which is though handle_state_update, or handle_price_update """

        super(BatteryAgent, self).do_runlevel_update()

        if self.current_power > 0:
            self.charge_state = ChargeState.CHARGING
        elif self.current_power < 0:
            self.charge_state = ChargeState.DISCHARGING
        else:
            self.charge_state = ChargeState.IDLE

    def calculate_bid(self):
        # Calculate bid based on current state of charge
        # - for soc=0, bid should be always charge (unless price = max_price)
        # - for soc=1, bid should be always discharge (unless price = min_price)
        # - for soc=0.5, bid should be from min_price until max_price

        if self.soc <= 0:
            # Always charge
            if self.auctioneer.price == self.auctioneer.max_price:
                # Unless price is maximum, then go idle
                return Bid(self.auctioneer, Decimal(0))
            else:
                return Bid(self.auctioneer, self.max_charge_power)
        elif self.soc >= 1:
            # Always discharge
            if self.auctioneer.price == self.auctioneer.min_price:
                # Unless price is minimum, then go idle
                return Bid(self.auctioneer, Decimal(0))
            else:
                return Bid(self.auctioneer, -self.max_discharge_power)
        elif self.soc <= 0.5:
            # Bid leans towards charging
            min_price = self.auctioneer.max_price - (self.auctioneer.max_price - self.auctioneer.min_price) * Decimal(self.soc/.5)
            max_price = self.auctioneer.max_price
        elif self.soc < 1:
            # Bid leans towards discharging
            min_price = self.auctioneer.min_price
            max_price = self.auctioneer.min_price + (self.auctioneer.max_price - self.auctioneer.min_price) * Decimal(2 * (1 - self.soc))

        charge_step = (self.max_charge_power+self.max_discharge_power) / (self.bidding_ladder_steps + 1)
        quantities = tuple(self.max_charge_power - n * charge_step for n in range(self.bidding_ladder_steps+1))

        price_step = (max_price - min_price) / (self.bidding_ladder_steps + 1)
        prices = tuple(min_price + n * price_step for n in range(1, self.bidding_ladder_steps+1))

        return Bid(self.auctioneer, quantities, prices)
