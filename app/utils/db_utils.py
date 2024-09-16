"""
db_utils.py

This module provides utility functions for database operations, including creating SSH tunnels,
connecting to the database, executing queries, and building specific queries for video events and user data.
"""

import os
import re
import subprocess
import time
from urllib.parse import quote_plus

import pandas as pd
import sqlalchemy as s
from dotenv import load_dotenv
from sqlalchemy.exc import OperationalError

# Load environment variables from .env file
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path)

# Environment variables for database connection
DB_NAME = os.getenv("PG_DB")
DB_PASS = os.getenv("PG_PW")
DB_USER = os.getenv("PG_USER")
EC2_ADDRESS = os.getenv("EC2_ADDRESS")
SSH_KEY_LOCATION = os.getenv("SSH_KEY_LOCATION")


def create_ssh_tunnel(ssh_key=SSH_KEY_LOCATION, local_port=1111, remote_port=54321, ec2_address=EC2_ADDRESS):
    """
    Create an SSH tunnel to securely connect to a remote server.

    Parameters:
    ssh_key (str): Path to the SSH key.
    local_port (int): Local port for the SSH tunnel.
    remote_port (int): Remote port for the SSH tunnel.
    ec2_address (str): EC2 instance address.

    Returns:
    subprocess.Popen: A Popen object representing the SSH tunnel process.
    """
    try:
        print("Creating SSH tunnel...")
        cmd = [
            'ssh',
            '-i', ssh_key,
            '-NL', f"{local_port}:localhost:{remote_port}",
            ec2_address
        ]
        print(" ".join(cmd))

        # Launch a new process for SSH tunneling. The SSH tunnel will remain open as long as the Python process is running.
        tunnel_process = subprocess.Popen(cmd)
        time.sleep(2)

        return tunnel_process

    except Exception as e:
        print(f"Error creating SSH tunnel: {e}")
        return None


def connect_to_db(password=DB_PASS, host='localhost', port=1111, user=DB_USER, db_name=DB_NAME, ssh_key=SSH_KEY_LOCATION, ec2_address=EC2_ADDRESS):
    """
    Connect to the PostgreSQL database after establishing an SSH tunnel.

    Parameters:
    password (str): Database password.
    host (str): Host address.
    port (int): Port number.
    user (str): Database user.
    db_name (str): Database name.
    ssh_key (str): Path to the SSH key.
    ec2_address (str): EC2 instance address.

    Returns:
    tuple: SQLAlchemy engine and SSH tunnel process.
    """
    tunnel_process = create_ssh_tunnel(ssh_key, port, 54321, ec2_address)
    if tunnel_process is None:
        return None

    connection_str = f'postgresql://{user}:{quote_plus(password)}@{host}:{port}/{db_name}'
    engine = s.create_engine(connection_str)
    return engine, tunnel_process


def execute_query(query, engine=None):
    """
    Execute a SQL query and return the result as a DataFrame.

    Parameters:
    query (str): SQL query to be executed.
    engine (sqlalchemy.engine.Engine, optional): SQLAlchemy engine for database connection.

    Returns:
    pd.DataFrame: Query result as a DataFrame.
    """
    if engine is None:
        close = True
        engine, tunnel_process = connect_to_db()
    else:
        close = False
    try:
        with engine.connect() as connection:
            df = pd.read_sql(s.text(query), connection)
        result = df
    except OperationalError as e:
        print("Error: Could not execute query.")
        print(e)
        result = None
    if close:
        close_db_connection(engine)
        close_ssh_tunnel(tunnel_process)
    return result


def close_ssh_tunnel(tunnel_process):
    """
    Close the SSH tunnel.

    Parameters:
    tunnel_process (subprocess.Popen): SSH tunnel process to be closed.
    """
    print("Closing SSH tunnel...")
    tunnel_process.kill()


def close_db_connection(engine):
    """
    Close the database connection.

    Parameters:
    engine (sqlalchemy.engine.Engine): SQLAlchemy engine to be disposed.
    """
    print("Closing database connection...")
    engine.dispose()
    
def close(engine, tunnel_process):
    """
    Close the database connection and the SSH tunnel.

    Parameters:
    engine (sqlalchemy.engine.Engine): SQLAlchemy engine to be disposed.
    tunnel_process (subprocess.Popen): SSH tunnel process to be closed.
    """
    close_db_connection(engine)
    time.sleep(1)
    close_ssh_tunnel(tunnel_process)
    time.sleep(1)

if __name__ == "__main__":
    # Example usage
    engine, tunnel_process = connect_to_db()
    # Query to list all the tables in the database
    query = "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';"
    result = execute_query(query, engine)
    print(query)
    print(result)
    close(engine, tunnel_process)
    