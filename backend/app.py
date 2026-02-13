from fastapi import FastAPI, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse # Uncommented for streaming
import asyncio 
import json
from pydantic import BaseModel
from starlette.responses import JSONResponse 

# Re-enable Imports for the research agent and the modified StreamingCallbackHandler
from src.agent import create_research_agent, StreamingCallbackHandler, ResearchOutput 

print("DEBUG: Before load_dotenv()")
from dotenv import load_dotenv
import os
print("DEBUG: After load_dotenv()")

load_dotenv() # Load environment variables

class ResearchRequest(BaseModel):
    query: str

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Adjust this to your frontend's domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"DEBUG: Incoming request: {request.method} {request.url}")
    response = await call_next(request)
    print(f"DEBUG: Outgoing response: {response.status_code}")
    return response

@app.get("/")
async def read_root():
    return {"message": "FastAPI backend is running! Navigate to /docs for API documentation."}

async def event_generator(request: Request, research_topic: str):
    print("DEBUG: event_generator started") 
    queue = asyncio.Queue()
    
    print("DEBUG: Before create_task for ainvoke")
    # Run the research agent in a separate task
    task = asyncio.create_task(
        create_research_agent().ainvoke(
            {"input": research_topic, "chat_history": [], "callback_queue": queue}
        )
    )
    print("DEBUG: After create_task for ainvoke")

    try:
        while True:
            if await request.is_disconnected():
                print("DEBUG: Client disconnected, breaking event_generator loop.")
                break
            
            event = await queue.get()
            print(f"DEBUG: event_generator yielding event: {event['type']}")
            
            # Send all events, including final_research_output
            yield f"event: {event['type']}\ndata: {json.dumps(event, default=str)}\n\n"
            
            # Break the loop ONLY when workflow_end is received
            if event["type"] == "workflow_end":
                print("DEBUG: workflow_end received, breaking event_generator loop.")
                break
            
    except asyncio.CancelledError:
        print("DEBUG: event_generator task cancelled.")
        pass
    except Exception as e:
        print(f"ERROR: Exception in event_generator: {e}")
        yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
    finally:
        print("DEBUG: event_generator finally block.")
        task.cancel()
        try:
            await task # Await the task to ensure it cleans up
        except asyncio.CancelledError:
            print("DEBUG: event_generator agent task already cancelled.")
            pass # Expected if task was cancelled

@app.get("/api/v1/research") 
async def research_stream_endpoint(request: Request, query: str = Query(...)): 
    print(f"DEBUG: research_stream_endpoint hit - Query: {query}")
    return StreamingResponse(
        event_generator(request, query),
        media_type="text/event-stream"
    )