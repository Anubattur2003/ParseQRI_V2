from pydantic import BaseModel, ConfigDict
from enum import Enum
from typing import Optional

class DBType(str, Enum):
    mssql = "mssql"

class DBConfigCreate(BaseModel):
    server_name: str
    database_name: str
    use_windows_auth: bool = True
    description: Optional[str] = None
    db_type: DBType = DBType.mssql  # Only MSSQL supported

class DBConfigOut(BaseModel):
    id: int
    user_id: int
    server_name: str
    database_name: str
    use_windows_auth: bool = True
    description: Optional[str] = None
    db_type: DBType = DBType.mssql

    model_config = ConfigDict(from_attributes=True)

class DBConnectionTest(BaseModel):
    server_name: str
    database_name: str
    use_windows_auth: bool = True
    db_type: DBType = DBType.mssql