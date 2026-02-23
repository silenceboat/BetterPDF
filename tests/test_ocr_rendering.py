"""Tests for OCR rendering module."""

import os
import shutil
import tempfile
from unittest.mock import Mock, patch

import pytest

from backend.ocr.rendering import Renderer


class _MockDoc:
    def __init__(self, pages):
        self._pages = pages

    def __len__(self):
        return len(self._pages)

    def __getitem__(self, index):
        return self._pages[index]

    def close(self):
        pass


class TestRenderer:
    """Test cases for Renderer class."""

    @pytest.fixture
    def temp_dir(self):
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)

    def _build_doc(self, page_count: int):
        pages = []
        pixmaps = []
        for _ in range(page_count):
            pix = Mock()
            page = Mock()
            page.get_pixmap.return_value = pix
            pages.append(page)
            pixmaps.append(pix)
        return _MockDoc(pages), pages, pixmaps

    @patch("backend.ocr.rendering.fitz.open")
    def test_render_single_page(self, mock_open, temp_dir):
        doc, pages, pixmaps = self._build_doc(1)
        mock_open.return_value = doc

        pdf_path = "/path/to/document.pdf"
        renderer = Renderer(pdf_path=pdf_path, output_folder=temp_dir)
        result = renderer.render_pdf_to_images(first_page=1, last_page=1, dpi=150)

        assert len(result) == 1
        expected_path = os.path.join(temp_dir, "document_page1_dpi150.png")
        assert result[0] == expected_path
        pixmaps[0].save.assert_called_once_with(expected_path)
        pages[0].get_pixmap.assert_called_once()

    @patch("backend.ocr.rendering.fitz.open")
    def test_render_multiple_pages(self, mock_open, temp_dir):
        doc, pages, pixmaps = self._build_doc(3)
        mock_open.return_value = doc

        renderer = Renderer(pdf_path="/path/to/book.pdf", output_folder=temp_dir)
        result = renderer.render_pdf_to_images(first_page=1, last_page=3, dpi=200)

        assert len(result) == 3
        for i in range(1, 4):
            expected_path = os.path.join(temp_dir, f"book_page{i}_dpi200.png")
            assert expected_path in result
            pixmaps[i - 1].save.assert_called_once_with(expected_path)
            pages[i - 1].get_pixmap.assert_called_once()

    @patch("backend.ocr.rendering.fitz.open")
    def test_render_partial_pages(self, mock_open, temp_dir):
        doc, _, pixmaps = self._build_doc(10)
        mock_open.return_value = doc

        renderer = Renderer(pdf_path="/path/to/document.pdf", output_folder=temp_dir)
        result = renderer.render_pdf_to_images(first_page=5, last_page=6, dpi=150)

        assert result == [
            os.path.join(temp_dir, "document_page5_dpi150.png"),
            os.path.join(temp_dir, "document_page6_dpi150.png"),
        ]
        pixmaps[4].save.assert_called_once()
        pixmaps[5].save.assert_called_once()

    @patch("backend.ocr.rendering.fitz.open")
    def test_render_default_dpi(self, mock_open, temp_dir):
        doc, pages, _ = self._build_doc(1)
        mock_open.return_value = doc

        renderer = Renderer(pdf_path="/path/to/doc.pdf", output_folder=temp_dir)
        renderer.render_pdf_to_images(first_page=1, last_page=None)

        kwargs = pages[0].get_pixmap.call_args.kwargs
        assert kwargs["alpha"] is False
        assert "matrix" in kwargs

    @patch("backend.ocr.rendering.fitz.open")
    def test_render_creates_output_folder(self, mock_open, temp_dir):
        doc, _, _ = self._build_doc(1)
        mock_open.return_value = doc

        nested_folder = os.path.join(temp_dir, "nested", "output")
        assert not os.path.exists(nested_folder)

        renderer = Renderer(pdf_path="/path/to/doc.pdf", output_folder=nested_folder)
        renderer.render_pdf_to_images()

        assert os.path.exists(nested_folder)

    @patch("backend.ocr.rendering.fitz.open")
    def test_render_existing_output_folder(self, mock_open, temp_dir):
        doc, _, pixmaps = self._build_doc(1)
        mock_open.return_value = doc

        os.makedirs(temp_dir, exist_ok=True)

        renderer = Renderer(pdf_path="/path/to/doc.pdf", output_folder=temp_dir)
        renderer.render_pdf_to_images()

        pixmaps[0].save.assert_called_once()

    @patch("backend.ocr.rendering.fitz.open")
    def test_render_different_pdf_names(self, mock_open, temp_dir):
        test_cases = [
            ("/path/to/my-file.pdf", "my-file_page1_dpi150.png"),
            ("/path/to/my_file_v2.pdf", "my_file_v2_page1_dpi150.png"),
            ("/path/to/Document.PDF", "Document_page1_dpi150.png"),
        ]

        for pdf_path, expected_name in test_cases:
            doc, _, pixmaps = self._build_doc(1)
            mock_open.return_value = doc

            renderer = Renderer(pdf_path=pdf_path, output_folder=temp_dir)
            renderer.render_pdf_to_images(first_page=1, last_page=1)

            expected_path = os.path.join(temp_dir, expected_name)
            pixmaps[0].save.assert_called_once_with(expected_path)
