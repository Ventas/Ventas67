_products = [
    {"name": "Empanada de carne", "price": 3000, "stock": 100},
    {"name": "Gaseosa", "price": 2000, "stock": 50},
    {"name": "Hamburguesa", "price": 10000, "stock": 30},
]

def get_products():
    return _products

def add_new_product(name, price, stock):
    _products.append({"name": name, "price": price, "stock": stock})