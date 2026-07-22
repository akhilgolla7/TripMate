from tavily import TavilyClient
import os
from dotenv import load_dotenv

load_dotenv()

tavily_client = TavilyClient(api_key = os.getenv("TAVILY_API_KEY"))

def tavily_search(query: str):
    """
    Search for a query using the Tavily API.

    Args:
        query (str): The search query.
        """
    response = tavily_client.search(query, max_results=5)

    results = []

    for i, r in enumerate(response['results'],1):
        title = r.get('title', 'Unknown')
        url = r.get("url")
        snippet = r.get("content", "").strip()

        # to keep only first 300 characters to avoid wall-of-text
        if(len(snippet) > 300):
            snippet = snippet[:300].rsplit(" ",1)[0] + "..."
        
        results.append(f"{i}. **{title}** \n   {url}\n   {snippet}\n")

    return "\n\n".join(results)