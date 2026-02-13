from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, HttpUrl

class Source(BaseModel):
    """Represents a single source of information."""
    title: str = Field(..., description="Title of the source.")
    url: HttpUrl = Field(..., description="URL of the source document.")
    type: Literal["web", "pdf"] = Field(..., description="Type of the source (web or pdf).")
    key_points: List[str] = Field(..., description="List of key points extracted from the source.")
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0) for the information from this source."
    )

class Metadata(BaseModel):
    """Contains metadata about the research process."""
    search_queries_used: List[str] = Field(
        ..., description="List of search queries used during the research."
    )
    total_sources_analyzed: int = Field(
        ..., description="Total number of sources (web pages, PDFs) analyzed."
    )
    generation_timestamp: datetime = Field(
        ..., description="Timestamp when the research output was generated in ISO-8601 format."
    )

class ResearchOutput(BaseModel):
    """The structured output for the research assistant."""
    topic: str = Field(..., description="The original research topic provided by the user.")
    summary: str = Field(..., description="A comprehensive summary of the research findings.")
    sources: List[Source] = Field(
        ..., description="A list of sources with their extracted key points and confidence scores."
    )
    metadata: Metadata = Field(..., description="Metadata about the research process.")

# Author: Lakshitha Karunaratna
