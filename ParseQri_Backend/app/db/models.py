from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.sql import func
from app.core.database import Base

class UserDatabase(Base):
    __tablename__ = "user_databases"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)  # Removed FK constraint for now
    db_type = Column(String(50), nullable=False, default="mssql")  # Only MSSQL supported
    server_name = Column(String(255), nullable=False)  # SQL Server instance name
    database_name = Column(String(255), nullable=False)  # Database name
    use_windows_auth = Column(Boolean, nullable=False, default=True)  # Windows Authentication
    description = Column(String(500), nullable=True)  # Optional description
    created_at = Column(DateTime(timezone=True), server_default=func.now())