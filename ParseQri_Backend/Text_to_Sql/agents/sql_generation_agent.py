import os
import re
import requests
import sys
from typing import Dict, Any, Optional

from dotenv import load_dotenv
from models.data_models import QueryContext, AgentResponse
from langgraph.graph import StateGraph, START, END

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.models import AgentType, get_config_for_agent

# Load environment variables
load_dotenv()


class SQLAgentLangGraph:
    """SQL Generation Agent using Ollama with deepseek-coder model."""

    def __init__(self, max_retries=3):
        # Load model configuration from centralized config
        config = get_config_for_agent(AgentType.SQL_GENERATION)
        self.model_name = config["model_name"]
        self.context_window = config["context_window"]
        self.api_url = config["api_url"]
        self.max_retries = max_retries
        
        # Comment out original Gemini initialization
        # self.gemini_api_key = os.getenv("GOOGLE_API_KEY")
        # if not self.gemini_api_key:
        #     raise ValueError("Gemini API key not found in environment variables")
        # genai.configure(api_key=self.gemini_api_key)
        # self.model = genai.GenerativeModel(model_name=model_name)

    def validate_input(self, state):
        """Validate input for SQL generation"""
        user_id = state.get("user_id")
        schema = state.get("schema") or state.get("db_schema")
        if not user_id:
            state["validation_error"] = "User ID is required for SQL generation."
            state["valid"] = False
            return state
        if not schema:
            state["validation_error"] = "Schema information is required for SQL generation."
            state["valid"] = False
            return state
        state["valid"] = True
        return state

    def generate_sql_with_cot(self, state) -> Dict[str, Any]:
        """Generate SQL with chain of thought"""
        try:
            result = self._generate_sql_with_cot_impl(
                user_question=state.get("user_question"),
                schema=state.get("schema", state.get("db_schema", {})),
                table_name=state.get("table_name"),
                user_id=state.get("user_id", "default_user"),
                relevant_metadata=state.get("relevant_metadata")
            )
            
            # Add confidence score based on whether SQL was generated
            if result.get("sql_query"):
                result["confidence"] = 0.9  # High confidence if SQL generated
            else:
                result["confidence"] = 0.0
                
            return result
        except Exception as e:
            return {"sql_query": None, "error": str(e), "confidence": 0.0}

    def _generate_sql_with_cot_impl(
        self,
        user_question: str,
        schema: Dict[str, Dict[str, str]],
        table_name: Optional[str],
        user_id: str,
        relevant_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        # Get filtered schema info from schema_filtering_agent
        schema_info = ""
        if relevant_metadata and "relevant_tables" in relevant_metadata:
            for table in relevant_metadata["relevant_tables"]:
                if table in schema:
                    schema_info += f"Table: {table}\n"
                    if "relevant_columns" in relevant_metadata and table in relevant_metadata["relevant_columns"]:
                        columns = relevant_metadata["relevant_columns"][table]
                        for col in columns:
                            schema_info += f"- {col}\n"
                    schema_info += "\n"
        else:
            # Fallback to full schema if no filtering
            for table, info in schema.items():
                schema_info += f"Table: {table}\n"
                for col, dtype in info.items():
                    schema_info += f"- {col}: {dtype}\n"
                schema_info += "\n"

        # Add relationships info
        relationships_info = ""
        if relevant_metadata and "relationships" in relevant_metadata:
            relationships_info = "Relationships:\n"
            for rel in relevant_metadata["relationships"]:
                relationships_info += f"- {rel['from_table']}.{rel['from_column']} references {rel['to_table']}.{rel['to_column']}\n"

        # Get intent from intent_classifier_agent
        query_intent = relevant_metadata.get("intent", "Data Retrieval Intent") if relevant_metadata else "Data Retrieval Intent"

        prompt = f"""You are an expert SQL Server query generator. Generate a precise SQL query following these strict rules:

1. ONLY use column names that exist in the schema
2. NEVER include explanatory text as part of the SELECT clause
3. Use proper SQL Server syntax
4. ALWAYS use the EXACT table names as shown in the schema, including schema prefixes (e.g., if the schema shows 'SalesLT.SalesOrderDetail', you MUST use 'SalesLT.SalesOrderDetail', NOT just 'SalesOrderDetail')
5. Use table aliases for clarity
6. Always qualify column names with table aliases
7. Put each major clause (SELECT, FROM, WHERE, etc.) on a new line
8. Use proper JOINS instead of WHERE clause joins

CRITICAL AGGREGATION RULES:
- If the user asks for "total", "sum", "how many", "count", "average", or similar aggregation terms, you MUST use aggregate functions (SUM, COUNT, AVG, etc.)
- When using aggregate functions, return ONLY the aggregated result, NOT individual rows
- Examples:
  * "total number of X" → SELECT SUM(column) AS Total
  * "how many X" → SELECT COUNT(*) AS Count
  * "average of X" → SELECT AVG(column) AS Average
  * "total quantity for product 123" → SELECT SUM(OrderQty) AS TotalQuantity WHERE ProductID = 123
- Do NOT return individual rows when user asks for aggregated data

CRITICAL SCHEMA USAGE RULES:
- The schema shows table names EXACTLY as they exist in the database
- Use table names EXACTLY as shown in the schema below - do NOT add or remove any prefixes
- If a table is listed as "SalesLT.Customer", use "SalesLT.Customer"
- If a table is listed as "T_Equipment", use "T_Equipment" (no prefix)
- If a table is listed as "dbo.Users", use "dbo.Users"
- NEVER assume a schema prefix - always use the EXACT table name from the schema

USER QUESTION: "{user_question}"
QUERY INTENT: {query_intent}

AVAILABLE SCHEMA:
{schema_info}
{relationships_info}

Let's solve this step by step:

1) First, identify what type of query this is:
   Thought: Does the user want aggregated data (total/sum/count/average) or individual records?
   Action: Check for aggregation keywords in the question
   Output: Determine if we need aggregate functions

2) Identify the exact columns we need from the schema:
   Thought: Match user requirements to actual column names from the schema above
   Action: List only existing columns from the schema
   Output: Specific column names with their tables

3) Identify the tables and joins:
   Thought: Which tables have our required columns?
   Action: List tables - USE EXACT TABLE NAMES AS SHOWN IN SCHEMA (with any prefixes they have)
   Output: FROM clause with proper JOINs using EXACT table names from schema

4) Build the WHERE clause:
   Thought: What conditions do we need?
   Action: Translate filters to SQL using proper aliases
   Output: WHERE conditions using proper column names

5) Determine aggregation and GROUP BY:
   Thought: Do we need aggregate functions? Do we need GROUP BY?
   Action: Add SUM/COUNT/AVG if user asks for totals/counts/averages
   Output: Proper SELECT with aggregation functions if needed

6) Final query construction:
   Thought: Assemble the query with proper syntax
   Action: Write the complete SQL query using EXACT table names from schema
   Output: The SQL query using EXACT table names as shown above

Based on the above analysis, here's the SQL Server query:

"""

        # Generate the SQL with CoT using Ollama
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_ctx": self.context_window
            }
        }
        
        try:
            response = requests.post(self.api_url, json=payload)
            if response.status_code == 200:
                sql_raw = response.json()["response"].strip()
                
                # Extract the final SQL query from the CoT response
                sql_lines = sql_raw.split('\n')
                sql_query = ""
                capture_sql = False
                
                for line in sql_lines:
                    if line.strip().upper().startswith("SELECT"):
                        capture_sql = True
                    if capture_sql:
                        sql_query += line + "\n"
                        
                sql_query = sql_query if sql_query else self._extract_sql_from_response(sql_raw)
                sql_query = self.sanitize_sql_query(sql_query)
                return {"sql_query": sql_query}
            else:
                raise Exception(f"Ollama API request failed with status code: {response.status_code}")
        except Exception as e:
            print(f"Error generating SQL with Ollama: {str(e)}")
            return {"sql_query": None, "error": str(e)}

    def _extract_sql_from_response(self, response: str) -> str:
        if "```sql" in response:
            start_idx = response.find("```sql") + 6
            end_idx = response.find("```", start_idx)
            sql = response[start_idx:end_idx].strip()
        elif "```" in response:
            start_idx = response.find("```") + 3
            end_idx = response.find("```", start_idx)
            sql = response[start_idx:end_idx].strip()
        else:
            sql = response.strip()
        return sql

    def sanitize_sql_query(self, sql_query: str) -> str:
        sql_query = sql_query.replace('`', '')
        sql_query = re.sub(r'```sql|```', '', sql_query).strip()
        sql_query = re.sub(r'[；｜;]+', ';', sql_query)
        sql_query = re.sub(r';;+', ';', sql_query)
        match = re.search(r"(SELECT .*?;)", sql_query, re.DOTALL | re.IGNORECASE)
        if match:
            sql_query = match.group(1).strip()
        sql_query = sql_query.rstrip(';') + ';'
        ascii_query = ''.join(c for c in sql_query if ord(c) < 128)
        return ascii_query if ascii_query else sql_query


class SQLGenerationAgentGraph:
    def __init__(self, agent: SQLAgentLangGraph):
        self.agent = agent
        
        # Create the graph
        self.graph = StateGraph(dict)
        self.graph.add_node("validate_input", self.agent.validate_input)
        self.graph.add_node("generate_sql", self.agent.generate_sql_with_cot)
        
        # Connect nodes
        self.graph.add_edge(START, "validate_input")
        self.graph.add_edge("validate_input", "generate_sql")
        self.graph.add_edge("generate_sql", END)
        
        # Compile the graph
        self.app = self.graph.compile()

    def run(self, context: QueryContext) -> AgentResponse:
        state = {
            "user_question": context.user_question,
            "schema": context.db_schema,
            "table_name": context.table_name,
            "user_id": context.user_id,
            "relevant_metadata": getattr(context, "relevant_metadata", None)
        }

        result = self.app.invoke(state)

        if result.get("validation_error"):
            return AgentResponse(success=False, message=result.get("validation_error"))

        if result.get("sql_generation_error"):
            return AgentResponse(success=False, message=result.get("sql_generation_error"))

        sql_query = result.get("sql_query", "")
        return AgentResponse(success=True, message="SQL generated successfully", data={"sql_query": sql_query})
