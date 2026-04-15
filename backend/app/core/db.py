"""Neo4j database connection module.

This module provides a singleton Neo4jDatabase class for managing
database connections to Neo4j using the official Python driver.
"""

import logging
import os
import random
import time
from typing import Optional

from dotenv import load_dotenv
from neo4j import GraphDatabase, Driver
from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError

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
            self._max_connection_pool_size: int = int(os.getenv("NEO4J_MAX_CONNECTION_POOL_SIZE", "50"))
            self._connection_acquisition_timeout: float = float(
                os.getenv("NEO4J_CONNECTION_ACQUISITION_TIMEOUT", "30")
            )
            self._max_connection_lifetime: int = int(os.getenv("NEO4J_MAX_CONNECTION_LIFETIME", "3600"))
            self._max_retry_time: float = float(os.getenv("NEO4J_MAX_TRANSACTION_RETRY_TIME", "30"))
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
                auth=(self._username, self._password),
                max_connection_pool_size=self._max_connection_pool_size,
                connection_acquisition_timeout=self._connection_acquisition_timeout,
                max_connection_lifetime=self._max_connection_lifetime,
                max_transaction_retry_time=self._max_retry_time,
            )
            self._driver.verify_connectivity()
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

    def execute_query_with_retry(
        self,
        query: str,
        parameters: dict | None = None,
        *,
        retries: int = 3,
        base_delay_s: float = 0.5,
        database_: str | None = None,
    ):
        """Execute query with retry for transient Neo4j failures."""
        if self._driver is None:
            self.connect()
        last_exc: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                return self._driver.execute_query(  # type: ignore[union-attr]
                    query,
                    parameters or {},
                    database_=database_,
                )
            except (TransientError, ServiceUnavailable, SessionExpired) as exc:
                last_exc = exc
                if attempt == retries:
                    break
                delay = base_delay_s * (2 ** (attempt - 1)) + random.uniform(0, 0.25)
                logger.warning(
                    "Neo4j transient error on attempt %d/%d: %s, retrying in %.2fs",
                    attempt,
                    retries,
                    exc,
                    delay,
                )
                time.sleep(delay)
        raise last_exc  # type: ignore[misc]
    
    @property
    def driver(self) -> Optional[Driver]:
        """Get the Neo4j driver instance.
        
        Returns:
            Optional[Driver]: The driver instance, or None if not connected.
        """
        return self._driver
