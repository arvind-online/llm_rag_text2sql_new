"""Test script to demonstrate SQL-Aware Memory in Text2SQLAgent."""

from agents.text2sql_agent import Text2SQLAgent


def test_memory_feature():
    """Test the memory feature with follow-up queries."""
    print("=" * 80)
    print("Testing SQL-Aware Memory Feature")
    print("=" * 80)
    
    agent = Text2SQLAgent()
    
    # Test 1: Initial query
    print("\n### Query 1: Initial query")
    query1 = "Show me all users"
    print(f"User: {query1}")
    result1 = agent.query(query1)
    print(f"Answer: {result1.content}")
    if result1.metadata.get("sql"):
        print(f"SQL: {result1.metadata['sql']}")
    
    # Test 2: Follow-up query using pronoun
    print("\n### Query 2: Follow-up using pronoun 'them'")
    query2 = "How many of them are there?"
    print(f"User: {query2}")
    result2 = agent.query(query2)
    print(f"Answer: {result2.content}")
    if result2.metadata.get("sql"):
        print(f"SQL: {result2.metadata['sql']}")
    
    # Test 3: Another follow-up
    print("\n### Query 3: Another follow-up")
    query3 = "Filter those results by active status"
    print(f"User: {query3}")
    result3 = agent.query(query3)
    print(f"Answer: {result3.content}")
    if result3.metadata.get("sql"):
        print(f"SQL: {result3.metadata['sql']}")
    
    # Show conversation history
    print("\n" + "=" * 80)
    print("Conversation History in Memory:")
    print("=" * 80)
    for i, ctx in enumerate(agent.query_history, 1):
        print(f"\n{i}. User Query: {ctx.user_query}")
        print(f"   SQL: {ctx.generated_sql}")
        print(f"   Result: {ctx.result_summary}")
    
    print("\n" + "=" * 80)
    print("Memory Test Complete!")
    print("=" * 80)


if __name__ == "__main__":
    test_memory_feature()
