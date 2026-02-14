import os
import re
import shutil
from pathlib import Path


class Engine:
    def __init__(self, ocr_model=None):
        self._ocr_model = ocr_model
        self._configure_model_source()

    def _configure_model_source(self):
        """
        Configure model download source for better availability on Windows.

        PaddleOCR 3.x defaults to HuggingFace; on many CN networks this is
        unreliable. Respect user-provided env var, otherwise fall back to BOS.
        """
        if "PADDLE_PDX_MODEL_SOURCE" in os.environ:
            return
        if os.name == "nt":
            os.environ["PADDLE_PDX_MODEL_SOURCE"] = "BOS"

    @property
    def ocr_model(self):
        """Lazy-load PaddleOCR to avoid blocking startup."""
        if self._ocr_model is None:
            self._ocr_model = self._create_ocr_model_with_recovery()
        return self._ocr_model

    def _build_ocr_model(self):
        """
        Build PaddleOCR model with mobile defaults when supported.
        """
        from paddleocr import PaddleOCR

        kwargs = {
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": False,
        }

        # Prefer mobile models to reduce download size and improve cold-start.
        try:
            return PaddleOCR(
                text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name="PP-OCRv5_mobile_rec",
                **kwargs,
            )
        except TypeError:
            # Older/newer PaddleOCR builds may not expose these kwargs.
            return PaddleOCR(**kwargs)

    def _create_ocr_model_with_recovery(self):
        """
        Create OCR model and recover from broken local model cache once.
        """
        try:
            return self._build_ocr_model()
        except Exception as first_error:
            if not self._recover_broken_model_cache(str(first_error)):
                raise
            # Retry once after removing broken cache.
            return self._build_ocr_model()

    def _recover_broken_model_cache(self, error_message: str) -> bool:
        """
        Detect broken Paddle model files (missing inference.json) and remove
        the model directory so PaddleOCR can re-download it.
        """
        if "Cannot open file" not in error_message or "inference.json" not in error_message:
            return False

        # Works for both Windows and POSIX paths.
        match = re.search(r"Cannot open file\s+(.+?inference\.json)", error_message, re.IGNORECASE)
        if not match:
            return False

        broken_file = match.group(1).strip().strip("'\"")
        broken_dir = Path(os.path.dirname(broken_file))
        if not broken_dir.exists():
            return False

        home_dir = Path.home().resolve()
        try:
            resolved_dir = broken_dir.resolve()
        except Exception:
            return False

        # Safety guard: only delete inside user cache locations.
        allowed_roots = [
            home_dir / ".paddlex",
            home_dir / ".paddleocr",
        ]
        resolved_norm = os.path.normcase(str(resolved_dir))
        allowed_norm = [os.path.normcase(str(root)) for root in allowed_roots]
        if not any(resolved_norm.startswith(root) for root in allowed_norm):
            return False

        shutil.rmtree(resolved_dir, ignore_errors=True)
        return True

    def process_image(self, image_path) -> list:
        """
        对单张图片执行 OCR 识别。

        Args:
            image_path (str): 单张图片的文件路径

        Returns:
            list[dict]: 该页所有行的识别结果，每个元素格式为：
            {
                "text": str,          # 识别出的文字
                "confidence": float,  # 置信度 (0~1)
                "bbox": list          # 多边形顶点坐标 [[x1,y1], [x2,y2], ...]，单位为像素
            }
        """
        try:
            result = self.ocr_model.predict(image_path)
        except Exception as first_error:
            # Some PaddleOCR builds fail lazily on first predict when cached
            # model files are corrupted. Recover once and retry.
            if not self._recover_broken_model_cache(str(first_error)):
                raise
            self._ocr_model = None
            result = self.ocr_model.predict(image_path)
        data = result[0].json["res"]

        lines = []
        for text, score, poly in zip(
            data["rec_texts"],
            data["rec_scores"],
            data["dt_polys"]
        ):
            lines.append({
                "text": text,
                "confidence": float(score),
                "bbox": poly.tolist() if hasattr(poly, 'tolist') else poly
            })

        return lines

    def process_images(self, image_paths) -> list:
        """
        对多张图片执行 OCR 识别，按页分组返回。

        Args:
            image_paths (list[str]): 图片路径列表，每个路径对应 PDF 的一页

        Returns:
            list[list[dict]]: 外层 list 的每个元素对应一页，
                              内层 list 是该页的所有行识别结果
            例如：
            [
                [ {"text": "第一页第一行", ...}, {"text": "第一页第二行", ...} ],  # 第 1 页
                [ {"text": "第二页第一行", ...} ],                                # 第 2 页
            ]
        """
        return [self.process_image(path) for path in image_paths]

# 不在模块级别创建实例。
# PaddleOCR 模型加载很慢且占用大量内存，
# 应该由 pipeline 在需要时创建，并控制其生命周期。
