import os
import sys
import requests
from dotenv import load_dotenv
from typing import Dict, Any, Optional, TypedDict, Annotated
import pandas as pd
from langgraph.graph import StateGraph, START, END
from models.data_models import QueryContext, AgentResponse
from sqlalchemy import create_engine, text

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.models import AgentType, get_config_for_agent

# Load environment variables
load_dotenv()

# Comment out Google API configuration
# api_key = os.getenv("GOOGLE_API_KEY")
# if not api_key:
#     print("Warning: GOOGLE_API_KEY not found. Text-to-SQL functionality may be limited.")
#     print("Please set GOOGLE_API_KEY environment variable for full functionality.")
#     api_key = "placeholder_api_key"
# try:
#     genai.configure(api_key=api_key)
# except Exception as e:
#     print(f"Warning: Failed to configure Google AI: {str(e)}")
#     print("Some Text-to-SQL features may not work properly.")

class State(TypedDict):
    """State for the response formatting workflow."""
    context: QueryContext
    sql_query: str
    query_results: Optional[pd.DataFrame]
    formatted_response: Optional[str]
    error: Optional[str]
    success: bool

class ResponseFormattingAgent:
    """
    Agent responsible for executing SQL queries and formatting results into natural language responses.
    Uses SQL Server for query execution and Gemini Pro for response formatting.
    """

    def __init__(self, server_name: str, database_name: str):
        """Initialize the Response Formatting Agent."""
        # Load model configuration from centralized config
        config = get_config_for_agent(AgentType.RESPONSE_FORMATTING)
        self.model_name = config["model_name"]
        self.context_window = config["context_window"]
        self.api_url = config["api_url"]
    
        self.server_name = server_name
        self.database_name = database_name
        self.connection_string = f"Driver={{SQL Server}};Server={server_name};Database={database_name};Trusted_Connection=yes;"
        self.engine = create_engine(
            f"mssql+pyodbc:///?odbc_connect={self.connection_string}",
            fast_executemany=True
        )
        self.setup_graph()
    
    def setup_graph(self):
        """Set up the LangGraph workflow."""
        self.graph = StateGraph(State)
    
        # Add nodes
        self.graph.add_node("execute_query", self._execute_query_node)
        self.graph.add_node("format_results", self._format_results_node)
    
        # Add edges
        self.graph.add_edge(START, "execute_query")
        self.graph.add_edge("execute_query", "format_results")
        self.graph.add_edge("format_results", END)
    
        # Compile the graph
        self.workflow = self.graph.compile()
    
    def _execute_query_node(self, state: State) -> State:
        """Execute the SQL query and store results in state."""
        try:
            sql_query = state.get("sql_query")
            if not sql_query:
                state["error"] = "No SQL query provided"
                state["success"] = False
                return state
    
            try:
                # Execute query directly using SQLAlchemy engine
                with self.engine.connect() as connection:
                    result = connection.execute(text(sql_query))
                    # Convert result to DataFrame
                    results = pd.DataFrame(result.fetchall(), columns=result.keys())
                    state["query_results"] = results
                    state["success"] = True
            except Exception as e:
                state["error"] = f"Failed to execute query: {str(e)}"
                state["success"] = False
    
            return state
    
        except Exception as e:
            state["error"] = f"Error executing query: {str(e)}"
            state["success"] = False
            return state
    
    def _format_results_node(self, state: State) -> State:
        """Format the query results using the LLM."""
        try:
            if not state.get("success"):
                return state
                
            results = state.get("query_results")
            context = state.get("context")

            if results is None or results.empty:
                # Create formatting prompt for no results case
                no_results_prompt = f"""You are an expert Microsoft SQL Server (MSSQL) database analyst. The user asked a question but no results were found or the query returned empty results.

                Original Question: {context.user_question}

                Requirements:
                1. Start with a direct, clear answer explaining that you couldn't find the information
                2. Format the response using Markdown:
                - Use ## for main sections
                - Use **bold** for key points
                - Use bullet points for suggestions
                3. Clearly state that you didn't understand the specific term or concept being searched for
                4. Provide helpful suggestions on how the user might rephrase their question
                5. Avoid technical SQL syntax or jargon

                Please provide a formatted response explaining that no results were found and you may not have understood the main keyword/search term in their question:"""
           
                # Get formatted response from Ollama
                payload = {
                    "model": self.model_name,
                    "prompt": no_results_prompt,
                    "stream": False,
                    "options": {
                        "num_ctx": self.context_window
                    }
                }
                response = requests.post(self.api_url, json=payload)
                if response.status_code == 200:
                    state["formatted_response"] = response.json()["response"]
                else:
                    state["error"] = f"Failed to get response from Ollama: {response.status_code}"
                    state["success"] = False
                return state
            
            # Convert results to a readable format
            results_str = results.to_json(orient='records', indent=2)
            
            # Create the formatting prompt
            formatting_prompt = f"""You are an expert Microsoft SQL Server (MSSQL) database analyst specializing in presenting query results 
in clear, accurate format. Your task is to present these MSSQL query results in response to the user's question:

Original Question: {context.user_question}

Query Results (Total Rows: {len(results)}):
{results_str}

CRITICAL REQUIREMENTS:
1. **BE FAITHFUL TO THE DATA**: Show the ACTUAL results from the query - do NOT summarize, categorize, or truncate
2. **LIST QUERIES**: If the user asks for "all X" or "show me X" or "list X", you MUST show ALL the results, not a summary
   - Show each item from the results
   - Do NOT say "here are some examples" or "including X, Y, Z" - show EVERYTHING
   - Do NOT categorize the results into groups unless specifically asked
3. **COUNT QUERIES**: If the results show a count/total, present the exact number
4. **AGGREGATION QUERIES**: If showing sums, averages, maxes - present the exact values

FORMATTING GUIDELINES:
- Use Markdown formatting:
  * Use ## for main sections
  * Use **bold** for key metrics  
  * Use bullet points (- ) for lists of items
  * Use tables for structured comparisons
  * Use `code` for specific values
- Format numbers appropriately (currency, percentages)
- Start with a direct answer
- If there are 100+ items, present them all in a clear list format
- Avoid SQL terminology - use plain language

CRITICAL: You MUST extract and display the ACTUAL values from the Query Results JSON above.
Do NOT use placeholder text like "Ship 1", "Ship 2", "Item 1", "Item 2", etc.
Look at the actual field values in the JSON data and list those exact values.

For example, if the JSON contains: [{{"ShipName": "Pacific Explorer"}}, {{"ShipName": "Atlantic Voyager"}}]
You should output:
- Pacific Explorer
- Atlantic Voyager

NOT:
- Ship 1
- Ship 2

Please provide your formatted response using the REAL data values from the Query Results above:"""

            # Get response from Ollama
            payload = {
                "model": self.model_name,
                "prompt": formatting_prompt,
                "stream": False,
                "options": {
                    "num_ctx": self.context_window
                }
            }
            response = requests.post(self.api_url, json=payload)
            if response.status_code == 200:
                state["formatted_response"] = response.json()["response"]
            else:
                state["error"] = f"Failed to get response from Ollama: {response.status_code}"
                state["success"] = False
            return state
            
        except Exception as e:
            state["error"] = f"Error formatting results: {str(e)}"
            state["success"] = False
            return state
    
    def process(self, context: QueryContext, sql_query: str) -> AgentResponse:
        """Process the query context through execution and formatting."""
        try:
            # Initialize state
            initial_state = {
                "context": context,
                "sql_query": sql_query,
                "query_results": None,
                "formatted_response": None,
                "error": None,
                "success": True
            }
            
            # Run the workflow
            final_state = self.workflow.invoke(initial_state)
            
            # Check for errors
            if not final_state.get("success"):
                return AgentResponse(
                    success=False,
                    message=final_state.get("error", "Unknown error occurred")
                )
            
            # Convert query results to raw_results format (list of dicts) for visualization
            raw_results = None
            query_results = final_state.get("query_results")
            if query_results is not None and not query_results.empty:
                # Convert DataFrame to list of dictionaries
                raw_results = query_results.to_dict(orient='records')
            
            # Return successful response
            return AgentResponse(
                success=True,
                message="Query executed and results formatted successfully",
                data={
                    "formatted_response": final_state.get("formatted_response") if query_results is not None else None,
                    "raw_results": raw_results
                }
            )
            
        except Exception as e:
            return AgentResponse(
                success=False,
                message=f"Error in response formatting: {str(e)}"
            )