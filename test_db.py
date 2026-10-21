from db import get_db_connection, close_connection

connection = get_db_connection()

if connection:
    print("Database Connected Successfully!")
    close_connection(connection)
else:
    print("Database Connection Failed!")