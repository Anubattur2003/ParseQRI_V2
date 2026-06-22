import sqlalchemy
from sqlalchemy import inspect, create_engine, text
from typing import Dict, Any, Optional, List
from models.data_models import QueryContext, AgentResponse
import ollama
import os
import chromadb
import logging

class SchemaUnderstandingAgent:
    """
    Agent responsible for retrieving and processing database schema information.
    Provides context for SQL generation and other downstream tasks.
    """
    
    def __init__(self, llm_model="PetrosStav/gemma3-tools:4b", api_base="http://localhost:11434", 
                db_url="postgresql://postgres:root@localhost:5432/parseqri",
                schema="public",
                chroma_persist_dir="../data/db_storage"):
        """Initialize the Schema Understanding Agent with the specified LLM model."""
        self.llm_model = llm_model
        ollama.api_base = api_base
        self.db_url = db_url
        self.schema = schema
        self.chroma_persist_dir = chroma_persist_dir
        self.logger = logging.getLogger(__name__)
        
        # Create SQLAlchemy engine
        try:
            self.engine = create_engine(self.db_url)
            print(f"PostgreSQL connection established successfully for schema retrieval")
        except Exception as e:
            self.engine = None
            print(f"Error connecting to PostgreSQL: {e}")
        
        # We'll create separate ChromaDB clients for each user as needed
        self.chroma_clients = {}
        self.collections = {}
    
    def process(self, context: QueryContext) -> AgentResponse:
        """Process the query context and extract schema information"""
        try:
            # Ensure we have a user_id for ChromaDB lookup
            if not context.user_id:
                # Check available users in the storage directory
                user_dirs = self._get_available_users()
                if user_dirs:
                    context.user_id = user_dirs[0]  # Use first available user
                    print(f"No user ID provided, using first available user: {context.user_id}")
                else:
                    context.user_id = "default_user"
                    print("No user ID provided or available, using default_user")
            else:
                # Validate if user exists
                user_dirs = self._get_available_users()
                if user_dirs and context.user_id not in user_dirs:
                    print(f"Warning: User '{context.user_id}' not found. Available users: {', '.join(user_dirs)}")
                    if user_dirs:
                        context.user_id = user_dirs[0]
                        print(f"Using available user: {context.user_id}")
                        
            # If we don't have a table name yet, try to get it from relevant metadata
            if not context.table_name and hasattr(context, 'relevant_metadata') and context.relevant_metadata:
                # The table name from metadata is already the full table name (e.g., "2_loan")
                # Use it directly without trying to extract parts
                retrieved_table = context.relevant_metadata.get('table_name', '')
                context.table_name = retrieved_table
                print(f"Found table name from relevant_metadata: {context.table_name}")
                
            # If we still don't have a table name, try to find it from ChromaDB
            if not context.table_name:
                # Search for relevant table in ChromaDB
                relevant_table = self._find_relevant_table(context.user_id, context.user_question)
                if relevant_table:
                    # Use the table name directly (it's already in the correct format)
                    context.table_name = relevant_table
                    print(f"Found relevant table from ChromaDB: {context.table_name}")
                else:
                    print(f"No relevant table found in ChromaDB for user {context.user_id}")
                    
                    # Check if we have any tables for this user in PostgreSQL
                    if self.engine:
                        postgres_tables = self._get_user_postgres_tables(context.user_id)
                        if postgres_tables:
                            # Get table name without user prefix
                            first_table = postgres_tables[0]
                            if first_table.startswith(f"{context.user_id}_"):
                                context.table_name = first_table.replace(f"{context.user_id}_", "")
                            else:
                                context.table_name = first_table
                            print(f"Using first available PostgreSQL table: {context.table_name}")
            
            # Store the original table name for reference
            original_table_name = context.table_name
            
            # Ensure the table name is properly formatted for database queries
            # We enforce {user_id}_{table_name} pattern now (as per postgres_handler fix)
            
            postgres_table_name = context.table_name
            
            # If table already has user_id as prefix, use it directly
            if postgres_table_name and postgres_table_name.startswith(f"{context.user_id}_"):
                print(f"Table already has user_id as prefix: {postgres_table_name}")
                # context.table_name should ideally be the suffix for user display, but for now we keep sync
                
            # If table already has user_id as suffix, check if that's the table we want
            elif postgres_table_name and postgres_table_name.endswith(f"_{context.user_id}"):
                print(f"Table has user_id as suffix, assuming it matches: {postgres_table_name}")
                
            # Otherwise, try prepending user_id (standard pattern)
            elif postgres_table_name:
                # But first check if the table exists as is (maybe it's a shared table)
                # For now, default to prefixing
                postgres_table_name = f"{context.user_id}_{postgres_table_name}"
                print(f"Using table name with user_id prefix: {postgres_table_name}")
                
            # If we still don't have a table name, check if there are any tables for this user
            if not context.table_name and self.engine:
                postgres_tables = self._get_user_postgres_tables(context.user_id)
                if postgres_tables:
                    # Use the first table found
                    first_table = postgres_tables[0]
                    postgres_table_name = first_table
                    
                    # Update context.table_name to be the "clean" name (without prefix)
                    if first_table.startswith(f"{context.user_id}_"):
                         context.table_name = first_table[len(context.user_id)+1:]
                    else:
                         context.table_name = first_table
                    
                    print(f"No table specified, using first available table: {context.table_name} (DB: {postgres_table_name})")
            
            if not context.table_name:
                return AgentResponse(
                    success=False,
                    message=f"No table name found for query. Please upload data first or specify a table for user {context.user_id}."
                )
            
            # Resolve to an actual table name in PostgreSQL to avoid stale metadata names.
            resolved_table_name = self._resolve_existing_table_name(postgres_table_name)
            if not resolved_table_name:
                resolved_table_name = postgres_table_name
            self.logger.info(
                "Schema resolution: requested_table=%s resolved_table=%s user_id=%s",
                postgres_table_name,
                resolved_table_name,
                context.user_id
            )
            # Keep context aligned so downstream SQL generation uses the true table.
            context.table_name = resolved_table_name
            
            # Get schema from PostgreSQL using the resolved table name
            schema = self.get_postgres_schema(resolved_table_name)
            
            # If schema not found, try with just the base table name (without UUIDs)
            if not schema and '_' in postgres_table_name:
                # Try to get the actual table name from the database
                actual_table = self._find_actual_table_name(context.user_id, postgres_table_name)
                if actual_table:
                    print(f"Found actual table in database: {actual_table}")
                    schema = self.get_postgres_schema(actual_table)
            
            if not schema:
                return AgentResponse(
                    success=False,
                    message=f"Failed to retrieve schema for table {resolved_table_name}. Make sure the table exists in PostgreSQL."
                )
            
            cleaned_schema = self.clean_schema(schema)
            print(f"Successfully retrieved schema for table {postgres_table_name} with {len(cleaned_schema)} columns")
            return AgentResponse(
                success=True,
                message="Schema retrieved successfully",
                data={"schema": cleaned_schema, "resolved_table_name": resolved_table_name}
            )
        except Exception as e:
            return AgentResponse(
                success=False,
                message=f"Error in schema understanding: {str(e)}"
            )
    
    def _resolve_existing_table_name(self, candidate_table_name: str) -> Optional[str]:
        """Resolve a candidate table name to a real table name present in PostgreSQL."""
        try:
            if not self.engine or not candidate_table_name:
                return None
            inspector = inspect(self.engine)
            all_tables = inspector.get_table_names(schema=self.schema)
            if candidate_table_name in all_tables:
                return candidate_table_name
            
            candidate_parts = candidate_table_name.split('_')
            for table in all_tables:
                table_parts = table.split('_')
                if any(part and part in table_parts for part in candidate_parts):
                    return table
            return None
        except Exception as e:
            self.logger.warning("Failed to resolve table name %s: %s", candidate_table_name, e)
            return None
    
    def _get_available_users(self):
        """Get available user IDs from storage directory"""
        storage_dir = os.path.join(self.chroma_persist_dir)
        if not os.path.exists(storage_dir):
            return []
        
        users = []
        for item in os.listdir(storage_dir):
            if os.path.isdir(os.path.join(storage_dir, item)):
                users.append(item)
        
        return users
    
    def _get_user_postgres_tables(self, user_id: str) -> List[str]:
        """Get all PostgreSQL tables for a user"""
        try:
            if not self.engine:
                return []
                
            with self.engine.connect() as conn:
                inspector = inspect(self.engine)
                all_tables = inspector.get_table_names(schema=self.schema)
                
                # Filter tables by user_id prefix (standard)
                user_tables = [table for table in all_tables if table.startswith(f"{user_id}_")]
                
                # Print all found tables for debugging
                if user_tables:
                    print(f"Found {len(user_tables)} tables for user {user_id}: {', '.join(user_tables)}")
                else:
                    # Also look for tables with other patterns (for compatibility)
                    user_tables = [table for table in all_tables if f"_{user_id}_" in table or table.startswith(f"{user_id}_")]
                    if user_tables:
                        print(f"Found {len(user_tables)} tables with alternative patterns for user {user_id}: {', '.join(user_tables)}")
                    else:
                        # As a fallback, just list all available tables
                        print(f"No tables found for user {user_id}. Available tables: {', '.join(all_tables) if all_tables else 'None'}")
                
                return user_tables
                
        except Exception as e:
            print(f"Error getting user PostgreSQL tables: {e}")
            return []
    
    def _get_user_collection(self, user_id):
        """Get or create a user-specific ChromaDB collection"""
        if user_id in self.collections:
            return self.collections[user_id]
            
        # Create user directory if it doesn't exist
        user_dir = os.path.join(self.chroma_persist_dir, user_id)
        os.makedirs(user_dir, exist_ok=True)
        
        # Create or get client for this user
        if user_id not in self.chroma_clients:
            from chromadb.config import Settings
            self.chroma_clients[user_id] = chromadb.PersistentClient(
                path=user_dir,
                settings=Settings(
                    anonymized_telemetry=False,
                    chroma_product_telemetry_impl="agents.telemetry_noop.NoopTelemetryClient",
                    chroma_telemetry_impl="agents.telemetry_noop.NoopTelemetryClient",
                )
            )
        
        # Create or get collection for this user
        try:
            collection = self.chroma_clients[user_id].get_collection(f"{user_id}_metadata")
        except ValueError:
            # Collection doesn't exist yet
            return None
            
        self.collections[user_id] = collection
        return collection
    
    def _find_relevant_table(self, user_id: str, query_text: str) -> Optional[str]:
        """Find the most relevant table for a query using ChromaDB"""
        try:
            collection = self._get_user_collection(user_id)
            if not collection:
                print(f"No ChromaDB collection found for user {user_id}, checking PostgreSQL tables directly")
                # If no ChromaDB collection exists, try to find tables in the database
                postgres_tables = self._get_user_postgres_tables(user_id)
                if postgres_tables:
                    # Return the full table name as it exists in the database
                    first_table = postgres_tables[0]
                    print(f"Using PostgreSQL table: {first_table}")
                    return first_table
                return None
                
            # Query ChromaDB for relevant tables
            try:
                results = collection.query(
                    query_texts=[query_text],
                    n_results=1,
                    where={"user_id": user_id}
                )
                
                if not results['ids'][0]:
                    return None
                    
                # Get the most relevant metadata
                metadata = results['metadatas'][0][0]
                table_name = metadata.get("table_name")
                
                # Return the table name directly - it should already be in the correct format
                print(f"Found table from ChromaDB metadata: {table_name}")
                return table_name
                
            except Exception as query_error:
                print(f"Error querying ChromaDB: {query_error}, checking PostgreSQL tables directly")
                # If ChromaDB query fails, try to find tables in the database
                postgres_tables = self._get_user_postgres_tables(user_id)
                if postgres_tables:
                    # Return the full table name as it exists in the database
                    first_table = postgres_tables[0]
                    print(f"Using PostgreSQL table: {first_table}")
                    return first_table
                return None
                
        except Exception as e:
            print(f"Error finding relevant table: {e}")
            # Try PostgreSQL as a last resort
            try:
                postgres_tables = self._get_user_postgres_tables(user_id)
                if postgres_tables:
                    # Remove user_id prefix if it exists
                    first_table = postgres_tables[0]
                    print(f"Using PostgreSQL table as fallback: {first_table}")
                    return first_table
            except Exception as pg_error:
                print(f"Failed to fetch PostgreSQL tables: {pg_error}")
            return None
    
    def get_postgres_schema(self, table_name: str) -> Dict[str, str]:
        """Retrieve the schema of the table from PostgreSQL database"""
        try:
            if not self.engine:
                print("PostgreSQL engine not initialized")
                return None
                
            with self.engine.connect() as conn:
                inspector = inspect(self.engine)
                
                # Get schema and table name parts
                if '.' in table_name:
                    schema_name, pure_table_name = table_name.split('.', 1)
                else:
                    schema_name = self.schema
                    pure_table_name = table_name
                
                # Check if table exists directly
                all_tables = inspector.get_table_names(schema=schema_name)
                
                # Debug output
                print(f"Searching for table: {pure_table_name}")
                print(f"Available tables: {', '.join(all_tables)}")
                
                if pure_table_name not in all_tables:
                    print(f"Table {pure_table_name} not found in schema {schema_name}")
                    
                    # Try direct matches with common patterns
                    base_name = None
                    user_id = None
                    
                    # Extract potential user_id and base_name from table
                    if '_' in pure_table_name:
                        parts = pure_table_name.split('_')
                        if len(parts) >= 2:
                            # Check if it's in format base_name_user_id
                            user_id = parts[-1]
                            base_name = parts[0]
                            
                            # Try pattern: base_name_user_id
                            if f"{base_name}_{user_id}" in all_tables:
                                pure_table_name = f"{base_name}_{user_id}"
                                print(f"Found table with suffix format: {pure_table_name}")
                            
                            # Try pattern: user_id_base_name
                            elif f"{user_id}_{base_name}" in all_tables:
                                pure_table_name = f"{user_id}_{base_name}"
                                print(f"Found table with prefix format: {pure_table_name}")
                            
                            # Try partial matches
                            else:
                                for table in all_tables:
                                    # Match tables that start with base_name_ and end with _user_id
                                    if table.startswith(f"{base_name}_") and table.endswith(f"_{user_id}"):
                                        pure_table_name = table
                                        print(f"Found table with extended suffix: {pure_table_name}")
                                        break
                                    
                                    # Match tables that start with user_id_base_name_
                                    elif table.startswith(f"{user_id}_{base_name}_"):
                                        pure_table_name = table
                                        print(f"Found table with extended prefix: {pure_table_name}")
                                        break
                    
                    # If we still don't have a match, try all tables again
                    if pure_table_name not in all_tables:
                        # As a last resort, check if there's any table with a similar name
                        for table in all_tables:
                            parts_table = table.split('_')
                            parts_name = pure_table_name.split('_')
                            
                            # Check for common parts
                            if any(part in parts_table for part in parts_name):
                                pure_table_name = table
                                print(f"Found partially matching table: {pure_table_name}")
                                break
                    
                    # Final check
                    if pure_table_name not in all_tables:
                        return None
                
                # Get column info
                columns = inspector.get_columns(pure_table_name, schema=schema_name)
                schema = {col['name']: str(col['type']) for col in columns}
                return schema
                
        except Exception as e:
            print(f"Error retrieving PostgreSQL schema: {e}")
            return None
    
    def clean_schema(self, schema: Dict[str, str]) -> Dict[str, str]:
        """Clean the schema by converting column names to lowercase and removing spaces"""
        cleaned_schema = {}
        for key, value in schema.items():
            cleaned_key = self.clean_column_name(key)
            cleaned_schema[cleaned_key] = value
        return cleaned_schema
    
    def clean_column_name(self, col_name: str) -> str:
        """Clean column names by converting to lowercase and replacing spaces with underscores"""
        col_name = col_name.lower().replace(' ', '_').replace('\n', '_').replace('/', '_')
        col_name = col_name.replace(',', '').replace('(', '').replace(')', '')
        return col_name
    
    def _find_actual_table_name(self, user_id: str, table_name: str) -> str:
        """
        Find the actual table name in the database by prefix matching.
        This helps when we have a table name with UUID but the actual database table uses a simpler name.
        
        Args:
            user_id: User identifier
            table_name: The table name to match (likely includes UUID)
            
        Returns:
            The actual table name from the database or None if not found
        """
        try:
            if not self.engine:
                return None
                
            with self.engine.connect() as conn:
                inspector = inspect(self.engine)
                all_tables = inspector.get_table_names(schema=self.schema)
                
                # Try to extract the base name (assuming format: base_name_uuid)
                base_parts = []
                if '_' in table_name:
                    parts = table_name.split('_')
                    # If the last part is the user ID, use parts before that
                    if parts[-1] == user_id and len(parts) > 1:
                        base_parts = [parts[0]]  # Use the first part
                    # If the first part is the user ID, use parts after that
                    elif parts[0] == user_id and len(parts) > 1:
                        base_parts = [parts[1]]  # Use the second part
                    else:
                        base_parts = [parts[0]]  # Use the first part
                else:
                    base_parts = [table_name]  # Use the whole name
                    
                # Create a simpler base name (just the main part without UUIDs)
                base_name = base_parts[0]
                
                # Look for tables that match the base name
                for table in all_tables:
                    # Perfect match
                    if table == table_name:
                        print(f"Found exact table match: {table}")
                        return table
                    
                    # Match on base_name_user_id pattern (suffix)
                    if table == f"{base_name}_{user_id}":
                        print(f"Found suffix match: {table}")
                        return table
                    
                    # Match on user_id_base_name pattern (prefix)
                    if table == f"{user_id}_{base_name}":
                        print(f"Found prefix match: {table}")
                        return table
                    
                    # Partial match on prefix (old pattern)
                    if table.startswith(f"{user_id}_{base_name}_"):
                        print(f"Found prefix pattern match: {table}")
                        return table
                    
                    # Partial match on suffix (new pattern)
                    if table.startswith(f"{base_name}_") and table.endswith(f"_{user_id}"):
                        print(f"Found suffix pattern match: {table}")
                        return table
                
                print(f"No matching table found for {table_name} or {base_name}")
                
                # As a fallback, list all available tables
                if all_tables:
                    print(f"Available tables: {', '.join(all_tables)}")
                
                return None
                
        except Exception as e:
            print(f"Error finding actual table name: {e}")
            return None 