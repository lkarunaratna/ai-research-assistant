from typing import List, Literal
from pydantic import BaseModel, Field

class StructuredNote(BaseModel):
    """Represents a structured note compiled from various sources."""
    topic: str = Field(..., description="The main topic of the research.")
    category: str = Field(..., description="A category for the collected notes (e.g., 'Web Search Findings', 'PDF Extracts', 'Key Concepts').")
    notes: List[str] = Field(..., description="A list of aggregated notes or key findings.")

class NoteTakerInput(BaseModel):
    """Input for the note taker tool."""
    topic: str = Field(..., description="The main topic of the research.")
    category: str = Field(..., description="The category under which to file these notes.")
    texts: List[str] = Field(..., description="A list of text snippets to be aggregated into notes.")

def note_taker_tool(topic: str, category: str, texts: List[str]) -> StructuredNote:
    """
    Organizes and structures findings from other tools into a coherent note.
    This tool aggregates raw text snippets under a specified topic and category.

    Args:
        topic: The main topic of the research.
        category: The category for the collected notes (e.g., 'Web Search Findings', 'PDF Extracts').
        texts: A list of text snippets to be aggregated.

    Returns:
        A StructuredNote object containing the topic, category, and aggregated notes.
    """
    aggregated_notes = [note.strip() for note in texts if note.strip()]
    return StructuredNote(topic=topic, category=category, notes=aggregated_notes)

# Author: Lakshitha Karunaratna
