"""
Integration service for Text-to-SQL functionality with the FastAPI backend
"""
import asyncio
import os
import sys
from typing import Dict, Any, Optional
from pathlib import Path

# Add the Text_to_Sql directory to the FRONT of sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
elif sys.path[0] != current_dir:
    # Ensure it's at position 0 so it takes priority
    sys.path.remove(current_dir)
    sys.path.insert(0, current_dir)

# Handle namespace collision for 'core' package
# The FastAPI app loads 'app.core' which registers 'core' in sys.modules,
# causing 'from core.supervisor import ...' to resolve to app/core/ instead
# of Text_to_Sql/core/. We must clear conflicting modules BEFORE importing
# and NOT restore them until all Text_to_Sql imports (including transitive
# ones like supervisor.py -> core.chroma_client) have fully completed.
import importlib

# Save and remove conflicting modules so Text_to_Sql/core takes priority
_saved_modules = {}
_conflicting_prefixes = ['core.', 'agents.', 'config.', 'utils.', 'models.']
_modules_to_clear = ['core', 'agents', 'config', 'utils', 'models']

for mod_name in list(sys.modules.keys()):
    for prefix in _conflicting_prefixes:
        if mod_name.startswith(prefix):
            _saved_modules[mod_name] = sys.modules.pop(mod_name)
            break
    else:
        if mod_name in _modules_to_clear and mod_name in sys.modules:
            _saved_modules[mod_name] = sys.modules.pop(mod_name)

# Now import from Text_to_Sql/core (sys.path[0] points here)
try:
    from core.supervisor import SupervisorAgent
    from main import TextToSQLSystem
    from core.cache_service import get_cache_service
except (ImportError, AttributeError, NameError) as e:
    print(f"Text-to-SQL: Import error after clearing namespace: {e}")
    import traceback
    traceback.print_exc()
    raise

# Capture the Text_to_Sql modules that were just loaded so we can preserve them
_text_to_sql_modules = {}
for mod_name in list(sys.modules.keys()):
    for prefix in _conflicting_prefixes:
        if mod_name.startswith(prefix):
            _text_to_sql_modules[mod_name] = sys.modules[mod_name]
            break
    else:
        if mod_name in _modules_to_clear and mod_name in sys.modules:
            _text_to_sql_modules[mod_name] = sys.modules[mod_name]

# Restore the saved app modules only if they don't collide with Text_to_Sql ones.
# The app uses fully-qualified imports (app.core.security, etc.) so it doesn't
# actually need bare 'core' in sys.modules. We only restore non-conflicting ones.
for mod_name, mod in _saved_modules.items():
    if mod_name not in _text_to_sql_modules:
        sys.modules[mod_name] = mod


class TextToSQLIntegrationService:
    """Service class to integrate Text-to-SQL with the backend API"""
    
    def __init__(self):
        self.systems = {}  # Cache of systems per database connection
    
    def get_or_create_system(self, server_name: str, database_name: str) -> TextToSQLSystem:
        """Get or create a Text-to-SQL system for the given database connection"""
        key = f"{server_name}_{database_name}"
        
        if key not in self.systems:
            self.systems[key] = TextToSQLSystem(server_name, database_name)
        
        return self.systems[key]
    
    async def process_query_for_database(
        self, 
        query: str, 
        server_name: str, 
        database_name: str,
        user_id: str = "default_user"
    ) -> Dict[str, Any]:
        """
        Process a natural language query for a specific database
        
        Args:
            query: Natural language query
            server_name: SQL Server name
            database_name: Database name
            user_id: User ID for the query
            
        Returns:
            Dictionary containing the processing results
        """
        try:
            print(f"Processing query for database: {server_name}/{database_name}")
            print(f"Query: {query}")
            
            # Check cache first
            cache_service = get_cache_service()
            cache_match = cache_service.find_match(query)
            
            if cache_match:
                print(f"Cache hit! Using cached SQL for question ID: {cache_match.get('id')}")
                # Get or create the system for this database
                system = self.get_or_create_system(server_name, database_name)
                print(f"System created/retrieved successfully")
                
                # Process with cached SQL (bypass SQL generation)
                result = await system.process_query_with_cached_sql(
                    query=query,
                    cached_sql=cache_match.get("sql", ""),
                    cached_db_schema=cache_match.get("db_schema", ""),
                    user_id=user_id
                )
                print(f"Query processing completed with cache. Success: {not result.get('error')}")
            else:
                print("No cache match found, proceeding with normal query processing...")
                # Get or create the system for this database
                system = self.get_or_create_system(server_name, database_name)
                print(f"System created/retrieved successfully")
                
                # Ensure the supervisor has the database connection
                if system.supervisor.database_agent:
                    print(f"Database agent available: {system.supervisor.database_agent.server_name}/{system.supervisor.database_agent.database_name}")
                else:
                    print("Warning: No database agent in supervisor")
                
                # Process the query normally
                print("Starting query processing...")
                result = await system.process_query(query)
                print(f"Query processing completed. Success: {not result.get('error')}")
            
            # Format the response for API consumption
            formatted_result = self._format_api_response(result, query)
            
            return formatted_result
            
        except Exception as e:
            print(f"Error in process_query_for_database: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "sql_query": "",
                "answer": f"Error processing query: {str(e)}",
                "data": [],
                "chart_type": "bar",
                "question": query
            }
    
    def _format_api_response(self, result: Dict[str, Any], original_query: str) -> Dict[str, Any]:
        """Format the supervisor result for API response"""
        try:
            if result.get("error"):
                return {
                    "success": False,
                    "error": result["error"],
                    "query": original_query,
                    "sql_query": "",
                    "answer": f"Error: {result['error']}",
                    "data": [],
                    "chart_type": "bar",
                    "question": original_query
                }
            
            # Supervisor uses a different state structure
            # Extract SQL query from supervisor state
            sql_query = result.get("sql", {}).get("query", "")
            
            # If not found, check in step_result (used by cached queries)
            if not sql_query:
                step_result = result.get("step_result", {})
                sql_query = step_result.get("sql_query", "")
            
            # Extract formatted response from supervisor state
            # Check multiple possible locations for the answer
            answer = result.get("final_response")
            
            # If not found, check in step_result.formatted_response (used by cached queries)
            if not answer:
                step_result = result.get("step_result", {})
                formatted_response = step_result.get("formatted_response", {})
                
                # AgentResponse stores data in .data.formatted_response
                if hasattr(formatted_response, 'data'):
                    answer = formatted_response.data.get("formatted_response") if formatted_response.data else None
                elif isinstance(formatted_response, dict):
                    # Check if it's a dict with data key
                    data = formatted_response.get("data", {})
                    if isinstance(data, dict):
                        answer = data.get("formatted_response")
            
            # Default message if still no answer found
            if not answer:
                answer = "Query processed successfully"
            
            # Extract raw results from supervisor state
            raw_results = result.get("execution", {}).get("rows", [])
            
            # If not found, check in step_result.formatted_response (used by cached queries)
            if not raw_results:
                step_result = result.get("step_result", {})
                formatted_response = step_result.get("formatted_response", {})
                
                # AgentResponse stores data in .data.raw_results
                if hasattr(formatted_response, 'data') and formatted_response.data:
                    raw_results = formatted_response.data.get("raw_results", [])
                elif isinstance(formatted_response, dict):
                    data = formatted_response.get("data", {})
                    if isinstance(data, dict):
                        raw_results = data.get("raw_results", [])
            
            # Convert raw results to simple data format for visualization
            data = []
            if raw_results and isinstance(raw_results, list):
                # Try to convert results to visualization format
                try:
                    # If results are tuples/lists, convert first 10 items
                    for i, row in enumerate(raw_results[:10]):
                        if isinstance(row, (tuple, list)) and len(row) > 0:
                            data.append({
                                "name": str(row[0]) if len(row) > 0 else f"Item {i+1}",
                                "value": float(row[1]) if len(row) > 1 and isinstance(row[1], (int, float)) else len(str(row))
                            })
                        elif isinstance(row, dict):
                            # If row is a dict, use first key-value pair
                            keys = list(row.keys())
                            if len(keys) >= 2:
                                data.append({
                                    "name": str(row[keys[0]]),
                                    "value": float(row[keys[1]]) if isinstance(row[keys[1]], (int, float)) else len(str(row[keys[1]]))
                                })
                except Exception as e:
                    print(f"Warning: Could not format data for visualization: {str(e)}")
                    data = []
            
            return {
                "success": True,
                "query": original_query,
                "sql_query": sql_query,
                "answer": answer,
                "data": data,
                "chart_type": "bar",
                "question": original_query,
                "processing_steps": {
                    "intent": result.get("intent", {}).get("type", ""),
                    "intent_confidence": result.get("intent", {}).get("confidence", 0.0),
                    "schema_tables": result.get("schema_context", {}).get("tables", []),
                    "sql_attempts": result.get("sql", {}).get("attempts", 0),
                    "validation_errors": result.get("validation", {}).get("errors", []),
                    "row_count": result.get("execution", {}).get("row_count", 0)
                }
            }
            
        except Exception as e:
            print(f"Error in _format_api_response: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": f"Error formatting response: {str(e)}",
                "query": original_query,
                "sql_query": "",
                "answer": f"Error formatting response: {str(e)}",
                "data": [],
                "chart_type": "bar",
                "question": original_query
            }


# Global instance
text_to_sql_service = TextToSQLIntegrationService()


async def process_text_to_sql_query(
    query: str,
    server_name: str,
    database_name: str,
    user_id: str = "default_user"
) -> Dict[str, Any]:
    """
    Main function to process text-to-SQL queries
    This is the function that should be called from the FastAPI backend
    """
    return await text_to_sql_service.process_query_for_database(
        query=query,
        server_name=server_name,
        database_name=database_name,
        user_id=user_id
    )


if __name__ == "__main__":
    # Test the integration service
    async def test():
        result = await process_text_to_sql_query(
            "How many compressors are fitted onboard?",
            "C2C-LP-25-012",
            "INSMA"
        )
        print("Result:", result)
    
    asyncio.run(test())
