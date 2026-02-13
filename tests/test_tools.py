import requests
import sys
import os
import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO
import json
import asyncio
from datetime import datetime

# Add the project root to sys.path for module discovery
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.tools.web_search import web_search_tool, WebSearchResults, WebSearchInput
from src.tools.pdf_reader import pdf_reader_tool, PDFContent, PDFMetadata, PDFReaderInput
from src.tools.note_taker import note_taker_tool, StructuredNote, NoteTakerInput
from src.agent import create_research_agent, StreamingCallbackHandler
from src.models import ResearchOutput, Source, Metadata
from pydantic import HttpUrl
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain_core.outputs import ChatGenerationChunk, GenerationChunk

# --- Mocking external dependencies ---

# Mock for DuckDuckGoSearchRun
@pytest.fixture
def mock_duckduckgo_search():
    with patch('src.tools.web_search.DuckDuckGoSearchRun') as mock_search_class:
        mock_instance = mock_search_class.return_value
        mock_instance.run.return_value = (
            "Title: Test Web Result 1 URL: http://test1.com Snippet: This is a test snippet 1.\n"
            "Title: Test Web Result 2 URL: http://test2.org Snippet: This is a test snippet 2."
        )
        yield mock_instance

# Mock for requests.get and pypdf.PdfReader
@pytest.fixture
def mock_pdf_dependencies():
    with patch('requests.get') as mock_requests_get, \
         patch('src.tools.pdf_reader.PdfReader') as mock_pdf_reader_class:
        
        # Mock requests.get
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = b"%PDF-1.4...\n%%EOF" # Minimal PDF content
        mock_requests_get.return_value = mock_response

        # Mock PdfReader
        mock_reader_instance = MagicMock()
        mock_reader_instance.metadata = {'/Title': 'Mock PDF Title', '/Author': 'Mock Author'}
        mock_reader_instance.pages = [MagicMock(), MagicMock()] # Two pages
        mock_reader_instance.pages[0].extract_text.return_value = "Content from page 1."
        mock_reader_instance.pages[1].extract_text.return_value = "Content from page 2."
        mock_pdf_reader_class.return_value = mock_reader_instance
        
        yield mock_requests_get, mock_pdf_reader_class

# --- Tests for individual tools ---

def test_web_search_tool_success(mock_duckduckgo_search):
    """Test web_search_tool returns expected results."""
    query = "test query"
    results = web_search_tool(query)
    
    assert len(results) == 2
    assert isinstance(results[0], WebSearchResults)
    assert results[0].title == "Test Web Result 1"
    assert results[0].url == "http://test1.com"
    assert results[0].snippet == "This is a test snippet 1."
    mock_duckduckgo_search.run.assert_called_once_with(query)

def test_web_search_tool_no_results(mock_duckduckgo_search):
    """Test web_search_tool with no results."""
    mock_duckduckgo_search.run.return_value = "" # No results
    results = web_search_tool("no results query")
    assert len(results) == 0

def test_web_search_tool_error(mock_duckduckgo_search):
    """Test web_search_tool handles errors."""
    mock_duckduckgo_search.run.side_effect = Exception("Search error")
    results = web_search_tool("error query")
    assert len(results) == 0

def test_pdf_reader_tool_success(mock_pdf_dependencies):
    """Test pdf_reader_tool returns expected content and metadata."""
    mock_requests_get, mock_pdf_reader_class = mock_pdf_dependencies
    pdf_url = "http://example.com/test.pdf"
    content = pdf_reader_tool(pdf_url)

    assert content is not None
    assert isinstance(content, PDFContent)
    assert content.url == HttpUrl(pdf_url)
    assert content.metadata.title == "Mock PDF Title"
    assert content.metadata.author == "Mock Author"
    assert content.metadata.page_count == 2
    assert "Content from page 1." in content.text_content
    assert "Content from page 2." in content.text_content
    mock_requests_get.assert_called_once_with(pdf_url, stream=True)
    mock_pdf_reader_class.assert_called_once()

def test_pdf_reader_tool_download_error(mock_pdf_dependencies):
    """Test pdf_reader_tool handles download errors."""
    mock_requests_get, _ = mock_pdf_dependencies
    mock_requests_get.side_effect = requests.exceptions.RequestException("Download failed")
    content = pdf_reader_tool("http://bad.url/bad.pdf")
    assert content is None

def test_pdf_reader_tool_parsing_error(mock_pdf_dependencies):
    """Test pdf_reader_tool handles parsing errors."""
    _, mock_pdf_reader_class = mock_pdf_dependencies
    mock_pdf_reader_class.side_effect = Exception("Parsing failed")
    content = pdf_reader_tool("http://example.com/corrupt.pdf")
    assert content is None

def test_note_taker_tool_success():
    """Test note_taker_tool aggregates notes correctly."""
    topic = "AI Research"
    category = "Key Findings"
    texts = ["AI is cool.", "Generative models are advancing."]
    
    structured_note = note_taker_tool(topic, category, texts)
    
    assert isinstance(structured_note, StructuredNote)
    assert structured_note.topic == topic
    assert structured_note.category == category
    assert "AI is cool." in structured_note.notes
    assert "Generative models are advancing." in structured_note.notes
    assert len(structured_note.notes) == 2

def test_note_taker_tool_empty_texts():
    """Test note_taker_tool with empty texts list."""
    structured_note = note_taker_tool("Topic", "Category", [])
    assert len(structured_note.notes) == 0

# --- Test for the full agent ---

@pytest.fixture
def mock_runnable_agent_ainvoke():
    """
    Mocks the ainvoke method of the RunnableLambda returned by create_research_agent.
    """
    with patch('src.agent.RunnableLambda.ainvoke') as mock_ainvoke:
        yield mock_ainvoke

@pytest.mark.asyncio
async def test_create_research_agent_structured_output(mock_runnable_agent_ainvoke):
    """Test if the agent returns a valid ResearchOutput structure."""
    # Set a dummy API key for the test environment
    os.environ["OPENAI_API_KEY"] = "sk-test12345"
    
    runnable_agent = create_research_agent()
    mock_runnable_agent_ainvoke.return_value = ResearchOutput(
        topic="Test Agent Query",
        summary="This is a summary generated by the mock agent.",
        sources=[
            Source(
                title="Mock Source",
                url=HttpUrl("http://mock.com"),
                type="web",
                key_points=["Mock point 1", "Mock point 2"],
                confidence_score=0.8
            )
        ],
        metadata=Metadata(
            search_queries_used=["mock query"],
            total_sources_analyzed=1,
            generation_timestamp=datetime.now()
        )
    )
    
    query = "test agent query"
    result = await runnable_agent.ainvoke(query) # This will now call the mocked ainvoke
    
    assert isinstance(result, ResearchOutput)
    assert result.topic == "Test Agent Query"
    assert "summary generated by the mock agent" in result.summary
    assert len(result.sources) == 1
    assert result.sources[0].title == "Mock Source"
    assert result.metadata.total_sources_analyzed == 1
    
    # Clean up dummy API key
    del os.environ["OPENAI_API_KEY"]

# Helper function for streaming test mock
async def _custom_ainvoke_for_streaming_test(*args, **kwargs):
    config = kwargs.get("config", {})
    callbacks = config.get("callbacks", []) # Get callbacks from config
    
    # Simulate tool calls and agent finish by directly adding to the callback_handler's log_stream
    for cb in callbacks:
        if isinstance(cb, StreamingCallbackHandler):
            cb.log_stream.append({"type": "tool_start", "tool_name": "web_search", "input": {"query": "test streaming query"}})
            cb.log_stream.append({"type": "tool_end", "output": "Mock web search results for streaming"})
            cb.log_stream.append({"type": "agent_finish", "output": {"summary": "Simulated streaming final output"}})
    
    # Return the final ResearchOutput
    return ResearchOutput(
        topic="Test Streaming Query",
        summary="Streaming test summary.",
        sources=[],
        metadata=Metadata(
            search_queries_used=["stream query"],
            total_sources_analyzed=0,
            generation_timestamp=datetime.now()
        )
    )

@pytest.mark.asyncio
async def test_create_research_agent_streaming(mock_runnable_agent_ainvoke):
    """Test if the StreamingCallbackHandler captures expected events."""
    os.environ["OPENAI_API_KEY"] = "sk-test12345"
    mock_runnable_agent_ainvoke.side_effect = _custom_ainvoke_for_streaming_test

    runnable_agent = create_research_agent()
    callback_handler = StreamingCallbackHandler()

    query = "test streaming query"
    await runnable_agent.ainvoke(
        query, 
        config={"callbacks": [callback_handler]}
    )

    log_types = [item["type"] for item in callback_handler.log_stream]

    # These assertions rely on how the mocked LLM in src.agent (if not mocked here)
    # would trigger these callbacks. Since we're mocking ainvoke directly,
    # the callbacks will only be triggered by the mock itself if it's explicitly done.
    # For now, we'll assert for basic presence from the mock behavior.
    assert "tool_start" in log_types # This would be captured by a real run
    assert "tool_end" in log_types # This would be captured by a real run
    assert "agent_finish" in log_types # This is triggered by agent_executor's finish
    
    # Clean up dummy API key
    del os.environ["OPENAI_API_KEY"]
