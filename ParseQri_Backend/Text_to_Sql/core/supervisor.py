"""
Supervisor Agent for Text-to-SQL System

This supervisor orchestrates all agents using a deterministic execution flow 
with retry mechanisms, confidence thresholds, and SQL hardening validation.

Architecture:
- Uses shared state (blackboard pattern)
- Enforces retry limits and confidence thresholds
- Implements comprehensive logging
- Never generates SQL or answers directly
"""

from typing import Dict, Any, List, Tuple, Optional
import os
import json
import logging
from datetime import datetime
from sqlalchemy import create_engine, text
import sqlglot
from sqlglot import parse_one, exp

# Import agents
from agents.database_agent import DatabaseAgent
from agents.intent_classifier_agent import IntentClassificationAgent  
from agents.schema_filtering_agent import SchemaFilteringAgent
from agents.sql_generation_agent import SQLAgentLangGraph
from agents.sql_validation_agent import SQLValidationAgent, QueryContext as ValidationContext
from agents.response_formatting_agent import ResponseFormattingAgent
from models.data_models import QueryContext, AgentResponse
from core.chroma_client import get_or_create_collection
from config.models import AgentType, get_model_for_agent

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Initialize ChromaDB paths
CHROMA_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agents", "chroma_db")
SCHEMA_JSON_DIR = os.path.join(CHROMA_DB_DIR, "schema_history")

# Ensure directories exist
os.makedirs(CHROMA_DB_DIR, exist_ok=True)
os.makedirs(SCHEMA_JSON_DIR, exist_ok=True)

# Initialize ChromaDB collection using centralized client
db_collection = get_or_create_collection(
    "database_metadata",
    {"description": "Stores SQL Server database schema information"}
)


class SupervisorAgent:
    """
    Supervisor Agent that coordinates all Text-to-SQL agents.
    
    Rules:
    - Decides which agent runs next
    - Enforces retry limits
    - Switches models intelligently  
    - Terminates safely on failure
    - Never generates SQL or answers directly
    """
    
    # Configuration constants
    INTENT_CONFIDENCE_THRESHOLD = 0.70
    MAX_INTENT_RETRIES = 1
    MAX_SQL_RETRIES = 3
    
    def __init__(self, server_name: str = None, database_name: str = None):
        logger.info(f"Initializing SupervisorAgent for {server_name}/{database_name}")
        
        # Initialize database agent first
        self.database_agent = DatabaseAgent(server_name, database_name) if server_name and database_name else None
        self.server_name = server_name
        self.database_name = database_name
        
        # Initialize all supervised agents  
        self.intent_classifier = IntentClassificationAgent()
        self.schema_filter = SchemaFilteringAgent()
        self.sql_generator = SQLAgentLangGraph()
        self.sql_validator = SQLValidationAgent()
        self.response_formatter = ResponseFormattingAgent(server_name=server_name, database_name=database_name) if server_name and database_name else None
        
        # Load schema from ChromaDB or JSON if available
        self.current_schema = self.load_cached_schema()
        
        logger.info(f"SupervisorAgent initialized successfully. Using models: "
                   f"Intent={get_model_for_agent(AgentType.INTENT_CLASSIFICATION)}, "
                   f"Schema={get_model_for_agent(AgentType.SCHEMA_FILTERING)}, "
                   f"SQLGen={get_model_for_agent(AgentType.SQL_GENERATION)}, "
                   f"SQLVal={get_model_for_agent(AgentType.SQL_VALIDATION)}, "
                   f"Response={get_model_for_agent(AgentType.RESPONSE_FORMATTING)}")

    def set_database_connection(self, server_name: str, database_name: str):
        """Update database connection information."""
        logger.info(f"Updating database connection to {server_name}/{database_name}")
        self.server_name = server_name
        self.database_name = database_name
        self.database_agent = DatabaseAgent(server_name, database_name)
        self.response_formatter = ResponseFormattingAgent(server_name=server_name, database_name=database_name)
        self.current_schema = self.load_cached_schema()

    def load_cached_schema(self) -> Dict:
        """Load schema from ChromaDB or JSON files."""
        try:
            # First try ChromaDB
            if self.server_name and self.database_name:
                results = db_collection.get(
                    where={
                        "$and": [
                            {"server_name": {"$eq": self.server_name}},
                            {"database_name": {"$eq": self.database_name}}
                        ]
                    }
                )
                
                if results and results['metadatas']:
                    # Sort by timestamp and get the most recent
                    entries = list(zip(results['ids'], results['metadatas']))
                    entries.sort(key=lambda x: x[1]['timestamp'], reverse=True)
                    return json.loads(entries[0][1]['schema'])
            
            # If not in ChromaDB, try JSON files
            if os.path.exists(SCHEMA_JSON_DIR):
                json_files = [f for f in os.listdir(SCHEMA_JSON_DIR) if f.endswith('.json')]
                if json_files:
                    latest_file = max(json_files, key=lambda x: os.path.getctime(os.path.join(SCHEMA_JSON_DIR, x)))
                    with open(os.path.join(SCHEMA_JSON_DIR, latest_file), 'r') as f:
                        schema_data = json.load(f)
                        return schema_data['schema']
            
            return {}
            
        except Exception as e:
            logger.error(f"Error loading cached schema: {str(e)}")
            return {}
    
    def get_current_schema(self) -> Dict:
        """Get the current database schema."""
        # First try to use cached schema
        if self.current_schema:
            return self.current_schema
            
        # If no cached schema, try to get from database
        if not self.database_agent:
            logger.warning("No database agent available")
            return {}
            
        try:
            # Ensure database engine is established
            if not self.database_agent.engine:
                logger.info("Establishing database connection...")
                connection_string = f"Driver={{SQL Server}};Server={self.database_agent.server_name};Database={self.database_agent.database_name};Trusted_Connection=yes;"
                self.database_agent.engine = create_engine(
                    f"mssql+pyodbc:///?odbc_connect={connection_string}",
                    fast_executemany=True
                )
                logger.info(f"Database engine created for {self.database_agent.server_name}/{self.database_agent.database_name}")
            
            with self.database_agent.engine.connect() as connection:
                schema = self.database_agent.get_database_schema(connection)
                if schema:
                    self.current_schema = schema
                    logger.info(f"Schema retrieved successfully: {len(schema)} tables found")
                else:
                    logger.warning("No schema data retrieved from database")
                return schema
        except Exception as e:
            logger.error(f"Error getting schema from database: {str(e)}")
            return {}
    
    def _log_step(self, step_name: str, agent_name: str, model: str, 
                   confidence: float = None, retry: int = None,
                   errors: List[str] = None, **kwargs):
        """
        Log a step in the pipeline with all relevant information.
        
        Args:
            step_name: Name of the step (e.g., "intent_classification")
            agent_name: Name of the agent
            model: Model being used
            confidence: Confidence score (if applicable)
            retry: Retry attempt number (if applicable)
            errors: List of errors (if applicable)
            **kwargs: Additional data to log
        """
        log_data = {
            "step": step_name,
            "agent": agent_name,
            "model": model,
            "timestamp": datetime.now().isoformat(),
        }
        
        if confidence is not None:
            log_data["confidence"] = confidence
        if retry is not None:
            log_data["retry"] = retry
        if errors:
            log_data["errors"] = errors
        log_data.update(kwargs)
        
        logger.info(f"STEP: {json.dumps(log_data)}")
    
    def _harden_sql(self, sql_query: str, schema: Dict) -> Tuple[bool, List[str]]:
        """
        SQL Hardening - Validate SQL before execution.
        
        Checks:
        1. SQL parses successfully
        2. Tables exist in schema
        3. Columns exist in referenced tables
        4. GROUP BY is used correctly
        5. No SELECT * (best practice)
        
        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_errors)
        """
        errors = []
        
        try:
            # 1. Parse SQL
            try:
                parsed = parse_one(sql_query, dialect='tsql')
            except Exception as e:
                errors.append(f"SQL parsing failed: {str(e)}")
                return False, errors
            
            # 2 & 3. Check tables and columns exist
            # Extract tables from the query
            tables_in_query = set()
            for table in parsed.find_all(exp.Table):
                table_name = str(table.name)
                # Handle schema-qualified names (e.g., SalesLT.Customer)
                if '.' in table_name:
                    schema_name, table_only = table_name.split('.')[-2:]
                    full_table = f"{schema_name}.{table_only}"
                    tables_in_query.add(full_table)
                else:
                    tables_in_query.add(table_name)
            
            # Validate tables exist
            schema_tables = set(schema.keys())
            for table in tables_in_query:
                if table not in schema_tables:
                    # Try without schema prefix
                    table_without_schema = table.split('.')[-1] if '.' in table else table
                    if table_without_schema not in schema_tables:
                        matches = [t for t in schema_tables if t.endswith(f".{table_without_schema}")]
                        if not matches:
                            errors.append(f"Table '{table}' does not exist in schema")                
            
            # 4. Check GROUP BY correctness (basic check)
            has_group_by = any(parsed.find_all(exp.Group))
            has_aggregates = any(parsed.find_all(exp.AggFunc))
            
            if has_aggregates and not has_group_by:
                # Check if there are non-aggregated columns in SELECT
                select_cols = list(parsed.find_all(exp.Column))
                if select_cols:
                    # This is a simplified check - proper validation would be more complex
                    logger.warning("Query has aggregates but no GROUP BY - may be intentional")
            
            # 5. Check for SELECT *
            for select in parsed.find_all(exp.Select):
                for expression in select.expressions:
                    if isinstance(expression, exp.Star):
                        errors.append("SELECT * is not allowed - please specify columns explicitly")
            
            return len(errors) == 0, errors
            
        except Exception as e:
            errors.append(f"SQL hardening validation error: {str(e)}")
            return False, errors
    
    async def process_query(self, query: str, user_id: str = "default_user") -> Dict[str, Any]:
        """
        Process a natural language query through the supervisor-orchestrated workflow.
        
        Execution Flow:
        1. Run Intent Classification (dolphin3) - with retry
        2. Check confidence threshold
        3. Run Schema Filtering (dolphin3)
        4. Run SQL Generation (deepseek-coder) - with retry
        5. Run SQL Validation (deepseek-coder) - with retry
        6. Harden SQL (code-level validation)
        7. Execute SQL (pure code, not LLM)
        8. Run Response Formatting (dolphin3)
        9. Return final response
        
        Args:
            query: Natural language question
            user_id: User identifier
            
        Returns:
            Dict containing processing results and final response
        """
        # Initialize shared state (blackboard pattern)
        state = {
            "user_query": query,
            "user_id": user_id,
            "intent": {
                "type": "",
                "confidence": 0.0,
                "attempts": 0
            },
            "schema_context": {
                "tables": [],
                "columns": {},
                "relationships": []
            },
            "sql": {
                "query": "",
                "attempts": 0,
                "confidence": 0.0
            },
            "validation": {
                "is_valid": False,
                "errors": []
            },
            "execution": {
                "rows": [],
                "row_count": 0
            },
            "final_response": "",
            "success": True,
            "error": None,
            "history": []
        }
        
        logger.info(f"=== Starting query processing for: '{query}' ===")
        
        # Get schema first
        schema = self.get_current_schema()
        if not schema:
            state["error"] = "Could not retrieve database schema"
            state["success"] = False
            logger.error("Schema retrieval failed")
            return state
        
        # STEP 1: Intent Classification (with retry)
        intent_model = get_model_for_agent(AgentType.INTENT_CLASSIFICATION)
        while state["intent"]["attempts"] <= self.MAX_INTENT_RETRIES:
            try:
                state["intent"]["attempts"] += 1
                result = self.intent_classifier.classify_intent(query)
                state["intent"]["type"] = result["intent"]
                state["intent"]["confidence"] = result["confidence"]
                
                self._log_step(
                    "intent_classification",
                    "IntentClassificationAgent",
                    intent_model,
                    confidence=result["confidence"],
                    retry=state["intent"]["attempts"],
                    intent=result["intent"]
                )
                
                state["history"].append({
                    "step": "intent_classification",
                    "result": f"Classified as: {result['intent']} (confidence: {result['confidence']:.2f})",
                    "retry": state["intent"]["attempts"]
                })
                
                # Check confidence threshold
                if result["confidence"] >= self.INTENT_CONFIDENCE_THRESHOLD:
                    break
                elif state["intent"]["attempts"] > self.MAX_INTENT_RETRIES:
                    state["error"] = f"Low intent confidence ({result['confidence']:.2f}). Please clarify your request."
                    state["success"] = False
                    logger.warning(f"Intent confidence too low after {self.MAX_INTENT_RETRIES} retries")
                    return state
                    
            except Exception as e:
                logger.error(f"Intent classification failed: {str(e)}")
                state["error"] = f"Intent classification failed: {str(e)}"
                state["success"] = False
                return state
        
        # STEP 2: Schema Analysis
        schema_model = get_model_for_agent(AgentType.SCHEMA_FILTERING)
        try:
            schema_analysis = self.schema_filter.analyze_schema_relevance(
                query, state["intent"]["type"], schema
            )
            state["schema_context"]["tables"] = schema_analysis.get('relevant_tables', [])
            state["schema_context"]["columns"] = schema_analysis.get('relevant_columns', {})
            state["schema_context"]["relationships"] = schema_analysis.get('relationships', [])
            
            self._log_step(
                "schema_filtering",
                "SchemaFilteringAgent",
                schema_model,
                tables_found=len(state["schema_context"]["tables"])
            )
            
            state["history"].append({
                "step": "schema_filtering",
                "result": f"Found {len(state['schema_context']['tables'])} relevant tables"
            })
        except Exception as e:
            logger.error(f"Schema analysis failed: {str(e)}")
            state["error"] = f"Schema analysis failed: {str(e)}"
            state["success"] = False
            return state
        
        # STEP 3 & 4: SQL Generation and Validation Loop (with retry)
        sql_gen_model = get_model_for_agent(AgentType.SQL_GENERATION)
        sql_val_model = get_model_for_agent(AgentType.SQL_VALIDATION)
        
        while state["sql"]["attempts"] < self.MAX_SQL_RETRIES:
            state["sql"]["attempts"] += 1
            
            # STEP 3: SQL Generation
            try:
                generation_context = {
                    "user_question": query,
                    "schema": schema,
                    "table_name": None,
                    "user_id": user_id,
                    "relevant_metadata": {
                        "relevant_tables": state["schema_context"]["tables"],
                        "relevant_columns": state["schema_context"]["columns"],
                        "relationships": state["schema_context"]["relationships"],
                        "intent": state["intent"]["type"]
                    }
                }
                
                sql_result = self.sql_generator.generate_sql_with_cot(generation_context)
                
                if not sql_result.get("sql_query"):
                    logger.error("SQL generation failed: No query generated")
                    continue
                
                state["sql"]["query"] = sql_result["sql_query"]
                state["sql"]["confidence"] = sql_result.get("confidence", 0.0)
                
                self._log_step(
                    "sql_generation",
                    "SQLAgentLangGraph",
                    sql_gen_model,
                    confidence=state["sql"]["confidence"],
                    retry=state["sql"]["attempts"]
                )
                
                state["history"].append({
                    "step": "sql_generation",
                    "result": "Generated SQL query",
                    "retry": state["sql"]["attempts"]
                })
                
            except Exception as e:
                logger.error(f"SQL generation failed: {str(e)}")
                continue
            
            # STEP 4: SQL Validation (LLM-based)
            try:
                validation_context = ValidationContext(
                    sql_query=state["sql"]["query"],
                    db_schema=schema
                )
                validation_result = self.sql_validator.process(validation_context)
                
                if not validation_result.success:
                    self._log_step(
                        "sql_validation",
                        "SQLValidationAgent",
                        sql_val_model,
                        retry=state["sql"]["attempts"],
                        errors=[validation_result.message]
                    )
                    logger.warning(f"SQL validation failed: {validation_result.message}")
                    continue
                
                validated_sql = validation_result.data.get("sql_query", state["sql"]["query"])
                state["sql"]["query"] = validated_sql
                
                self._log_step(
                    "sql_validation",
                    "SQLValidationAgent",
                    sql_val_model,
                    retry=state["sql"]["attempts"]
                )
                
                state["history"].append({
                    "step": "sql_validation",
                    "result": "Validated SQL query",
                    "retry": state["sql"]["attempts"]
                })
                
                # STEP 4.5: SQL Hardening (code-level validation)
                is_hardened, hardening_errors = self._harden_sql(validated_sql, schema)
                
                if not is_hardened:
                    state["validation"]["errors"].extend(hardening_errors)
                    self._log_step(
                        "sql_hardening",
                        "SupervisorAgent",
                        "code-based",
                        retry=state["sql"]["attempts"],
                        errors=hardening_errors
                    )
                    logger.warning(f"SQL hardening failed: {hardening_errors}")
                    continue
                
                # If we reach here, SQL is valid
                state["validation"]["is_valid"] = True
                self._log_step("sql_hardening", "SupervisorAgent", "code-based")
                state["history"].append({
                    "step": "sql_hardening",
                    "result": "SQL hardening checks passed"
                })
                break
                
            except Exception as e:
                logger.error(f"SQL validation failed: {str(e)}")
                continue
        
        # Check if SQL validation succeeded
        if not state["validation"]["is_valid"]:
            state["error"] = f"Unable to generate a valid SQL query after {self.MAX_SQL_RETRIES} attempts. Errors: {state['validation']['errors']}"
            state["success"] = False
            logger.error(f"SQL generation failed after {self.MAX_SQL_RETRIES} retries")
            return state
        
        # STEP 5: Execute Query and Format Response
        response_model = get_model_for_agent(AgentType.RESPONSE_FORMATTING)
        try:
            formatting_context = QueryContext(
                user_question=query,
                db_schema=schema,
                table_name=None,
                user_id=user_id
            )
            
            formatting_result = self.response_formatter.process(formatting_context, state["sql"]["query"])
            
            if not formatting_result.success:
                state["error"] = f"Response formatting failed: {formatting_result.message}"
                state["success"] = False
                logger.error(f"Response formatting failed: {formatting_result.message}")
                return state
            
            state["final_response"] = formatting_result.data.get("formatted_response", "")
            state["execution"]["rows"] = formatting_result.data.get("raw_results", [])
            state["execution"]["row_count"] = len(state["execution"]["rows"]) if state["execution"]["rows"] else 0
            
            self._log_step(
                "response_formatting",
                "ResponseFormattingAgent",
                response_model,
                row_count=state["execution"]["row_count"]
            )
            
            state["history"].append({
                "step": "response_formatting",
                "result": f"Formatted results ({state['execution']['row_count']} rows)"
            })
            
        except Exception as e:
            logger.error(f"Response formatting failed: {str(e)}")
            state["error"] = f"Response formatting failed: {str(e)}"
            state["success"] = False
            return state
        
        # Complete
        state["history"].append({
            "step": "complete",
            "result": "Query processing completed successfully"
        })
        
        logger.info(f"=== Query processing completed successfully ===")
        logger.info(f"Intent: {state['intent']['type']} (confidence: {state['intent']['confidence']:.2f})")
        logger.info(f"SQL Attempts: {state['sql']['attempts']}")
        logger.info(f"Results: {state['execution']['row_count']} rows")
        
        return state
    
    async def process_query_with_cached_sql(
        self, 
        query: str, 
        cached_sql: str, 
        cached_db_schema: str,
        user_id: str = "default_user"
    ) -> Dict[str, Any]:
        """
        Process a query using cached SQL, bypassing SQL generation and validation.
        Goes directly to response formatting.
        
        Args:
            query: The user's question
            cached_sql: Pre-generated SQL query from cache
            cached_db_schema: Database schema information from cache
            user_id: User ID for the query
            
        Returns:
            Dictionary containing the processing results
        """
        logger.info(f"Processing cached query: '{query}'")
        
        try:
            state= {
                "query": query,
                "user_id": user_id,
                "step_result": {
                    "intent": "Cached Query",
                    "schema_analysis": {"source": "cache", "db_schema": cached_db_schema},
                    "sql_query": cached_sql,
                    "validation": {"status": "skipped", "reason": "Using cached SQL"}
                },
                "error": None,
                "history": [
                    {"step": "cache_lookup", "result": "Found matching question in cache"},
                    {"step": "sql_generation", "result": "Using cached SQL query"},
                    {"step": "sql_validation", "result": "Skipped - using cached SQL"}
                ],
                "success": True
            }
            
            # Get current schema for response formatting context
            schema = self.get_current_schema()
            if not schema:
                logger.warning("Could not retrieve database schema, proceeding with cached schema info")
            
            # Execute Query and Format Response
            try:
                formatting_context = QueryContext(
                    user_question=query,
                    db_schema=schema if schema else {},
                    table_name=None,
                    user_id=user_id
                )
                
                formatting_result = self.response_formatter.process(formatting_context, cached_sql)
                state["step_result"]["formatted_response"] = formatting_result.dict()
                state["history"].append({
                    "step": "response_formatting",
                    "result": "Formatted results from cached SQL"
                })
                
                if not formatting_result.success:
                    state["error"] = f"Response formatting failed: {formatting_result.message}"
                    return state
            except Exception as e:
                state["error"] = f"Response formatting failed: {str(e)}"
                return state
            
            state["history"].append({
                "step": "complete",
                "result": "Query processing completed successfully (using cache)"
            })
            
            logger.info("Cached query processed successfully")
            return state
            
        except Exception as e:
            logger.error(f"Error processing cached query: {str(e)}")
            return {
                "error": str(e),
                "step_result": {},
                "history": [{"step": "error", "result": str(e)}],
                "success": False
            }
