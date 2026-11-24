import os
from io import BytesIO
from datetime import datetime, timezone
from urllib.parse import urlparse, unquote

import requests
from pypdf import PdfReader


def get_sample_ingestion() -> dict:
    """
    Returns sample tender data when no PDF is provided.
    This allows the rest of the project to be tested.
    """

    return {
        "document_name": "Tender_Chikhloli_Road_Drainage.pdf",
        "source_page_url": None,
        "pdf_url": None,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "total_pages": 3,
        "pages_text": [
            {
                "page_number": 1,
                "text": (
                    "AMBERNATH MUNICIPAL COUNCIL "
                    "TENDER NOTICE NO. 88 OF 2026. "
                    "Name of Work: Construction of RCC "
                    "Drainage and Asphalt Road Repair "
                    "at Chikhloli, Ambernath East."
                )
            },
            {
                "page_number": 2,
                "text": (
                    "ESTIMATED COST OF WORK: INR 6,626,532. "
                    "Stated Completion Period: 6 Months "
                    "including monsoon season."
                )
            },
            {
                "page_number": 3,
                "text": (
                    "GENERAL CONDITIONS: Contractor must "
                    "adhere to Maharashtra PWD specifications. "
                    "Note: Defect liability period clause "
                    "page missing in this tender extract."
                )
            }
        ]
    }


def fetch_tender_pdf(pdf_path_or_url: str = None) -> dict:
    """
    Downloads or opens a tender PDF and extracts text
    from every page.

    Accepts:
    1. A local PDF file path.
    2. An online PDF URL.

    Returns a dictionary following the team data contract.
    """

    # Generate the retrieval timestamp
    retrieved_timestamp = datetime.now(timezone.utc).isoformat()

    # If no PDF is provided, use sample data
    if not pdf_path_or_url:
        print("[Ingestion] No PDF provided. Loading sample data.")
        return get_sample_ingestion()

    # Check whether the input is an online URL
    if pdf_path_or_url.lower().startswith(("http://", "https://")):

        print("[Ingestion] Downloading PDF from URL...")

        response = requests.get(pdf_path_or_url, timeout=30)
        response.raise_for_status()

        pdf_file = BytesIO(response.content)

        # Extract filename from the URL
        filename = unquote(
            os.path.basename(urlparse(pdf_path_or_url).path)
        ) or "downloaded_tender.pdf"

        pdf_url = pdf_path_or_url

    else:
        # Treat the input as a local file
        if not os.path.isfile(pdf_path_or_url):
            print("[Ingestion] PDF not found. Loading sample data.")
            return get_sample_ingestion()

        print("[Ingestion] Opening local PDF...")

        pdf_file = pdf_path_or_url
        filename = os.path.basename(pdf_path_or_url)
        pdf_url = None

    # Read the PDF
    reader = PdfReader(pdf_file)

    pages_text = []

    # Extract text from every page
    for idx, page in enumerate(reader.pages):

        extracted_text = page.extract_text() or ""

        pages_text.append({
            "page_number": idx + 1,
            "text": extracted_text.strip()
        })

    # Create the final structured dictionary
    result = {
        "document_name": filename,
        "source_page_url": None,
        "pdf_url": pdf_url,
        "retrieved_at": retrieved_timestamp,
        "total_pages": len(reader.pages),
        "pages_text": pages_text
    }

    print("[Ingestion] PDF successfully processed!")

    return result


if __name__ == "__main__":

    print("Testing Ingestion Module...")

    result = fetch_tender_pdf("sample_data/test_tender.pdf")

    print("Document Name:", result["document_name"])
    print("Total Pages Extracted:", result["total_pages"])

    print(
        "Page 1 Snippet:",
        result["pages_text"][0]["text"][:80] + "..."
    )

    print("Ingestion Module Test PASSED!")
result = fetch_tender_pdf(
    "https://cic.gov.in/sites/default/files/Tenders/tender%201.pdf"
)