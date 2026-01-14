"""Neo4j database connection module.

This module provides a singleton Neo4jDatabase class for managing
database connections to Neo4j using the official Python driver.
"""

import logging
import os
from typing import Optional

from dotenv import load_dotenv
from neo4j import GraphDatabase, Driver

# Load environment variables from .env file
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


class Neo4jDatabase:
    """Singleton class for managing Neo4j database connections.
    
    This class ensures only one driver instance exists across the application,
    providing methods to connect, verify, and close the database connection.
    """
    
    _instance: Optional['Neo4jDatabase'] = None
    _driver: Optional[Driver] = None
    
    def __new__(cls) -> 'Neo4jDatabase':
        """Singleton pattern: ensure only one instance exists.
        
        Returns:
            Neo4jDatabase: The singleton instance of the class.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        """Initialize the Neo4jDatabase instance.
        
        Loads configuration from environment variables but does not
        establish a connection until connect() is called.
        """
        if not hasattr(self, '_initialized'):
            self._uri: str = os.getenv('NEO4J_URI', '')
            self._username: str = os.getenv('NEO4J_USERNAME', '')
            self._password: str = os.getenv('NEO4J_PASSWORD', '')
            self._initialized = True
    
    def connect(self) -> None:
        """Establish connection to the Neo4j database.
        
        Creates a new driver instance if one doesn't exist.
        Logs success or failure of the connection attempt.
        
        Raises:
            ValueError: If required environment variables are missing.
            Exception: If connection to Neo4j fails.
        """
        if self._driver is not None:
            logger.info("Driver already exists. Skipping connection.")
            return
        
        if not self._uri or not self._username or not self._password:
            error_msg = "Missing required environment variables: NEO4J_URI, NEO4J_USERNAME, or NEO4J_PASSWORD"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        try:
            self._driver = GraphDatabase.driver(
                self._uri,
                auth=(self._username, self._password)
            )
            logger.info("Connected to Neo4j successfully.")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {str(e)}")
            raise
    
    def verify_connection(self) -> bool:
        """Verify that the database connection is healthy.
        
        Runs a simple Cypher query (RETURN 1 AS result) to check
        if the connection is working properly.
        
        Returns:
            bool: True if connection is healthy, False otherwise.
            
        Raises:
            RuntimeError: If connect() has not been called first.
        """
        if self._driver is None:
            error_msg = "Driver not initialized. Call connect() first."
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        try:
            records, summary, keys = self._driver.execute_query(
                "RETURN 1 AS result",
                database_="neo4j"
            )
            logger.info("Connection verification successful.")
            return True
        except Exception as e:
            logger.error(f"Connection verification failed: {str(e)}")
            return False
    
    def close(self) -> None:
        """Close the database driver connection.
        
        Properly releases all resources held by the driver.
        Safe to call multiple times.
        """
        if self._driver is not None:
            try:
                self._driver.close()
                self._driver = None
                logger.info("Neo4j driver closed successfully.")
            except Exception as e:
                logger.error(f"Error closing Neo4j driver: {str(e)}")
                raise
    
    @property
    def driver(self) -> Optional[Driver]:
        """Get the Neo4j driver instance.
        
        Returns:
            Optional[Driver]: The driver instance, or None if not connected.
        """
        return self._driver
