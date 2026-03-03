"""
Engine factory - returns the appropriate document engine based on file extension.
"""

from pathlib import Path

from .pdf_engine import PDFEngine
from .txt_engine import TextEngine
from .docx_engine import DocxEngine
from .pptx_engine import PptxEngine


def create_engine(file_path: str):
    """
    Create and return the appropriate document engine for the given file.

    Args:
        file_path: Path to the document file

    Returns:
        PDFEngine, DocxEngine, TextEngine, or PptxEngine instance

    Raises:
        ValueError: If the file extension is not supported
    """
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return PDFEngine(file_path)
    elif ext == ".docx":
        return DocxEngine(file_path)
    elif ext == ".txt":
        return TextEngine(file_path)
    elif ext in (".pptx", ".ppt"):
        if ext == ".ppt":
            raise ValueError(
                "旧版 .ppt 格式不被支持，请将文件另存为 .pptx 格式后再试。"
            )
        return PptxEngine(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")
