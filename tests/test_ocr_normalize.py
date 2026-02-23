"""Tests for OCR normalize module."""

import pytest

from backend.ocr.normalize import Normalize


class TestNormalize:
    """Test cases for Normalize class."""

    def test_init(self):
        """Test Normalize initializes with correct DPI."""
        norm = Normalize(dpi=300)
        assert norm.dpi == 300

    def test_normalize_single_line(self):
        """Test normalizing a single OCR line."""
        norm = Normalize(dpi=72)  # 1:1 scale for simplicity
        page_height = 100

        ocr_lines = [
            {"text": "Hello", "confidence": 0.95, "bbox": [[10, 10], [50, 10], [50, 30], [10, 30]]}
        ]

        result = norm.normalize_to_pdf_coords(ocr_lines, page_height)

        assert len(result) == 1
        assert result[0]['text'] == "Hello"
        assert result[0]['confidence'] == 0.95
        # Y should be inverted: page_height - y
        assert result[0]['bbox'] == [[10, 90], [50, 90], [50, 70], [10, 70]]

    def test_normalize_multiple_lines(self):
        """Test normalizing multiple OCR lines."""
        norm = Normalize(dpi=72)
        page_height = 200

        ocr_lines = [
            {"text": "First", "confidence": 0.90, "bbox": [[10, 10], [50, 10], [50, 30], [10, 30]]},
            {"text": "Second", "confidence": 0.85, "bbox": [[10, 40], [50, 40], [50, 60], [10, 60]]}
        ]

        result = norm.normalize_to_pdf_coords(ocr_lines, page_height)

        assert len(result) == 2
        assert result[0]['text'] == "First"
        assert result[1]['text'] == "Second"
        # Check Y inversion for second line
        assert result[1]['bbox'][0] == [10, 160]  # 200 - 40 = 160

    def test_normalize_scale_factor(self):
        """Test scale factor conversion from pixels to points."""
        norm = Normalize(dpi=150)  # scale_factor = 72/150 = 0.48
        page_height = 100

        ocr_lines = [
            {"text": "Text", "confidence": 0.95, "bbox": [[100, 100], [200, 100], [200, 200], [100, 200]]}
        ]

        result = norm.normalize_to_pdf_coords(ocr_lines, page_height)

        # X: 100 * 0.48 = 48
        # Y: 100 - (100 * 0.48) = 100 - 48 = 52
        assert result[0]['bbox'][0] == [48.0, 52.0]
        assert result[0]['bbox'][1] == [96.0, 52.0]

    def test_normalize_empty_list(self):
        """Test normalizing empty list."""
        norm = Normalize(dpi=150)
        result = norm.normalize_to_pdf_coords([], 100)
        assert result == []

    def test_normalize_various_dpi(self):
        """Test normalization with various DPI values."""
        test_cases = [
            (72, 72, 72, 72.0, 100 - 72.0),
            (150, 100, 100, 48.0, 100 - 48.0),
            (300, 100, 100, 24.0, 100 - 24.0),
        ]

        for dpi, input_x, input_y, expected_x, expected_y in test_cases:
            norm = Normalize(dpi=dpi)
            ocr_lines = [
                {"text": "Test", "confidence": 0.95, "bbox": [[input_x, input_y]]}
            ]
            result = norm.normalize_to_pdf_coords(ocr_lines, page_height=100)
            assert result[0]['bbox'][0] == [expected_x, expected_y]

    def test_normalize_preserves_text_and_score(self):
        """Test that text and score are preserved unchanged."""
        norm = Normalize(dpi=150)
        ocr_lines = [
            {"text": "Special Characters: 你好", "confidence": 0.99, "bbox": [[0, 0], [10, 0], [10, 10], [0, 10]]}
        ]

        result = norm.normalize_to_pdf_coords(ocr_lines, page_height=100)

        assert result[0]['text'] == "Special Characters: 你好"
        assert result[0]['confidence'] == 0.99
