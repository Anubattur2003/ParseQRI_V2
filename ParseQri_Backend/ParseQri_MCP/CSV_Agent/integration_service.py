import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import asyncio
import logging

# Add current directory to path so imports work correctly
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from core.orchestrator import TextSQLOrchestrator
from utils.data_folder_monitor import DataFolderMonitor
from models.data_models import QueryContext

class CsvAgentService:
    """Service wrapper for the CSV Agent to handle API requests"""
    
    def __init__(self):
        self.config_path = os.path.join(current_dir, "config.json")
        self.logger = logging.getLogger(__name__)
        self._ensure_config()
        self.orchestrator = TextSQLOrchestrator(self.config_path)
        
    def _ensure_config(self):
        """Ensure configuration file exists"""
        if not os.path.exists(self.config_path):
            # This should ideally be copied from main.py's create_default_config
            # For now assume it exists or will be created by main.py if run once
            pass
            
    async def process_query(self, query: str, user_id: str, table_name: str = "", db_id: int = None, visualization: bool = False) -> Dict[str, Any]:
        """Process a natural language query against CSV data"""
        try:
            self.logger.info(
                "CSV process_query start: user_id=%s table_name=%s query=%s",
                user_id,
                table_name,
                query
            )
            # We need to run this in a thread pool since orchestrator might be synchronous
            # checking orchestrator.py, it seems synchronous
            
            # Helper to run synchronous orchestrator method
            def _run_orchestrator():
                # Determine db path for user
                user_db_path = os.path.join(current_dir, f"../data/db_storage/{user_id}")
                
                # Process query
                context = self.orchestrator.process_query(
                    user_question=query,
                    db_name="", # Determined dynamically
                    table_name=table_name, 
                    user_id=user_id,
                    force_visualization=visualization
                )
                
                return context
            
            # Run in thread pool
            context = await asyncio.to_thread(_run_orchestrator)
            
            # Format response
            response = {
                "success": True,
                "answer": context.formatted_response,
                "sql_query": context.sql_query,
                "data": context.query_results.to_dict(orient='records') if hasattr(context, 'query_results') and context.query_results is not None else [],
                "chart_type": context.visualization_data.get('chart_type', 'bar') if hasattr(context, 'visualization_data') and context.visualization_data else 'bar',
                "visualization_data": context.visualization_data if hasattr(context, 'visualization_data') else None,
                "table_name": context.table_name
            }
            self.logger.info(
                "CSV process_query success: user_id=%s resolved_table=%s rows=%s",
                user_id,
                response.get("table_name"),
                len(response.get("data", []))
            )
            
            return response
            
        except Exception as e:
            self.logger.exception("Error in CsvAgentService.process_query: %s", e)
            return {
                "error": str(e)
            }

    async def execute_sql(self, sql_query: str, user_id: str) -> Dict[str, Any]:
        """Execute a raw SQL query directly"""
        try:
            self.logger.info("CSV execute_sql start: user_id=%s sql=%s", user_id, sql_query)
            # Helper to run synchronous logic
            def _run_execution():
                # Check if orchestrator has query_execution agent
                if 'query_execution' not in self.orchestrator.agents:
                     raise Exception("Query execution agent not available")
                
                context = QueryContext(
                    user_question="Manual Execution",
                    db_name="", 
                    table_name="",
                    user_id=user_id
                )
                context.sql_query = sql_query
                context.sql_valid = True 
                
                execution_response = self.orchestrator.agents['query_execution'].process(context)
                
                if not execution_response.success:
                    raise Exception(execution_response.message)
                    
                return execution_response.data.get('query_results')

            # Run in thread pool
            result_df = await asyncio.to_thread(_run_execution)
            
            return {
                "success": True,
                "data": result_df.to_dict(orient='records') if result_df is not None else [],
                "sql_query": sql_query
            }
            
        except Exception as e:
            self.logger.exception("Error in CsvAgentService.execute_sql: %s", e)
            return {"success": False, "error": str(e)}

    async def upload_csv(self, file_path: str, user_id: str, original_filename: str, db_id: int = None) -> Dict[str, Any]:
        """Process an uploaded CSV file"""
        try:
            suggested_table_name = Path(original_filename).stem
            self.logger.info(
                "CSV upload start: user_id=%s file=%s suggested_table=%s",
                user_id,
                file_path,
                suggested_table_name
            )
            
            def _run_upload():
                context = self.orchestrator.process_upload(
                    csv_file=file_path,
                    user_id=user_id,
                    suggested_table_name=suggested_table_name,
                    db_id=db_id
                )
                return context
                
            context = await asyncio.to_thread(_run_upload)
            
            if hasattr(context, 'table_name') and context.table_name:
                self.logger.info(
                    "CSV upload success: user_id=%s stored_table=%s",
                    user_id,
                    context.table_name
                )
                return {
                    "success": True,
                    "table_name": context.table_name,
                    "message": f"Successfully uploaded and indexed {original_filename}"
                }
            else:
                 return {
                    "success": False,
                    "error": "Failed to determine table name after processing"
                }
                
        except Exception as e:
            self.logger.exception("Error in CsvAgentService.upload_csv: %s", e)
            return {
                "success": False,
                "error": str(e)
            }

    async def list_tables(self, user_id: str) -> List[Dict[str, Any]]:
        """List available tables for a user"""
        try:
            def _get_tables():
                tables = []
                
                # Use SQLAlchemy inspector directly to get ONLY tables that actually exist
                from sqlalchemy import create_engine, inspect
                # Keep credentials consistent with the repo's local Postgres setup.
                db_url = "postgresql://postgres:root@localhost:5432/parseqri"
                engine = create_engine(db_url)
                inspector = inspect(engine)
                
                # Get all tables from PostgreSQL
                all_pg_tables = inspector.get_table_names(schema='public')
                
                # Filter to only user's tables (with user_id_ prefix)
                user_prefix = f"{user_id}_"
                for table in all_pg_tables:
                    if table.startswith(user_prefix):
                        # Extract display name (without prefix)
                        display_name = table[len(user_prefix):]
                        
                        tables.append({
                            "name": display_name,
                            "full_name": table,
                            "source": "postgres"
                        })
                
                # Note: We intentionally don't add metadata-only tables since they might be stale
                # Only tables that actually exist in PostgreSQL are returned
                        
                return tables

            return await asyncio.to_thread(_get_tables)
            
        except Exception as e:
            print(f"Error in CsvAgentService.list_tables: {str(e)}")
            return []
            
    async def get_table_schema(self, user_id: str, table_name: str) -> Dict[str, Any]:
        """Get schema/columns for a specific table"""
        try:
            # We can use the postgres handler or metadata indexer to get columns
            # For now, let's try to inspect the database directly or use metadata
            
            def _get_schema():
                # This is a bit hacky, reusing get_postgres_tables logic from main.py but for columns
                # Ideally, we should add a get_schema method to the postgres_handler agent
                
                from sqlalchemy import create_engine, inspect
                from sqlalchemy.exc import NoSuchTableError
                
                # Assuming standard postgres connection from config
                # We should really read this from config, but hardcoding for now based on main.py
                db_url = "postgresql://postgres:root@localhost:5432/parseqri"
                engine = create_engine(db_url)
                inspector = inspect(engine)
                
                # Build candidates list intelligently to avoid double-prefixing
                candidates = []
                
                # If table_name already starts with user_id_, use it as-is first (it's already the full name)
                if table_name.startswith(f"{user_id}_"):
                    candidates.append(table_name)  # e.g., "2_loan"
                else:
                    # Otherwise, try prefixing it first (standard pattern)
                    candidates.append(f"{user_id}_{table_name}")  # e.g., "2_loan" from "loan"
                    # Then try the raw name (for shared tables or already-full names)
                    candidates.append(table_name)
                
                # Remove duplicates while preserving order
                candidates = list(dict.fromkeys(candidates))
                
                target_table = None
                for candidate in candidates:
                    if inspector.has_table(candidate):
                        target_table = candidate
                        break
                
                if not target_table:
                    print(f"Schema lookup failed. Checked: {candidates}")
                    return None
                    
                columns = []
                for col in inspector.get_columns(target_table):
                    columns.append({
                        "name": col['name'],
                        "type": str(col['type']),
                        "nullable": col['nullable']
                    })
                    
                return {"table_name": table_name, "columns": columns}

            return await asyncio.to_thread(_get_schema)
            
        except Exception as e:
            print(f"Error getting schema: {e}")
            return None

# Singleton instance
csv_agent_service = CsvAgentService()
