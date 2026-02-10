"""Text2SQL agent for natural language to SQL conversion.

Supports both PostgreSQL and ClickHouse databases via the DB_TYPE
setting in config.py / .env.
"""

import re
from typing import Optional

from sqlalchemy import create_engine, inspect, text
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

from config import settings
from models import AgentResult
import socket


# ── Dialect-specific prompt templates ────────────────────────────────────

POSTGRES_SQL_RULES = """Rules:
1. Generate ONLY valid PostgreSQL syntax
2. Use only the tables and columns shown in the schema
3. Always use proper JOINs when accessing multiple tables
4. Use aggregation functions (COUNT, SUM, AVG, etc.) when appropriate
5. NEVER generate DELETE, UPDATE, INSERT, DROP, or any data-modifying queries
6. Return ONLY the SQL query, no explanations
7. Use double quotes for identifiers if they contain special characters or are case-sensitive
8. You can use ILIKE for case-insensitive matching
9. Use standard PostgreSQL date functions (NOW(), CURRENT_DATE, INTERVAL, etc.)"""

CLICKHOUSE_SQL_RULES = """Rules:
1. Generate ONLY valid ClickHouse SQL syntax
2. Use only the tables and columns shown in the schema
3. Always use proper JOINs when accessing multiple tables
4. Use aggregation functions (COUNT, SUM, AVG, etc.) when appropriate
5. NEVER generate DELETE, UPDATE, INSERT, DROP, ALTER, or any data-modifying queries
6. Return ONLY the SQL query, no explanations
7. Use backticks for identifiers if they contain special characters or are case-sensitive
8. Use ClickHouse date functions: toDate(), toDateTime(), today(), now(), etc.
9. Use ClickHouse string functions: like (case-sensitive) or ilike (case-insensitive)
10. Arrays can be accessed with array[index] syntax
11. Use FORMAT clause only if needed; by default omit it"""

TEXT2SQL_SYSTEM_PROMPT = """You are an expert SQL query generator. Your job is to convert natural language questions into valid {db_dialect} queries.

Database Schema:
{schema}

{sql_rules}

If you cannot generate a valid query for the question, respond with: CANNOT_GENERATE
"""

TEXT2SQL_USER_PROMPT = """Question: {query}

Generate the SQL query:"""

RESULT_FORMATTER_PROMPT = """You are a professional data analyst. Format the following database query results into a clear, professional response for an end customer.

Original Question: {query}

Query Results: {results}

Provide a concise, professional answer that:
1. Directly answers the question in natural language
2. Uses proper formatting (bullet points, numbers, etc. where appropriate)
3. Is easy to understand for non-technical users
4. Highlights key insights or patterns if relevant

Do not mention SQL, databases, or technical details."""


class Text2SQLAgent:
    """Agent that converts natural language to SQL and executes queries.
    
    Supports PostgreSQL and ClickHouse databases based on the DB_TYPE
    configuration setting.
    """
    
    def __init__(self):
        """Initialize the Text2SQL agent."""
        self.llm = ChatGroq(
            model=settings.llm_model,
            api_key=settings.groq_api_key,
            temperature=settings.llm_temperature,
        )

        # Force IPv4 resolution
        old_getaddrinfo = socket.getaddrinfo

        def ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
            return old_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

        socket.getaddrinfo = ipv4_only_getaddrinfo
        
        # Store the active dialect
        self.db_dialect = settings.db_dialect      # "PostgreSQL" or "ClickHouse"
        self.db_type = settings.db_type.lower()    # "postgres" or "clickhouse"
                
        # Initialize database connection using the active URL
        self.engine = create_engine(settings.active_database_url)
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", TEXT2SQL_SYSTEM_PROMPT),
            ("human", TEXT2SQL_USER_PROMPT),
        ])
        
        self.formatter_prompt = ChatPromptTemplate.from_messages([
            ("human", RESULT_FORMATTER_PROMPT),
        ])
    
    def _get_sql_rules(self) -> str:
        """Get dialect-specific SQL rules for the LLM prompt."""
        if self.db_type == "clickhouse":
            return CLICKHOUSE_SQL_RULES
        return POSTGRES_SQL_RULES
    
    def get_schema(self) -> str:
        """
        Get the database schema as a string.
        
        Works with both PostgreSQL and ClickHouse via SQLAlchemy inspect().
        
        Returns:
            Schema description
        """
        inspector = inspect(self.engine)
        schema_parts = []
        
        for table_name in inspector.get_table_names():
            columns = inspector.get_columns(table_name)
            column_defs = []
            for col in columns:
                col_type = str(col['type'])
                nullable = "NULL" if col.get('nullable', True) else "NOT NULL"
                column_defs.append(f"    {col['name']} {col_type} {nullable}")
            
            # Primary key introspection — ClickHouse doesn't always support this
            if self.db_type != "clickhouse":
                try:
                    pk_columns = inspector.get_pk_constraint(table_name).get('constrained_columns', [])
                    if pk_columns:
                        column_defs.append(f"    PRIMARY KEY ({', '.join(pk_columns)})")
                except Exception:
                    pass  # Skip PK introspection if not supported
            
            schema_parts.append(f"TABLE {table_name}:\n" + "\n".join(column_defs))
        
        if not schema_parts:
            return "No tables found in the database."
        
        return "\n\n".join(schema_parts)
    
    def _is_safe_query(self, sql: str) -> bool:
        """
        Check if the SQL query is safe to execute (read-only).
        
        Args:
            sql: SQL query string
            
        Returns:
            True if safe, False otherwise
        """
        # Normalize and check for dangerous keywords
        sql_upper = sql.upper().strip()
        dangerous_keywords = [
            'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE',
            'TRUNCATE', 'REPLACE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE'
        ]
        
        for keyword in dangerous_keywords:
            # Check if keyword appears as a word boundary
            if re.search(rf'\b{keyword}\b', sql_upper):
                return False
        
        return True
    
    def _clean_sql(self, sql: str) -> str:
        """
        Clean the generated SQL query.
        
        Args:
            sql: Raw SQL from LLM
            
        Returns:
            Cleaned SQL query
        """
        # Remove markdown code blocks if present
        sql = re.sub(r'```sql\s*', '', sql)
        sql = re.sub(r'```\s*', '', sql)
        sql = sql.strip()
        
        # Remove trailing semicolons
        sql = sql.rstrip(';')
        
        return sql
    
    def generate_sql(self, query: str) -> Optional[str]:
        """
        Generate SQL from natural language.
        
        The generated SQL dialect matches the configured DB_TYPE.
        
        Args:
            query: Natural language query
            
        Returns:
            SQL query string or None if generation failed
        """
        schema = self.get_schema()
        sql_rules = self._get_sql_rules()
        
        chain = self.prompt | self.llm
        
        try:
            response = chain.invoke({
                "schema": schema,
                "query": query,
                "db_dialect": self.db_dialect,
                "sql_rules": sql_rules,
            })
            
            sql = self._clean_sql(response.content)
            
            if "CANNOT_GENERATE" in sql.upper():
                return None
            
            return sql
        except Exception:
            return None
    
    def execute_sql(self, sql: str) -> list[dict]:
        """
        Execute a SQL query and return results.
        
        Args:
            sql: SQL query to execute
            
        Returns:
            List of result rows as dictionaries
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(sql))
            columns = result.keys()
            rows = result.fetchall()
            
            return [dict(zip(columns, row)) for row in rows]
    
    def _format_results_professionally(self, query: str, results: list[dict]) -> str:
        """
        Format query results into professional, customer-friendly text.
        
        Args:
            query: Original user query
            results: Query results
            
        Returns:
            Formatted professional response
        """
        if not results:
            return "No results found for your query."
        
        # Use LLM to format results professionally
        chain = self.formatter_prompt | self.llm
        
        try:
            response = chain.invoke({
                "query": query,
                "results": str(results[:20])  # Limit to first 20 for formatting
            })
            return response.content
        except Exception:
            # Fallback to simple formatting
            if len(results) == 1 and len(results[0]) == 1:
                key, value = list(results[0].items())[0]
                return f"The answer is: **{value}**"
            else:
                return f"Found {len(results)} result(s) matching your query."
    
    def query(self, query: str) -> AgentResult:
        """
        Convert natural language to SQL, execute, and return results.
        
        Args:
            query: Natural language question about the data
            
        Returns:
            AgentResult with the query results
        """
        # Generate SQL
        sql = self.generate_sql(query)
        
        if not sql:
            return AgentResult(
                agent_type="sql",
                content="I couldn't generate a valid query for your question. Please try rephrasing it.",
                sources=[],
                metadata={"error": "sql_generation_failed"}
            )
        
        # Validate query is safe
        if not self._is_safe_query(sql):
            return AgentResult(
                agent_type="sql",
                content="This query was rejected for safety reasons.",
                sources=[],
                metadata={"error": "unsafe_query", "sql": sql}
            )
        
        # Execute query
        try:
            results = self.execute_sql(sql)
            
            # Format results professionally
            content = self._format_results_professionally(query, results)
            
            # Prepare metadata
            metadata = {
                "row_count": len(results),
                "db_type": self.db_type,
                "results": results[:100]  # Include up to 100 results in metadata
            }
            
            # Only include SQL query if debugging is enabled
            if settings.show_sql_queries:
                metadata["sql"] = sql
            
            return AgentResult(
                agent_type="sql",
                content=content,
                sources=[f"Database ({self.db_dialect})"],
                metadata=metadata
            )
        except Exception as e:
            return AgentResult(
                agent_type="sql",
                content=f"An error occurred while processing your query. Please try again.",
                sources=[],
                metadata={"error": str(e), "sql": sql if settings.show_sql_queries else None}
            )
