import gradio as gr
import asyncio
import json
from core.supervisor import SupervisorAgent
from agents.database_agent import DatabaseAgent

# Global supervisor instance
supervisor = None

async def test_connection(server_name: str, database_name: str) -> str:
    """Test if database connection is possible."""
    try:
        # Initialize database agent for testing
        agent = DatabaseAgent(server_name, database_name)
        
        # Test connection
        is_connected, version, info = await agent.test_connection()
        
        if is_connected:
            return f"""✅ Connection Test Successful!

Server Version: {version}
{info}

Click 'Connect to Database' to establish connection and fetch schema metadata."""
        else:
            return f"❌ Connection test failed: {info}"
            
    except Exception as e:
        return f"❌ Error testing connection: {str(e)}"

async def establish_connection(server_name: str, database_name: str) -> tuple[str, str, str]:
    """Establish database connection and fetch schema metadata."""
    global supervisor
    try:
        # Initialize supervisor with database connection
        supervisor = SupervisorAgent(server_name, database_name)
        
        # Establish connection and get schema
        success, message, schema_markdown = await supervisor.database_agent.establish_connection()
        
        if success:
            # If connection successful, also get schema history
            history = supervisor.database_agent.get_schema_history()
            return (
                f"✅ Connection Established! {message}",
                schema_markdown,  # Current schema
                history  # Schema history
            )
        else:
            supervisor = None  # Reset on failure
            return (
                f"❌ Failed to establish connection: {message}",
                "No current schema available.",
                "No schema history available."
            )
            
    except Exception as e:
        supervisor = None  # Reset on error
        return (
            f"❌ Error: {str(e)}",
            "An error occurred while establishing connection.",
            "No schema history available."
        )

def format_step_output(step_results: dict, step_name: str, error: str = None) -> str:
    """Format the output for a specific processing step."""
    if error:
        return f"❌ Error: {error}"
        
    # Intent Classification
    if step_name == "intent" and "intent" in step_results:
        return f"""### Intent Classification
**Detected Intent**: {step_results['intent']}
This query appears to be a {step_results['intent'].lower()} request."""
    
    # Schema Analysis
    if step_name == "schema_analysis" and "schema_analysis" in step_results:
        schema = step_results["schema_analysis"]
        output = "### Schema Analysis\n"
        output += f"**Relevant Tables**: {', '.join(schema.get('relevant_tables', []))}\n\n"
        output += "**Relevant Columns**:\n"
        for table, columns in schema.get('relevant_columns', {}).items():
            output += f"- {table}: {', '.join(columns)}\n"
        output += f"\n**Reasoning**: {schema.get('reasoning', '')}"
        return output
    
    # SQL Generation
    if step_name == "sql_query" and "sql_query" in step_results:
        return f"""### Generated SQL Query
```sql
{step_results['sql_query']}
```"""
    
    # SQL Validation
    if step_name == "validation" and "validation" in step_results:
        validation = step_results["validation"]
        output = "### SQL Validation\n"
        if validation.get("success"):
            output += "✅ Query validated successfully\n"
            if validation.get("data", {}).get("requires_human_approval"):
                output += "⚠️ Requires human review:\n"
                output += f"Reason: {validation['data'].get('review_reason', '')}"
        else:
            output += f"❌ Validation failed: {validation.get('message', '')}"
        return output
    
    # Query Results
    if step_name == "formatted_response" and "formatted_response" in step_results:
        formatted = step_results["formatted_response"]
        output = "### Query Results\n"
        if formatted.get("success"):
            output += formatted.get("data", {}).get("formatted_response", "No results")
            raw_results = formatted.get("data", {}).get("raw_results")
            if raw_results:
                output += "\n\n**Raw Results**:\n```json\n"
                output += json.dumps(raw_results, indent=2)
                output += "\n```"
        else:
            output += f"❌ Formatting failed: {formatted.get('message', '')}"
        return output
    
    return "Waiting for processing..."

async def process_query_async(query: str) -> tuple[str, str, str, str, str]:
    """Process the natural language query through all agents."""
    global supervisor
    try:
        if not supervisor:
            no_connection_msg = "⚠️ No database connection. Please test connection and connect to database first."
            return (no_connection_msg,) * 5
            
        # Process the query through the supervisor
        result = await supervisor.process_query(query)
        
        # Check for overall error
        if result.get("error"):
            error_msg = f"❌ Error: {result['error']}"
            return (error_msg,) * 5
        
        # Format each step's output (supervisor uses different state structure)
        # Map the supervisor state to the expected format
        step_results = {
            "intent": result.get("intent", {}).get("type", ""),
            "schema_analysis": {
                "relevant_tables": result.get("schema_context", {}).get("tables", []),
                "relevant_columns": result.get("schema_context", {}).get("columns", {}),
                "reasoning": f"Found {len(result.get('schema_context', {}).get('tables', []))} relevant tables"
            },
            "sql_query": result.get("sql", {}).get("query", ""),
            "validation": {
                "success": result.get("validation", {}).get("is_valid", False),
                "message": "Query validated" if result.get("validation", {}).get("is_valid") else "Validation failed"
            },
            "formatted_response": {
                "success": result.get("success", False),
                "data": {
                    "formatted_response": result.get("final_response", ""),
                    "raw_results": result.get("execution", {}).get("rows", [])
                }
            }
        }
        error = result.get("error")
        
        intent_output = format_step_output(step_results, "intent", error)
        schema_output = format_step_output(step_results, "schema_analysis", error)
        sql_output = format_step_output(step_results, "sql_query", error)
        validation_output = format_step_output(step_results, "validation", error)
        results_output = format_step_output(step_results, "formatted_response", error)
        
        return (
            intent_output,
            schema_output,
            sql_output,
            validation_output,
            results_output
        )
        
    except Exception as e:
        error_msg = f"❌ Error processing query: {str(e)}"
        return (error_msg,) * 5

def process_query(query: str) -> tuple[str, str, str, str, str]:
    """Synchronous wrapper for the async process_query function."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(process_query_async(query))
    finally:
        loop.close()

# Create the Gradio interface
with gr.Blocks(title="Text to SQL Assistant") as demo:
    gr.Markdown("""
    # Text to SQL Assistant
    Convert natural language questions into SQL queries with detailed analysis.
    """)
    
    with gr.Row():
        # Left Column: Input Section
        with gr.Column(scale=1):
            # Database Connection
            gr.Markdown("### 1. Database Connection")
            with gr.Row():
                server_name = gr.Textbox(
                    label="Server Name",
                    placeholder="Enter SQL Server name",
                    value="C2C-LP-25-012"
                )
                database_name = gr.Textbox(
                    label="Database Name",
                    placeholder="Enter database name",
                    value="INSMA"
                )
            with gr.Row():
                test_btn = gr.Button("Test Connection", variant="secondary")
                connect_btn = gr.Button("Connect to Database", variant="primary")
            connection_status = gr.Markdown("Not connected to database")
            
            # Schema Information in Accordions
            with gr.Accordion("Database Schema Information", open=False):
                current_schema = gr.Markdown("No current schema available")
            with gr.Accordion("Schema History", open=False):
                schema_history = gr.Markdown("No schema history available")
            
            # Query Input
            gr.Markdown("### 2. Enter Your Question")
            query_input = gr.Textbox(
                label="Natural Language Query",
                placeholder="e.g., 'What is the name of the equipment with serial number A-177792?'",
                lines=3
            )
            process_btn = gr.Button("Process Query", variant="primary")
            
            # Examples
            gr.Markdown("""
            ### Example Questions
            - What is the name of the equipment with serial number 'A-177792'?
            - Show me all defects reported for ship DART_NUMBER 12345
            - Find all equipment whose name contains 'BOLLARD'
            """)
        
        # Right Column: Processing Pipeline
        with gr.Column(scale=2):
            gr.Markdown("### Processing Pipeline")
            
            # Step 1 & 2
            with gr.Row():
                with gr.Column():
                    gr.Markdown("#### Step 1: Intent Classification")
                    intent_output = gr.Markdown("Waiting for query...")
                
                with gr.Column():
                    gr.Markdown("#### Step 2: Schema Analysis")
                    schema_output = gr.Markdown("Waiting for query...")
            
            # Step 3 & 4
            with gr.Row():
                with gr.Column():
                    gr.Markdown("#### Step 3: SQL Generation")
                    sql_output = gr.Markdown("Waiting for query...")
                
                with gr.Column():
                    gr.Markdown("#### Step 4: SQL Validation")
                    validation_output = gr.Markdown("Waiting for query...")
            
            # Step 5: Results
            gr.Markdown("#### Step 5: Query Results")
            results_output = gr.Markdown("Waiting for query...")
    
    # Wire up the event handlers
    test_btn.click(
        fn=test_connection,
        inputs=[server_name, database_name],
        outputs=[connection_status]
    )
    
    connect_btn.click(
        fn=establish_connection,
        inputs=[server_name, database_name],
        outputs=[connection_status, current_schema, schema_history]
    )
    
    process_btn.click(
        fn=process_query,
        inputs=[query_input],
        outputs=[
            intent_output,
            schema_output,
            sql_output,
            validation_output,
            results_output
        ]
    )

if __name__ == "__main__":
    demo.launch(
        share=True,
        inbrowser=True
    )