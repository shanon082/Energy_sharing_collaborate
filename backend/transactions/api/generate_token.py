import random

def generate_numeric_token():
    return str(random.randint(1000000000, 9999999999))  # Generates a 10-digit token
