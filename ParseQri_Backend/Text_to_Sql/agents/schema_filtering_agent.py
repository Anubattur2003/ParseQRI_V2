import os
import sys
import requests
from typing import Dict, List, Optional
from dotenv import load_dotenv
import json
from datetime import datetime
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

# Add the parent directory to the path so we can import from core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.models import AgentType, get_config_for_agent
from core.chroma_client import get_or_create_collection

# Load environment variables
load_dotenv()

# Comment out Google API configuration
# GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# if not GOOGLE_API_KEY:
#     print("Warning: GOOGLE_API_KEY not found. Using placeholder for schema filtering.")
#     GOOGLE_API_KEY = "placeholder_api_key"
# try:
#     genai.configure(api_key=GOOGLE_API_KEY)
# except Exception as e:
#     print(f"Warning: Failed to configure Google AI: {str(e)}")

# Initialize ChromaDB
CHROMA_DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")
SCHEMA_JSON_DIR = os.path.join(CHROMA_DB_DIR, "schema_history")

# Initialize ChromaDB collection using centralized client
db_collection = get_or_create_collection(
    "embedding_metadata",
    {"description": "Stores SQL Server database schema information"}
)

class SchemaFilteringAgent:
    def __init__(self):
        # Load model configuration from centralized config
        config = get_config_for_agent(AgentType.SCHEMA_FILTERING)
        self.model_name = config["model_name"]
        self.context_window = config["context_window"]
        self.api_url = config["api_url"]
        
    def load_schema_metadata(self, server_name: str, database_name: str) -> Dict:
        """Load the most recent schema metadata from ChromaDB or JSON files"""
        try:
            # First try ChromaDB
            results = db_collection.get(
                where={
                    "$and": [
                        {"server_name": {"$eq": server_name}},
                        {"database_name": {"$eq": database_name}}
                    ]
                }
            )
            
            if results and results['metadatas']:
                # Sort by timestamp and get the most recent
                entries = list(zip(results['ids'], results['metadatas']))
                entries.sort(key=lambda x: x[1]['timestamp'], reverse=True)
                return json.loads(entries[0][1]['schema'])
            
            # If not in ChromaDB, try JSON files
            json_files = [f for f in os.listdir(SCHEMA_JSON_DIR) if f.endswith('.json')]
            if not json_files:
                raise FileNotFoundError("No schema history files found")
                
            latest_file = max(json_files, key=lambda x: os.path.getctime(os.path.join(SCHEMA_JSON_DIR, x)))
            with open(os.path.join(SCHEMA_JSON_DIR, latest_file), 'r') as f:
                schema_data = json.load(f)
                return schema_data['schema']
                
        except Exception as e:
            print(f"Error loading schema metadata: {str(e)}")
            return {}

    def analyze_schema_relevance(self, query: str, intent: str, schema: Dict) -> Dict:
        """Use ReAct prompting to analyze schema relevance to the query"""
        
        react_prompt = f"""You are a Schema Analysis Agent that helps identify relevant database objects for user queries.
        Your task is to analyze the query and schema to find the most relevant tables, columns, and relationships.

        SCHEMA INFORMATION:
        {json.dumps(schema, indent=2)}

        USER QUERY: {query}
        QUERY INTENT: {intent}

        CRITICAL INSTRUCTION FOR TABLE NAMES:
        - When listing tables in your output, you MUST use the EXACT table names as they appear in the schema above
        - If a table is named "dbo.M_Equipment" in the schema, you MUST write "dbo.M_Equipment" in your output
        - If a table is named "SalesLT.Customer" in the schema, you MUST write "SalesLT.Customer" in your output  
        - DO NOT remove schema prefixes (like "dbo.", "SalesLT.")
        - DO NOT shorten table names (e.g., don't change "M_Equipment" to "Equipment")
        - DO NOT invent table names that don't exist in the schema

        Use the following ReAct format to analyze step by step:

        Thought: Think about what information we need to find
        Action: Identify relevant tables
        Observation: List tables that could contain relevant data
        
        Thought: Consider which columns are needed
        Action: Analyze column relevance
        Observation: List relevant columns from identified tables
        
        Thought: Check for relationships
        Action: Find related tables through foreign keys
        Observation: Document any important relationships
        
        Thought: Finalize the analysis
        Action: Summarize findings
        Output: Return a JSON with the following structure:
        {{
            "relevant_tables": ["table1", "table2"],
            "relevant_columns": {{"table1": ["col1", "col2"], "table2": ["col1", "col2"]}},
            "relationships": [
                {{"from_table": "table1", "from_column": "col1", "to_table": "table2", "to_column": "col2"}}
            ],
            "reasoning": "Brief explanation of why these are relevant"
        }}

        Begin your analysis:
        """

        try:
            # Use Ollama API with context window configuration
            payload = {
                "model": self.model_name,
                "prompt": react_prompt,
                "stream": False,
                "options": {
                    "num_ctx": self.context_window
                }
            }
            response = requests.post(self.api_url, json=payload)
            
            if response.status_code == 200:
                output_text = response.json()["response"]
                # Extract the JSON output from the response
                json_start = output_text.find('{')
                json_end = output_text.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    result = json.loads(output_text[json_start:json_end])
                    return result
            return {}
        except Exception as e:
            print(f"Error in schema analysis: {str(e)}")
            return {}

def schema_filtering_node(state):
    """LangGraph node for schema filtering"""
    try:
        agent = SchemaFilteringAgent()
        
        # Extract required information from state
        server_name = state.get("server_name")
        database_name = state.get("database_name")
        user_question = state.get("user_question")
        intent = state.get("intent")
        
        if not all([server_name, database_name, user_question, intent]):
            return {
                "success": False,
                "message": "Missing required information",
                "schema_metadata": {}
            }
        
        # Load schema metadata
        schema = agent.load_schema_metadata(server_name, database_name)
        if not schema:
            return {
                "success": False,
                "message": "Failed to load schema metadata",
                "schema_metadata": {}
            }
            
        # Analyze schema relevance
        analysis = agent.analyze_schema_relevance(user_question, intent, schema)
        
        return {
            "success": True,
            "message": "Schema analysis completed",
            "schema_metadata": analysis
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Error in schema filtering: {str(e)}",
            "schema_metadata": {}
        }

# === LangGraph Setup ===
graph = StateGraph(dict)

# Add nodes
graph.add_node("schema_filtering", schema_filtering_node)

# Add edges
graph.add_edge(START, "schema_filtering")
graph.add_edge("schema_filtering", END)

# Compile the graph
app = graph.compile()