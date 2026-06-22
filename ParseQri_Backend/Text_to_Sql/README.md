# Text-to-SQL Agent System

A modular system for converting natural language queries to SQL using LangGraph with human-in-the-loop verification.

## Architecture

The system consists of six main agents:

1. **Database Agent**: Handles database connections, metadata extraction, and ChromaDB indexing
2. **Intent Classifier**: Classifies the intent of user queries
3. **Schema Understanding**: Analyzes database schema based on query intent
4. **SQL Generation**: Generates MSSQL queries
5. **SQL Validation**: Validates and fixes generated queries
6. **Response Formatting**: Formats query results in natural language

## Features

- LangGraph-based workflow orchestration
- Checkpoint-based time travel for error recovery
- Human-in-the-loop verification at critical steps
- Automatic error recovery through checkpoints
- Modular agent architecture

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure the system:
- Edit `config.json` with your database and agent settings
- Ensure MSSQL ODBC drivers are installed

3. Initialize the environment:
```bash
python -m Text_to_Sql.main
```

## Usage

```python
from Text_to_Sql.main import TextToSQLSystem

# Initialize the system
system = TextToSQLSystem()

# Process a query
result = await system.process_query("Show me total sales by product for last month")
```

## Project Structure

```
Text_To_SQL/
├── __init__.py
├── README.md
├── config.json
├── main.py
├── requirements.txt
├── agents/           # Individual agent implementations
├── cache/           # Temporary data and ChromaDB storage
├── core/            # Core system components
├── models/          # Data models and schemas
├── tests/          # Test suite
└── utils/          # Utility functions and helpers
```

## Development

- Each agent is designed to be modular and replaceable
- Use the checkpoint system for debugging and recovery
- Add tests in the `tests/` directory
- Configure logging in `config.json`

## License

MIT License