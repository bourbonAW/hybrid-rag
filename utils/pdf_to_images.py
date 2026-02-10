import fitz
from pathlib import Path
from typing import Dict


async def extract_pdf_pages(pdf_path: str, output_dir: str, dpi: int = 200) -> Dict[int, str]:
    """Extract PDF pages as images.

    Returns:
        Dict mapping page_number (1-indexed) to image path
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    page_images = {}

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        # Use matrix for higher resolution
        mat = fitz.Matrix(dpi/72, dpi/72)
        pix = page.get_pixmap(matrix=mat)

        image_path = output_path / f"page_{page_num + 1:04d}.jpg"
        pix.save(str(image_path))
        page_images[page_num + 1] = str(image_path)

    doc.close()
    return page_images
