import os
import datetime
import operator
from typing import List, Dict, Any, Optional, TypedDict, Annotated
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.base import Runnable
from langchain.tools import tool
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, FunctionMessage
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import ChatGenerationChunk, GenerationChunk
from langchain_core.agents import AgentFinish, AgentAction # Keep for callback handler definition
from langchain_core.runnables import RunnableLambda

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from src.models import ResearchOutput, Source, Metadata, HttpUrl
from src.tools.web_search import web_search_tool, WebSearchResults, WebSearchInput
from src.tools.pdf_reader import pdf_reader_tool, PDFContent, PDFReaderInput
from src.tools.note_taker import note_taker_tool, StructuredNote, NoteTakerInput
import json
import asyncio # Import asyncio

# Author: Lakshitha Karunaratna

class StreamingCallbackHandler(BaseCallbackHandler):
    """
    Callback handler for streaming agent output, tool invocations, and agent reasoning.
    Events are put into an asyncio.Queue for external consumption (e.g., by a FastAPI SSE endpoint).
    """
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue
        self.llm_token_buffer = []

    async def _put_event(self, event_type: str, data: Dict[str, Any]):
        """Helper to put a JSON-serializable event into the queue."""
        event_data = {"type": event_type, **data}
        await self.queue.put(event_data)

    async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Runs on new LLM token callbacks."""
        self.llm_token_buffer.append(token)

    async def on_llm_end(self, response, **kwargs: Any) -> None:
        """Runs on LLM end callbacks."""
        if self.llm_token_buffer:
            full_response = "".join(self.llm_token_buffer)
            await self._put_event("llm_full_response", {"content": full_response})
            self.llm_token_buffer = [] # Clear the buffer

    async def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs: Any) -> None:
        """Runs on tool start callbacks."""
        tool_name = serialized.get("name", "Unknown Tool")
        await self._put_event("tool_start", {"tool_name": tool_name, "input": input_str})

    async def on_tool_end(self, output: Any, **kwargs: Any) -> None:
        """Runs on tool end callbacks."""
        await self._put_event("tool_end", {"output": str(output)})

    async def on_agent_action(self, action: AgentAction, **kwargs: Any) -> None:
        """Runs on agent action."""
        await self._put_event("agent_action", {"tool": action.tool, "tool_input": action.tool_input})
    
    async def on_agent_finish(self, finish: AgentFinish, **kwargs: Any) -> None:
        """Runs on agent finish."""
        await self._put_event("agent_finish", {"output": finish.return_values})

    async def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> None:
        """Runs on LLM start."""
        await self._put_event("agent_reasoning_start", {})

    async def on_workflow_end(self):
        """Signals the end of the workflow for the queue consumer."""
        await self.queue.put({"type": "workflow_end"})

class AgentState(TypedDict):
    """
    Represents the state of the agent in the LangGraph.
    Messages are an annotated list, allowing new messages to be appended.
    """
    messages: Annotated[List[BaseMessage], operator.add]
    topic: str
    sources: List[Source]
    metadata: Metadata

def create_research_agent() -> Runnable:
    """
    Creates and configures the intelligent research assistant agent using LangGraph.

    The agent integrates web search, PDF reading, and note-taking capabilities.
    It's designed to produce structured JSON output.

    Returns:
        A compiled LangGraph application (Runnable) representing the research agent.
    """
    # Load OpenAI API key from environment variable
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set.")

    # Initialize the LLM
    llm = ChatOpenAI(model="gpt-4o", temperature=0, openai_api_key=openai_api_key, streaming=True)

    # Define the tools the agent can use
    # Wrap functions with @tool decorator to make them usable by the agent
    @tool("web_search", args_schema=WebSearchInput)
    def _web_search_tool(query: str) -> List[WebSearchResults]:
        """Search the web for relevant information."""
        return web_search_tool(query)

    @tool("pdf_reader", args_schema=PDFReaderInput)
    def _pdf_reader_tool(pdf_url: str) -> Optional[PDFContent]:
        """Download and extract text from PDF documents."""
        return pdf_reader_tool(pdf_url)

    @tool("note_taker", args_schema=NoteTakerInput)
    def _note_taker_tool(topic: str, category: str, texts: List[str]) -> StructuredNote:
        """Organize and structure findings from other tools."""
        return note_taker_tool(topic, category, texts)

    tools = [_web_search_tool, _pdf_reader_tool, _note_taker_tool]
    llm_with_tools = llm.bind_tools(tools)

    # Define the nodes for the graph
    def call_llm(state: AgentState):
        """Node to invoke the LLM with the current messages."""
        messages = state["messages"]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    tool_node = ToolNode(tools)

    def should_continue(state: AgentState) -> str:
        """
        Conditional edge logic to determine if the agent should call a tool or end.
        """
        last_message = state["messages"][-1]
        # If the LLM makes a tool call, then we route to the tool node
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "call_tool"
        # Otherwise, the LLM is not making a tool call, so it's a final answer
        return "end"

    # Build the LangGraph
    workflow = StateGraph(AgentState)

    workflow.add_node("llm", call_llm)
    workflow.add_node("call_tool", tool_node)

    # After a tool call, always go back to the LLM to process the tool output
    workflow.add_edge("call_tool", "llm")

    # Define the conditional edges from the LLM node
    workflow.add_conditional_edges(
        "llm",
        should_continue,
        {
            "call_tool": "call_tool", # If LLM suggests tool call, execute tool
            "end": END               # If LLM provides final answer, end graph
        },
    )

    workflow.set_entry_point("llm")
    app = workflow.compile()

    # Create a runnable that takes the query, initializes the state, and runs the graph
    # Then it uses another LLM call to structure the final output
    async def run_graph_and_structure_output(input_dict: Dict[str, Any]) -> ResearchOutput:
        query = input_dict.get("input")
        chat_history = input_dict.get("chat_history", [])
        callback_queue = input_dict.get("callback_queue") # Extract callback_queue here
        
        # Initialize StreamingCallbackHandler with the provided queue
        # For CLI usage, a dummy queue will be used if callback_queue is None
        _callback_handler = StreamingCallbackHandler(callback_queue if callback_queue is not None else asyncio.Queue())
        
        initial_state = AgentState(
            messages=[HumanMessage(content=query)] + chat_history,
            topic=query,
            sources=[],
            metadata=Metadata(
                search_queries_used=[],
                total_sources_analyzed=0,
                generation_timestamp=datetime.datetime.now()
            )
        )
        
        # Run the graph with the streaming callback handler
        final_state = {}
        # Pass the callback handler to the astream method
        async for s in app.astream(initial_state, config={"callbacks": [_callback_handler]}):
            final_state.update(s)
            
        # Use an LLM to coerce the final messages and collected data into ResearchOutput
        # This LLM call will explicitly format the output
        structuring_llm = ChatOpenAI(model="gpt-4o", temperature=0, openai_api_key=os.getenv("OPENAI_API_KEY"))
        
        # Construct a prompt for structuring the output
        structuring_prompt = ChatPromptTemplate.from_messages([
            ("system", 
             "You are an expert at structuring research results. Given the conversation history and any tool outputs, "
             "generate a comprehensive research output in the specified JSON format. "
             "Include the original topic, a summary of findings, details for each source (use a confidence score of 0.7 for all sources for this exercise),"
             "and appropriate metadata. "
             "Your output MUST strictly conform to the ResearchOutput Pydantic model. "
             "The full list of messages in the final state is: {final_messages}"
            ),
            ("human", "Generate the structured research output for the topic: {topic}")
        ])
        
        # Bind the ResearchOutput schema to the LLM
        structured_output_chain = structuring_prompt | structuring_llm.with_structured_output(ResearchOutput, method="function_calling")
        
        # Invoke the chain to get the final structured output
        research_output = await structured_output_chain.ainvoke({
            "topic": query,
            "final_messages": final_messages
        })
        
        # Put the final research output into the queue and then signal end
        await _callback_handler._put_event("final_research_output", research_output.dict())
        await _callback_handler.on_workflow_end()

        return research_output
    
    # Return the runnable function directly
    return RunnableLambda(run_graph_and_structure_output)


# Example usage (for testing purposes, not part of the agent itself)
async def aget_research_output(query: str, callback_queue: asyncio.Queue = None) -> ResearchOutput:
    """
    Asynchronously gets research output for a given query.
    """
    runnable_agent = create_research_agent()
    # The runnable_agent expects a dictionary input
    # We now pass the callback_queue directly as part of the input dict to the runnable,
    # as run_graph_and_structure_output expects it there.
    input_payload = {"input": query, "chat_history": []}
    if callback_queue:
        input_payload["callback_queue"] = callback_queue

    result = await runnable_agent.ainvoke(input_payload)
    
    if isinstance(result, ResearchOutput):
        return result
    else:
        try:
            return ResearchOutput.parse_obj(result)
        except Exception as e:
            print(f"Error parsing agent output to ResearchOutput: {e}")
            raise

if __name__ == "__main__":
    async def main_cli():
        research_topic = "latest advancements in AI for drug discovery"
        print(f"Starting research for: {research_topic}")
        try:
            # For CLI usage, we create a queue and pass it.
            # The StreamingCallbackHandler in aget_research_output will use this queue.
            cli_queue = asyncio.Queue()
            output = await aget_research_output(research_topic, callback_queue=cli_queue)
            print("\n--- Final Research Output ---")
            print(json.dumps(output.dict(), indent=2, default=str))
        except ValueError as e:
            print(f"Configuration Error: {e}")
        except Exception as e:
            print(f"An error occurred during research: {e}")

    asyncio.run(main_cli())