"""Result combiner for merging outputs from multiple agents."""

from typing import Optional

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

from config import settings
from models import AgentResult, QueryResponse, RouteType


COMBINER_SYSTEM_PROMPT = """You are a professional analyst combining information from multiple sources.

You have information from:
1. Knowledge Base - conceptual information and best practices
2. Database - factual data and statistics

Create a comprehensive, professional response that:
- Integrates both sources naturally
- Uses clear, professional language suitable for end customers
- Highlights key insights
- Uses proper formatting (bullet points, paragraphs, etc.)
- Does not mention "RAG", "SQL", "database queries", or technical details
"""

COMBINER_USER_PROMPT = """Question: {query}

Knowledge Base Information:
{rag_result}

Database Information:
{sql_result}

Provide a comprehensive, professional answer:"""


class ResultCombiner:
    """Combines results from multiple agents."""
    
    def __init__(self):
        """Initialize the result combiner."""
        self.llm = ChatGroq(
            model=settings.llm_model,
            api_key=settings.groq_api_key,
            temperature=settings.llm_temperature,
        )
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", COMBINER_SYSTEM_PROMPT),
            ("human", COMBINER_USER_PROMPT),
        ])
    
    def combine(
        self,
        query: str,
        rag_result: Optional[AgentResult],
        sql_result: Optional[AgentResult],
        route: RouteType
    ) -> QueryResponse:
        """
        Combine results from agents into a final response.
        
        Args:
            query: Original user query
            rag_result: Result from RAG agent (if any)
            sql_result: Result from SQL agent (if any)
            route: The route that was taken
            
        Returns:
            Combined QueryResponse
        """
        # Single source - just format the result
        if route == RouteType.RAG and rag_result:
            return QueryResponse(
                answer=rag_result.content,
                route_taken=route,
                sources=rag_result.sources,
                sql_query=None if not settings.show_sql_queries else None,
                sql_results=None
            )
        
        if route == RouteType.SQL and sql_result:
            return QueryResponse(
                answer=sql_result.content,
                route_taken=route,
                sources=sql_result.sources,
                sql_query=sql_result.metadata.get("sql") if settings.show_sql_queries else None,
                sql_results=sql_result.metadata.get("results")
            )
        
        # Hybrid - combine both results
        if route == RouteType.HYBRID and rag_result and sql_result:
            chain = self.prompt | self.llm
            
            try:
                response = chain.invoke({
                    "query": query,
                    "rag_result": rag_result.content,
                    "sql_result": sql_result.content,
                })
                
                # Combine sources
                all_sources = list(set(rag_result.sources + sql_result.sources))
                
                return QueryResponse(
                    answer=response.content,
                    route_taken=route,
                    sources=all_sources,
                    sql_query=sql_result.metadata.get("sql") if settings.show_sql_queries else None,
                    sql_results=sql_result.metadata.get("results")
                )
            except Exception as e:
                # Fallback: concatenate results
                combined = f"{rag_result.content}\n\n{sql_result.content}"
                return QueryResponse(
                    answer=combined,
                    route_taken=route,
                    sources=rag_result.sources + sql_result.sources,
                    sql_query=sql_result.metadata.get("sql") if settings.show_sql_queries else None,
                    sql_results=sql_result.metadata.get("results")
                )
        
        # Fallback for edge cases
        return QueryResponse(
            answer="I'm unable to generate a response at this time. Please try rephrasing your question.",
            route_taken=route,
            sources=[],
            sql_query=None,
            sql_results=None
        )
