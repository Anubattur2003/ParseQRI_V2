"""
Metadata Extraction Service

Service for extracting database metadata.
Provides enhanced metadata extraction capabilities with schema analysis.
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import asyncio
from sqlalchemy import create_engine, inspect

# Don't try to import Database_Agent_SQL components since they don't exist
SchemaAgent = None
DatabaseAgent = None
SchemaAnalyzer = None

from app.schemas.db import DBConfigOut
from app.db.connectors import DatabaseConnectorFactory, chroma_manager


class MetadataExtractionService:
    """
    Service for extracting database metadata.
    
    Provides enhanced metadata extraction with:
    - Schema analysis
    - Relationship detection
    - Column type analysis
    - Data quality insights
    """
    
    def __init__(self):
        """Initialize the metadata extraction service."""
        self.schema_agent = None
        self.database_agent = None
        
        # Initialize agents if available (currently disabled)
        # The Database_Agent_SQL module is not available, so we'll use the connector approach only
    
    async def extract_metadata(self, config: DBConfigOut, user_id: str) -> Dict[str, Any]:
        """
        Extract comprehensive metadata from a database.
        
        Args:
            config: Database configuration
            user_id: User identifier
            
        Returns:
            Dictionary containing extracted metadata
        """
        try:
            # Create database connector
            try:
                connector = DatabaseConnectorFactory.create_connector(config)
            except Exception as e:
                print(f"Error creating database connector: {str(e)}")
                return {
                    "status": "error",
                    "message": f"Failed to connect to database: {str(e)}",
                    "metadata": []
                }
            
            # Extract metadata using database_agent.py for MSSQL
            metadata_extracted = []
            
            if config.db_type == "mssql":
                # Use Text_to_Sql database_agent.py for MSSQL
                metadata_extracted = await self._extract_with_database_agent(config, user_id)
            else:
                print(f"Warning: Unsupported database type: {config.db_type}")
                return {
                    "status": "error",
                    "message": f"Unsupported database type: {config.db_type}. Only MSSQL is supported.",
                    "metadata": []
                }
            
            # Store metadata in ChromaDB
            try:
                await self._store_metadata_in_chroma(user_id, config, metadata_extracted)
            except Exception as e:
                print(f"Warning: Failed to store metadata in ChromaDB: {str(e)}")
                # Continue with the process even if ChromaDB storage fails
            
            try:
                connector.close()
            except Exception as e:
                print(f"Warning: Failed to close database connection: {str(e)}")
            
            return {
                "status": "success",
                "message": f"Metadata extracted and stored for {len(metadata_extracted)} tables/collections",
                "metadata": metadata_extracted,
                "extraction_method": "connector"
            }
            
        except Exception as e:
            print(f"Unhandled error in extract_metadata: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to extract metadata: {str(e)}",
                "metadata": []
            }
    
    async def _extract_with_database_agent(self, config: DBConfigOut, user_id: str) -> List[Dict[str, Any]]:
        """
        Extract metadata using Text_to_Sql database_agent.py for MSSQL.
        
        Args:
            config: Database configuration
            user_id: User identifier
            
        Returns:
            List of table metadata
        """
        try:
            # Import the database agent from Text_to_Sql
            sys.path.append(str(Path(__file__).parent.parent.parent / "Text_to_Sql" / "agents"))
            from database_agent import DatabaseAgent
            
            # Create database agent
            agent = DatabaseAgent(config.server_name, config.database_name)
            
            # Establish connection and extract metadata
            success, message, schema_markdown = await agent.establish_connection()
            
            if not success:
                print(f"Database agent connection failed: {message}")
                return []
            
            print(f"Database agent connected successfully: {message}")
            
            # Get the schema from the agent's engine
            metadata_extracted = []
            if agent.engine:
                with agent.engine.connect() as connection:
                    schema = agent.get_database_schema(connection)
                    
                    for table_name, table_info in schema.items():
                        columns = []
                        for col, dtype in zip(table_info['columns'], table_info['data_types']):
                            columns.append({
                                "column_name": col,
                                "data_type": dtype,
                                "is_nullable": "YES",  # Default for now
                                "column_default": None
                            })
                        
                        metadata_extracted.append({
                            "table_name": table_name,
                            "column_count": len(columns),
                            "columns": columns,
                            "foreign_keys": table_info.get('foreign_keys', []),
                            "extraction_method": "database_agent",
                            "schema_markdown": schema_markdown
                        })
            
            return metadata_extracted
            
        except Exception as e:
            print(f"Error using database agent: {str(e)}")
            # Fallback to connector approach
            try:
                connector = DatabaseConnectorFactory.create_connector(config)
                return await self._extract_with_connector(connector, config)
            except Exception as fallback_error:
                print(f"Fallback connector also failed: {str(fallback_error)}")
                return []
    
    async def _extract_with_connector(self, connector, config: DBConfigOut) -> List[Dict[str, Any]]:
        """
        Extract metadata using database connector (fallback method).
        
        Args:
            connector: Database connector
            config: Database configuration
            
        Returns:
            List of table metadata
        """
        metadata_extracted = []
        
        # Get all tables
        tables = connector.list_tables()
        
        for table_name in tables:
            # Get table schema
            schema_info = connector.get_table_schema(table_name)
            
            metadata_extracted.append({
                "table_name": table_name,
                "column_count": len(schema_info),
                "columns": schema_info,
                "extraction_method": "connector"
            })
        
        return metadata_extracted
    
    async def _extract_mongodb_metadata(self, connector, config: DBConfigOut) -> List[Dict[str, Any]]:
        """
        Extract metadata from MongoDB.
        
        Args:
            connector: MongoDB connector
            config: Database configuration
            
        Returns:
            List of collection metadata
        """
        metadata_extracted = []
        
        # Get all collections
        collections = connector.list_collections()
        
        for collection_name in collections:
            # Get collection schema
            schema_info = connector.get_collection_schema(collection_name)
            
            metadata_extracted.append({
                "collection_name": collection_name,
                "field_count": len(schema_info),
                "fields": schema_info,
                "extraction_method": "mongodb_connector"
            })
        
        return metadata_extracted
    
    async def _store_metadata_in_chroma(self, user_id: str, config: DBConfigOut, 
                                       metadata_extracted: List[Dict[str, Any]]) -> None:
        """
        Store extracted metadata in ChromaDB.
        
        Args:
            user_id: User identifier
            config: Database configuration
            metadata_extracted: List of extracted metadata
        """
        try:
            for metadata in metadata_extracted:
                table_name = metadata.get("table_name") or metadata.get("collection_name")
                
                if table_name:
                    # Store in ChromaDB
                    chroma_manager.store_table_metadata(
                        user_id=int(user_id),
                        source_type=config.db_type,
                        source_name=config.database_name,
                        table_name=table_name,
                        schema_info={"columns": metadata.get("columns", metadata.get("fields", []))}
                    )
        except Exception as e:
            print(f"Warning: Could not store metadata in ChromaDB: {e}")
    
    def _build_database_url(self, config: DBConfigOut) -> str:
        """
        Build database URL from configuration.
        
        Args:
            config: Database configuration
            
        Returns:
            Database URL string
        """
        try:
            if config.db_type == "mysql":
                return f"mysql+pymysql://{config.db_user}:{config.db_password}@{config.host}:{config.port}/{config.db_name}"
            elif config.db_type == "postgres":
                return f"postgresql://{config.db_user}:{config.db_password}@{config.host}:{config.port}/{config.db_name}"
            elif config.db_type == "mongodb":
                return f"mongodb://{config.db_user}:{config.db_password}@{config.host}:{config.port}/{config.db_name}"
            else:
                # Default to MySQL if unknown
                print(f"Warning: Unknown database type '{config.db_type}', defaulting to MySQL")
                return f"mysql+pymysql://{config.db_user}:{config.db_password}@{config.host}:{config.port}/{config.db_name}"
        except Exception as e:
            print(f"Error building database URL: {e}")
            # Provide a fallback URL that will fail gracefully
            return "mysql+pymysql://invalid:invalid@localhost:3306/invalid"
    
    def _analyze_table_relationships(self, table_name: str, foreign_keys: List[Dict]) -> List[Dict[str, Any]]:
        """
        Analyze relationships for a table based on foreign keys.
        
        Args:
            table_name: Name of the table
            foreign_keys: List of foreign key constraints
            
        Returns:
            List of relationship information
        """
        relationships = []
        
        for fk in foreign_keys:
            relationship = {
                "type": "foreign_key",
                "from_table": table_name,
                "to_table": fk["referred_table"],
                "from_columns": fk["constrained_columns"],
                "to_columns": fk["referred_columns"],
                "relationship_type": "many-to-one"  # Default assumption
            }
            relationships.append(relationship)
        
        return relationships


# Create a singleton instance
metadata_extraction_service = MetadataExtractionService() 