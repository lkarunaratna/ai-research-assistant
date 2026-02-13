import requests
from typing import Optional, List
from pydantic import BaseModel, HttpUrl, Field
from pypdf import PdfReader
import io

class PDFMetadata(BaseModel):
    """Metadata extracted from a PDF document."""
    title: Optional[str] = Field(None, description="Title of the PDF document.")
    author: Optional[str] = Field(None, description="Author of the PDF document.")
    page_count: int = Field(..., description="Total number of pages in the PDF document.")

class PDFContent(BaseModel):
    """Content extracted from a PDF document."""
    url: HttpUrl = Field(..., description="URL of the PDF document.")
    metadata: PDFMetadata = Field(..., description="Metadata of the PDF document.")
    text_content: str = Field(..., description="Extracted text content from the PDF.")

class PDFReaderInput(BaseModel):
    """Input for the PDF reader tool."""
    pdf_url: HttpUrl = Field(..., description="The URL of the PDF document to read.")

def pdf_reader_tool(pdf_url: str) -> Optional[PDFContent]:
    """
    Downloads a PDF from a given URL and extracts its text content and metadata.

    Args:
        pdf_url: The URL of the PDF document.

    Returns:
        An Optional[PDFContent] object containing the URL, metadata, and extracted text content.
        Returns None if the PDF cannot be downloaded or parsed.
    """
    try:
        response = requests.get(pdf_url, stream=True)
        response.raise_for_status()  # Raise an exception for HTTP errors
        
        # Read the PDF content from the response
        pdf_file = io.BytesIO(response.content)
        reader = PdfReader(pdf_file)

        metadata_dict = reader.metadata
        title = metadata_dict.get('/Title') if metadata_dict else None
        author = metadata_dict.get('/Author') if metadata_dict else None
        page_count = len(reader.pages)

        text_content = ""
        for page in reader.pages:
            text_content += page.extract_text() + "\n"

        pdf_metadata = PDFMetadata(title=title, author=author, page_count=page_count)
        return PDFContent(url=HttpUrl(pdf_url), metadata=pdf_metadata, text_content=text_content)

    except requests.exceptions.RequestException as e:
        print(f"Error downloading PDF from {pdf_url}: {e}")
        return None
    except Exception as e:
        print(f"Error parsing PDF from {pdf_url}: {e}")
        return None

# Author: Lakshitha Karunaratna
