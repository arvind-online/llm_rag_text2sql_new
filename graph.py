"""LangGraph workflow for the router pattern."""

from typing import Literal, Optional

from langgraph.graph import StateGraph, END

from models import GraphState, RouteType


# Lazy-initialized agent instances
_router_agent = None
_rag_agent = None
_sql_agent = None
_combiner = None


def get_router_agent():
    """Get or create the router agent (lazy initialization)."""
    global _router_agent
    if _router_agent is None:
        from agents.router import RouterAgent
        _router_agent = RouterAgent()
    return _router_agent


def get_rag_agent():
    """Get or create the RAG agent (lazy initialization)."""
    global _rag_agent
    if _rag_agent is None:
        from agents.rag_agent import RAGAgent
        _rag_agent = RAGAgent()
    return _rag_agent


def get_sql_agent():
    """Get or create the SQL agent (lazy initialization)."""
    global _sql_agent
    if _sql_agent is None:
        from agents.text2sql_agent import Text2SQLAgent
        _sql_agent = Text2SQLAgent()
    return _sql_agent


def get_combiner():
    """Get or create the result combiner (lazy initialization)."""
    global _combiner
    if _combiner is None:
        from agents.combiner import ResultCombiner
        _combiner = ResultCombiner()
    return _combiner


def route_query(state: GraphState) -> GraphState:
    """Router node: determine which agent(s) to use."""
    decision = get_router_agent().route(state.query, state.context)
    state_dict = state.model_dump()
    state_dict["route_decision"] = decision
    return GraphState(**state_dict)


def execute_rag(state: GraphState) -> GraphState:
    """RAG agent node: query the document store."""
    result = get_rag_agent().query(state.query)
    state_dict = state.model_dump()
    state_dict["rag_result"] = result
    return GraphState(**state_dict)


def execute_sql(state: GraphState) -> GraphState:
    """SQL agent node: convert to SQL and query database."""
    result = get_sql_agent().query(state.query)
    state_dict = state.model_dump()
    state_dict["sql_result"] = result
    return GraphState(**state_dict)


def execute_both(state: GraphState) -> GraphState:
    """Execute both RAG and SQL agents for hybrid queries."""
    rag_result = get_rag_agent().query(state.query)
    sql_result = get_sql_agent().query(state.query)
    state_dict = state.model_dump()
    state_dict["rag_result"] = rag_result
    state_dict["sql_result"] = sql_result
    return GraphState(**state_dict)


def combine_results(state: GraphState) -> GraphState:
    """Combiner node: merge results into final response."""
    route = state.route_decision.route if state.route_decision else RouteType.HYBRID
    
    final_response = get_combiner().combine(
        query=state.query,
        rag_result=state.rag_result,
        sql_result=state.sql_result,
        route=route
    )
    
    state_dict = state.model_dump()
    state_dict["final_response"] = final_response
    return GraphState(**state_dict)


def route_decision_branch(state: GraphState) -> Literal["rag", "sql", "hybrid"]:
    """Conditional branch based on router decision."""
    if state.route_decision is None:
        return "hybrid"
    
    route = state.route_decision.route
    if route == RouteType.RAG:
        return "rag"
    elif route == RouteType.SQL:
        return "sql"
    else:
        return "hybrid"


def build_graph() -> StateGraph:
    """
    Build the LangGraph workflow.
    
    Flow:
    1. Router node decides the route
    2. Conditional branch to appropriate agent(s)
    3. Combiner merges results
    4. End
    
    Returns:
        Compiled StateGraph
    """
    # Create the graph with state schema
    workflow = StateGraph(GraphState)
    
    # Add nodes
    workflow.add_node("router", route_query)
    workflow.add_node("rag_agent", execute_rag)
    workflow.add_node("sql_agent", execute_sql)
    workflow.add_node("hybrid_agents", execute_both)
    workflow.add_node("combiner", combine_results)
    
    # Set entry point
    workflow.set_entry_point("router")
    
    # Add conditional edges from router
    workflow.add_conditional_edges(
        "router",
        route_decision_branch,
        {
            "rag": "rag_agent",
            "sql": "sql_agent",
            "hybrid": "hybrid_agents"
        }
    )
    
    # All agent paths lead to combiner
    workflow.add_edge("rag_agent", "combiner")
    workflow.add_edge("sql_agent", "combiner")
    workflow.add_edge("hybrid_agents", "combiner")
    
    # Combiner leads to end
    workflow.add_edge("combiner", END)
    
    # Compile the graph
    return workflow.compile()


# Lazy-built graph instance
_graph = None


def get_graph():
    """Get or create the compiled graph (lazy initialization)."""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def run_query(query: str, context: Optional[str] = None) -> GraphState:
    """
    Run a query through the LangGraph workflow.
    
    Args:
        query: User's natural language query
        context: Optional additional context
        
    Returns:
        Final GraphState with results
    """
    initial_state = GraphState(query=query, context=context)
    
    # Run the graph
    result = get_graph().invoke(initial_state)
    
    return result
