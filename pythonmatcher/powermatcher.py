from decimal import Decimal
from ext import environment
import uuid
import logging
import influx
import settings

logger = logging.getLogger(settings.app_name + '.' + __name__)

class InvalidBidException(Exception):
    pass

class Bid(object):

    # Positive quantities indicate amount of production
    # quantity[0] is production at min_price

    def __init__(self, auctioneer, quantities=(), prices=()):
        """Creates a bid curve based on supplied quantities and prices"""

        # A bid contains points on a bidding ladder.
        # - The first quantity indicates consumption at min_price
        # - Following price/quantity pairs give new points on the ladder. The quantity extends until the next price
        # - Positive quantities indicate consumption
        # - prices and quantities are a tuple
        #  - if quantity is a Decimal instead of tuple, it is assumed to be the consumption at min_price

        self.auctioneer = auctioneer

        # Construct an empty bid (0 consumption) in case of no parameters
        if not (prices or quantities):
            quantities = (Decimal(0),)

        # Convert quantities to a tuple in case there is one number. e.g. Bid(Decimal(2000)) represents a load of 2kW
        if isinstance(quantities, Decimal):
            quantities = (quantities,)

        # Needs one more quantity than price, to determine the consumption at minimal price
        if len(quantities) == len(prices) + 1:
            self.quantities = tuple(quantities)
            self.prices = tuple(prices)
        else:
            raise InvalidBidException("Invalid number of prices / quantities")

        # Sanity checks
        if any(price <= auctioneer.min_price or price > auctioneer.max_price for price in self.prices):
            raise InvalidBidException("Invalid prices, should be between min_price and max_price")

        for p_i in range(len(prices)-1):
            if self.prices[p_i] > self.prices[p_i+1]:
                raise InvalidBidException("Prices should be increasing")

        if any(self.quantities[q_i] < self.quantities[q_i+1] for q_i in range(len(self.quantities)-1)):
            raise InvalidBidException("Quantities should be strictly decreasing")

        if not all(isinstance(price, Decimal) for price in self.prices):
            raise InvalidBidException("Not all prices are of type Decimal")

        if not all(isinstance(quantity, Decimal) for quantity in self.quantities):
            raise InvalidBidException("Not all quantities are of type Decimal")

    def __str__(self):
        # Prints bidding ladder as total quantity_1@min_price quantity_2@price_1 etc

        s = '{:.2f}@{:.2f}'.format(self.quantities[0], self.auctioneer.min_price)
        s = s + ''.join(' {:.2f}@{:.2f}'.format(q, p) for p, q in zip(self.prices, self.quantities[1:]))
        return s

    def __eq__(self, other):
        # Checks if self and other are equals bidding ladders, which is true when prices and quantities are the same
        return self.prices == other.prices and self.quantities == other.quantities

    def __add__(self, other):

        def price_quantity_gen():
            # Generator function that return next price, quantity point from adding the two bidcurves

            # Start values
            self_i = 0
            other_i = 0
            quantity = self.quantities[0] + other.quantities[0]

            # Aux functions for testing which price point is next. Evaluated as lambda function, since early evaluation leads to 'index out of range' errors
            self_has_ended = lambda: self_i >= len(self.prices)
            other_has_ended = lambda: other_i >= len(other.prices)
            self_price_is_lowest = lambda: (not self_has_ended()) and self.prices[self_i] < other.prices[other_i]
            other_price_is_lowest = lambda: (not other_has_ended()) and self.prices[self_i] > other.prices[other_i]

            # First yield the base quantity, with None price (will be removed later)
            yield None, quantity

            while self_i <= len(self.prices) or other_i <= len(other.prices):

                if self_has_ended() and other_has_ended():
                    # Final two prices were the same, both indices out of range
                    break

                if other_has_ended() or self_price_is_lowest():
                    # Yield from self
                    quantity -= self.quantities[self_i] - self.quantities[self_i + 1]
                    yield self.prices[self_i], quantity
                    self_i += 1

                elif self_has_ended() or other_price_is_lowest():
                    # Yield from other
                    quantity -= other.quantities[other_i] - other.quantities[other_i + 1]
                    yield other.prices[other_i], quantity
                    other_i += 1

                else:
                    # Self price == other price, yield combined quantity
                    quantity -= self.quantities[self_i] - self.quantities[self_i + 1] + other.quantities[other_i] - other.quantities[other_i + 1]
                    yield self.prices[self_i], quantity
                    self_i += 1
                    other_i += 1

        new_prices, new_quantities = zip(*price_quantity_gen())
        new_prices = new_prices[1:] # Remove first None value

        return Bid(self.auctioneer, new_quantities, new_prices)

    def equilibrium_price(self):
        # Return price at which production is equal to consumption

        if len(self.quantities) == 1:
            # Flat bidcurve
            if self.quantities[0] < 0:
                # Production at any price
                return self.auctioneer.min_price
            elif self.quantities[0] > 0:
                # Consumption at any price
                return self.auctioneer.max_price

        if self.quantities[0] < 0:
            # Production at any price
            return self.auctioneer.min_price
        elif self.quantities[-1] > 0:
            # Consumption at any price
            return self.auctioneer.max_price
        else:
            # Return price at which crossing through zero quantity occurred

            q_i = next(q_i for q_i, quantity in enumerate(self.quantities) if quantity <= 0)

            return self.prices[q_i-1]

            # prices_with_boundaries = (self.auctioneer.min_price,) + self.prices + (self.auctioneer.max_price,)
            # for q_i, quantity in enumerate(self.quantities[1:]):
            #     if quantity < 0:
            #         # This is the point where shift from + to - occured, return midpoint
            #         return (prices_with_boundaries[q_i+1] + prices_with_boundaries[q_i])/2


    def find_quantity(self, price):
        # Find which consumption agrees with specified price

        for p_i, p in enumerate(self.prices):
            if price < p:
                # First price which is smaller than p, return previous quantity (equals p_i since q_i is 1 longer)
                return self.quantities[p_i]

        # Didn't find one smaller, so it must be the last quantity
        return self.quantities[-1]

class Auctioneer(object):

    def __init__(self, id=None, min_price=Decimal(0), max_price=Decimal(1000)):
        self.agents = []
        self.bids = {}
        self.price = (max_price + min_price) / 2

        if not id:
            id = uuid.uuid4()
        self.id = id

        self.min_price = min_price
        self.max_price = max_price

    def register_agent(self, agent):
        self.agents.append(agent)
        self.bids[agent] = agent._lastbid

        agent.handle_price_update() # Provide agent with initial price

    def unregister_agent(self, agent):
        self.agents.remove(agent)
        self.bids.pop(agent)

    def handle_bid_update(self, agent, bid):
        logger.debug("Got new bid from {} with bid {}".format(type(agent).__name__, bid))
        self.bids[agent] = bid

        bidding_ladder = self.get_bidding_ladder()
        logger.debug("Total bidding ladder is now {}".format(bidding_ladder))
        new_price = bidding_ladder.equilibrium_price()

        if new_price != self.price:
            self.price = new_price

            logging.debug("New auctioneer price: {}".format(self.price))

            points = [
                {
                    "measurement": "auctioneer_prices",
                    "tags": {
                        "auctioneer_id": self.id
                    },
                    "fields": {
                        'price': float(self.price)
                    },
                    "time": environment.current_time
                }
            ]
            influx.write_points(points, settings.influxdb_database)

            for agent in self.agents:
                agent.handle_price_update() # Trigger an update in state due to new available price

            pass

    def get_bidding_ladder(self):
        bid_sum = Bid(self)
        for b in self.bids.values():
            bid_sum += b
        return bid_sum


class BaseAgent(object):

    def __init__(self, auctioneer, initial_bid = None, id = None, current_power = Decimal(0)):

        self._current_power = current_power
        self.auctioneer = auctioneer

        if not id:
            id = "{}-{}".format(type(self).__name__, uuid.uuid4())
        self.id = id

        if not initial_bid:
            initial_bid = Bid(auctioneer) # Create empty bid if not provided

        self._lastbid = initial_bid
        auctioneer.register_agent(self)

    @property
    def current_power(self):
        return self._current_power

    @current_power.setter
    def current_power(self, current_power):
        if current_power != self._current_power:
            self._current_power = current_power

            points = [
                {
                    "measurement": "deviceagent_power",
                    "tags": {
                        "deviceagent_id": self.id,
                        "auctioneer_id": self.auctioneer.id
                    },
                    "fields": {
                        'power': float(self.current_power)
                    },
                    "time": environment.current_time
                }
            ]
            influx.write_points(points, settings.influxdb_database)

    def do_bid_update(self, bid):
        if bid != self._lastbid:
            self._lastbid = bid
            self.do_runlevel_update()
            self.auctioneer.handle_bid_update(self, bid)

    def do_runlevel_update(self):
        # Trigger to calculate new runlevel. May be due to price update or environment change
        # Default behaviour is that is will adjust current power according to bidcurve

        # Individual agents may deviate from this behavior, if a good reason is present.
        # This would imply that the device might not be operating according to its own bidding ladder

        # Set current_power according to own bid
        self.current_power = self._lastbid.find_quantity(self.auctioneer.price)

    def handle_price_update(self):
        # In Powermatcher handle_price_update is used. Since the effect of a price update is a potential runlevel update, call the do_runlevel_update
        self.do_runlevel_update()

    def handle_state_update(self):
        # Called from the environment, whenever a variable is changed. E.g. updated solar forecast or new timestamp
        # Step it should handle:
        # - Calculate new bidding ladder if necessary
        # - Call self.do_bid_update with new bidding ladder
        # - Call self.do_runlevel_update to adjust runlevel to updated bidcurve
        logger.warning('Agent not overriding handle_state_update function')