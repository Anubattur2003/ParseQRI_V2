from dotenv import load_dotenv
import os
import re
import requests
from typing import Dict, Any, Tuple
import chromadb
import sys

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from models.data_models import QueryContext, AgentResponse

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.models import AgentType, get_config_for_agent


# === Load Environment and Configure ===
load_dotenv()

# Initialize ChromaDB collection
chromadb_client = chromadb.Client()
collection = chromadb_client.get_or_create_collection(name="metadata")


# === Intent Classification Agent ===
class IntentClassificationAgent:
    def __init__(self):
        # Load model configuration from centralized config
        config = get_config_for_agent(AgentType.INTENT_CLASSIFICATION)
        self.model_name = config["model_name"]
        self.context_window = config["context_window"]
        self.api_url = config["api_url"]

    def rule_based_classification(self, question: str) -> str:
        question = question.lower().strip()

        conversational_phrases = [
            'hi', 'hello', 'thank you', 'thanks', 'bye', 'exit', 'quit', 'help', 'what can you do'
        ]

        schema_phrases = [
            'list tables', 'show tables', 'show schema', 'columns of', 'list columns',
            'data types', 'primary key', 'foreign key', 'schema of', 'table structure',
            'describe table', 'show all tables', 'show column names'
        ]

        analytical_phrases = [
            'group by', 'sum', 'avg', 'count', 'having', 'aggregate', 'total',
            'maximum', 'minimum', 'average', 'trend', 'compare by', 'distribution of',
            'number of', 'total sales', 'sales by region', 'count the number of'
        ]

        retrieval_phrases = [
            'select', 'where', 'filter', 'find all', 'retrieve', 'fetch',
            'list all', 'get the rows', 'get records', 'show me', 'display all records',
            'who are', 'which customers', 'show employees', 'list customers'
        ]

        # Check in order of specificity (most specific first)
        for phrase in analytical_phrases:
            if phrase in question:
                return "Analytical / Structured Query Intent"

        for phrase in schema_phrases:
            if phrase in question:
                return "Schema Metadata Discovery Intent"

        for phrase in retrieval_phrases:
            if phrase in question:
                return "Data Retrieval Intent"

        for phrase in conversational_phrases:
            if phrase in question:
                return "Conversational / System Intent"

        return None

    def metadata_match_classification(self, question: str) -> str:
        try:
            results = collection.query(query_texts=[question], n_results=1)
            if results and results['distances'][0][0] < 0.3:
                return "Data Retrieval Intent"
        except Exception:
            pass
        return None

    def llm_fallback_classification(self, question: str) -> Tuple[str, float]:
        """Classify using LLM and return intent with confidence score."""
        prompt = f"""
You are an IntentClassifier Agent designed to classify user queries into one of several predefined intent categories related to querying and interacting with structured data systems.

🎯 Intent Categories:
Data Retrieval Intent:
Queries that fetch specific rows or columns of data, often using SELECT, conditions, filters, or WHERE clauses.

Analytical / Structured Query Intent:
Queries that involve aggregations, calculations, or grouping like GROUP BY, COUNT, SUM, AVG, or dimensional breakdowns.

Schema Metadata Discovery Intent:
Queries that explore the structure of the database — such as listing tables, columns, data types, primary keys, or foreign keys.

Conversational / System Intent:
Non-SQL or natural language queries such as greetings ("hi", "hello"), general help requests, thank you messages, or unrelated system instructions.

🧠 Task:
Read the user's query.
Classify it into one and only one of the above intent categories.
Provide a confidence score between 0.0 and 1.0.
Respond with the intent label and confidence score in this format:
Intent: <intent label>
Confidence: <score>

Query: {question.strip()}
"""
        try:
            # Use Ollama API with context window configuration
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_ctx": self.context_window
                }
            }
            response = requests.post(self.api_url, json=payload)
            if response.status_code == 200:
                result = response.json()["response"].strip()
                
                # Extract intent and confidence
                intent = "Unknown Intent"
                confidence = 0.5
                
                for line in result.split('\n'):
                    if line.startswith("Intent:"):
                        intent = line.split("Intent:")[1].strip()
                    elif line.startswith("Confidence:"):
                        try:
                            confidence = float(line.split("Confidence:")[1].strip())
                        except:
                            confidence = 0.5
                
                valid = {
                    "Data Retrieval Intent",
                    "Analytical / Structured Query Intent",
                    "Schema Metadata Discovery Intent",
                    "Conversational / System Intent"
                }
                if intent not in valid:
                    intent = "Unknown Intent"
                    confidence = 0.3
                    
                return intent, confidence
            return "Unknown Intent", 0.3
        except Exception:
            return "Unknown Intent", 0.3

    def classify_intent(self, question: str) -> Dict[str, Any]:
        """Classify intent and return with confidence score."""
        # Try rule-based first (high confidence)
        intent = self.rule_based_classification(question)
        if intent:
            return {"intent": intent, "confidence": 0.95}

        # Try metadata match (medium confidence)
        intent = self.metadata_match_classification(question)
        if intent:
            return {"intent": intent, "confidence": 0.85}

        # Fall back to LLM (variable confidence)
        intent, confidence = self.llm_fallback_classification(question)
        return {"intent": intent, "confidence": confidence}

# === LangGraph Node ===
def intent_classification_node(state):
    """LangGraph node for intent classification"""
    try:
        agent = IntentClassificationAgent()
        result = agent.classify_intent(state["user_question"])
        return {
            "intent": result["intent"], 
            "intent_confidence": result["confidence"],
            "success": True, 
            "message": "Intent classified"
        }
    except Exception as e:
        return {
            "intent": "Unknown Intent", 
            "intent_confidence": 0.0,
            "success": False, 
            "message": f"Error: {str(e)}"
        }


# === LangGraph Setup ===
graph = StateGraph(dict)
graph.add_node("intent_classification", intent_classification_node)
graph.add_edge(START, "intent_classification")
graph.add_edge("intent_classification", END)

# Compile the graph
app = graph.compile()