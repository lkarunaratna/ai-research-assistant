import asyncio
import argparse
import json
import os
from dotenv import load_dotenv
import warnings # Import the warnings module
import time # Import the time module for simulated streaming delay

from src.agent import create_research_agent, StreamingCallbackHandler
from src.models import ResearchOutput

# Suppress the specific UserWarning from langchain_core
warnings.filterwarnings("ignore", category=UserWarning, module='langchain_core')

async def main():
    """
    Main function to run the AI Research Assistant.
    It loads environment variables, parses command-line arguments,
    creates the research agent, and executes a research query.
    """
    load_dotenv()  # Load environment variables from .env file

    # Check for OPENAI_API_KEY
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set.")
        print("Please set the OPENAI_API_KEY in your environment or in a .env file.")
        return

    parser = argparse.ArgumentParser(
        description="AI Research Assistant: Gathers, organizes, and summarizes information from multiple sources."
    )
    parser.add_argument("query", type=str, help="The research topic or query.")
    
    args = parser.parse_args()
    research_topic = args.query

    print(f"[*] Starting research for: '{research_topic}'...")

    try:
        agent_executor = create_research_agent()
        callback_handler = StreamingCallbackHandler()

        # Invoke the agent with the query and the streaming callback handler
        result = await agent_executor.ainvoke(
            {"input": research_topic, "chat_history": []},
            config={"callbacks": [callback_handler]}
        )
        
        print("\n--- Final Research Output ---")
        # The result from with_structured_output is already a Pydantic object
        if isinstance(result, ResearchOutput):
            # Simulate streaming the final JSON output
            json_output = json.dumps(result.dict(), indent=2, default=str)
            for char in json_output:
                print(char, end="", flush=True)
                await asyncio.sleep(0.005) # Small delay to simulate streaming
            print() # Newline at the end
        else:
            # Fallback in case structured output fails for some reason
            print("Warning: Output is not a ResearchOutput Pydantic object. Attempting to print raw result.")
            print(json.dumps(result, indent=2, default=str))

    except Exception as e:
        print(f"\nError: An unexpected error occurred during research: {e}")
        import traceback
        traceback.print_exc() # Print full traceback for debugging

if __name__ == "__main__":
    asyncio.run(main())

# Author: Lakshitha Karunaratna
