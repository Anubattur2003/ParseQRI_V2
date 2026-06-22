#!/usr/bin/env python3
"""
Test script for database_agent.py connection and metadata extraction
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the Text_to_Sql agents directory to Python path
sys.path.append(str(Path(__file__).parent / "ParseQri_Backend" / "Text_to_Sql" / "agents"))

try:
    from database_agent import DatabaseAgent
except ImportError as e:
    print(f"Error importing database_agent: {e}")
    print("Please ensure the Text_to_Sql module is properly set up")
    sys.exit(1)

async def test_database_connection():
    """Test database connection and metadata extraction"""
    
    # Use sample database credentials (update these for your environment)
    server_name = "C2C-LP-25-012"  # Replace with your SQL Server name
    database_name = "INSMA"        # Replace with your database name
    
    print(f"Testing connection to SQL Server: {server_name}")
    print(f"Database: {database_name}")
    print("-" * 50)
    
    try:
        # Create database agent
        agent = DatabaseAgent(server_name, database_name)
        print("✓ Database agent created successfully")
        
        # Test connection
        print("\n1. Testing database connection...")
        is_connected, version, info = await agent.test_connection()
        
        if is_connected:
            print(f"✓ Connection test successful!")
            print(f"  Server Version: {version}")
            print(f"  Info: {info}")
        else:
            print(f"✗ Connection test failed: {info}")
            return False
        
        # Establish persistent connection and extract metadata
        print("\n2. Establishing connection and extracting metadata...")
        success, message, schema_markdown = await agent.establish_connection()
        
        if success:
            print(f"✓ Connection established successfully!")
            print(f"  Message: {message}")
            
            # Display schema summary
            print(f"\n3. Schema Summary:")
            print("-" * 30)
            if agent.engine:
                with agent.engine.connect() as connection:
                    schema = agent.get_database_schema(connection)
                    
                    if schema:
                        print(f"Found {len(schema)} tables:")
                        for table_name, table_info in schema.items():
                            column_count = len(table_info['columns'])
                            fk_count = len(table_info.get('foreign_keys', []))
                            print(f"  - {table_name}: {column_count} columns, {fk_count} foreign keys")
                    else:
                        print("No tables found or error retrieving schema")
            
            # Display schema markdown (truncated)
            print(f"\n4. Schema Markdown (first 500 chars):")
            print("-" * 40)
            print(schema_markdown[:500] + "..." if len(schema_markdown) > 500 else schema_markdown)
            
            # Get schema history
            print(f"\n5. Schema History:")
            print("-" * 20)
            history = agent.get_schema_history()
            print(history[:300] + "..." if len(history) > 300 else history)
            
            return True
        else:
            print(f"✗ Connection establishment failed: {message}")
            return False
            
    except Exception as e:
        print(f"✗ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function"""
    print("=== Database Agent Connection Test ===")
    print("This script tests the database_agent.py connection and metadata extraction")
    print()
    
    # Check if running on Windows (required for Windows Authentication)
    if os.name != 'nt':
        print("Warning: This script is designed for Windows with SQL Server using Windows Authentication")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print("Exiting...")
            return
    
    # Run the test
    success = asyncio.run(test_database_connection())
    
    print("\n" + "=" * 50)
    if success:
        print("✓ All tests passed! Database agent is working correctly.")
        print("✓ Metadata extraction is functional.")
        print("✓ The system is ready for use.")
    else:
        print("✗ Some tests failed. Please check your database configuration.")
        print("✗ Ensure SQL Server is running and accessible.")
        print("✗ Verify Windows Authentication is enabled.")
    
    print("\nNext steps:")
    print("1. Start the backend server: python ParseQri_Backend/app/main.py")
    print("2. Start the frontend: cd frontend && npm run dev")
    print("3. Test the connection through the web interface")

if __name__ == "__main__":
    main()
