import os
from typing import Dict, List, Tuple
from dotenv import load_dotenv
import pyodbc
from sqlalchemy import create_engine, text
import json
from datetime import datetime
import sys

# Add the parent directory to the path so we can import from core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.chroma_client import get_or_create_collection

# Load environment variables
load_dotenv()

# Create local directories for storage
CHROMA_DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")
SCHEMA_JSON_DIR = os.path.join(CHROMA_DB_DIR, "schema_history")
os.makedirs(CHROMA_DB_DIR, exist_ok=True)
os.makedirs(SCHEMA_JSON_DIR, exist_ok=True)

# Initialize ChromaDB collection using centralized client
db_collection = get_or_create_collection(
    "database_metadata",
    {"description": "Stores SQL Server database schema information"}
)

class DatabaseAgent:
    def __init__(self, server_name: str, database_name: str):
        self.server_name = server_name
        self.database_name = database_name
        self.connection_string = f"Driver={{SQL Server}};Server={server_name};Database={database_name};Trusted_Connection=yes;"
        self.engine = None
        
    def get_database_schema(self, connection) -> Dict:
        """Get all tables and their column names from the database WITH schema prefix"""
        schema = {}
        try:
            # First switch to the specified database
            use_db_query = text(f"USE {self.database_name};")
            connection.execute(use_db_query)
            
            # Get all tables with their columns AND schema prefix in a single query
            schema_query = text("""
                SELECT 
                    t.TABLE_SCHEMA,
                    t.TABLE_NAME,
                    STRING_AGG(c.COLUMN_NAME, ', ') WITHIN GROUP (ORDER BY c.COLUMN_NAME) AS COLUMNS,
                    STRING_AGG(c.DATA_TYPE, ', ') WITHIN GROUP (ORDER BY c.COLUMN_NAME) AS DATA_TYPES
                FROM INFORMATION_SCHEMA.TABLES t
                JOIN INFORMATION_SCHEMA.COLUMNS c 
                    ON t.TABLE_CATALOG = c.TABLE_CATALOG 
                    AND t.TABLE_SCHEMA = c.TABLE_SCHEMA 
                    AND t.TABLE_NAME = c.TABLE_NAME
                WHERE t.TABLE_TYPE = 'BASE TABLE'
                GROUP BY t.TABLE_SCHEMA, t.TABLE_NAME
                ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME;
            """)
            
            # Get foreign key relationships
            fk_query = text("""
                SELECT 
                    fk.name AS FK_NAME,
                    SCHEMA_NAME(t.schema_id) AS TABLE_SCHEMA,
                    OBJECT_NAME(fk.parent_object_id) AS TABLE_NAME,
                    COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS COLUMN_NAME,
                    SCHEMA_NAME(rt.schema_id) AS REFERENCED_TABLE_SCHEMA,
                    OBJECT_NAME(fk.referenced_object_id) AS REFERENCED_TABLE_NAME,
                    COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS REFERENCED_COLUMN_NAME
                FROM 
                    sys.foreign_keys AS fk
                    INNER JOIN sys.foreign_key_columns AS fkc 
                        ON fk.object_id = fkc.constraint_object_id
                    INNER JOIN sys.tables AS t 
                        ON fk.parent_object_id = t.object_id
                    INNER JOIN sys.tables AS rt 
                        ON fk.referenced_object_id = rt.object_id
                ORDER BY 
                    TABLE_SCHEMA, TABLE_NAME, FK_NAME;
            """)
            
            # Execute queries
            result = connection.execute(schema_query)
            for table_schema, table_name, columns_str, data_types_str in result:
                # Create fully qualified table name (schema.table)
                full_table_name = f"{table_schema}.{table_name}" if table_schema else table_name
                schema[full_table_name] = {
                    'columns': columns_str.split(', '),
                    'data_types': data_types_str.split(', '),
                    'foreign_keys': [],  # Will be populated below
                    'schema': table_schema,  # Store schema separately as well
                    'table_name': table_name  # Store table name without schema
                }
            
            # Add foreign key information
            fk_result = connection.execute(fk_query)
            for fk in fk_result:
                # Create fully qualified table name
                full_table_name = f"{fk.TABLE_SCHEMA}.{fk.TABLE_NAME}" if fk.TABLE_SCHEMA else fk.TABLE_NAME
                full_ref_table = f"{fk.REFERENCED_TABLE_SCHEMA}.{fk.REFERENCED_TABLE_NAME}" if fk.REFERENCED_TABLE_SCHEMA else fk.REFERENCED_TABLE_NAME
                
                if full_table_name in schema:
                    schema[full_table_name]['foreign_keys'].append({
                        'name': fk.FK_NAME,
                        'column': fk.COLUMN_NAME,
                        'referenced_table': full_ref_table,  # Use fully qualified name
                        'referenced_column': fk.REFERENCED_COLUMN_NAME
                    })
                
            return schema
        except Exception as e:
            print(f"Error fetching schema: {str(e)}")
            return {}

    async def generate_schema_description(self, schema: Dict) -> str:
        """Generate a technical description of the schema in markdown format"""
        return self.schema_to_markdown(schema)

    def schema_to_markdown(self, schema: Dict) -> str:
        """Convert schema dictionary to basic markdown format"""
        if not schema:
            return "No tables found in the database or error fetching schema."
            
        markdown = "# Database Schema\n\n"
        for table_name, info in schema.items():
            markdown += f"## Table: {table_name}\n\n"
            markdown += "### Columns:\n"
            for col, dtype in zip(info['columns'], info['data_types']):
                markdown += f"- {col} ({dtype})\n"
            
            if info['foreign_keys']:
                markdown += "\n### Foreign Keys:\n"
                for fk in info['foreign_keys']:
                    markdown += f"- {fk['column']} ➡️ {fk['referenced_table']}.{fk['referenced_column']}\n"
            markdown += "\n"
        return markdown

    def save_schema_to_json(self, schema: Dict, schema_markdown: str, version: str, timestamp: str) -> None:
        """Save schema information to a JSON file"""
        try:
            # Create a filename with timestamp, replacing invalid characters
            safe_server_name = self.server_name.replace('\\', '_').replace('/', '_')
            # Replace colons and other invalid characters in timestamp
            safe_timestamp = timestamp.replace(':', '-').replace('.', '_')
            filename = f"{safe_server_name}_{self.database_name}_{safe_timestamp}.json"
            filepath = os.path.join(SCHEMA_JSON_DIR, filename)
            
            # Prepare the data to save
            schema_data = {
                "server_name": self.server_name,
                "database_name": self.database_name,
                "timestamp": timestamp,  # Keep original timestamp in the JSON content
                "sql_server_version": version,
                "schema": schema,
                "schema_markdown": schema_markdown
            }
            
            # Save to JSON file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(schema_data, f, indent=2, ensure_ascii=False)
                
            print(f"Schema saved to JSON file: {filepath}")
        except Exception as e:
            print(f"Error saving schema to JSON: {str(e)}")
            raise  # Re-raise the exception to help with debugging

    async def test_connection(self) -> Tuple[bool, str, str]:
        """Test if database connection is possible without establishing a persistent connection."""
        try:
            print(f"Testing connection to server: {self.server_name}, database: {self.database_name}")
            print(f"Connection string: {self.connection_string}")
            
            # Create a temporary engine for testing
            test_engine = create_engine(
                f"mssql+pyodbc:///?odbc_connect={self.connection_string}",
                fast_executemany=True
            )
            
            with test_engine.connect() as connection:
                # Test connection with version and database check
                version = connection.execute(text("SELECT @@VERSION")).scalar()
                db_size = connection.execute(text(
                    "SELECT CAST(SUM(size * 8.0 / 1024) AS DECIMAL(10,2)) "
                    "FROM sys.master_files WHERE database_id = DB_ID()"
                )).scalar()
                
                print(f"Successfully tested connection to SQL Server!\nServer Version: {version}")
                return True, version, f"Database Size: {db_size} MB"
                
        except Exception as e:
            error_msg = f"Failed to test connection: {str(e)}"
            print(f"Connection error: {error_msg}")
            return False, "", error_msg

    async def establish_connection(self) -> Tuple[bool, str, str]:
        """Establish a persistent connection and fetch schema metadata."""
        try:
            print(f"Establishing connection to server: {self.server_name}, database: {self.database_name}")
            print(f"Connection string: {self.connection_string}")
            
            # Test connection first
            is_connectable, version, info = await self.test_connection()
            if not is_connectable:
                return False, f"Connection test failed: {info}", ""
            
            # Create persistent engine with fast_executemany for better performance
            self.engine = create_engine(
                f"mssql+pyodbc:///?odbc_connect={self.connection_string}",
                fast_executemany=True
            )
            
            with self.engine.connect() as connection:
                print(f"Successfully established connection to SQL Server!\nServer Version: {version}")
                
                try:
                    # Get database schema
                    schema = self.get_database_schema(connection)
                    
                    # Generate schema description using Gemini
                    schema_markdown = await self.generate_schema_description(schema)
                    
                    # Store in ChromaDB with simplified metadata
                    timestamp = datetime.now().isoformat()
                    connection_id = f"{self.server_name}_{self.database_name}_{timestamp}"
                    
                    # Convert schema to a simple string representation for metadata
                    schema_meta = {}
                    for table, info in schema.items():
                        schema_meta[table] = {
                            'columns': ','.join(info['columns']),
                            'data_types': ','.join(info['data_types']),
                            'foreign_keys': [
                                {
                                    'name': fk['name'],
                                    'column': fk['column'],
                                    'referenced_table': fk['referenced_table'],
                                    'referenced_column': fk['referenced_column']
                                } for fk in info['foreign_keys']
                            ]
                        }
                    
                    # Save to ChromaDB
                    db_collection.upsert(
                        documents=[schema_markdown],
                        metadatas=[{
                            "server_name": self.server_name,
                            "database_name": self.database_name,
                            "schema": json.dumps(schema_meta),
                            "timestamp": timestamp,
                            "version": version
                        }],
                        ids=[connection_id]
                    )
                    
                    # Save to JSON file
                    self.save_schema_to_json(schema, schema_markdown, version, timestamp)
                    
                    return True, "Connection established and schema metadata fetched successfully!", schema_markdown
                except Exception as schema_error:
                    error_msg = f"Connected to database, but could not fetch schema: {str(schema_error)}"
                    print(f"Warning: {error_msg}")
                    return True, error_msg, "Schema information not available."
            
        except Exception as e:
            error_msg = f"Failed to connect to the database: {str(e)}"
            print(f"Connection error: {error_msg}")
            return False, error_msg, ""

    def get_schema_history(self) -> str:
        """Retrieve schema history for the current database from ChromaDB"""
        try:
            # Query ChromaDB for all schemas of this database using the correct where clause format
            results = db_collection.get(
                where={
                    "$and": [
                        {"server_name": {"$eq": self.server_name}},
                        {"database_name": {"$eq": self.database_name}}
                    ]
                }
            )
            
            if not results or not results['ids']:
                return "No schema history found for this database."
            
            # Create a markdown formatted history
            history_md = "# Schema History\n\n"
            
            # Sort by timestamp (newest first)
            entries = list(zip(
                results['ids'], 
                results['metadatas'], 
                results['documents']
            ))
            entries.sort(key=lambda x: x[1]['timestamp'], reverse=True)
            
            for id, metadata, doc in entries:
                timestamp = metadata['timestamp']
                version = metadata.get('version', 'Unknown version')
                schema = json.loads(metadata['schema'])
                
                history_md += f"## Snapshot from {timestamp}\n"
                history_md += f"SQL Server Version: {version}\n\n"
                history_md += "### Tables:\n"
                for table, info in schema.items():
                    history_md += f"- {table}\n"
                    history_md += f"  - Columns: {info['columns']}\n"
                    history_md += f"  - Types: {info['data_types']}\n"
                    if 'foreign_keys' in info and info['foreign_keys']:
                        history_md += f"  - Foreign Keys:\n"
                        for fk in info['foreign_keys']:
                            history_md += f"    - {fk['column']} ➡️ {fk['referenced_table']}.{fk['referenced_column']}\n"
                history_md += "\n---\n\n"
            
            return history_md
        except Exception as e:
            print(f"Error retrieving schema history: {str(e)}")
            return f"Error retrieving schema history: {str(e)}"

def main():
    # Example usage of DatabaseAgent
    server_name = "YOUR_SERVER_NAME"  # Replace with your SQL Server name
    database_name = "YOUR_DATABASE_NAME"  # Replace with your database name
    
    # Initialize the database agent
    agent = DatabaseAgent(server_name, database_name)
    
    async def run_example():
        try:
            # Test connection and get schema
            print("Connecting to database...")
            success, message, schema_markdown = await agent.connect_to_database()
            
            if success:
                print(f"Connection successful: {message}")
                print("\nDatabase Schema:")
                print(schema_markdown)
                
                # Get schema history
                print("\nSchema history:")
                history = agent.get_schema_history()
                print(history)
                
            else:
                print(f"Connection failed: {message}")
                
        except Exception as e:
            print(f"Error in example: {str(e)}")

    # Run the async example
    import asyncio
    asyncio.run(run_example())

if __name__ == "__main__":
    main() 