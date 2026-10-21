"""
db.py
Database connection module for Secure ATM System
"""

import mysql.connector
from mysql.connector import Error, pooling
from config import DB_CONFIG

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="secure_atm_pool",
            pool_size=5,
            host=DB_CONFIG["host"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=DB_CONFIG["database"],
        )
    return _pool


def get_db_connection():
    """
    Returns a MySQL database connection from the pool.
    Returns None if the connection fails (caller must check for this).
    """
    try:
        return _get_pool().get_connection()
    except Error as e:
        print(f"Database Error: {e}")
        return None


def close_connection(connection):
    """
    Safely closes (returns to pool) the database connection.
    """
    if connection and connection.is_connected():
        connection.close()