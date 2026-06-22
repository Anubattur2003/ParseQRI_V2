import asyncio
import logging
import argparse
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from core.supervisor import SupervisorAgent

# Load environment variables
load_dotenv()

class TextToSQLSystem:
    """Main Text-to-SQL system class"""
    
    def __init__(self, server_name: str, database_name: str):
        """
        Initialize the Text-to-SQL system with database connection info
        
        Args:
            server_name: SQL Server instance name
            database_name: Database name
        """
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize supervisor
        self.supervisor = SupervisorAgent(server_name, database_name)
        
        self.logger.info("Text-to-SQL system initialized")
    
    async def process_query(self, query: str, user_id: str = "default_user") -> Dict[str, Any]:
        """Process a natural language query."""
        self.logger.info(f"Processing query: {query}")
        
        try:
            result = await self.supervisor.process_query(query, user_id)
            self.logger.info("Query processing completed successfully")
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing query: {str(e)}")
            raise
    
    async def process_query_with_cached_sql(
        self, 
        query: str, 
        cached_sql: str, 
        cached_db_schema: str,
        user_id: str = "default_user"
    ) -> Dict[str, Any]:
        """Process a query using cached SQL, bypassing SQL generation."""
        self.logger.info(f"Processing query with cached SQL: {query}")
        
        try:
            result = await self.supervisor.process_query_with_cached_sql(
                query=query,
                cached_sql=cached_sql,
                cached_db_schema=cached_db_schema,
                user_id=user_id
            )
            self.logger.info("Query processing with cache completed successfully")
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing query with cache: {str(e)}")
            raise

async def main():
    """Main entry point for the system."""
    parser = argparse.ArgumentParser(description='Text to SQL Agent')
    parser.add_argument('query', nargs='?', default="Show me the total sales by product category for the last month", help='Natural language query')
    parser.add_argument('--user', help='User ID')
    parser.add_argument('--db-id', help='Database ID')
    parser.add_argument('--upload', help='Upload file path')
    parser.add_argument('--table', help='Table name')
    
    args = parser.parse_args()
    
    # Initialize the system
    system = TextToSQLSystem()
    
    try:
        # Process the query
        result = await system.process_query(args.query)
        
        # Print the result in a format the API can parse
        print("\nSQL Query:")
        print(result.get('step_result', {}).get('sql_query', 'No SQL query generated'))
        
        print("\nResponse:")
        formatted_response = result.get('step_result', {}).get('formatted_response', {})
        if formatted_response and formatted_response.get('success'):
            print(formatted_response.get('message', 'Query processed successfully'))
        else:
            print("Query processing completed but no formatted response available")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())