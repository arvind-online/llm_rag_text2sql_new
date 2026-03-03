"""Pydantic models for request/response schemas and internal state."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class RouteType(str, Enum):
    """Types of query routing."""
    RAG = "rag"
    SQL = "sql"
    HYBRID = "hybrid"


@dataclass
class QueryContext:
    """Context from a previous SQL query for conversation memory."""
    user_query: str
    generated_sql: str
    result_summary: str
    timestamp: float


class ConversationTurn(BaseModel):
    """A single conversation turn passed from the frontend."""
    user: str = Field(..., description="The user's query text")
    assistant: str = Field(..., description="The assistant's response text")
    sql_query: Optional[str] = Field(None, description="SQL query from that turn, if any")


class QueryRequest(BaseModel):
    """User query request."""
    query: str = Field(..., description="The user's natural language query")
    context: Optional[str] = Field(None, description="Optional additional context")
    history: list[ConversationTurn] = Field(default_factory=list, description="Recent conversation turns (up to 5)")


class QueryResponse(BaseModel):
    """Final response to user query."""
    answer: str = Field(..., description="The generated answer")
    route_taken: RouteType = Field(..., description="Which route was used")
    sources: list[str] = Field(default_factory=list, description="Source references")
    sql_query: Optional[str] = Field(None, description="SQL query if applicable")
    sql_results: Optional[list[dict[str, Any]]] = Field(None, description="SQL results if applicable")
    model_used: Optional[str] = Field(None, description="LLM provider/model used to generate the response")


class RouteDecision(BaseModel):
    """Router agent's decision on how to handle the query."""
    route: RouteType = Field(..., description="The chosen route")
    reasoning: str = Field(..., description="Explanation for the routing decision")


class AgentResult(BaseModel):
    """Result from an individual agent."""
    agent_type: str = Field(..., description="Type of agent that produced this result")
    content: str = Field(..., description="The agent's response content")
    sources: list[str] = Field(default_factory=list, description="Sources used")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class DocumentInput(BaseModel):
    """Input for adding documents to the RAG system."""
    content: str = Field(..., description="Document content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Document metadata")


class GraphState(BaseModel):
    """State passed through the LangGraph workflow."""
    query: str = Field(..., description="Original user query")
    context: Optional[str] = Field(None, description="Optional context")
    history: list[ConversationTurn] = Field(default_factory=list, description="Conversation history from frontend")
    timezone: str = Field(default="UTC", description="IANA timezone for displaying times (e.g. 'America/New_York')")
    route_decision: Optional[RouteDecision] = Field(None, description="Router's decision")
    rag_result: Optional[AgentResult] = Field(None, description="RAG agent result")
    sql_result: Optional[AgentResult] = Field(None, description="Text2SQL agent result")
    final_response: Optional[QueryResponse] = Field(None, description="Final combined response")
    error: Optional[str] = Field(None, description="Error message if any")
