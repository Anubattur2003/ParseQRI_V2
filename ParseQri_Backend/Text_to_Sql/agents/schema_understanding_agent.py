from typing import Dict, List, Any, Optional, Union
import pandas as pd
import json
from collections import defaultdict
from sqlalchemy import create_engine, inspect
import os
import chromadb
from dotenv import load_dotenv
from urllib.parse import quote_plus

from langgraph.graph import StateGraph, START, END
import requests

# --- Load .env and DB config ---
load_dotenv()
driver = os.getenv("DB_DRIVER")
server = os.getenv("DB_SERVER")
database = os.getenv("DB_DATABASE")
trusted_connection = os.getenv("DB_TRUSTED_CONNECTION")

connection_string = (
    f"DRIVER={{{driver}}};"
    f"SERVER={server};"
    f"DATABASE={database};"
    f"Trusted_Connection={trusted_connection};"
)
encoded_connection = quote_plus(connection_string)
SQL_SERVER_ODBC_URL = f"mssql+pyodbc:///?odbc_connect={encoded_connection}"

# Helper: Default user
def _default_user() -> str:
    storage_dir = os.path.join("..", "data", "db_storage")
    if not os.path.exists(storage_dir):
        return "default_user"
    users = [d for d in os.listdir(storage_dir) if os.path.isdir(os.path.join(storage_dir, d))]
    return users[0] if users else "default_user"

# Helper: Get user tables
def _get_user_tables(engine, user_id: str) -> List[str]:
    insp = inspect(engine)
    return [t for t in insp.get_table_names() if t.endswith(f"_{user_id}")]

# Helper: Semantic search for relevant table
def _find_relevant_table(user_id: str, question: str) -> Optional[str]:
    # Import here to avoid circular imports
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core.chroma_client import get_or_create_collection
    
    try:
        coll = get_or_create_collection(f"{user_id}_metadata")
    except Exception:
        return None
    res = coll.query(query_texts=[question], n_results=1, where={"user_id": user_id})
    if not res["ids"][0]:
        return None
    raw = res["metadatas"][0][0].get("table_name", "")
    return raw.split("_")[0] if "_" in raw else raw

# Helper: Detect relationships
def _detect_relationships(df: pd.DataFrame) -> Dict[str, List[str]]:
    rel = {}
    for c1 in df.columns:
        for c2 in df.columns:
            if c1 != c2 and df[c1].dropna().isin(df[c2].dropna()).all():
                rel.setdefault(c1, []).append(c2)
    return rel

class CombinedSchemaAgent:
    def __init__(self, llm_model="llama3:8b", api_base=None):
        self.schema_info: Dict[str, Any] = {}
        self.previous_thoughts: List[str] = []
        self.api_base = api_base or "http://localhost:11434/api/generate"
        self.engine = create_engine(SQL_SERVER_ODBC_URL)
        self.metadata: Dict[str, Any] = {}
        self.model_name = llm_model
        
        # Comment out original Gemini initialization
        # api_key = os.getenv("GOOGLE_API_KEY")
        # if not api_key:
        #     raise ValueError("Google API key not found in environment variables")
        # genai.configure(api_key=api_key)
        # self.model = genai.GenerativeModel(llm_model)

    def _extract_schema_from_db(self, user_id: Optional[str] = None, user_question: Optional[str] = None) -> Dict[str, Any]:
        insp = inspect(self.engine)
        schema = defaultdict(dict)
        table_names = []
        if user_id and user_question:
            relevant_table = _find_relevant_table(user_id, user_question)
            if relevant_table:
                matching_tables = [t for t in insp.get_table_names() if t.startswith(relevant_table) and t.endswith(f"_{user_id}")]
                if matching_tables:
                    table_names = matching_tables
            else:
                table_names = _get_user_tables(self.engine, user_id)
        else:
            table_names = insp.get_table_names()

        if not table_names:
            table_names = insp.get_table_names()

        for table_name in table_names:
            columns = insp.get_columns(table_name)
            foreign_keys = insp.get_foreign_keys(table_name)
            schema[table_name]["columns"] = columns
            schema[table_name]["foreign_keys"] = foreign_keys

        return dict(schema)

    def _extract_schema_from_df(self, dfs: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        schema = {}
        for table_name, df in dfs.items():
            table_schema = {"columns": []}
            for col in df.columns:
                dtype = str(df[col].dtype)
                table_schema["columns"].append({"column_name": col, "type": dtype})
            schema[table_name] = table_schema

        for t1, df1 in dfs.items():
            for t2, df2 in dfs.items():
                if t1 == t2:
                    continue
                for col1 in df1.columns:
                    for col2 in df2.columns:
                        if df1[col1].dropna().isin(df2[col2].dropna()).mean() > 0.9:
                            schema[t1].setdefault("foreign_keys", []).append({
                                "column": col1,
                                "ref_table": t2,
                                "ref_column": col2
                            })
        return schema

    def _build_reasoning_prompt(self, query_text: str, schema_info: Dict[str, Any], previous_thoughts: List[str]) -> str:
        prompt = (
            "You are an expert database assistant.\n\n"
            f"User question: \"{query_text}\"\n\n"
            f"Schema: {json.dumps(schema_info, indent=2)}\n\n"
            "Step 1: Think step-by-step about which tables and columns are relevant.\n"
            "Step 2: Decide what actions to take (e.g., fetch data, detect relationships).\n"
            "Step 3: Explain your reasoning and suggest next steps in JSON format.\n\n"
            "Respond ONLY with a JSON object containing:\n"
            "- reasoning: explanation\n"
            "- action: SQL query or action plan"
        )
        if previous_thoughts:
            prompt += "\n\nPrevious thoughts:\n"
            for thought in previous_thoughts:
                prompt += f"- {thought}\n"
        return prompt

    def _reason_and_act(self, query_text: str) -> Dict[str, Any]:
        prompt = self._build_reasoning_prompt(query_text, self.schema_info, self.previous_thoughts)

        # Use Ollama API instead of Gemini
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False
        }
        
        try:
            response = requests.post(self.api_base, json=payload)
            if response.status_code == 200:
                reply = response.json()["response"]
                try:
                    reasoning = json.loads(reply)
                except json.JSONDecodeError:
                    reasoning = {"reasoning": reply.strip(), "action": "unknown"}
                
                self.previous_thoughts.append(reasoning.get("reasoning", "No reasoning"))
                self.metadata["llm_reasoning"] = reasoning.get("reasoning", "")
                self.metadata["llm_action"] = reasoning.get("action", "")
                return reasoning
            else:
                raise Exception(f"Ollama API request failed with status code: {response.status_code}")
        except Exception as e:
            print(f"Error in reasoning: {str(e)}")
            return {"reasoning": "Error occurred", "action": "unknown"}

    def _manage_metadata(self, dfs: Optional[Dict[str, pd.DataFrame]] = None):
        if dfs:
            relationships = {}
            for df in dfs.values():
                rels = _detect_relationships(df)
                relationships.update(rels)
            self.metadata["relationships"] = relationships

    def run(self, query_text: str, source_type: str, source: Union[str, Dict[str, pd.DataFrame]], user_id: Optional[str] = None) -> Dict[str, Any]:
        if source_type == "db":
            self.schema_info = self._extract_schema_from_db(user_id=user_id, user_question=query_text)
        elif source_type == "df":
            self.schema_info = self._extract_schema_from_df(source)
            self._manage_metadata(source)
        else:
            raise ValueError("Unsupported source_type. Use 'db' or 'df'.")

        reasoning = self._reason_and_act(query_text)

        return {
            "reasoning": reasoning,
            "schema_summary": self.schema_info,
            "metadata": self.metadata
        }

# Create an agent instance
agent = CombinedSchemaAgent()

# LangGraph Node functions
def schema_extraction_node(state):
    """Extract schema from database or DataFrame"""
    source_type = state.get("source_type")
    source = state.get("source")
    user_id = state.get("user_id", None)
    
    # Create agent instance
    agent = CombinedSchemaAgent()
    
    if source_type == "db":
        schema = agent._extract_schema_from_db(user_id=user_id, user_question=None)
    elif source_type == "df":
        schema = agent._extract_schema_from_df(source)
        agent._manage_metadata(source)
    else:
        raise ValueError("Unsupported source_type, use 'db' or 'df'")
    
    agent.schema_info = schema
    return {"schema_info": schema}

def reasoning_node(state):
    """Perform reasoning on the query"""
    query_text = state.get("query_text")
    
    # Create agent instance
    agent = CombinedSchemaAgent()
    reasoning = agent._reason_and_act(query_text)
    return {"reasoning_result": reasoning}

def metadata_node(state):
    """Manage metadata"""
    dfs = state.get("dfs", None)
    
    # Create agent instance
    agent = CombinedSchemaAgent()
    agent._manage_metadata(dfs)
    return {"metadata": agent.metadata}

# Build the LangGraph graph
graph = StateGraph(dict)
graph.add_node("extract_schema", schema_extraction_node)
graph.add_node("reason", reasoning_node)
graph.add_node("manage_metadata", metadata_node)

# Connect nodes with proper data flow
graph.add_edge(START, "extract_schema")
graph.add_edge("extract_schema", "reason")
graph.add_edge("reason", "manage_metadata")
graph.add_edge("manage_metadata", END)

# Compile the graph
app = graph.compile()

