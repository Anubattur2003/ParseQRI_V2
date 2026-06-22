# ParseQri Product Document

## 1. Introduction

ParseQri is an advanced AI-powered data analytics platform designed to bridge the gap between technical data systems and business users. It offers a unified natural language interface to query both **connected enterprise databases (MSSQL)** and **ad-hoc CSV files**.

## 2. Problem Statement

Business users often struggle to access data residing in complex SQL databases or locked away in spread-out CSV files without help from technical teams. ParseQri eliminates this bottleneck by allowing users to ask questions in plain English ("What were the sales in Q3?") and receiving accurate data, charts, and analysis instantly.

## 3. Product Features / Scope

### Core Capabilities

1.  **Enterprise Database Connectivity**:
    - Secure connection to MSSQL servers.
    - AI-driven schema extraction and understanding.
    - Automated SQL generation and safe execution.
2.  **CSV Data Analysis**:
    - Drag-and-drop file upload.
    - Instant "Chat with your Data" capability.
    - Data visualization generation (Bar, Line, Pie).
3.  **Advanced Visualization**:
    - Automatic recommendation of chart types based on result sets.
    - Interactive dashboards.

### User Interface

- **Chat Interface**: A conversational UI for interacting with data agents.
- **SQL Editor**: A transparent view for power users to inspect, edit, and run raw SQL.
- **Dashboard**: Central hub for managing database connections and uploaded datasets.

## 4. Enabling Technology

- **AI Agents**: Specialized multi-agent systems (using LangGraph for MSSQL) that handle intent classification, SQL generation, and validation.
- **Vector Search**: ChromaDB is used to index database metadata, allowing the AI to understand massive schemas efficiently.
- **Local Privacy**: Built on local LLM inference (Ollama), ensuring sensitive financial or operational data never leaves the premise.

## 5. Workflow

### Database Workflow

1.  **Connect**: User enters DB credentials. System tests and saves config.
2.  **Index**: System extracts table schema and saves vectors to ChromaDB.
3.  **Query**: User asks a question -> Text-to-SQL Agent generates SQL -> Executed on DB -> Results returned.

### CSV Workflow

1.  **Upload**: User uploads a CSV.
2.  **Analyze**: CSV Agent ingests data into a temporary store.
3.  **Query**: User talks to the data. Agent translates to SQL/Pandas operations.

## 6. Architecture Highlights

The system is split into two powerful engines behind a single API:

- **Text_to_Sql**: A robust, state-aware agent designed for the complexities of formal SQL databases.
- **CSV_Agent**: A flexible, rapid-analysis tool for flat files.

Both are accessible via the modern React frontend, providing a seamless user experience regardless of the data source.

## 1. Introduction

ParseQri is an AI-powered data analysis platform that enables users to query CSV data using natural language. The system provides a seamless experience where users can upload CSV files through an intuitive interface and immediately start exploring their data using plain English queries. ParseQri automatically processes these files, extracts metadata, creates appropriate database schemas, and makes the data available for querying without requiring users to have SQL knowledge.

## 2. Problem Statement

Traditionally, data analysis requires specialized technical skills such as knowledge of SQL, database management, and data modeling. This creates significant barriers for non-technical users who need to extract insights from their data. Current solutions either:

- Require users to learn complex query languages
- Depend on data teams to create reports, causing delays
- Offer limited analysis capabilities for non-technical users
- Lack the ability to understand the context and relationships in data

ParseQri addresses these challenges by providing an intuitive interface that allows anyone to analyze data through natural language, democratizing access to data insights.

## 3. Scope

The ParseQri platform encompasses:

**In Scope:**

- CSV file upload and processing
- Natural language to SQL query conversion
- Database schema creation and management
- Query execution and results visualization
- User authentication and data security
- Metadata extraction and indexing
- Error handling and user feedback
- Multi-user support with isolated data access

**Out of Scope:**

- ETL for extremely large datasets (>100GB)
- Support for non-CSV file formats (initial release)
- Automated data cleaning and transformation
- Real-time data streaming
- Complex data integration with third-party systems

## 4. Enabling Technology

ParseQri leverages several cutting-edge technologies to deliver its capabilities:

- **AI and Natural Language Processing**:
  - Language models for understanding natural language queries
  - Semantic search using vector embeddings
  - ChromaDB for metadata indexing

- **Backend Technologies**:
  - FastAPI for high-performance API endpoints
  - SQLAlchemy for database ORM
  - MySQL for relational data storage
  - Redis for caching and session management
  - Python ecosystem (Pandas, NumPy) for data processing

- **Frontend Technologies**:
  - React with TypeScript for type-safe UI development
  - TailwindCSS for responsive design
  - Chart.js for data visualization
  - Framer Motion for smooth animations
  - React Router for client-side routing

- **DevOps and Infrastructure**:
  - Docker for containerization
  - Authentication using JWT tokens
  - RESTful API architecture

## 5. Workflow & Architecture

### High-Level Workflow

```
┌─────────────┐     ┌──────────────┐     ┌────────────────┐     ┌───────────────┐
│  User       │────▶│ File Upload  │───▶│ File Processing│────▶│ Data Available│
│  Interface  │     │ Component    │     │ Pipeline       │     │ for Querying  │
└─────────────┘     └──────────────┘     └────────────────┘     └───────────────┘
       │                                                               ▲
       │                                                               │
       │               ┌───────────────┐     ┌────────────────┐        │
       └─────────────▶│  NL Query     │───▶│ SQL Generation │────────┘
                       │ Interface     │     │ & Execution    │
                       └───────────────┘     └────────────────┘
```

### Detailed Architecture

```
┌─────────────────────────────────────┐
│           Frontend                  │
│  ┌─────────────┐  ┌─────────────┐   │
│  │ File Upload │  │ Query       │   │
│  │ Component   │  │ Interface   │   │
│  └─────────────┘  └─────────────┘   │
│         │               │           │
└─────────┼───────────────┼───────────┘
          │               │
          ▼               ▼
┌─────────────────────────────────────┐
│           Backend API               │
│  ┌─────────────┐  ┌─────────────┐   │
│  │ Auth        │  │ File        │   │
│  │ Service     │  │ Service     │   │
│  └─────────────┘  └─────────────┘   │
│  ┌─────────────┐  ┌─────────────┐   │
│  │ Query       │  │ Results     │   │
│  │ Service     │  │ Service     │   │
│  └─────────────┘  └─────────────┘   │
└─────────┼───────────────┼───────────┘
          │               │
          ▼               ▼
┌─────────────────────────────────────┐
│         ParseQri Agent              │
│  ┌─────────────┐  ┌─────────────┐   │
│  │ File Watcher│  │ TextToSQL   │   │
│  │ System      │  │ Agent       │   │
│  └─────────────┘  └─────────────┘   │
│  ┌─────────────┐  ┌─────────────┐   │
│  │ Metadata    │  │ DB Schema   │   │
│  │ Extractor   │  │ Generator   │   │
│  └─────────────┘  └─────────────┘   │
└─────────┼───────────────┼───────────┘
          │               │
          ▼               ▼
┌─────────────────────────────────────┐
│         Data Storage                │
│  ┌─────────────┐  ┌─────────────┐   │
│  │  MySQL      │  │ ChromaDB    │   │
│  │ (Data)      │  │ (Metadata)  │   │
│  └─────────────┘  └─────────────┘   │
│  ┌─────────────┐                    │
│  │  Redis      │                    │
│  │ (Cache)     │                    │
│  └─────────────┘                    │
└─────────────────────────────────────┘
```

## 6. System Architecture

### Frontend Components

- **Authentication Module**: Handles user login, registration, and session management
- **File Upload Component**: Provides drag-and-drop functionality for CSV files
- **Chat-Based Analysis Interface**: Conversational UI for natural language querying with history
- **Interactive Results Viewer**: Displays query results, data tables, and schema information inline
- **SQL Editor**: Built-in editor for viewing and executing raw SQL queries
- **Visualization Engine**: Generates charts and graphs based on query results

### Backend Components

- **FastAPI Server**: Core API server handling requests and responses
- **Authentication Service**: Manages JWT tokens and user permissions
- **File Processing Service**: Validates, transforms, and stores uploaded files
- **Database Connector**: Interfaces with MySQL for data operations
- **Cache Manager**: Optimizes performance through Redis caching

### ParseQri Agent Components

- **File Watcher**: Monitors input directory for new files
- **Metadata Extractor**: Analyzes files to extract schema information
- **TextToSQL Agent**: Converts natural language to SQL queries
- **Database Schema Generator**: Creates appropriate database tables
- **Query Executor**: Runs generated SQL and returns results

### Data Storage

- **MySQL**: Primary relational database for storing user data and CSV content
- **ChromaDB**: Vector database for semantic metadata indexing
- **Redis**: In-memory cache for session data and frequent queries
- **File Storage**: System for storing original CSV files and temporary data

## 7. Data Engineering

### Data Types and Processing

- **Structured Data**:
  - CSV files with headers
  - Tabular data with various column types (text, numeric, datetime)
  - Metadata about tables, columns, and relationships

- **Derived Data**:
  - Vector embeddings of column names and descriptions
  - Statistical summaries of column data
  - Query result sets and visualizations

### Database Architecture

- **MySQL Configuration**:
  - Multiple schemas for multi-user isolation
  - Dynamic table creation based on CSV structure
  - Optimized indexing for query performance
  - Connection pooling for scalability

- **ChromaDB Implementation**:
  - Semantic indexing of table and column metadata
  - Vector embeddings for similarity search
  - Persistent storage for embeddings

- **Redis Usage**:
  - Session caching
  - Frequently accessed query results
  - Background task management

### Data Flow

1. CSV file uploaded by user
2. File validated and stored in temporary location
3. File processed and loaded into MySQL
4. Metadata extracted and stored in ChromaDB
5. Data becomes available for querying
6. Natural language queries converted to SQL
7. SQL executed against MySQL
8. Results returned to user interface

## 8. Deployment

### Cloud Deployment

- **Container Orchestration**:
  - Docker containers for each component
  - Kubernetes for orchestration (optional for scaling)
  - CI/CD pipeline for automated deployments

- **Cloud Providers**:
  - AWS: EC2 for compute, RDS for MySQL, ElastiCache for Redis
  - Azure: App Service, Azure Database for MySQL, Azure Cache for Redis
  - GCP: Compute Engine, Cloud SQL, Memorystore

- **Scaling Strategy**:
  - Horizontal scaling of API servers
  - Database connection pooling
  - Load balancing for high availability

### Local Deployment

- **Development Environment**:
  - Docker Compose for local containers
  - Virtual environment for Python dependencies
  - Node.js for frontend development

- **On-Premises Requirements**:
  - Linux/Windows server with Docker support
  - MySQL database server
  - Sufficient storage for data files
  - Memory requirements based on expected data volume

- **Installation Process**:
  1. Clone repository and install dependencies
  2. Configure environment variables
  3. Initialize database schemas
  4. Start backend services
  5. Build and serve frontend application

### Security Considerations

- JWT-based authentication
- HTTPS for all communications
- Data encryption at rest
- Regular security updates
- Input validation and sanitization
