# Utilities

This directory contains utility functions and helper classes used throughout the Text-to-SQL system.

## Contents

- Database connection helpers
- Configuration management
- Logging utilities
- Type conversion utilities
- Error handling utilities
- Testing helpers

## Usage

Import utilities as needed:

```python
from utils.database import create_connection
from utils.config import load_config
from utils.logging import setup_logging
```

## Adding New Utilities

1. Create a new module in this directory
2. Add appropriate tests in the tests directory
3. Update this README with new functionality
4. Ensure proper error handling and logging