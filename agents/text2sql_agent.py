"""Text2SQL agent for natural language to SQL conversion."""

import re
from typing import Optional

from sqlalchemy import create_engine, inspect, text
from langchain_core.prompts import ChatPromptTemplate

from config import settings, get_llm
from models import AgentResult, ConversationTurn
import socket


def get_text2sql_system_prompt(db_type: str) -> str:
    """Get the appropriate system prompt based on database type."""
    dialect = "ClickHouse" if db_type.lower() == "clickhouse" else "PostgreSQL"
    
    return f"""You are an expert SQL query generator. Your job is to convert natural language questions into valid {dialect} queries.

Database Schema:
{{schema}}

Conversation History:
{{history}}

Rules:
1. Generate ONLY valid {dialect} syntax
2. Use only the tables and columns shown in the schema
3. Always use proper JOINs when accessing multiple tables
4. Use aggregation functions (COUNT, SUM, AVG, etc.) when appropriate
5. NEVER generate DELETE, UPDATE, INSERT, DROP, or any data-modifying queries
6. Return ONLY the SQL query, no explanations
7. Use double quotes for identifiers if they contain special characters or are case-sensitive
8. Use the conversation history to understand context for follow-up questions
9. If the user refers to previous results or uses pronouns like "it", "those", "that", "them", resolve them based on the conversation history
10. For follow-up queries like "show more details" or "filter those", use the previous SQL context to build upon it
11. Always use the metric system: distances in kilometers (km), speeds in km/h. the database stores values in metric system only. 


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
5. Always express distances in kilometers (km) and speeds in km/h — never in miles or mph
6. All timestamps/datetimes in the results are in UTC. Convert and display them in the {timezone} timezone.

Do not mention SQL, databases, or technical details."""


class Text2SQLAgent:
    """Agent that converts natural language to SQL and executes queries."""
    
    def __init__(self):
        """Initialize the Text2SQL agent."""
        self.llm = get_llm()

        # Force IPv4 resolution
        old_getaddrinfo = socket.getaddrinfo

        def ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
            return old_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

        socket.getaddrinfo = ipv4_only_getaddrinfo
                
        # Initialize database connection based on db_type
        self.engine = create_engine(settings.database_url)

        # Get appropriate system prompt based on database type
        system_prompt = get_text2sql_system_prompt(settings.db_type)
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", TEXT2SQL_USER_PROMPT),
        ])
        
        self.formatter_prompt = ChatPromptTemplate.from_messages([
            ("human", RESULT_FORMATTER_PROMPT),
        ])
    
    def get_schema(self) -> str:
        """
        Get the database schema as a string.
        Only includes tables specified in settings.table_filter_list.
        If table_filter_list is empty, includes all tables.
        
        Returns:
            Schema description
        """
        inspector = inspect(self.engine)
        schema_parts = []
        allowed_tables = settings.allowed_tables
        
        for table_name in inspector.get_table_names():
            # Skip table if filter is specified and table is not in the list
            if allowed_tables and table_name not in allowed_tables:
                continue
            
            columns = inspector.get_columns(table_name)
            column_defs = []
            for col in columns:
                col_type = str(col['type'])
                nullable = "NULL" if col.get('nullable', True) else "NOT NULL"
                column_defs.append(f"    {col['name']} {col_type} {nullable}")
            
            pk_columns = inspector.get_pk_constraint(table_name).get('constrained_columns', [])
            if pk_columns:
                column_defs.append(f"    PRIMARY KEY ({', '.join(pk_columns)})")
            
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

    def _format_history(self, history: list[ConversationTurn]) -> str:
        """Format frontend-supplied conversation history into a context string."""
        if not history:
            return "No previous queries in this session."
        context_parts = []
        for i, turn in enumerate(history[-5:], 1):
            entry = f"Query {i}:\n  User asked: \"{turn.user}\""
            if turn.sql_query:
                entry += f"\n  SQL executed: {turn.sql_query}"
            entry += f"\n  Assistant answered: {turn.assistant[:300]}"
            context_parts.append(entry)
        return "\n\n".join(context_parts)

    def generate_sql(self, query: str, history: list[ConversationTurn] | None = None) -> Optional[str]:
        """
        Generate SQL from natural language.
        
        Args:
            query: Natural language query
            
        Returns:
            SQL query string or None if generation failed
        """
        schema = self.get_schema()
        history_str = self._format_history(history or [])

        chain = self.prompt | self.llm

        try:
            response = chain.invoke({
                "schema": schema,
                "history": history_str,
                "query": query,
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
    
    def _format_results_professionally(self, query: str, results: list[dict], timezone: str = "UTC") -> str:
        """
        Format query results into professional, customer-friendly text.

        Args:
            query: Original user query
            results: Query results
            timezone: IANA timezone name for displaying times

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
                "results": str(results[:20]),  # Limit to first 20 for formatting
                "timezone": timezone,
            })
            return response.content
        except Exception:
            # Fallback to simple formatting
            if len(results) == 1 and len(results[0]) == 1:
                key, value = list(results[0].items())[0]
                return f"The answer is: **{value}**"
            else:
                return f"Found {len(results)} result(s) matching your query."
    
    def query(self, query: str, history: list[ConversationTurn] | None = None, timezone: str = "UTC") -> AgentResult:
        """
        Convert natural language to SQL, execute, and return results.
        
        Args:
            query: Natural language question about the data
            
        Returns:
            AgentResult with the query results
        """
        # Generate SQL
        sql = self.generate_sql(query, history)
        
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
            content = self._format_results_professionally(query, results, timezone)
            
            # Prepare metadata
            metadata = {
                "row_count": len(results),
                "results": results[:100]  # Include up to 100 results in metadata
            }
            
            # Only include SQL query if debugging is enabled
            if settings.show_sql_queries:
                metadata["sql"] = sql
            
            return AgentResult(
                agent_type="sql",
                content=content,
                sources=["Database"],
                metadata=metadata
            )
        except Exception as e:
            return AgentResult(
                agent_type="sql",
                content=f"An error occurred while processing your query. Please try again.",
                sources=[],
                metadata={"error": str(e), "sql": sql if settings.show_sql_queries else None}
            )
