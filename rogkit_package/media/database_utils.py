# base.py
import os
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .media_settings import db_url

Base = declarative_base()

def create_database(engine_url):
    """
    Create the database file and initialize tables if it doesn't exist.
    """
    db_file_path = engine_url[len('sqlite:///'):]
    if not os.path.exists(db_file_path):
        os.makedirs(os.path.dirname(db_file_path), exist_ok=True)
    engine = create_engine(engine_url)
    Base.metadata.create_all(engine)

def update_database_schema(engine):
    """
    Update the database schema by dropping all tables and recreating them.
    """
    print("Updating database schema...")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

def initialize_database(engine_url):
    """
    Initialize the database by creating it if it doesn't exist,
    or updating the schema if needed.
    """
    engine = create_engine(engine_url)
    if not os.path.exists(engine_url[len('sqlite:///'):]):
        create_database(engine_url)
    else:
        try:
            Base.metadata.create_all(engine)
        except Exception as e:
            print(f"Error during table creation: {e}")
            update_database_schema(engine)
    return engine

# Initialize the database and create a session factory
engine = initialize_database(db_url)
Session = sessionmaker(bind=engine)