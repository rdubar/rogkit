"""
MongoDB logger and utility for rogkit.

Connects to MongoDB using config from TOML, logs generated text with timestamps,
and retrieves records from collections.
"""
import argparse
from dataclasses import dataclass
from datetime import datetime
import os
from pymongo import MongoClient  # type: ignore
from pymongo.errors import ConnectionFailure, PyMongoError  # type: ignore
from typing import List, Optional
from ..bin.tomlr import load_rogkit_toml


@dataclass
class MongoDBConfig:
    """MongoDB connection configuration."""
    uri: str
    db_name: str
    collection_name: str

def load_config() -> MongoDBConfig:
    """Load MongoDB configuration from rogkit TOML or environment variables."""
    TOML = load_rogkit_toml()
    return MongoDBConfig(
        uri=TOML.get('mongodb', {}).get('uri', '') or os.getenv('MONGO_URI', ''),
        db_name=TOML.get('mongodb', {}).get('db', '') or os.getenv('MONGO_DB', ''),
        collection_name=TOML.get('mongodb', {}).get('collection', '') or os.getenv('MONGO_COLLECTION', '')
    )

class MongoDBLogger:
    """MongoDB logger for writing and retrieving timestamped text records."""
    
    def __init__(self, config: MongoDBConfig):
        self.config = config
        self.client = None
        self.db = None
        self.collection = None
        self._connect()

    def _connect(self):
        """Establish connection to MongoDB."""
        try:
            self.client = MongoClient(self.config.uri)
            self.db = self.client[self.config.db_name]
            self.collection = self.db[self.config.collection_name]
            print("Connected to MongoDB.")
        except ConnectionFailure as e:
            print(f"Failed to connect to MongoDB: {e}")
            raise

    def log_text(self, generated_text: str, model: Optional[str] = None):
        """Log generated text with timestamp to MongoDB."""
        if not self.client:
            print("MongoDB connection not established.")
            return
        document = {
            "timestamp": datetime.now(),
            "generated_text": generated_text
        }
        if model:
            document["model"] = model
        try:
            self.collection.insert_one(document)
            print("Log successfully written to MongoDB.")
        except PyMongoError as e:
            print(f"Failed to write log to MongoDB: {e}")

    def get_records(self) -> List[dict]:
        """Retrieve all records from the configured collection."""
        if not self.client:
            print("MongoDB connection not established.")
            return []
        try:
            records = list(self.collection.find({}))
            for record in records:
                record['_id'] = str(record['_id'])
            return records
        except PyMongoError as e:
            print(f"Failed to retrieve records from MongoDB: {e}")
            return []
    
    def get_all_records_from_all_collections(self) -> dict:
        """
        Retrieves all records from all collections in the database.

        Returns:
            A dictionary with collection names as keys and a list of their documents as values.
        """
        if not self.client:
            print("MongoDB connection not established.")
            return {}
        
        all_records = {}
        try:
            for collection_name in self.db.list_collection_names():
                collection = self.db[collection_name]
                records = list(collection.find({}))
                for record in records:
                    record['_id'] = str(record['_id'])
                all_records[collection_name] = records
            return all_records
        except PyMongoError as e:
            print(f"Failed to retrieve records from all collections: {e}")
            return {}

def parse_arguments():
    """Parse command-line arguments for MongoDB operations."""
    parser = argparse.ArgumentParser(description='Log generated text to MongoDB.')
    parser.add_argument('-l', '--log', type=str, help='Log the generated text to MongoDB.')
    parser.add_argument('-r', '--retrieve', action='store_true', help='Retrieve all records from MongoDB.')
    parser.add_argument('-d', '--db', type=str, help='Database name for MongoDB.')  
    parser.add_argument('-c', '--collection', type=str, help='Collection name for MongoDB.')
    parser.add_argument('-a', '--all', action='store_true', help='Retrieve all records from MongoDB.')
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    args = parse_arguments()
    config = load_config()
    
    try:
        logger = MongoDBLogger(config)
    except ConnectionFailure:
        print("Exiting due to MongoDB connection failure.")
        exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        exit(1)

    if args.log:
        logger.log_text(args.log)
    elif args.retrieve:
        records = logger.get_records()
        print(f"Retrieved {len(records)} records from MongoDB.")
        for record in records:
            print(record)
    elif args.all:
        records = logger.get_all_records_from_all_collections()
        print(f"Retrieved {len(records)} records from MongoDB.")
        for record in records:
            print(record)
