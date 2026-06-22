# Text-to-SQL API Endpoints Specification

## Overview
This document defines the REST API endpoints for the Text-to-SQL conversion system. These endpoints are implemented using the Text_to_Sql module and can be accessed through FastAPI, Flask, or any other backend framework to replace the current Gradio interface.

## Base Configuration
- **Base URL**: `http://localhost:8000/api/v1` (configurable)
- **Content-Type**: `application/json`
- **Authentication**: Bearer token (optional, can be added later)
- **Database Support**: Microsoft SQL Server with Windows Authentication

---

## 1. Database Connection Management

### 1.1 Test Database Connection
**Endpoint**: `POST /database/test-connection`

**Description**: Test if a database connection can be established without persisting the connection.

**Request Body**:
```json
{
  "server_name": "string",
  "database_name": "string"
}
```

**Response**:
```json
{
  "success": boolean,
  "message": "string",
  "data": {
    "server_version": "string",
    "connection_info": "string"
  }
}
```

**Example Request**:
```json
{
  "server_name": "C2C-LP-25-012",
  "database_name": "INSMA"
}
```

**Example Response**:
```json
{
  "success": true,
  "message": "Connection test successful",
  "data": {
    "server_version": "Microsoft SQL Server 2019",
    "connection_info": "Connection established successfully"
  }
}
```

---

### 1.2 Establish Database Connection
**Endpoint**: `POST /database/connect`

**Description**: Establish a persistent database connection and retrieve schema metadata.

**Request Body**:
```json
{
  "server_name": "string",
  "database_name": "string"
}
```

**Response**:
```json
{
  "success": boolean,
  "message": "string",
  "data": {
    "connection_id": "string",
    "schema_markdown": "string",
    "schema_history": "string"
  }
}
```

**Example Response**:
```json
{
  "success": true,
  "message": "Connection established successfully",
  "data": {
    "connection_id": "conn_123456",
    "schema_markdown": "## Database Schema\n### Tables\n- Equipment\n- Defects\n...",
    "schema_history": "### Schema History\n- 2025-01-13: Last updated\n..."
  }
}
```

---

### 1.3 Get Current Schema
**Endpoint**: `GET /database/schema`

**Description**: Retrieve the current database schema information.

**Query Parameters**:
- `connection_id` (optional): string - Connection ID if multiple connections

**Response**:
```json
{
  "success": boolean,
  "message": "string",
  "data": {
    "schema": {
      "tables": {
        "table_name": {
          "columns": [
            {
              "name": "string",
              "type": "string",
              "nullable": boolean,
              "primary_key": boolean
            }
          ],
          "relationships": [
            {
              "type": "string",
              "target_table": "string",
              "foreign_key": "string"
            }
          ]
        }
      }
    },
    "last_updated": "datetime"
  }
}
```

---

### 1.4 Get Schema History
**Endpoint**: `GET /database/schema-history`

**Description**: Retrieve historical schema changes.

**Response**:
```json
{
  "success": boolean,
  "message": "string",
  "data": {
    "history": [
      {
        "timestamp": "datetime",
        "changes": "string",
        "version": "string"
      }
    ]
  }
}
```

---

## 2. Query Processing

### 2.1 Process Natural Language Query
**Endpoint**: `POST /query/process`

**Description**: Main endpoint to process a natural language query through the complete Text-to-SQL pipeline.

**Request Body**:
```json
{
  "query": "string",
  "user_id": "string (optional)",
  "connection_id": "string (optional)",
  "options": {
    "include_raw_results": boolean,
    "format_response": boolean,
    "validate_sql": boolean
  }
}
```

**Response**:
```json
{
  "success": boolean,
  "message": "string",
  "data": {
    "query_id": "string",
    "processing_steps": {
      "intent_classification": {
        "intent": "string",
        "confidence": number
      },
      "schema_analysis": {
        "relevant_tables": ["string"],
        "relevant_columns": {
          "table_name": ["column_name"]
        },
        "reasoning": "string"
      },
      "sql_generation": {
        "sql_query": "string",
        "reasoning": "string"
      },
      "sql_validation": {
        "is_valid": boolean,
        "validation_message": "string",
        "requires_human_approval": boolean,
        "review_reason": "string (optional)"
      },
      "query_execution": {
        "execution_time_ms": number,
        "rows_affected": number,
        "formatted_response": "string",
        "raw_results": [{}]  // Optional based on request
      }
    },
    "processing_history": [
      {
        "step": "string",
        "result": "string",
        "timestamp": "datetime"
      }
    ]
  },
  "error": "string (optional)"
}
```

**Example Request**:
```json
{
  "query": "What is the name of the equipment with serial number 'A-177792'?",
  "user_id": "user123",
  "options": {
    "include_raw_results": true,
    "format_response": true,
    "validate_sql": true
  }
}
```

---

### 2.2 Get Processing Steps (Detailed)
**Endpoint**: `POST /query/process-detailed`

**Description**: Process query with detailed step-by-step results, useful for debugging or educational purposes.

**Request Body**: Same as `/query/process`

**Response**: Returns individual step results in separate fields for easier frontend handling:
```json
{
  "success": boolean,
  "message": "string",
  "data": {
    "query_id": "string",
    "step_1_intent": {
      "status": "completed|failed|pending",
      "result": {},
      "error": "string (optional)"
    },
    "step_2_schema": {
      "status": "completed|failed|pending",
      "result": {},
      "error": "string (optional)"
    },
    "step_3_sql": {
      "status": "completed|failed|pending",
      "result": {},
      "error": "string (optional)"
    },
    "step_4_validation": {
      "status": "completed|failed|pending",
      "result": {},
      "error": "string (optional)"
    },
    "step_5_execution": {
      "status": "completed|failed|pending",
      "result": {},
      "error": "string (optional)"
    }
  }
}
```

---

## 3. Individual Agent Endpoints

### 3.1 Intent Classification Only
**Endpoint**: `POST /agents/classify-intent`

**Request Body**:
```json
{
  "query": "string"
}
```

**Response**:
```json
{
  "success": boolean,
  "message": "string",
  "data": {
    "intent": "string",
    "confidence": number,
    "possible_intents": [
      {
        "intent": "string",
        "confidence": number
      }
    ]
  }
}
```

---

### 3.2 Schema Analysis Only
**Endpoint**: `POST /agents/analyze-schema`

**Request Body**:
```json
{
  "query": "string",
  "intent": "string",
  "schema": {} // Optional, uses current connection schema if not provided
}
```

**Response**:
```json
{
  "success": boolean,
  "message": "string",
  "data": {
    "relevant_tables": ["string"],
    "relevant_columns": {
      "table_name": ["column_name"]
    },
    "relationships": [
      {
        "type": "string",
        "tables": ["string"]
      }
    ],
    "reasoning": "string"
  }
}
```

---

### 3.3 SQL Generation Only
**Endpoint**: `POST /agents/generate-sql`

**Request Body**:
```json
{
  "query": "string",
  "schema": {},
  "relevant_metadata": {
    "relevant_tables": ["string"],
    "relevant_columns": {},
    "intent": "string"
  }
}
```

**Response**:
```json
{
  "success": boolean,
  "message": "string",
  "data": {
    "sql_query": "string",
    "reasoning": "string",
    "confidence": number
  }
}
```

---

### 3.4 SQL Validation Only
**Endpoint**: `POST /agents/validate-sql`

**Request Body**:
```json
{
  "sql_query": "string",
  "schema": {}
}
```

**Response**:
```json
{
  "success": boolean,
  "message": "string",
  "data": {
    "is_valid": boolean,
    "validation_errors": ["string"],
    "suggestions": ["string"],
    "requires_human_approval": boolean,
    "review_reason": "string (optional)"
  }
}
```

---

## 4. Utility Endpoints

### 4.1 Health Check
**Endpoint**: `GET /health`

**Description**: System health check endpoint.

**Response**:
```json
{
  "status": "healthy|unhealthy",
  "timestamp": "datetime",
  "version": "string",
  "components": {
    "database": "connected|disconnected",
    "agents": "operational|error",
    "memory": "ok|warning|critical"
  }
}
```

---

### 4.2 System Information
**Endpoint**: `GET /system/info`

**Description**: Get system configuration and capabilities.

**Response**:
```json
{
  "success": boolean,
  "data": {
    "version": "string",
    "supported_databases": ["mssql"],
    "available_agents": ["string"],
    "configuration": {
      "max_query_length": number,
      "timeout_seconds": number,
      "supported_intents": ["string"]
    }
  }
}
```

---

### 4.3 Query History
**Endpoint**: `GET /query/history`

**Description**: Retrieve query processing history.

**Query Parameters**:
- `user_id` (optional): string
- `limit` (optional): number (default: 50)
- `offset` (optional): number (default: 0)

**Response**:
```json
{
  "success": boolean,
  "data": {
    "queries": [
      {
        "query_id": "string",
        "query": "string",
        "user_id": "string",
        "timestamp": "datetime",
        "success": boolean,
        "processing_time_ms": number
      }
    ],
    "total_count": number,
    "has_more": boolean
  }
}
```

---

## 5. Error Handling

### Standard Error Response Format
All endpoints return errors in this standardized format:

```json
{
  "success": false,
  "message": "string",
  "error": {
    "code": "string",
    "details": "string",
    "timestamp": "datetime"
  }
}
```

### Common Error Codes
- `DATABASE_CONNECTION_FAILED`: Database connection issues
- `INVALID_QUERY`: Malformed or invalid input query
- `SCHEMA_NOT_FOUND`: Database schema not available
- `SQL_GENERATION_FAILED`: SQL generation process failed
- `VALIDATION_FAILED`: SQL validation failed
- `EXECUTION_FAILED`: Query execution failed
- `TIMEOUT`: Request timeout
- `INTERNAL_ERROR`: Unexpected system error
- `MSSQL_AUTH_FAILED`: Windows Authentication failed
- `CSV_NOT_SUPPORTED`: CSV operations coming soon

---

## 6. WebSocket Endpoints (Optional)

### 6.1 Real-time Query Processing
**Endpoint**: `WS /query/process-stream`

**Description**: WebSocket endpoint for real-time step-by-step query processing updates.

**Message Format**:
```json
{
  "type": "step_update|error|complete",
  "step": "intent|schema|sql|validation|execution",
  "data": {},
  "progress": number // 0-100
}
```

---

## 7. CSV Data Import (Coming Soon)

### 7.1 CSV File Upload
**Status**: Coming Soon

**Description**: CSV file upload and processing capabilities will be available in a future release. This will include:
- File upload validation
- Automatic schema detection
- Data type inference
- CSV to SQL table conversion
- Query support for uploaded CSV data

### 7.2 CSV Data Management
**Status**: Coming Soon

**Features planned**:
- CSV file management interface
- Data preview capabilities
- Schema modification tools
- Data quality validation
- Export functionality

---

## 8. Implementation Notes

### Required Environment Variables
```bash
DATABASE_DRIVER=ODBC Driver 17 for SQL Server
DATABASE_TIMEOUT=30
API_PORT=8000
API_HOST=0.0.0.0
LOG_LEVEL=INFO
CHROMA_DB_PATH=./Text_to_Sql/agents/chroma_db
```

### Recommended FastAPI Implementation Structure
```
api/
├── main.py                 # FastAPI app initialization
├── routers/
│   ├── database.py         # Database connection endpoints
│   ├── query.py           # Query processing endpoints
│   ├── agents.py          # Individual agent endpoints
│   └── utility.py         # Health and system endpoints
├── models/
│   ├── requests.py        # Pydantic request models
│   └── responses.py       # Pydantic response models
├── middleware/
│   ├── auth.py           # Authentication middleware
│   ├── cors.py           # CORS configuration
│   └── logging.py        # Request logging
├── dependencies.py        # FastAPI dependencies
└── Text_to_Sql/           # Text-to-SQL module integration
    ├── core/
    ├── agents/
    └── models/
```

### Security Considerations
1. **Input Validation**: Validate all input parameters
2. **SQL Injection Prevention**: Use parameterized queries
3. **Rate Limiting**: Implement request rate limiting
4. **Authentication**: Add Bearer token authentication
5. **CORS**: Configure appropriate CORS policies
6. **Logging**: Log all database queries and access attempts

### Performance Optimization
1. **Caching**: Cache database schema and frequently used queries
2. **Connection Pooling**: Use database connection pooling
3. **Async Processing**: Use async/await for database operations
4. **Background Tasks**: Use background tasks for long-running operations
5. **Response Compression**: Enable gzip compression for responses

This specification provides a complete foundation for implementing the Text-to-SQL system as a REST API, maintaining all the functionality currently available in the Gradio interface while providing the flexibility to integrate with various frontend technologies.
