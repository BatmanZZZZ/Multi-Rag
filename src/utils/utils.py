from dotenv import load_dotenv
import os
import time
from psycopg2 import pool


load_dotenv()



def get_rds_connection():
    try:
        # Database connection parameters
        DB_HOST = os.getenv('DB_HOST')
        DB_PORT = os.getenv('DB_PORT')
        DB_NAME = os.getenv('DB_NAME')
        DB_USER = os.getenv('DB_USER')
        DB_PASSWORD = os.getenv('DB_PASSWORD')
        
        connection_pool = pool.SimpleConnectionPool(
            1, 10,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME
        )
        print (f"Connection pool: {connection_pool}")
        print("Add logger here")
        return connection_pool
    except Exception as e:
        # logger.error(f"Error obtaining database connection: {e}")
        raise e