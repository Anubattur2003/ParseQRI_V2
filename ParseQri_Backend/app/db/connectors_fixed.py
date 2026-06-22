from typing import Any, Dict, List, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.sql import text
import pyodbc
from urllib.parse import quote_plus
from app.core.exceptions import DatabaseConnectionError, DataInsertionError
from app.schemas.db import DBConfigOut, DBType
import os
import chromadb
import requests

class ChromaDBManager:
    """Centralized ChromaDB manager for all users and data sources"""
    
    def __init__(self, persist_dir: str = "./data/chroma_storage", 
                 ollama_api_url: str = "http://localhost:11434/api/embeddings",
                 model_name: str = "mahonzhan/all-MiniLM-L6-v2"):
        """
        Initialize ChromaDB manager with Ollama embeddings.
        
        Args:
            persist_dir: Directory to persist ChromaDB data
            ollama_api_url: Ollama embeddings API endpoint
            model_name: Ollama model name for embeddings
        """
        self.persist_dir = persist_dir
        os.makedirs(persist_dir, exist_ok=True)
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.ollama_api_url = ollama_api_url
        self.model_name = model_name
    
    def encode(self, text: str) -> List[float]:
        """
        Generate embedding using Ollama API.
        
        Args:
            text: Text to encode
            
        Returns:
            List of embedding values
        """
        try:
            payload = {
                "model": self.model_name,
                "prompt": text
            }
            response = requests.post(self.ollama_api_url, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return result.get("embedding", [])
            else:
                raise Exception(f"Ollama API request failed with status code: {response.status_code}")
        except Exception as e:
            raise Exception(f"Failed to generate embedding: {str(e)}")
        
    def get_collection(self, collection_name: str = "unified_metadata"):
        """Get or create a unified collection for all metadata"""
        try:
            collection = self.client.get_collection(collection_name)
        except:
            collection = self.client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        return collection
    
    def store_table_metadata(self, user_id: int, source_type: str, source_name: str, 
                           table_name: str, schema_info: Dict[str, Any]):
        """Store table metadata in ChromaDB with user context"""
        collection = self.get_collection()
        
        # Create metadata document
        metadata_text = f"""
        Table: {table_name}
        Source: {source_name} ({source_type})
        User: {user_id}
        Columns: {', '.join([f"{col['column_name']} ({col['data_type']})" for col in schema_info.get('columns', [])])}
        Description: Table from {source_type} database containing {len(schema_info.get('columns', []))} columns
        """
        
        # Generate embedding using Ollama
        embedding = self.encode(metadata_text)
        
        # Store in ChromaDB
        collection.add(
            embeddings=[embedding],
            documents=[metadata_text],
            metadatas=[{
                "user_id": str(user_id),
                "source_type": source_type,
                "source_name": source_name,
                "table_name": table_name,
                "column_count": len(schema_info.get('columns', []))
            }],
            ids=[f"{user_id}_{source_type}_{source_name}_{table_name}"]
        )
    
    def search_relevant_tables(self, user_id: int, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant tables based on a query"""
        collection = self.get_collection()
        
        # Generate query embedding using Ollama
        query_embedding = self.encode(query)
        
        # Search in ChromaDB
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where={"user_id": str(user_id)}
        )
        
        return results

class MSSQLConnector:
    def __init__(self, config: DBConfigOut):
        self.config = config
        self.connection = None
        self.engine = None
        self.connect()

    def connect(self) -> None:
        """Establishes a connection to the SQL Server database."""
        try:
            # Build connection string for Windows Authentication
            if self.config.use_windows_auth:
                connection_string = (
                    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                    f"SERVER={self.config.server_name};"
                    f"DATABASE={self.config.database_name};"
                    f"Trusted_Connection=yes;"
                )
                encoded_connection = quote_plus(connection_string)
                engine_url = f"mssql+pyodbc:///?odbc_connect={encoded_connection}"
            else:
                # For future SQL Server authentication support
                raise NotImplementedError("SQL Server authentication not yet supported")
            
            # Create SQLAlchemy engine
            self.engine = create_engine(engine_url, fast_executemany=True)
            self.connection = self.engine.connect()
        except Exception as e:
            raise DatabaseConnectionError(f"Failed to connect to SQL Server: {str(e)}")

    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Executes an SQL query on the SQL Server database."""
        if not self.connection:
            self.connect()
        try:
            with self.connection.begin():
                self.connection.execute(text(query), params or {})
        except Exception as e:
            raise DatabaseConnectionError(f"Query execution failed: {str(e)}")
    
    def fetch_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Executes a query and returns the results."""
        if not self.connection:
            self.connect()
        try:
            result = self.connection.execute(text(query), params or {})
            # Fix for SQLAlchemy result handling - properly convert to list of dicts
            columns = list(result.keys())
            rows = result.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            raise DatabaseConnectionError(f"Query execution failed: {str(e)}")

    def insert_data(self, table: str, data: List[Dict[str, Any]]) -> None:
        """Inserts data into a table."""
        if not self.connection:
            self.connect()
        try:
            if not data:
                return
                
            keys = data[0].keys()
            columns = ", ".join(keys)
            placeholders = ", ".join([f":{key}" for key in keys])
            # Quote table identifier to safely handle table names derived from CSV filenames.
            query = f'INSERT INTO "{table}" ({columns}) VALUES ({placeholders})'
            
            with self.connection.begin():
                for row in data:
                    self.connection.execute(text(query), row)
        except Exception as e:
            raise DataInsertionError(f"Data insertion failed: {str(e)}")
    
    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """Retrieves schema information for a specified table."""
        query = """
            SELECT 
                COLUMN_NAME as column_name,
                DATA_TYPE as data_type,
                IS_NULLABLE as is_nullable,
                COLUMN_DEFAULT as column_default
            FROM 
                INFORMATION_SCHEMA.COLUMNS
            WHERE 
                TABLE_NAME = :table_name AND TABLE_CATALOG = :database
            ORDER BY 
                ORDINAL_POSITION;
        """
        try:
            return self.fetch_query(query, {"table_name": table_name, "database": self.config.database_name})
        except Exception as e:
            raise DatabaseConnectionError(f"Failed to get table schema: {str(e)}")
    
    def list_tables(self) -> List[str]:
        """Lists all tables in the current database."""
        try:
            query = """
                SELECT 
                    TABLE_NAME as table_name
                FROM 
                    INFORMATION_SCHEMA.TABLES 
                WHERE 
                    TABLE_CATALOG = :database AND TABLE_TYPE = 'BASE TABLE'
                ORDER BY 
                    TABLE_NAME;
            """
            result = self.fetch_query(query, {"database": self.config.database_name})
            return [row["table_name"] for row in result]
        except Exception as e:
            raise DatabaseConnectionError(f"Failed to list tables: {str(e)}")

    def close(self) -> None:
        """Closes the database connection."""
        if self.connection:
            self.connection.close()
            if self.engine:
                self.engine.dispose()
            self.connection = None

class DatabaseConnectorFactory:
    """Factory class to create appropriate database connectors"""
    
    @staticmethod
    def create_connector(config: DBConfigOut):
        """Create a database connector based on the database type"""
        if config.db_type == DBType.mssql:
            return MSSQLConnector(config)
        else:
            raise ValueError(f"Unsupported database type: {config.db_type}. Only MSSQL is supported.")
    
    @staticmethod
    def test_connection(config: DBConfigOut) -> bool:
        """Test database connection without storing the connector"""
        try:
            connector = DatabaseConnectorFactory.create_connector(config)
            connector.close()
            return True
        except Exception as e:
            print(f"Database connection test failed: {str(e)}")
            return False

# Initialize global ChromaDB manager
chroma_manager = ChromaDBManager()
