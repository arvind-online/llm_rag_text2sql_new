"""Setup demo data for testing the LangGraph router."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from config import settings


def setup_database():
    """Create demo PostgreSQL tables with sample data."""
    engine = create_engine(settings.database_url)
    
    with engine.connect() as conn:
        # Create customers table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS customers (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                city TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # Create products table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT,
                price NUMERIC(10,2) NOT NULL,
                stock INTEGER DEFAULT 0
            )
        """))
        
        # Create orders table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                customer_id INTEGER REFERENCES customers(id),
                product_id INTEGER REFERENCES products(id),
                quantity INTEGER NOT NULL,
                total_amount NUMERIC(10,2) NOT NULL,
                order_date DATE DEFAULT CURRENT_DATE
            )
        """))
        
        # Check if data exists
        result = conn.execute(text("SELECT COUNT(*) FROM customers"))
        count = result.scalar()
        
        if count == 0:
            # Insert sample customers
            conn.execute(text("""
                INSERT INTO customers (name, email, city) VALUES
                ('Alice Johnson', 'alice@example.com', 'New York'),
                ('Bob Smith', 'bob@example.com', 'Los Angeles'),
                ('Carol White', 'carol@example.com', 'Chicago'),
                ('David Brown', 'david@example.com', 'New York'),
                ('Eve Davis', 'eve@example.com', 'San Francisco')
            """))
            
            # Insert sample products
            conn.execute(text("""
                INSERT INTO products (name, category, price, stock) VALUES
                ('Laptop Pro', 'Electronics', 1299.99, 50),
                ('Wireless Mouse', 'Electronics', 49.99, 200),
                ('Office Chair', 'Furniture', 299.99, 30),
                ('Standing Desk', 'Furniture', 599.99, 15),
                ('Monitor 27"', 'Electronics', 399.99, 75)
            """))
            
            # Insert sample orders
            conn.execute(text("""
                INSERT INTO orders (customer_id, product_id, quantity, total_amount, order_date) VALUES
                (1, 1, 1, 1299.99, '2024-01-15'),
                (2, 2, 2, 99.98, '2024-01-16'),
                (1, 3, 1, 299.99, '2024-01-17'),
                (3, 5, 2, 799.98, '2024-01-18'),
                (4, 4, 1, 599.99, '2024-01-19'),
                (5, 1, 1, 1299.99, '2024-01-20'),
                (2, 3, 2, 599.98, '2024-01-21'),
                (3, 2, 3, 149.97, '2024-01-22')
            """))
            
            print("✓ Sample data inserted")
        else:
            print(f"✓ Database already has {count} customers, skipping data insertion")
        
        conn.commit()
    
    print(f"✓ Connected to PostgreSQL: {settings.pghost}")


def setup_documents():
    """Add sample documents to ChromaDB for RAG."""
    from agents.rag_agent import RAGAgent
    
    rag = RAGAgent()
    
    documents = [
        {
            "content": """LangGraph is a library for building stateful, multi-actor applications with LLMs. 
            It extends LangChain with the ability to coordinate multiple chains (or actors) across multiple 
            steps of computation in a cyclic manner. Key features include:
            - State management across conversation turns
            - Conditional branching and routing
            - Support for human-in-the-loop workflows
            - Built-in persistence and checkpointing""",
            "metadata": {"source": "LangGraph Documentation", "topic": "overview"}
        },
        {
            "content": """RAG (Retrieval-Augmented Generation) is a technique that combines retrieval-based 
            and generation-based approaches. It works by:
            1. Converting documents into embeddings and storing them in a vector database
            2. When a query arrives, finding the most relevant documents
            3. Providing those documents as context to an LLM
            4. Generating a response based on the retrieved context
            This approach reduces hallucinations and allows LLMs to access up-to-date information.""",
            "metadata": {"source": "AI Techniques Guide", "topic": "rag"}
        },
        {
            "content": """Text2SQL (Text-to-SQL) is a natural language processing task that converts 
            natural language questions into SQL queries. Best practices include:
            - Providing clear schema information to the LLM
            - Using few-shot examples for complex queries
            - Implementing safety checks to prevent SQL injection
            - Validating generated queries before execution
            - Limiting query capabilities to SELECT statements only""",
            "metadata": {"source": "Database AI Integration", "topic": "text2sql"}
        },
        {
            "content": """Our company follows a hybrid query approach for complex analytics questions. 
            When a user asks about trends or comparisons, we combine:
            - Document knowledge for industry benchmarks and best practices
            - Database queries for actual company metrics and statistics
            This provides comprehensive answers grounded in both external knowledge and internal data.""",
            "metadata": {"source": "Company Knowledge Base", "topic": "hybrid_approach"}
        },
        {
            "content": """Customer satisfaction best practices:
            - Respond to inquiries within 24 hours
            - Maintain a satisfaction score above 4.5/5
            - Follow up on all negative feedback
            - Implement regular customer surveys
            Industry benchmark: Top companies achieve 95% customer retention rate.""",
            "metadata": {"source": "Industry Report 2024", "topic": "customer_satisfaction"}
        }
    ]
    
    for doc in documents:
        doc_id = rag.add_document(doc["content"], doc["metadata"])
        print(f"✓ Added document: {doc['metadata']['source']} (ID: {doc_id[:8]}...)")
    
    print(f"✓ Documents stored in: {settings.chroma_persist_dir_resolved}")


def main():
    """Run all setup tasks."""
    print("Setting up demo data...\n")
    
    print("1. Setting up PostgreSQL database...")
    setup_database()
    
    print("\n2. Adding documents to ChromaDB...")
    setup_documents()
    
    print("\n✓ Setup complete! You can now run the API server with:")
    print("  uvicorn main:app --reload")


if __name__ == "__main__":
    main()
