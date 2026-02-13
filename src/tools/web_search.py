from typing import List, Dict, Any
from langchain_community.tools import DuckDuckGoSearchRun
from pydantic import BaseModel, Field

class WebSearchResults(BaseModel):
    """Represents a single web search result."""
    title: str = Field(..., description="Title of the search result.")
    url: str = Field(..., description="URL of the search result.")
    snippet: str = Field(..., description="A short snippet of the search result content.")

class WebSearchInput(BaseModel):
    """Input for the web search tool."""
    query: str = Field(..., description="The search query for the web search engine.")

def web_search_tool(query: str) -> List[WebSearchResults]:
    """
    Searches the web for relevant information using DuckDuckGo.

    Args:
        query: The search query string.

    Returns:
        A list of WebSearchResults containing titles, URLs, and snippets.
        Returns an empty list if no results are found or an error occurs.
    """
    search = DuckDuckGoSearchRun()
    try:
        # DuckDuckGoSearchRun returns a string of formatted results.
        # We need to parse this string into a list of dictionaries.
        raw_results = search.run(query)
        
        # A simple parsing logic for DuckDuckGoSearchRun output.
        # This might need to be more robust depending on the exact output format.
        results_list = []
        for line in raw_results.split('\n'):
            if "Title:" in line and "URL:" in line and "Snippet:" in line:
                title = line.split("Title:")[1].split("URL:")[0].strip()
                url = line.split("URL:")[1].split("Snippet:")[0].strip()
                snippet = line.split("Snippet:")[1].strip()
                results_list.append(WebSearchResults(title=title, url=url, snippet=snippet))
            elif "..." in line and "http" in line: # Fallback for less structured lines
                parts = line.split("...")
                if len(parts) >= 2:
                    snippet = parts[0].strip()
                    url_and_title = parts[1].strip()
                    # Attempt to extract URL and title, might be imperfect
                    url_match = [p for p in url_and_title.split() if p.startswith("http")]
                    url = url_match[0] if url_match else "N/A"
                    title = url_and_title.replace(url, "").strip() if url != "N/A" else url_and_title
                    if url != "N/A" and title and snippet:
                        results_list.append(WebSearchResults(title=title, url=url, snippet=snippet))

        return results_list
    except Exception as e:
        print(f"Error during web search: {e}")
        return []

# Author: Lakshitha Karunaratna
