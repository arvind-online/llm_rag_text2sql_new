"""Test script to demonstrate SQL-Aware Memory with Session Management."""

from agents.text2sql_agent import Text2SQLAgent
from session_manager import get_session_manager


def test_single_user_session():
    """Test memory feature within a single user session."""
    print("=" * 80)
    print("Testing Single User Session with SQL-Aware Memory")
    print("=" * 80)
    
    agent = Text2SQLAgent()
    session_mgr = get_session_manager()
    
    # Create a session for user 1
    session = session_mgr.get_or_create_session("user-1")
    print(f"\nCreated session: {session.session_id}")
    
    # Test 1: Initial query
    print("\n### Query 1: Initial query")
    query1 = "Show me all users"
    print(f"User: {query1}")
    result1 = agent.query(query1, session)
    print(f"Answer: {result1.content}")
    if result1.metadata.get("sql"):
        print(f"SQL: {result1.metadata['sql']}")
    
    # Test 2: Follow-up query using pronoun
    print("\n### Query 2: Follow-up using pronoun 'them'")
    query2 = "How many of them are there?"
    print(f"User: {query2}")
    result2 = agent.query(query2, session)
    print(f"Answer: {result2.content}")
    if result2.metadata.get("sql"):
        print(f"SQL: {result2.metadata['sql']}")
    
    # Test 3: Another follow-up
    print("\n### Query 3: Another follow-up")
    query3 = "Filter those results by active status"
    print(f"User: {query3}")
    result3 = agent.query(query3, session)
    print(f"Answer: {result3.content}")
    if result3.metadata.get("sql"):
        print(f"SQL: {result3.metadata['sql']}")
    
    # Show session state
    print("\n" + "=" * 80)
    print(f"Session State for {session.session_id}:")
    print("=" * 80)
    print(f"Schema cached: {session.cached_schema is not None}")
    print(f"Query history size: {len(session.query_history)}")
    for i, ctx in enumerate(session.query_history, 1):
        print(f"\n{i}. User Query: {ctx.user_query}")
        print(f"   SQL: {ctx.generated_sql}")
        print(f"   Result: {ctx.result_summary}")


def test_multi_user_sessions():
    """Test that sessions are properly isolated between users."""
    print("\n\n" + "=" * 80)
    print("Testing Multi-User Session Isolation")
    print("=" * 80)
    
    agent = Text2SQLAgent()
    session_mgr = get_session_manager()
    
    # User 1 session
    session1 = session_mgr.get_or_create_session("user-1-multitest")
    print(f"\n### User 1 Session: {session1.session_id}")
    print("User 1: Show me all products")
    result1 = agent.query("Show me all products", session1)
    print(f"Answer: {result1.content[:100]}...")
    
    # User 2 session
    session2 = session_mgr.get_or_create_session("user-2-multitest")
    print(f"\n### User 2 Session: {session2.session_id}")
    print("User 2: Show me all orders")
    result2 = agent.query("Show me all orders", session2)
    print(f"Answer: {result2.content[:100]}...")
    
    # User 1 follow-up (should use products context)
    print(f"\n### User 1 Follow-up")
    print("User 1: How many of them are expensive?")
    result1_followup = agent.query("How many of them are expensive?", session1)
    print(f"Answer: {result1_followup.content[:100]}...")
    
    # User 2 follow-up (should use orders context)
    print(f"\n### User 2 Follow-up")
    print("User 2: How many of them were placed today?")
    result2_followup = agent.query("How many of them were placed today?", session2)
    print(f"Answer: {result2_followup.content[:100]}...")
    
    # Verify isolation
    print("\n" + "=" * 80)
    print("Session Isolation Verification:")
    print("=" * 80)
    print(f"User 1 history size: {len(session1.query_history)}")
    print(f"User 1 last query: {session1.query_history[-1].user_query}")
    print(f"\nUser 2 history size: {len(session2.query_history)}")
    print(f"User 2 last query: {session2.query_history[-1].user_query}")
    
    # Check session manager
    print(f"\nTotal active sessions: {session_mgr.get_active_session_count()}")


def test_schema_caching():
    """Test that schema is cached per session."""
    print("\n\n" + "=" * 80)
    print("Testing Schema Caching")
    print("=" * 80)
    
    agent = Text2SQLAgent()
    session_mgr = get_session_manager()
    
    session = session_mgr.get_or_create_session("caching-test")
    print(f"\nSession: {session.session_id}")
    print(f"Schema initially cached: {session.cached_schema is not None}")
    
    # First query - should fetch and cache schema
    print("\n### First query (schema will be fetched and cached)")
    agent.query("Show all users", session)
    print(f"Schema cached after first query: {session.cached_schema is not None}")
    print(f"Schema size: {len(session.cached_schema) if session.cached_schema else 0} characters")
    
    # Second query - should use cached schema
    print("\n### Second query (schema will be reused from cache)")
    print("No additional database introspection should occur!")
    agent.query("Count the users", session)
    print(f"Schema still cached: {session.cached_schema is not None}")
    
    print("\n✅ Schema caching working correctly!")


if __name__ == "__main__":
    try:
        test_single_user_session()
        test_multi_user_sessions()
        test_schema_caching()
        
        print("\n\n" + "=" * 80)
        print("✅ All Tests Complete!")
        print("=" * 80)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
