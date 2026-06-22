# ParseQri Backend API Documentation

## Base URL

```
http://localhost:8000
```

## Authentication

The API uses JWT (JSON Web Token) Bearer authentication. Most endpoints require a valid access token.

### Authentication Flow

1. Register a new user or login with existing credentials
2. Receive access and refresh tokens
3. Include access token in all subsequent requests in the `Authorization` header
4. Use refresh token to get new access token when expired

## API Endpoints

### 1. Authentication (`/auth`)

#### 1.1 Register User

```http
POST /auth/register
Content-Type: application/json

{
    "username": "string",
    "email": "string",
    "password": "string"
}

Response (200 OK):
{
    "id": "number",
    "username": "string",
    "email": "string"
}
```

#### 1.2 Login

```http
POST /auth/login
Content-Type: application/json

{
    "username_or_email": "string",
    "password": "string"
}

Response (200 OK):
{
    "access": "string (JWT token)",
    "refresh": "string (refresh token)",
    "token_type": "bearer"
}
```

#### 1.3 Refresh Token

```http
POST /auth/token/refresh/
Content-Type: application/json

{
    "refresh": "string (refresh token)"
}

Response (200 OK):
{
    "access": "string (new JWT token)",
    "token_type": "bearer"
}
```

#### 1.4 Get Current User

```http
GET /auth/me
Authorization: Bearer <access_token>

Response (200 OK):
{
    "id": "number",
    "username": "string",
    "email": "string"
}
```

### 2. Database Management (`/db`)

Managed by `app/db/routes.py`.

#### 2.1 Test Database Connection

```http
POST /db/test-connection
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "server_name": "string",
    "database_name": "string",
    "use_windows_auth": true,
    "db_type": "string"
}

Response (200 OK):
{
    "status": "success|error",
    "message": "string"
}
```

#### 2.2 Create Database Configuration

```http
POST /db/config
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "db_type": "string",
    "server_name": "string",
    "database_name": "string",
    "use_windows_auth": true,
    "description": "string (optional)"
}

Response (200 OK):
{
    "id": "number",
    "user_id": "number",
    "db_type": "string",
    "server_name": "string",
    "database_name": "string",
    "use_windows_auth": true,
    "description": "string"
}
```

#### 2.3 Get Database Configurations

```http
GET /db/configs
Authorization: Bearer <access_token>

Response (200 OK):
[
    {
        "id": "number",
        "user_id": "number",
        "db_type": "string",
        "server_name": "string",
        "database_name": "string",
        "use_windows_auth": true,
        "description": "string"
    }
]
```

#### 2.4 Get Database Metadata

```http
GET /db/metadata/{config_id}
Authorization: Bearer <access_token>

Response (200 OK):
{
    "status": "success",
    "database_info": {
        "server_name": "string",
        "database_name": "string",
        "description": "string"
    },
    "tables": [...],
    "source": "chromadb|fresh_extraction"
}
```

#### 2.5 Extract Metadata

Extracts metadata from external database and indexes it in ChromaDB.

```http
POST /db/extract-metadata/{config_id}
Authorization: Bearer <access_token>

Response (200 OK):
{
    "success": true|false,
    "status": "success|error",
    "message": "string",
    "metadata": [...],
    "extraction_method": "string"
}
```

#### 2.6 Search Metadata

```http
GET /db/search-metadata
Authorization: Bearer <access_token>
Query Parameters:
- query: string
- limit: number (optional, default 5)

Response (200 OK):
{
    "status": "success",
    "query": "string",
    "results": [...]
}
```

### 3. Text-to-SQL Services (`/api`)

Managed by `app/routes/api.py`. Invokes the `Text_to_Sql` module (LangGraph agent).

#### 3.1 Process Natural Language Query

```http
POST /api/text-to-sql
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "query": "string (natural language query)",
    "database_id": number (optional),
    "user_id": "string (optional, defaults to authenticated user)",
    "visualization": boolean (optional)
}

Response (200 OK):
{
    "answer": "string",
    "sql_query": "string",
    "data": [...],
    "chart_type": "string",
    "question": "string"
}
```

#### 3.2 Get Databases for Dropdown

```http
GET /api/databases
Authorization: Bearer <access_token>

Response (200 OK):
{
    "success": true,
    "databases": [
        {
            "id": number,
            "server_name": "string",
            "database_name": "string",
            "description": "string",
            "display_name": "string"
        }
    ]
}
```

### 4. CSV Agent Services (`/csv`)

Managed by `app/routes/csv_agent.py`. Invokes the `ParseQri_MCP/CSV_Agent` module.

#### 4.1 Process CSV Query

```http
POST /csv/query
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "query": "string",
    "table_name": "string (optional)",
    "visualization": boolean,
    "database_id": number (optional)
}

Response (200 OK):
{
    "answer": "string",
    "sql_query": "string",
    "data": [...],
    "chart_type": "string",
    "visualization_data": {...},
    "table_name": "string"
}
```

#### 4.2 Execute Raw SQL (CSV Context)

```http
POST /csv/execute_sql
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "sql_query": "string"
}

Response (200 OK):
{
    "answer": "string",
    "sql_query": "string",
    "data": [...]
}
```

#### 4.3 Upload CSV

```http
POST /csv/upload
Authorization: Bearer <access_token>
Content-Type: multipart/form-data

Form Data:
- file: (File Object)
- db_id: number (optional)

Response (200 OK):
{
    "success": true,
    "table_name": "string",
    "message": "string"
}
```

#### 4.4 List CSV Tables

```http
GET /csv/tables
Authorization: Bearer <access_token>

Response (200 OK):
{
    "tables": [
        {
            "name": "string",
            "full_name": "string",
            "source": "string",
            "column_count": number
        }
    ]
}
```

#### 4.5 Get CSV Table Schema

```http
GET /csv/schema/{table_name}
Authorization: Bearer <access_token>

Response (200 OK):
{
    "table_name": "string",
    "columns": [
        {
            "name": "string",
            "type": "string",
            "nullable": boolean
        }
    ]
}
```

## Base URL

```
http://localhost:8000
```

## Authentication

The API uses JWT (JSON Web Token) Bearer authentication. Most endpoints require a valid access token.

### Authentication Flow

1. Register a new user or login with existing credentials
2. Receive access and refresh tokens
3. Include access token in all subsequent requests in the Authorization header
4. Use refresh token to get new access token when expired

## API Endpoints

### 1. Authentication

#### 1.1 Register User

```http
POST /auth/register
Content-Type: application/json

{
    "username": "string",
    "email": "string",
    "password": "string"
}

Response (200 OK):
{
    "id": "number",
    "username": "string",
    "email": "string"
}
```

#### 1.2 Login

```http
POST /auth/login
Content-Type: application/json

{
    "username_or_email": "string",
    "password": "string"
}

Response (200 OK):
{
    "access": "string (JWT token)",
    "refresh": "string (refresh token)",
    "token_type": "bearer"
}
```

#### 1.3 Refresh Token

```http
POST /auth/token/refresh/
Content-Type: application/json

{
    "refresh": "string (refresh token)"
}

Response (200 OK):
{
    "access": "string (new JWT token)",
    "token_type": "bearer"
}
```

#### 1.4 Verify Token

```http
POST /auth/token/verify/
Content-Type: application/json

{
    "token": "string (JWT token)"
}

Response (200 OK):
{
    "valid": true
}
```

#### 1.5 Get Current User

```http
GET /auth/me
Authorization: Bearer <access_token>

Response (200 OK):
{
    "id": "number",
    "username": "string",
    "email": "string"
}
```

### 2. Database Management

#### 2.1 Test Database Connection

```http
POST /db/test-connection
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "server_name": "string",
    "database_name": "string",
    "use_windows_auth": true,
    "db_type": "string"
}

Response (200 OK):
{
    "status": "success|error",
    "message": "string"
}
```

#### 2.2 Create Database Configuration

```http
POST /db/config
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "db_type": "string",
    "server_name": "string",
    "database_name": "string",
    "use_windows_auth": true,
    "description": "string (optional)"
}

Response (200 OK):
{
    "id": "number",
    "user_id": "number",
    "db_type": "string",
    "server_name": "string",
    "database_name": "string",
    "use_windows_auth": true,
    "description": "string"
}
```

#### 2.3 Get Database Configurations

```http
GET /db/configs
Authorization: Bearer <access_token>

Response (200 OK):
[
    {
        "id": "number",
        "user_id": "number",
        "db_type": "string",
        "server_name": "string",
        "database_name": "string",
        "use_windows_auth": true,
        "description": "string"
    }
]
```

#### 2.4 Get Database Metadata

```http
GET /db/metadata/{config_id}
Authorization: Bearer <access_token>

Response (200 OK):
{
    "status": "success",
    "database_info": {
        "server_name": "string",
        "database_name": "string",
        "description": "string"
    },
    "tables": [...],
    "source": "chromadb|fresh_extraction"
}
```

#### 2.5 Extract Metadata

```http
POST /db/extract-metadata/{config_id}
Authorization: Bearer <access_token>

Response (200 OK):
{
    "success": true|false,
    "status": "success|error",
    "message": "string",
    "metadata": [...],
    "extraction_method": "string"
}
```

#### 2.6 Search Metadata

```http
GET /db/search-metadata
Authorization: Bearer <access_token>
Query Parameters:
- query: string
- limit: number (optional, default 5)

Response (200 OK):
{
    "status": "success",
    "query": "string",
    "results": [...]
}
```

## Testing with Postman

### Environment Setup

1. Create a new environment in Postman
2. Add the following variables:
   - `base_url`: http://localhost:8000
   - `access_token`: (empty initially)
   - `refresh_token`: (empty initially)

### Authentication Flow Testing

1. Register a new user:

   ```http
   POST {{base_url}}/auth/register
   Content-Type: application/json

   {
       "username": "testuser",
       "email": "test@example.com",
       "password": "testpass123"
   }
   ```

2. Login to get tokens:

   ```http
   POST {{base_url}}/auth/login
   Content-Type: application/json

   {
       "username_or_email": "testuser",
       "password": "testpass123"
   }
   ```

   - Save the access token to environment variable: `access_token`
   - Save the refresh token to environment variable: `refresh_token`

3. Test protected endpoint:
   ```http
   GET {{base_url}}/auth/me
   Authorization: Bearer {{access_token}}
   ```

### Database Connection Testing

1. Test database connection:

   ```http
   POST {{base_url}}/db/test-connection
   Authorization: Bearer {{access_token}}
   Content-Type: application/json

   {
       "server_name": "localhost",
       "database_name": "test_db",
       "use_windows_auth": true,
       "db_type": "mssql"
   }
   ```

2. Create database configuration:

   ```http
   POST {{base_url}}/db/config
   Authorization: Bearer {{access_token}}
   Content-Type: application/json

   {
       "db_type": "mssql",
       "server_name": "localhost",
       "database_name": "test_db",
       "use_windows_auth": true,
       "description": "Test database configuration"
   }
   ```

3. Get database configurations:
   ```http
   GET {{base_url}}/db/configs
   Authorization: Bearer {{access_token}}
   ```

### Error Handling

The API returns standard HTTP status codes:

- 200: Success
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 500: Internal Server Error

Error responses include a detail message:

```json
{
  "detail": "Error message description"
}
```

## Security Notes

1. Always use HTTPS in production
2. Store tokens securely
3. Never send tokens or sensitive data in URL parameters
4. Refresh tokens should be stored securely and never exposed to client-side code
5. Access tokens have a limited lifetime and should be refreshed using the refresh token

### 3. CSV Agent Services

#### 3.1 Upload CSV

```http
POST /csv/upload
Authorization: Bearer <access_token>
Content-Type: multipart/form-data

Form Data:
- file: (File Object)
- db_id: number (optional)

Response (200 OK):
{
    "success": true,
    "table_name": "string",
    "message": "string"
}
```

#### 3.2 List Tables

```http
GET /csv/tables
Authorization: Bearer <access_token>

Response (200 OK):
{
    "tables": [
        {
            "name": "string",
            "full_name": "string",
            "source": "string",
            "column_count": number
        }
    ]
}
```

#### 3.3 Get Table Schema

```http
GET /csv/schema/{table_name}
Authorization: Bearer <access_token>

Response (200 OK):
{
    "table_name": "string",
    "columns": [
        {
            "name": "string",
            "type": "string",
            "nullable": boolean
        }
    ]
}
```

#### 3.4 Process CSV Query

```http
POST /csv/query
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "query": "string",
    "table_name": "string (optional)",
    "visualization": boolean,
    "database_id": number (optional)
}

Response (200 OK):
{
    "answer": "string",
    "sql_query": "string",
    "data": [...],
    "chart_type": "string",
    "visualization_data": {...},
    "table_name": "string"
}
```

#### 3.5 Execute Raw SQL

```http
POST /csv/execute_sql
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "sql_query": "string"
}

Response (200 OK):
{
    "answer": "string",
    "sql_query": "string",
    "data": [...],
    "table_name": "string (optional)"
}
```
