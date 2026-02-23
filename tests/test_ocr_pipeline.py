"""Tests for OCR pipeline module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from PIL import Image
import numpy as np
import tempfile
import os

from backend.ocr.pipeline import OCRPipeline


class TestOCRPipeline:
    """Test cases for OCRPipeline class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test outputs."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        import shutil
        shutil.rmtree(temp_path)

    @pytest.fixture
    def mock_images(self, temp_dir):
        """Create real temporary PNG images for testing."""
        paths = []
        for i in range(1, 3):
            path = os.path.join(temp_dir, f"doc_page{i}_dpi150.png")
            # 300x600 pixels at 150 DPI → 144x288 points
            img = Image.new("RGB", (300, 600), color="white")
            img.save(path, "PNG")
            paths.append(path)
        return paths

    @patch("backend.ocr.pipeline.Engine")
    @patch("backend.ocr.pipeline.Renderer")
    def test_pipeline_run(self, MockRenderer, MockEngine, mock_images, temp_dir):
        """Test full pipeline run wires all three stages correctly."""
        # Renderer returns image paths
        mock_renderer = MockRenderer.return_value
        mock_renderer.render_pdf_to_images.return_value = mock_images

        # Engine returns per-page OCR results
        mock_engine = MockEngine.return_value
        mock_engine.process_images.return_value = [
            [
                {"text": "Page 1 Line 1", "confidence": 0.95, "bbox": [[10, 10], [100, 10], [100, 30], [10, 30]]},
                {"text": "Page 1 Line 2", "confidence": 0.90, "bbox": [[10, 40], [100, 40], [100, 60], [10, 60]]},
            ],
            [
                {"text": "Page 2 Line 1", "confidence": 0.88, "bbox": [[10, 10], [100, 10], [100, 30], [10, 30]]},
            ],
        ]

        pipeline = OCRPipeline("/path/to/doc.pdf", temp_dir, dpi=150)
        result = pipeline.run(first_page=1, last_page=2)

        # Renderer called with correct args
        mock_renderer.render_pdf_to_images.assert_called_once_with(1, 2, 150)

        # Engine called with the image paths from Renderer
        mock_engine.process_images.assert_called_once_with(mock_images)

        # Result is per-page grouped
        assert len(result) == 2
        assert len(result[0]) == 2  # Page 1: 2 lines
        assert len(result[1]) == 1  # Page 2: 1 line

        # Text and confidence preserved
        assert result[0][0]["text"] == "Page 1 Line 1"
        assert result[1][0]["text"] == "Page 2 Line 1"

        # Bbox coordinates have been scaled (72/150 = 0.48)
        # Image is 600px tall → page_height = 600 * 72/150 = 288 points
        # First point [10, 10]: x = 10*0.48 = 4.8, y = 288 - 10*0.48 = 283.2
        assert result[0][0]["bbox"][0] == [pytest.approx(4.8), pytest.approx(283.2)]

    @patch("backend.ocr.pipeline.Engine")
    @patch("backend.ocr.pipeline.Renderer")
    def test_pipeline_empty_pdf(self, MockRenderer, MockEngine, temp_dir):
        """Test pipeline with no pages rendered."""
        mock_renderer = MockRenderer.return_value
        mock_renderer.render_pdf_to_images.return_value = []

        mock_engine = MockEngine.return_value
        mock_engine.process_images.return_value = []

        pipeline = OCRPipeline("/path/to/empty.pdf", temp_dir)
        result = pipeline.run()

        assert result == []

    @patch("backend.ocr.pipeline.Engine")
    @patch("backend.ocr.pipeline.Renderer")
    def test_pipeline_page_with_no_text(self, MockRenderer, MockEngine, mock_images, temp_dir):
        """Test pipeline when a page has no recognized text."""
        mock_renderer = MockRenderer.return_value
        mock_renderer.render_pdf_to_images.return_value = mock_images

        mock_engine = MockEngine.return_value
        mock_engine.process_images.return_value = [
            [{"text": "Some text", "confidence": 0.95, "bbox": [[10, 10], [50, 10], [50, 30], [10, 30]]}],
            [],  # Page 2: blank scan, no text
        ]

        pipeline = OCRPipeline("/path/to/doc.pdf", temp_dir)
        result = pipeline.run()

        assert len(result) == 2
        assert len(result[0]) == 1
        assert result[1] == []

    @patch("backend.ocr.pipeline.Engine")
    @patch("backend.ocr.pipeline.Renderer")
    def test_pipeline_dpi_consistency(self, MockRenderer, MockEngine, temp_dir):
        """Test that the same DPI is passed to both Renderer and Normalizer."""
        dpi = 300
        pipeline = OCRPipeline("/path/to/doc.pdf", temp_dir, dpi=dpi)

        # Normalizer should use the same DPI
        assert pipeline.normalizer.dpi == dpi

        # Renderer.render_pdf_to_images should receive the same DPI
        mock_renderer = MockRenderer.return_value
        mock_renderer.render_pdf_to_images.return_value = []
        MockEngine.return_value.process_images.return_value = []

        pipeline.run()
        mock_renderer.render_pdf_to_images.assert_called_once_with(1, None, dpi)
