# ==========================
# Secure ATM Configuration
# ==========================
import os
from dotenv import load_dotenv

load_dotenv()

# Flask
SECRET_KEY = os.environ.get("SECRET_KEY", "change_this_to_a_long_random_secret_key")

# MySQL Database
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),   # set in .env, never commit real passwords
    "database": os.environ.get("DB_NAME", "secure_atm"),
}

# Security
MAX_LOGIN_ATTEMPTS = 3
LOCKOUT_MINUTES = 15
OTP_LENGTH = 6
OTP_EXPIRY_MINUTES = 5

# Account
INITIAL_BALANCE = 0.00
ACCOUNT_NUMBER_LENGTH = 10
MAX_WITHDRAWAL_PER_TXN = 50000