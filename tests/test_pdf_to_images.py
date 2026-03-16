from pathlib import Path

import pytest
from utils.pdf_to_images import extract_pdf_pages


@pytest.mark.asyncio
async def test_extract_pdf_pages(tmp_path):
    # Create a simple test PDF using pymupdf
    import fitz

    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((100, 100), "Test content")
    doc.save(str(pdf_path))
    doc.close()

    output_dir = tmp_path / "pages"
    page_images = await extract_pdf_pages(str(pdf_path), str(output_dir))

    assert len(page_images) == 1
    assert Path(page_images[1]).exists()
