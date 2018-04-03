from agents import Bid
from decimal import Decimal


quantity_1 = [Decimal(10), Decimal(9), Decimal(5), Decimal(-5)]
price_1 = [Decimal(1), Decimal(3), Decimal(5)]
bid_1 = Bid(quantity_1, price_1)
print(bid_1.equilibrium_price())

quantity_2 = [Decimal(15), Decimal(5), Decimal(-10)]
price_2 = [Decimal(1), Decimal(2)]
bid_2 = Bid(quantity_2, price_2)

bid_add = bid_1 + bid_2

print(bid_add)

print(bid_add.quantities)
print(bid_add.prices)

bid_add.find_quantity(1.5)
bid_add.find_quantity(0)
