"""Tests for OCR engine module."""

import os

import pytest
from unittest.mock import Mock, patch
import numpy as np

from backend.ocr.engine import Engine


class TestEngine:
    """Test cases for Engine class."""

    def test_init_default_model(self):
        """Test Engine initializes with default PaddleOCR model."""
        with patch.object(Engine, "_cleanup_incomplete_model_cache"), patch.object(Engine, "_build_ocr_model") as mock_build:
            mock_ocr = Mock()
            mock_build.return_value = mock_ocr

            engine = Engine()

            assert engine.ocr_model == mock_ocr
            mock_build.assert_called_once()

    def test_init_custom_model(self):
        """Test Engine accepts custom OCR model."""
        custom_model = Mock()
        engine = Engine(ocr_model=custom_model)
        assert engine.ocr_model == custom_model

    def test_process_image(self):
        """Test processing image returns correct format."""
        mock_model = Mock()
        mock_result = Mock()

        # Setup mock OCR result
        mock_result.json = {
            "res": {
                "rec_texts": ["Hello", "World"],
                "rec_scores": np.array([0.95, 0.88]),
                "dt_polys": [np.array([[10, 10], [50, 10], [50, 30], [10, 30]]),
                             np.array([[60, 10], [100, 10], [100, 30], [60, 30]])]
            }
        }
        mock_model.predict.return_value = [mock_result]

        engine = Engine(ocr_model=mock_model)
        result = engine.process_image("test_image.png")

        assert len(result) == 2
        assert result[0]["text"] == "Hello"
        assert result[0]["confidence"] == 0.95
        assert result[0]["bbox"] == [[10, 10], [50, 10], [50, 30], [10, 30]]

        assert result[1]["text"] == "World"
        assert result[1]["confidence"] == 0.88

    def test_process_image_with_list_bbox(self):
        """Test processing image with bbox already as list."""
        mock_model = Mock()
        mock_result = Mock()

        # Setup mock OCR result with list bbox (not numpy array)
        mock_result.json = {
            "res": {
                "rec_texts": ["Test"],
                "rec_scores": np.array([0.99]),
                "dt_polys": [[[10, 10], [50, 10], [50, 30], [10, 30]]]
            }
        }
        mock_model.predict.return_value = [mock_result]

        engine = Engine(ocr_model=mock_model)
        result = engine.process_image("test_image.png")

        assert len(result) == 1
        assert result[0]["bbox"] == [[10, 10], [50, 10], [50, 30], [10, 30]]

    def test_process_image_empty_result(self):
        """Test processing image with no text detected."""
        mock_model = Mock()
        mock_result = Mock()

        mock_result.json = {
            "res": {
                "rec_texts": [],
                "rec_scores": np.array([]),
                "dt_polys": []
            }
        }
        mock_model.predict.return_value = [mock_result]

        engine = Engine(ocr_model=mock_model)
        result = engine.process_image("test_image.png")

        assert result == []

    def test_process_image_calls_predict(self):
        """Test that process_image calls predict with correct path."""
        mock_model = Mock()
        mock_result = Mock()
        mock_result.json = {"res": {"rec_texts": [], "rec_scores": np.array([]), "dt_polys": []}}
        mock_model.predict.return_value = [mock_result]

        engine = Engine(ocr_model=mock_model)
        engine.process_image("/path/to/image.png")

        mock_model.predict.assert_called_once_with("/path/to/image.png")

    def test_recover_broken_model_cache_uses_cache_root_fallback(self, tmp_path, monkeypatch):
        """Should remove broken model dir from cache root even if parsed path is unusable."""
        cache_root = tmp_path / "paddlex_cache"
        model_dir = cache_root / "official_models" / "PP-OCRv5_mobile_det"
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / "partial.tmp").write_text("incomplete", encoding="utf-8")

        monkeypatch.setenv("PADDLE_PDX_CACHE_HOME", str(cache_root))
        engine = Engine(ocr_model=Mock())

        error_message = (
            "(NotFound) Cannot open file "
            "C:\\Users\\tester\\.paddlex\\official_models\\PP-OCRv5_mobile_det\\inference.json, "
            "please confirm whether the file is normal."
        )

        assert engine._recover_broken_model_cache(error_message) is True
        assert not model_dir.exists()

    def test_cleanup_incomplete_model_cache_removes_only_broken_model_dirs(self, tmp_path, monkeypatch):
        """Should keep complete model dirs and remove only incomplete ones."""
        cache_root = tmp_path / "paddlex_cache"
        broken_dir = cache_root / "official_models" / "PP-OCRv5_mobile_det"
        good_dir = cache_root / "official_models" / "PP-OCRv5_mobile_rec"
        broken_dir.mkdir(parents=True, exist_ok=True)
        good_dir.mkdir(parents=True, exist_ok=True)
        (good_dir / "inference.json").write_text("{}", encoding="utf-8")

        monkeypatch.setenv("PADDLE_PDX_CACHE_HOME", str(cache_root))
        engine = Engine(ocr_model=Mock())
        engine._cleanup_incomplete_model_cache()

        assert not broken_dir.exists()
        assert good_dir.exists()

    def test_recover_broken_model_cache_does_not_delete_outside_allowed_roots(self, tmp_path):
        """Safety guard should prevent deleting arbitrary directories."""
        outside_dir = tmp_path / "outside_model_dir"
        outside_dir.mkdir(parents=True, exist_ok=True)
        (outside_dir / "placeholder.txt").write_text("x", encoding="utf-8")

        engine = Engine(ocr_model=Mock())
        error_message = f"(NotFound) Cannot open file {outside_dir}/inference.json, please confirm whether the file is normal."

        assert engine._recover_broken_model_cache(error_message) is False
        assert outside_dir.exists()

    def test_configure_model_source_prefers_local_bundle_root(self, tmp_path, monkeypatch):
        """Bundled model root should set Paddle cache env vars."""
        bundle_root = tmp_path / "models"
        bundle_root.mkdir(parents=True, exist_ok=True)

        monkeypatch.setenv("DEEPREAD_OCR_MODEL_DIR", str(bundle_root))
        monkeypatch.delenv("PADDLE_PDX_CACHE_HOME", raising=False)
        monkeypatch.delenv("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", raising=False)

        Engine(ocr_model=Mock())

        assert os.environ.get("PADDLE_PDX_CACHE_HOME") == str(bundle_root)
        assert os.environ.get("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK") == "True"

    def test_resolve_model_pair_prefers_local_pair(self, tmp_path, monkeypatch):
        """Model pair resolution should prefer a fully available local pair."""
        cache_root = tmp_path / "cache"
        server_det = cache_root / "official_models" / "PP-OCRv5_server_det"
        server_rec = cache_root / "official_models" / "PP-OCRv5_server_rec"
        server_det.mkdir(parents=True, exist_ok=True)
        server_rec.mkdir(parents=True, exist_ok=True)
        (server_det / "inference.json").write_text("{}", encoding="utf-8")
        (server_rec / "inference.json").write_text("{}", encoding="utf-8")

        monkeypatch.setenv("PADDLE_PDX_CACHE_HOME", str(cache_root))
        engine = Engine(ocr_model=Mock())
        assert engine._resolve_model_pair() == ("PP-OCRv5_server_det", "PP-OCRv5_server_rec")

    def test_create_ocr_model_retries_with_dependency_probe_patch(self):
        """Should retry once when dependency probe can be patched for packaged runtime."""
        engine = Engine(ocr_model=Mock())

        dep_error = None
        try:
            raise RuntimeError(
                Engine.PIPELINE_DEPENDENCY_ERROR_MARKER
            ) from RuntimeError("`OCR` requires additional dependencies.")
        except RuntimeError as err:
            dep_error = err

        assert dep_error is not None

        recovered_model = Mock()
        with (
            patch.object(engine, "_cleanup_incomplete_model_cache"),
            patch.object(engine, "_build_ocr_model", side_effect=[dep_error, recovered_model]) as mock_build,
            patch.object(engine, "_patch_paddlex_dependency_probe", return_value=True),
        ):
            assert engine._create_ocr_model_with_recovery() is recovered_model
            assert mock_build.call_count == 2

    def test_create_ocr_model_dependency_error_reports_missing_deps(self):
        """Should raise actionable message when OCR runtime deps are truly missing."""
        engine = Engine(ocr_model=Mock())

        dep_error = None
        try:
            raise RuntimeError(
                Engine.PIPELINE_DEPENDENCY_ERROR_MARKER
            ) from RuntimeError("`OCR` requires additional dependencies.")
        except RuntimeError as err:
            dep_error = err

        assert dep_error is not None

        with (
            patch.object(engine, "_cleanup_incomplete_model_cache"),
            patch.object(engine, "_build_ocr_model", side_effect=dep_error),
            patch.object(engine, "_patch_paddlex_dependency_probe", return_value=False),
            patch.object(engine, "_find_missing_ocr_dep_packages", return_value=["opencv-contrib-python", "tokenizers"]),
        ):
            with pytest.raises(RuntimeError, match="missing runtime dependencies"):
                engine._create_ocr_model_with_recovery()
