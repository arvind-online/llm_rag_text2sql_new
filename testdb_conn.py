
import sys
import os
from sqlalchemy import text, inspect

# Add current directory to path so imports work if running from root
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from agents.text2sql_agent import Text2SQLAgent
except ImportError as e:
    print(f"Error importing Text2SQLAgent: {e}")
    print("Make sure you are running this script from the project root.")
    sys.exit(1)

def main():
    print("Initializing Text2SQLAgent...")
    try:
        # This will initialize the agent, including the LLM (ChatGroq) and the Database Engine
        agent = Text2SQLAgent()
    except Exception as e:
        print(f"Failed to initialize Text2SQLAgent: {e}")
        print("Please check your .env file for GROQ_API_KEY and database credentials.")
        sys.exit(1)

    print("Agent initialized successfully.")
    print(f"Database type: {agent.db_dialect} (DB_TYPE={agent.db_type})")
    
    print("\n--- Checking database connection and schema ---")
    try:
        # Check connection implicitly via get_schema
        # get_schema uses inspector(self.engine) which connects to the DB
        print("Attempting to fetch database schema...")
        schema = agent.get_schema()
        
        if not schema or "No tables found" in schema:
            print("Connection successful, but no tables found in the database or schema is empty.")
        else:
            print("Schema retrieved successfully.")
            print("\nList of Tables found:")
            
            # Simple parsing to extract table names for display
            lines = schema.split('\n')
            tables = [line.replace('TABLE ', '').replace(':', '').strip() for line in lines if line.startswith('TABLE ')]
            
            if not tables:
                # If parsing failed but schema is not empty, just print the start
                print("(Could not parse table names clearly, showing raw schema start)")
            
            for t in tables:
                print(f"- {t}")
            
            print("\n--- Schema Sample (First 500 chars) ---")
            print(schema[:500] + ("..." if len(schema) > 500 else ""))

    except Exception as e:
        print(f"Error connecting to database or reading schema: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n--- Testing simple query execution ---")
    try:
        # Execute a simple test query
        test_query = "SELECT 1 as connection_test"
        print(f"Executing: {test_query}")
        result = agent.execute_sql(test_query)
        print(f"Query Result: {result}")
        print("Database connection execution test: PASSED")
        
    except Exception as e:
        print(f"Error executing test query: {e}")
        print("Database connection execution test: FAILED")

if __name__ == "__main__":
    main()
