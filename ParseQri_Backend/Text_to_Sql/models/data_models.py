from typing import Optional, Dict, Any, List
from datetime import datetime
import pandas as pd
from pydantic import BaseModel

class AgentState(BaseModel):
    """State information for an individual agent."""
    agent_id: str
    status: str  # "pending", "running", "completed", "failed"
    start_time: datetime
    end_time: Optional[datetime] = None
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    error: Optional[str] = None

class WorkflowState(BaseModel):
    """Overall workflow state."""
    query: str
    current_step: str
    steps_completed: List[str]
    agent_states: Dict[str, AgentState]
    start_time: datetime
    last_updated: datetime
    error: Optional[str] = None

class QueryContext:
    """
    Class to hold the context of a database query, including the user's question
    and related metadata.
    """
    def __init__(
        self,
        user_question: str,
        db_schema: Dict[str, Any],
        table_name: Optional[str] = None,
        user_id: Optional[str] = None,
        query_results: Optional[pd.DataFrame] = None,
        relevant_metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize a QueryContext instance.
        
        Args:
            user_question (str): The original question asked by the user
            db_schema (Dict[str, Any]): The database schema information
            table_name (Optional[str]): Specific table name if query is table-focused
            user_id (Optional[str]): ID of the user making the query
            query_results (Optional[pd.DataFrame]): The results of the SQL query
            relevant_metadata (Optional[Dict[str, Any]]): Additional context from schema analysis
        """
        self.user_question = user_question
        self.db_schema = db_schema
        self.table_name = table_name
        self.user_id = user_id
        self.query_results = query_results
        self.relevant_metadata = relevant_metadata if relevant_metadata is not None else {}

class AgentResponse(BaseModel):
    """
    Class to represent a standardized response from any agent in the system.
    """
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None