🛠 Solutions (From Simple to Advanced)
Solution 1: Simple Caching (Low Effort, High Impact)
Cache the schema at startup and refresh periodically:

python
class Text2SQLAgent:
    def __init__(self):
        ...
        self._cached_schema: Optional[str] = None
        self._schema_cached_at: float = 0
        self.SCHEMA_TTL = 300  # 5 minutes
    
    def get_schema(self) -> str:
        import time
        now = time.time()
        if self._cached_schema and (now - self._schema_cached_at < self.SCHEMA_TTL):
            return self._cached_schema
        
        # Existing introspection logic...
        self._cached_schema = schema_string
        self._schema_cached_at = now
        return self._cached_schema
Benefit: Reduces DB introspection from N queries to N/TTL queries

Solution 2: Schema Summarization (Medium Effort)
Instead of sending the raw schema, send a compressed version:

python
COMPACT_SCHEMA = """Tables: users(id,name,email), orders(id,user_id,total,date), 
products(id,name,price), order_items(order_id,product_id,qty)
Relations: orders.user_id→users.id, order_items→orders,products"""
Benefit: Reduces tokens by 50-80%

Solution 3: Selective Schema Injection (Advanced)
Only include tables relevant to the query using a two-step approach:

python
def get_relevant_tables(self, query: str) -> list[str]:
    """Use LLM to identify which tables might be needed."""
    # Quick classification call
    response = self.llm.invoke(
        f"Which tables might be needed for: '{query}'? "
        f"Available: {self.get_table_names()}. Reply with comma-separated list."
    )
    return response.content.split(',')
def get_filtered_schema(self, tables: list[str]) -> str:
    """Return schema for only the specified tables."""
    return "\n".join(
        schema for table, schema in self._table_schemas.items() 
        if table in tables
    )
Benefit: For large databases (50+ tables), can reduce schema size by 90%

Solution 4: Semantic Schema Caching with Embeddings (Most Advanced)
Pre-compute embeddings for table descriptions and retrieve only relevant ones:

python
# At init time
self.schema_embeddings = {
    table: embed(f"{table}: {description}") 
    for table, description in schema_descriptions.items()
}
# At query time
query_embedding = embed(user_query)
relevant_tables = top_k_similar(query_embedding, self.schema_embeddings, k=5)
schema = self.get_filtered_schema(relevant_tables)
Benefit: Most efficient for very large databases, minimal LLM calls

