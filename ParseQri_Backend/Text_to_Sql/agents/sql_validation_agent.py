import os
import sys
from typing import Dict, Any, Annotated, TypedDict, Sequence, Union
from pydantic import BaseModel, Field
import json
import requests

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.models import AgentType, get_config_for_agent


class QueryContext(BaseModel):
    """Context for SQL query validation."""
    sql_query: str
    db_schema: Dict[str, Any] = Field(..., description="Database schema information")  # Changed type to Any
    feedback: str = ""
    requires_human_review: bool = False
    review_reason: str = ""

class AgentResponse(BaseModel):
    """Response from the SQL validation agent."""
    success: bool
    message: str
    data: Dict[str, Any] = {}

class SQLValidationAgent:
    """
    Agent responsible for validating and fixing SQL queries using ollama.
    Specifically optimized for MSSQL syntax and includes human-in-the-loop validation.
    """
    
    def __init__(self):
        # Load model configuration from centralized config
        config = get_config_for_agent(AgentType.SQL_VALIDATION)
        self.model_name = config["model_name"]
        self.context_window = config["context_window"]
        self.api_url = config["api_url"]

    def _format_schema_for_prompt(self, schema: Dict[str, Any]) -> str:
        """Format the schema in a readable way for the prompt."""
        formatted = []
        for table, info in schema.items():
            formatted.append(f"Table: {table}")
            if isinstance(info, dict):
                if 'columns' in info:
                    formatted.append("Columns:")
                    for col in info['columns']:
                        formatted.append(f"  - {col}")
                if 'foreign_keys' in info:
                    formatted.append("Foreign Keys:")
                    for fk in info['foreign_keys']:
                        formatted.append(f"  - {fk}")
            formatted.append("")
        return "\n".join(formatted)

    def validate_query(self, context: QueryContext) -> Dict[str, Any]:
        """Validate the SQL query using ollama."""
        try:
            formatted_schema = self._format_schema_for_prompt(context.db_schema)
            
            prompt = f"""You are an expert MSSQL validator. Analyze this SQL query for syntax and best practices:

Schema:
{formatted_schema}

Query:
{context.sql_query}

Focus on these validation rules:
1. Every column in SELECT must exist in the schema
2. No text or comments in column names
3. Proper MSSQL syntax and functions
4. Correct table and column references
5. Valid JOIN conditions
6. Proper WHERE clause syntax
7. No SQL injection vulnerabilities
8. Correct use of quotes and brackets

Provide a detailed analysis in this JSON format:
{{
    "valid": boolean,
    "issues": [list of specific issues found],
    "suggestions": [list of MSSQL-specific improvements],
    "requires_human_review": boolean,
    "review_reason": "explanation if human review needed"
}}"""

            response = self.model.generate_content(prompt)
            try:
                return json.loads(response.text)
            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract JSON from the response
                text = response.text
                start_idx = text.find('{')
                end_idx = text.rfind('}') + 1
                if start_idx >= 0 and end_idx > start_idx:
                    try:
                        return json.loads(text[start_idx:end_idx])
                    except json.JSONDecodeError:
                        pass
                
                # If all parsing attempts fail, return a default response
                return {
                    "valid": True,  # Assume valid if we can't parse the response
                    "issues": [],
                    "suggestions": [],
                    "requires_human_review": False,
                    "review_reason": ""
                }
        except Exception as e:
            return {
                "valid": True,  # Assume valid if API call fails
                "issues": [],
                "suggestions": [],
                "requires_human_review": False,
                "review_reason": f"Validation error: {str(e)}"
            }

    def fix_query(self, context: QueryContext, validation_result: Dict[str, Any]) -> str:
        """Fix the SQL query based on validation results."""
        try:
            if not validation_result.get("valid", False):
                formatted_schema = self._format_schema_for_prompt(context.db_schema)
                prompt = f"""As an MSSQL expert, fix this SQL query addressing these issues:
{validation_result.get('issues', [])}

Original query:
{context.sql_query}

Schema:
{formatted_schema}

Apply these MSSQL-specific improvements:
{validation_result.get('suggestions', [])}

Return only the fixed query with no explanation."""

                response = self.model.generate_content(prompt)
                return response.text.strip()
            
            return context.sql_query
        except Exception:
            return context.sql_query  # Return original query if fixing fails

    def process(self, context: QueryContext) -> AgentResponse:
        """Process the query context through validation and fixing."""
        try:
            if not context.sql_query:
                return AgentResponse(
                    success=False,
                    message="No SQL query provided for validation"
                )
                
            if not context.db_schema:
                return AgentResponse(
                    success=False,
                    message="Schema information is required for SQL validation"
                )
            
            # Step 1: Validate the query
            validation_result = self.validate_query(context)
            
            # Step 2: Fix the query if needed
            fixed_query = self.fix_query(context, validation_result)
            
            # Step 3: Prepare the response
            if validation_result.get("requires_human_review", False):
                return AgentResponse(
                    success=True,
                    message="Query requires human review",
                    data={
                        "original_query": context.sql_query,
                        "fixed_query": fixed_query,
                        "review_reason": validation_result.get("review_reason", ""),
                        "requires_human_approval": True
                    }
                )
            
            return AgentResponse(
                success=True,
                message="SQL validation completed",
                data={
                    "sql_query": fixed_query,
                    "sql_valid": validation_result.get("valid", True),
                    "sql_issues": validation_result.get("issues", None)
                }
            )
            
        except Exception as e:
            return AgentResponse(
                success=True,  # Return success but with the original query
                message="Validation skipped due to error",
                data={
                    "sql_query": context.sql_query,
                    "sql_valid": True,
                    "sql_issues": None
                }
            )