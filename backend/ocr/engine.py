import os
import re
import shutil
import tempfile
import importlib.util
from functools import lru_cache
from pathlib import Path


class Engine:
    MODEL_PAIRS = (
        ("PP-OCRv5_mobile_det", "PP-OCRv5_mobile_rec"),
        ("PP-OCRv5_server_det", "PP-OCRv5_server_rec"),
    )
    PIPELINE_DEPENDENCY_ERROR_MARKER = "A dependency error occurred during pipeline creation"
    MODEL_NAME_MISMATCH_MARKER = "Model name mismatch"
    FALLBACK_OCR_DEP_PACKAGES = (
        "Jinja2",
        "beautifulsoup4",
        "einops",
        "ftfy",
        "imagesize",
        "lxml",
        "opencv-contrib-python",
        "openpyxl",
        "premailer",
        "pyclipper",
        "pypdfium2",
        "python-bidi",
        "regex",
        "safetensors",
        "scikit-learn",
        "scipy",
        "sentencepiece",
        "shapely",
        "tiktoken",
        "tokenizers",
    )
    DEP_IMPORT_MAP = {
        "aistudio-sdk": ("aistudio_sdk",),
        "beautifulsoup4": ("bs4",),
        "jinja2": ("jinja2",),
        "opencv-contrib-python": ("cv2",),
        "pillow": ("PIL",),
        "py-cpuinfo": ("cpuinfo",),
        "python-bidi": ("bidi",),
        "pyyaml": ("yaml",),
        "ruamel-yaml": ("ruamel.yaml",),
        "scikit-learn": ("sklearn",),
        "typing-extensions": ("typing_extensions",),
    }

    def __init__(self, ocr_model=None):
        self._ocr_model = ocr_model
        self._configure_model_source()

    def _configure_model_source(self):
        """
        Configure model download source for better availability on Windows.

        PaddleOCR 3.x defaults to HuggingFace; on many CN networks this is
        unreliable. Respect user-provided env var, otherwise fall back to BOS.
        """
        packaged_model_root = os.environ.get("DEEPREAD_OCR_MODEL_DIR", "").strip()
        if packaged_model_root:
            self._activate_local_model_root(packaged_model_root)

        if os.name == "nt":
            os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "BOS")
            self._configure_windows_cache_home()

    def _activate_local_model_root(self, model_root: str):
        """
        Point PaddleX cache to a bundled model root when available.
        """
        root = Path(model_root).expanduser()
        try:
            resolved = root.resolve()
        except Exception:
            resolved = root

        if not resolved.exists():
            return

        os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(resolved))
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

    @staticmethod
    def _is_ascii_path(path_str: str) -> bool:
        try:
            path_str.encode("ascii")
            return True
        except UnicodeEncodeError:
            return False

    def _configure_windows_cache_home(self):
        """
        On Windows, Paddle's native loader may fail on non-ASCII cache paths.
        Move PaddleX cache to an ASCII path unless user has set it explicitly.
        """
        if "PADDLE_PDX_CACHE_HOME" in os.environ:
            return

        home_dir = str(Path.home())
        if self._is_ascii_path(home_dir):
            return

        candidates = []
        public_dir = os.environ.get("PUBLIC")
        if public_dir:
            candidates.append(Path(public_dir) / "BetterPDF" / "paddlex_cache")
        candidates.append(Path.cwd() / ".paddlex_cache")
        candidates.append(Path(tempfile.gettempdir()) / "betterpdf_paddlex_cache")

        for candidate in candidates:
            try:
                resolved = candidate.resolve()
                if not self._is_ascii_path(str(resolved)):
                    continue
                resolved.mkdir(parents=True, exist_ok=True)
                os.environ["PADDLE_PDX_CACHE_HOME"] = str(resolved)
                return
            except Exception:
                continue

    def _get_explicit_model_root(self) -> Path | None:
        model_root = os.environ.get("DEEPREAD_OCR_MODEL_DIR", "").strip()
        if not model_root:
            return None
        root = Path(model_root).expanduser()
        try:
            return root.resolve()
        except Exception:
            return root

    def _get_model_cache_roots(self) -> list[Path]:
        explicit_root = self._get_explicit_model_root()
        if explicit_root is not None:
            # When explicit model root is provided (packaged build), keep OCR
            # model selection isolated from any stale user-level caches.
            return [explicit_root]

        roots: list[Path] = []

        pdx_cache_home = os.environ.get("PADDLE_PDX_CACHE_HOME")
        if pdx_cache_home:
            roots.append(Path(pdx_cache_home))

        home_dir = Path.home()
        roots.extend([
            home_dir / ".paddlex",
            home_dir / ".paddleocr",
        ])

        # De-duplicate while preserving order.
        deduped: list[Path] = []
        seen: set[str] = set()
        for root in roots:
            root_key = os.path.normcase(str(root))
            if root_key in seen:
                continue
            seen.add(root_key)
            deduped.append(root)
        return deduped

    @staticmethod
    def _iter_model_dir_candidates(root: Path, model_name: str) -> tuple[Path, Path]:
        return (
            root / "official_models" / model_name,
            root / model_name,
        )

    def _get_local_model_dir(self, model_name: str) -> Path | None:
        for root in self._get_model_cache_roots():
            for model_dir in self._iter_model_dir_candidates(root, model_name):
                if (model_dir / "inference.json").exists():
                    return model_dir
        return None

    def _resolve_model_pair_and_dirs(self) -> tuple[str, str, Path | None, Path | None]:
        roots = self._get_model_cache_roots()
        for det_name, rec_name in self.MODEL_PAIRS:
            for root in roots:
                det_dir = None
                rec_dir = None
                for candidate in self._iter_model_dir_candidates(root, det_name):
                    if (candidate / "inference.json").exists():
                        det_dir = candidate
                        break
                for candidate in self._iter_model_dir_candidates(root, rec_name):
                    if (candidate / "inference.json").exists():
                        rec_dir = candidate
                        break
                if det_dir and rec_dir:
                    return det_name, rec_name, det_dir, rec_dir
        det_name, rec_name = self.MODEL_PAIRS[0]
        return det_name, rec_name, None, None

    def _resolve_model_pair(self) -> tuple[str, str]:
        """
        Prefer already-downloaded model pairs; fall back to mobile pair.
        """
        det_name, rec_name, _, _ = self._resolve_model_pair_and_dirs()
        return det_name, rec_name

    def _is_within_allowed_roots(self, target_dir: Path, allowed_roots: list[Path]) -> bool:
        try:
            target_resolved = target_dir.resolve()
        except Exception:
            return False

        target_norm = os.path.normcase(str(target_resolved))
        for root in allowed_roots:
            try:
                root_resolved = root.resolve()
            except Exception:
                continue

            root_norm = os.path.normcase(str(root_resolved))
            try:
                common = os.path.commonpath([target_norm, root_norm])
            except ValueError:
                continue
            if common == root_norm:
                return True
        return False

    def _safe_delete_model_dir(self, target_dir: Path, allowed_roots: list[Path]) -> bool:
        if not target_dir.exists():
            return False
        if not self._is_within_allowed_roots(target_dir, allowed_roots):
            return False
        shutil.rmtree(target_dir, ignore_errors=True)
        return True

    def _cleanup_incomplete_model_cache(self):
        """
        PaddleX considers existing model directories as "downloaded" even if
        key files are missing. Remove incomplete directories proactively.
        """
        allowed_roots = self._get_model_cache_roots()
        model_names = {
            model_name
            for det_name, rec_name in self.MODEL_PAIRS
            for model_name in (det_name, rec_name)
        }

        for root in allowed_roots:
            for model_name in model_names:
                for model_dir in self._iter_model_dir_candidates(root, model_name):
                    if not model_dir.exists():
                        continue
                    # The current PaddleOCR/PaddleX stack expects inference.json.
                    if (model_dir / "inference.json").exists():
                        continue
                    self._safe_delete_model_dir(model_dir, allowed_roots)

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
        det_name, rec_name, det_dir, rec_dir = self._resolve_model_pair_and_dirs()

        if det_dir and rec_dir:
            local_kwargs = {
                "text_detection_model_dir": str(det_dir),
                "text_recognition_model_dir": str(rec_dir),
                "text_detection_model_name": det_name,
                "text_recognition_model_name": rec_name,
            }
            try:
                return PaddleOCR(**local_kwargs, **kwargs)
            except TypeError:
                # Some builds may not expose *_model_name kwargs together with
                # *_model_dir; retry with directory-only arguments.
                legacy_local_kwargs = {
                    "text_detection_model_dir": str(det_dir),
                    "text_recognition_model_dir": str(rec_dir),
                }
                try:
                    return PaddleOCR(**legacy_local_kwargs, **kwargs)
                except Exception as local_error:
                    # If local dir metadata and requested model name are not
                    # aligned, fall back to name-based resolution.
                    if self.MODEL_NAME_MISMATCH_MARKER not in str(local_error):
                        raise
            except Exception as local_error:
                if self.MODEL_NAME_MISMATCH_MARKER not in str(local_error):
                    raise

        # Prefer mobile models to reduce download size and improve cold-start.
        try:
            return PaddleOCR(
                text_detection_model_name=det_name,
                text_recognition_model_name=rec_name,
                **kwargs,
            )
        except TypeError:
            # Older/newer PaddleOCR builds may not expose these kwargs.
            return PaddleOCR(**kwargs)

    @staticmethod
    def _module_exists(module_name: str) -> bool:
        try:
            return importlib.util.find_spec(module_name) is not None
        except Exception:
            return False

    def _dep_to_module_candidates(self, dep_name: str) -> tuple[str, ...]:
        normalized = dep_name.strip().lower()
        mapped = self.DEP_IMPORT_MAP.get(normalized)
        if mapped:
            return mapped
        return (normalized.replace("-", "_"),)

    def _get_paddlex_ocr_dep_packages(self) -> list[str]:
        try:
            from paddlex.utils import deps as paddlex_deps

            extra = getattr(paddlex_deps, "EXTRAS", {}).get("ocr")
            if extra:
                return sorted(extra.keys())
        except Exception:
            pass
        return list(self.FALLBACK_OCR_DEP_PACKAGES)

    def _find_missing_ocr_dep_packages(self) -> list[str]:
        missing: list[str] = []
        for dep_name in self._get_paddlex_ocr_dep_packages():
            if any(self._module_exists(name) for name in self._dep_to_module_candidates(dep_name)):
                continue
            missing.append(dep_name)
        return missing

    def _is_pipeline_dependency_error(self, error: Exception) -> bool:
        if self.PIPELINE_DEPENDENCY_ERROR_MARKER in str(error):
            return True
        cause = getattr(error, "__cause__", None)
        if cause is None:
            return False
        cause_msg = str(cause)
        return (
            "requires additional dependencies" in cause_msg
            or "following dependencies are not available" in cause_msg
        )

    def _is_extra_dependency_error(self, error: Exception) -> bool:
        cause = getattr(error, "__cause__", None)
        if cause is None:
            return False
        cause_msg = str(cause)
        return (
            "requires additional dependencies" in cause_msg
            or "following dependencies are not available" in cause_msg
        )

    def _patch_paddlex_dependency_probe(self) -> bool:
        try:
            from paddlex.utils import deps as paddlex_deps
        except Exception:
            return False

        if getattr(paddlex_deps, "_betterpdf_dep_probe_patched", False):
            return True

        original_is_dep_available = paddlex_deps.is_dep_available

        @lru_cache(maxsize=None)
        def _patched_is_dep_available(dep, /, check_version=False):
            try:
                if original_is_dep_available(dep, check_version=check_version):
                    return True
            except Exception:
                if check_version:
                    return False

            # Frozen/packed builds may miss dist-info metadata while the module
            # itself is bundled and importable.
            if check_version:
                return False
            return any(
                self._module_exists(name)
                for name in self._dep_to_module_candidates(dep)
            )

        paddlex_deps.is_dep_available = _patched_is_dep_available
        clear_cache = getattr(getattr(paddlex_deps, "is_extra_available", None), "cache_clear", None)
        if callable(clear_cache):
            clear_cache()
        paddlex_deps._betterpdf_dep_probe_patched = True
        return True

    def _format_pipeline_dependency_error(self, error: Exception) -> RuntimeError:
        missing_deps = self._find_missing_ocr_dep_packages()
        if missing_deps:
            msg = (
                "OCR pipeline missing runtime dependencies: "
                + ", ".join(missing_deps)
                + '. Install/update with `pip install "paddlex[ocr]"` '
                "or use the latest official BetterPDF release package."
            )
            return RuntimeError(msg)

        msg = (
            "OCR dependency check failed during pipeline creation. "
            "Modules are present, but package metadata may be incomplete in this build."
        )
        return RuntimeError(msg)

    def _create_ocr_model_with_recovery(self):
        """
        Create OCR model and recover from broken local model cache once.
        """
        self._cleanup_incomplete_model_cache()
        try:
            return self._build_ocr_model()
        except Exception as first_error:
            if self._recover_model_name_mismatch(str(first_error)):
                self._cleanup_incomplete_model_cache()
                return self._build_ocr_model()

            if self._is_extra_dependency_error(first_error):
                # Retry once with metadata-independent dependency probing.
                if self._patch_paddlex_dependency_probe():
                    try:
                        return self._build_ocr_model()
                    except Exception as patched_error:
                        first_error = patched_error

            if self._is_pipeline_dependency_error(first_error):
                raise self._format_pipeline_dependency_error(first_error) from first_error

            if not self._recover_broken_model_cache(str(first_error)):
                raise
            # Retry once after removing broken cache.
            self._cleanup_incomplete_model_cache()
            try:
                return self._build_ocr_model()
            except Exception as second_error:
                if self._is_pipeline_dependency_error(second_error):
                    raise self._format_pipeline_dependency_error(second_error) from second_error
                raise

    def _recover_broken_model_cache(self, error_message: str) -> bool:
        """
        Detect broken Paddle model files (missing inference.json) and remove
        the model directory so PaddleOCR can re-download it.
        """
        if "Cannot open file" not in error_message or "inference.json" not in error_message:
            return False

        allowed_roots = self._get_model_cache_roots()
        candidate_dirs: list[Path] = []

        # Works for both Windows and POSIX paths.
        match = re.search(
            r"Cannot open file\s+(.+?inference\.json)",
            error_message,
            re.IGNORECASE,
        )
        if match:
            broken_file = match.group(1).strip().strip("'\"")
            candidate_dirs.append(Path(os.path.dirname(broken_file)))

        # Fallback: if path parsing fails, locate model directory by model name.
        model_match = re.search(
            r"official_models[\\/]+([^\\/,\s]+)[\\/]+inference\.json",
            error_message,
            re.IGNORECASE,
        )
        if model_match:
            model_name = model_match.group(1)
            for root in allowed_roots:
                candidate_dirs.append(root / "official_models" / model_name)
                candidate_dirs.append(root / model_name)

        deleted_any = False
        seen: set[str] = set()
        for candidate in candidate_dirs:
            key = os.path.normcase(str(candidate))
            if key in seen:
                continue
            seen.add(key)
            if self._safe_delete_model_dir(candidate, allowed_roots):
                deleted_any = True

        return deleted_any

    def _recover_model_name_mismatch(self, error_message: str) -> bool:
        """
        Model files may be placed under a wrong model folder name in stale
        caches. Delete those directories and force a clean model restore.
        """
        if self.MODEL_NAME_MISMATCH_MARKER not in error_message:
            return False

        allowed_roots = self._get_model_cache_roots()
        explicit_root = self._get_explicit_model_root()
        explicit_root_key = (
            os.path.normcase(str(explicit_root))
            if explicit_root is not None
            else None
        )
        model_names = {
            model_name
            for det_name, rec_name in self.MODEL_PAIRS
            for model_name in (det_name, rec_name)
        }

        deleted_any = False
        for root in allowed_roots:
            root_key = os.path.normcase(str(root))
            if explicit_root_key is not None and root_key == explicit_root_key:
                continue
            for model_name in model_names:
                for model_dir in self._iter_model_dir_candidates(root, model_name):
                    if self._safe_delete_model_dir(model_dir, allowed_roots):
                        deleted_any = True
        return deleted_any

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
            recovered = (
                self._recover_broken_model_cache(str(first_error))
                or self._recover_model_name_mismatch(str(first_error))
            )
            if not recovered:
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
