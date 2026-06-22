from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import sys
import os
import shutil
from pathlib import Path
from typing import List, Optional

from app.core.security import verify_token
from app.core.database import get_db
from sqlalchemy.orm import Session

# Add CSV Agent to path
csv_agent_path = Path(__file__).parent.parent.parent / "ParseQri_MCP" / "CSV_Agent"
if str(csv_agent_path) not in sys.path:
    sys.path.append(str(csv_agent_path))

try:
    from integration_service import csv_agent_service
except ImportError as e:
    print(f"Error importing CSV Agent service: {e}")
    csv_agent_service = None





# Force reload - added comment 4
router = APIRouter(
    prefix="/csv",
    tags=["csv-agent"]
)

# Models
class CsvQueryRequest(BaseModel):
    query: str
    table_name: Optional[str] = ""
    visualization: bool = False
    database_id: Optional[int] = None

class CsvQueryResponse(BaseModel):
    answer: str
    sql_query: Optional[str] = None
    data: List[dict] = []
    chart_type: str = "bar"
    visualization_data: Optional[dict] = None
    table_name: Optional[str] = None

@router.post("/query", response_model=CsvQueryResponse)
async def query_csv(
    request: CsvQueryRequest,
    token: dict = Depends(verify_token)
):
    """Process a natural language query against CSV data"""
    if not csv_agent_service:
        raise HTTPException(status_code=500, detail="CSV Agent service not available")
        
    user_id = token.get("user_id") or token.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found in token")
        
    # Convert user_id to string as expected by CSV Agent
    user_id = str(user_id)
        
    result = await csv_agent_service.process_query(
        query=request.query,
        user_id=user_id,
        table_name=request.table_name or "",
        db_id=request.database_id,
        visualization=request.visualization
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        
    return CsvQueryResponse(
        answer=result.get("answer", ""),
        sql_query=result.get("sql_query"),
        data=result.get("data", []),
        chart_type=result.get("chart_type", "bar"),
        visualization_data=result.get("visualization_data"),
        table_name=result.get("table_name")
    )

@router.post("/execute_sql", response_model=CsvQueryResponse)
async def execute_sql(
    request: dict = Body(...),
    token: dict = Depends(verify_token)
):
    """Execute a raw SQL query directly"""
    if not csv_agent_service:
        raise HTTPException(status_code=500, detail="CSV Agent service not available")
        
    user_id = token.get("user_id") or token.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found in token")
        
    sql_query = request.get("sql_query")
    if not sql_query:
        raise HTTPException(status_code=400, detail="SQL query is required")
        
    result = await csv_agent_service.execute_sql(
        sql_query=sql_query,
        user_id=str(user_id)
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Execution failed"))
        
    return CsvQueryResponse(
        answer="Manual execution successful",
        sql_query=result.get("sql_query"),
        data=result.get("data", [])
    )

@router.post("/upload")
async def upload_csv(
    file: UploadFile = File(...),
    db_id: Optional[int] = Form(None),
    token: dict = Depends(verify_token)
):
    """Upload a CSV file for analysis"""
    if not csv_agent_service:
        raise HTTPException(status_code=500, detail="CSV Agent service not available")
        
    user_id = token.get("user_id") or token.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found in token")
    
    # Check file extension
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")
        
    # User-specific upload directory within agent's data folder
    # We need to save it where the CSV Agent expects it, or pass the path
    # Agent typically looks in ../data/input, but we can pass absolute path
    
    # Let's save to a temp location first then pass to agent
    uploads_dir = Path(__file__).parent.parent.parent / "uploads" / "csv_tmp"
    os.makedirs(uploads_dir, exist_ok=True)
    
    file_path = uploads_dir / f"{user_id}_{file.filename}"
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Process with agent
        result = await csv_agent_service.upload_csv(
            file_path=str(file_path),
            user_id=str(user_id),
            original_filename=file.filename,
            db_id=db_id
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Upload processing failed"))
            
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")
    finally:
        # Cleanup temp file? 
        # The agent might copy it or use it. integration_service logic suggests it calls process_upload which copies/ingests.
        # So we might be able to delete it, but let's keep it for safety for now or delete if we are sure.
        pass

@router.get("/tables")
async def list_tables(token: dict = Depends(verify_token)):
    """List available CSV/Table data for the user"""
    if not csv_agent_service:
        raise HTTPException(status_code=500, detail="CSV Agent service not available")
        
    user_id = token.get("user_id") or token.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found in token")
        
    tables = await csv_agent_service.list_tables(str(user_id))
    return {"tables": tables}

@router.get("/schema/{table_name}")
async def get_table_schema(
    table_name: str, 
    token: dict = Depends(verify_token)
):
    """Get schema for a specific table"""
    if not csv_agent_service:
        raise HTTPException(status_code=500, detail="CSV Agent service not available")
        
    user_id = token.get("user_id") or token.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found in token")
        
    schema = await csv_agent_service.get_table_schema(str(user_id), table_name)
    if not schema:
        raise HTTPException(status_code=404, detail="Table not found")
        
    return schema
