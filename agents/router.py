"""Router agent that determines query routing."""

from typing import Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from config import settings, get_llm
from models import RouteDecision, RouteType


ROUTER_SYSTEM_PROMPT = """You are a query routing expert. Your job is to analyze user queries and determine the best way to answer them.

You must classify each query into one of three categories:
1. **rag** - Use this when the query asks about documents, concepts, explanations, definitions, or general knowledge that would be stored in a document database.
   Examples: "What is machine learning?", "Explain the company policy on remote work", "What are the features of product X?"

2. **sql** - Use this when the query asks for specific data, statistics, counts, aggregations, or information that would be stored in a structured database.
   Examples: "How many orders were placed last month?", "What is the total revenue?", "List all customers from New York"

3. **hybrid** - Use this when the query requires both document knowledge AND structured data to provide a complete answer.
   Examples: "Compare our sales performance with industry best practices", "How does our customer count compare to what our strategy documents predicted?"

Analyze the query carefully and provide your routing decision with clear reasoning.

{format_instructions}
"""

ROUTER_USER_PROMPT = """Query: {query}

Additional context (if any): {context}

Determine the appropriate route for this query."""


class RouterAgent:
    """Agent that routes queries to appropriate handlers."""
    
    def __init__(self):
        """Initialize the router agent."""
        self.llm = get_llm()
        self.parser = PydanticOutputParser(pydantic_object=RouteDecision)
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", ROUTER_SYSTEM_PROMPT),
            ("human", ROUTER_USER_PROMPT),
        ])
    
    def route(self, query: str, context: Optional[str] = None) -> RouteDecision:
        """
        Analyze a query and determine the appropriate route.
        
        Args:
            query: The user's query
            context: Optional additional context
            
        Returns:
            RouteDecision with the chosen route and reasoning
        """
        chain = self.prompt | self.llm | self.parser
        
        try:
            result = chain.invoke({
                "query": query,
                "context": context or "None provided",
                "format_instructions": self.parser.get_format_instructions(),
            })
            print("AVNNNNN::: ",result)
            return result
        except Exception as e:
            # Default to hybrid if routing fails
            return RouteDecision(
                route=RouteType.HYBRID,
                reasoning=f"Defaulting to hybrid due to routing error: {str(e)}"
            )
