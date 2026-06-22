from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import subprocess
import sys
import json
from pathlib import Path
import os
from app.auth.routes import router as auth_router
from app.db.routes import router as db_router
from app.routes.data import router as data_router
from app.core.security import verify_token
from app.core.database import get_db
from sqlalchemy.orm import Session

# Main API router without a prefix - will use the prefixes defined in the individual routers
router = APIRouter()

# Include all sub-routers
router.include_router(auth_router)
router.include_router(db_router)
router.include_router(data_router)

# Include CSV Agent router
from app.routes.csv_agent import router as csv_router
router.include_router(csv_router)

# Text to SQL router with API prefix
text_to_sql_router = APIRouter(
    prefix="/api",
    tags=["api"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

class TextToSQLQuery(BaseModel):
    query: str
    database_id: int = None  # Optional: database ID to use for query
    user_id: str = "default_user"
    visualization: bool = False

class TextToSQLResponse(BaseModel):
    answer: str
    sql_query: str
    data: list = []
    chart_type: str = "bar"
    question: str = ""

@text_to_sql_router.post("/text-to-sql", response_model=TextToSQLResponse)
async def process_text_to_sql(
    query_data: TextToSQLQuery, 
    token: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Process a natural language query and convert it to SQL"""
    try:
        # Get user_id from the token - check both "user_id" and "sub" fields
        user_id = token.get("user_id") or token.get("sub")
        if user_id:
            # Override the user_id in the query data with the authenticated user's ID
            query_data.user_id = str(user_id)  # Convert to string to ensure compatibility
            print(f"Using authenticated user_id: {user_id}")
        else:
            print(f"Warning: No user_id found in token, using default: {query_data.user_id}")
            
        # Get user's database configuration
        from app.db.models import UserDatabase
        
        # If database_id is provided, use that specific database
        if query_data.database_id:
            user_db_config = db.query(UserDatabase).filter(
                UserDatabase.id == query_data.database_id,
                UserDatabase.user_id == user_id
            ).first()
            
            if not user_db_config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Database with ID {query_data.database_id} not found for this user"
                )
        else:
            # Fall back to user's first database (default behavior)
            user_db_config = db.query(UserDatabase).filter(UserDatabase.user_id == user_id).first()
        
        if not user_db_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No database connection found for user. Please connect a database first."
            )
            
        # Import the Text-to-SQL integration service directly from file to avoid namespace collision
        # with CSV_Agent's integration_service. Cache the module so it only loads once.
        import importlib.util
        text_to_sql_dir = Path(__file__).parent.parent.parent / "Text_to_Sql"
        text_to_sql_dir_str = str(text_to_sql_dir)
        
        # Ensure Text_to_Sql is at position 0 in sys.path so its 'core' package takes priority
        if text_to_sql_dir_str in sys.path:
            if sys.path[0] != text_to_sql_dir_str:
                sys.path.remove(text_to_sql_dir_str)
                sys.path.insert(0, text_to_sql_dir_str)
        else:
            sys.path.insert(0, text_to_sql_dir_str)
        
        # Only load the module once; reuse on subsequent requests
        if "text_to_sql_integration_service" not in sys.modules:
            spec = importlib.util.spec_from_file_location(
                "text_to_sql_integration_service", 
                text_to_sql_dir / "integration_service.py"
            )
            text_to_sql_module = importlib.util.module_from_spec(spec)
            sys.modules["text_to_sql_integration_service"] = text_to_sql_module
            spec.loader.exec_module(text_to_sql_module)
        else:
            text_to_sql_module = sys.modules["text_to_sql_integration_service"]
        
        process_text_to_sql_query = text_to_sql_module.process_text_to_sql_query
        
        print(f"Processing query with Text-to-SQL service...")
        print(f"Query: {query_data.query}")
        print(f"User ID: {query_data.user_id}")
        print(f"Database: {user_db_config.database_name} on {user_db_config.server_name}")
        
        # Process the query using the integration service
        result = await process_text_to_sql_query(
            query=query_data.query,
            server_name=user_db_config.server_name,
            database_name=user_db_config.database_name,
            user_id=query_data.user_id
        )
        
        print(f"Text-to-SQL processing completed: {result.get('success', False)}")
        
        if not result.get("success"):
            error_msg = result.get("error", "Unknown error in Text-to-SQL processing")
            print(f"Text-to-SQL error: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Text-to-SQL error: {error_msg}"
            )
        
        return TextToSQLResponse(
            answer=result.get("answer", "No response generated"),
            sql_query=result.get("sql_query", ""),
            data=result.get("data", []),
            chart_type=result.get("chart_type", "bar"),
            question=result.get("question", query_data.query)
        )
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"CRITICAL ERROR in text-to-sql endpoint: {str(e)}")
        print(error_details)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing query: {str(e)}"
        )

@text_to_sql_router.get("/databases")
async def get_user_databases(
    token: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Get list of user's connected databases for dropdown selection"""
    try:
        user_id = token.get("user_id") or token.get("sub")
        
        from app.db.models import UserDatabase
        databases = db.query(UserDatabase).filter(UserDatabase.user_id == user_id).all()
        
        return {
            "success": True,
            "databases": [
                {
                    "id": db_config.id,
                    "server_name": db_config.server_name,
                    "database_name": db_config.database_name,
                    "description": db_config.description or f"{db_config.server_name}/{db_config.database_name}",
                    "display_name": f"{db_config.database_name} ({db_config.server_name})"
                }
                for db_config in databases
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching databases: {str(e)}"
        )

# Include the text-to-sql router
router.include_router(text_to_sql_router)