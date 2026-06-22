import os
import json
import pandas as pd
from schema_filtering_agent import SchemaFilteringAgent
from sql_generation_agent import SQLAgentLangGraph
from sql_validation_agent import SQLValidationAgent, QueryContext as ValidationContext
from response_formatting_agent import ResponseFormattingAgent
from models.data_models import QueryContext, AgentResponse
from dotenv import load_dotenv

def load_schema_file():
    """Load schema directly from JSON file for testing"""
    schema_path = os.path.join(
        os.path.dirname(__file__),
        "chroma_db",
        "schema_history",
        "C2C-LP-25-012_INSMA_2025-07-30T16-10-19_533067.json"
    )
    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('schema', {})
    except Exception as e:
        print(f"Error loading schema file: {str(e)}")
        return {}

def test_agents_pipeline():
    # Ensure environment variables are loaded
    load_dotenv()
    if not os.getenv("GOOGLE_API_KEY"):
        print("⚠️ GOOGLE_API_KEY not found in environment variables!")
        print("Please set your GOOGLE_API_KEY in the .env file")
        return
    
    # Initialize all agents
    schema_agent = SchemaFilteringAgent()
    sql_agent = SQLAgentLangGraph()
    validation_agent = SQLValidationAgent()
    formatting_agent = ResponseFormattingAgent()
    
    # Test parameters
    server_name = "C2C-LP-25-012"
    database_name = "INSMA"
    test_user_id = "test_user"
    
    # Test query and intent
    test_query = "What is the name of the equipment with serial number 'A-177792'?"
    test_intent = "data_retrieval"
    
    print("\n=== Testing Schema Filtering Agent ===\n")
    
    # Step 1: Load schema directly from file for testing
    print("1. Loading schema metadata...")
    schema = load_schema_file()
    
    if schema:
        print("✓ Schema loaded successfully")
        print(f"Number of tables in schema: {len(schema)}")
        print("\nAvailable tables:")
        for table_name in schema.keys():
            print(f"- {table_name}")
    else:
        print("✗ Failed to load schema")
        return
    
    # Step 2: Test schema analysis
    print("\n2. Analyzing schema relevance...")
    try:
        schema_analysis = schema_agent.analyze_schema_relevance(test_query, test_intent, schema)
        
        if schema_analysis:
            print("✓ Schema analysis completed")
            print("\nAnalysis Results:")
            print("-----------------")
            print(f"Relevant Tables: {', '.join(schema_analysis.get('relevant_tables', []))}")
            print("\nRelevant Columns:")
            for table, columns in schema_analysis.get('relevant_columns', {}).items():
                print(f"- {table}: {', '.join(columns)}")
            print("\nRelationships:")
            for rel in schema_analysis.get('relationships', []):
                print(f"- {rel['from_table']}.{rel['from_column']} → {rel['to_table']}.{rel['to_column']}")
            print(f"\nReasoning: {schema_analysis.get('reasoning', 'No reasoning provided')}")
        else:
            print("✗ Schema analysis failed")
            return
            
        # Step 3: Generate SQL Query
        print("\n=== Testing SQL Generation Agent ===\n")
        print("3. Generating SQL query...")
        
        # Create context for SQL generation
        context = {
            "user_question": test_query,
            "schema": schema,
            "table_name": None,  # We'll let the agent figure out tables from schema analysis
            "user_id": test_user_id,
            "relevant_metadata": {
                "relevant_tables": schema_analysis.get('relevant_tables', []),
                "relevant_columns": schema_analysis.get('relevant_columns', {}),
                "relationships": schema_analysis.get('relationships', []),
                "intent": test_intent
            }
        }
        
        # Generate SQL
        sql_result = sql_agent.generate_sql_with_cot(context)
        
        if sql_result.get("sql_query"):
            print("✓ SQL generation completed")
            print("\nGenerated SQL Query:")
            print("-----------------")
            generated_sql = sql_result.get("sql_query")
            print(generated_sql)
            
            # Step 4: Validate SQL Query
            print("\n=== Testing SQL Validation Agent ===\n")
            print("4. Validating SQL query...")
            
            validation_context = ValidationContext(
                sql_query=generated_sql,
                db_schema=schema
            )
            
            validation_result = validation_agent.process(validation_context)
            
            if validation_result.success:
                print("✓ SQL validation completed")
                print("\nValidation Results:")
                print("-----------------")
                if validation_result.data.get("requires_human_approval"):
                    print("⚠️ Query requires human review:")
                    print(f"Reason: {validation_result.data.get('review_reason')}")
                    if validation_result.data.get("fixed_query"):
                        print("\nSuggested Fixed Query:")
                        print(validation_result.data.get("fixed_query"))
                else:
                    print("✓ Query is valid")
                    validated_sql = validation_result.data.get("sql_query", generated_sql)
                    
                    # Step 5: Execute and Format Response
                    print("\n=== Testing Response Formatting Agent ===\n")
                    print("5. Executing query and formatting response...")
                    
                    formatting_context = QueryContext(
                        user_question=test_query,
                        db_schema=schema,
                        table_name=None,
                        user_id=test_user_id
                    )
                    
                    formatting_result = formatting_agent.process(formatting_context, validated_sql)
                    
                    if formatting_result.success:
                        print("✓ Query execution and response formatting completed")
                        print("\nFormatted Response:")
                        print("-----------------")
                        print(formatting_result.data.get("formatted_response"))
                        
                        if formatting_result.data.get("raw_results"):
                            print("\nRaw Results:")
                            print("-----------------")
                            print(json.dumps(formatting_result.data.get("raw_results"), indent=2))
                    else:
                        print("✗ Query execution or response formatting failed")
                        print(f"Error: {formatting_result.message}")
            else:
                print("✗ SQL validation failed")
                print(f"Error: {validation_result.message}")
        else:
            print("✗ SQL generation failed")
            print(f"Error: {sql_result.get('sql_generation_error', 'Unknown error')}")
            
    except Exception as e:
        print(f"Error during testing: {str(e)}")

if __name__ == "__main__":
    test_agents_pipeline()