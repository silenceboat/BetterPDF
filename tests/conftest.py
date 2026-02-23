"""Pytest configuration and shared fixtures."""

import pytest
import numpy as np


@pytest.fixture
def sample_ocr_result():
    """Sample OCR result mimicking PaddleOCR output format."""
    return [
        {
            "text": "Hello World",
            "confidence": 0.95,
            "bbox": [[10, 10], [100, 10], [100, 30], [10, 30]]
        },
        {
            "text": "Second Line",
            "confidence": 0.88,
            "bbox": [[10, 40], [100, 40], [100, 60], [10, 60]]
        }
    ]


@pytest.fixture
def mock_paddle_result():
    """Mock PaddleOCR result structure."""
    class MockResult:
        def __init__(self):
            self.json = {
                "res": {
                    "rec_texts": ["Test Text", "Another Line"],
                    "rec_scores": np.array([0.95, 0.90]),
                    "dt_polys": [
                        np.array([[10, 10], [50, 10], [50, 30], [10, 30]]),
                        np.array([[10, 40], [50, 40], [50, 60], [10, 60]])
                    ]
                }
            }
    return MockResult()
