# PDFEngine 迁移到 pdf2image 指南（历史文档）

> 当前主分支 OCR 渲染链路已使用 `PyMuPDF`，不再依赖 `pdf2image + poppler`。
> 本文档仅保留作为历史迁移记录，请勿作为当前发布配置依据。

## 概述

本文档记录将 `PDFEngine` 从 PyMuPDF (fitz) 迁移到 pdf2image 的注意事项和接口规范。

## 为什么要用 pdf2image

- **扫描型 PDF 渲染**：pdf2image 底层使用 poppler，对某些扫描型 PDF 的兼容性更好
- **图像质量**：支持更多渲染选项（DPI 控制、颜色空间等）
- **OCR 集成**：与 pytesseract 配合更自然，适合处理扫描文档

## 现有调用点

`backend/api.py` 中调用了以下 `PDFEngine` 方法：

| 行号 | 调用代码 | 说明 |
|------|----------|------|
| 46 | `PDFEngine(file_path)` | 构造函数 |
| 44 | `pdf_engine.close()` | 关闭旧文档 |
| 49 | `pdf_engine.get_metadata()` | 获取 PDF 元数据 |
| 79 | `pdf_engine.render_page(page_num, zoom)` | 渲染页面为 base64 图片 |
| 80 | `pdf_engine.get_page_size(page_num)` | 获取页面尺寸 |
| 108 | `pdf_engine.extract_text(page_num, rect=None)` | 提取文字 |
| 132 | `pdf_engine.search_text(query, page_num=None)` | 搜索文字 |

## 接口规范（必须保持一致）

重写时请保持以下方法签名完全一致：

```python
from typing import Optional, Tuple

class PDFEngine:
    def __init__(self, file_path: str) -> None:
        """初始化，打开 PDF 文件"""
        pass

    def close(self) -> None:
        """关闭 PDF，释放资源"""
        pass

    def get_metadata(self) -> dict:
        """
        返回格式：
        {
            "file_name": str,
            "page_count": int,
            "title": str,
            "author": str,
            "subject": str,
        }
        """
        pass

    def render_page(self, page_num: int, zoom: float = 1.0) -> str:
        """
        渲染页面为 base64 编码的 PNG 图片
        - page_num: 1-based 页码
        - zoom: 缩放比例，1.0 = 100%
        - 返回: base64 字符串（不含 data URI 前缀）
        """
        pass

    def get_page_size(self, page_num: int) -> Tuple[float, float]:
        """
        获取页面尺寸（单位：points）
        - page_num: 1-based 页码
        - 返回: (width, height)
        """
        pass

    def extract_text(self, page_num: int, rect: Optional[dict] = None) -> str:
        """
        提取文字
        - page_num: 1-based 页码
        - rect: 可选，格式 {"x1": float, "y1": float, "x2": float, "y2": float}
        - 返回: 提取的文本字符串
        """
        pass

    def search_text(self, query: str, page_num: Optional[int] = None) -> list:
        """
        搜索文字
        - query: 搜索关键词
        - page_num: 可选，指定搜索某页（1-based），None 表示搜索全部
        - 返回: [{"page": int, "rect": {"x1": x1, "y1": y1, "x2": x2, "y2": y2}}, ...]
        """
        pass
```

## 依赖安装

```bash
# 添加 Python 依赖
uv add pdf2image pillow

# 如果需要 OCR 功能
uv add pytesseract
```

### 系统依赖

pdf2image 需要 poppler 工具：

```bash
# Ubuntu/Debian
sudo apt install poppler-utils

# macOS
brew install poppler

# Windows
# 下载 poppler for Windows，添加到 PATH
# https://github.com/oschwartz10612/poppler-windows/releases
```

## 关键差异点

### 1. 页码索引

```python
# pdf2image 的页码从 0 开始
# 但你的接口要求 1-based，所以需要转换
pdf2image.convert_from_path(pdf_path, first_page=page_num, last_page=page_num)
# 这里的 page_num 是 1-based（pdf2image 内部会自动处理）
```

### 2. 渲染方式

```python
from pdf2image import convert_from_path
from PIL import Image
import base64
from io import BytesIO

# 按 DPI 渲染（推荐）
images = convert_from_path(
    self.file_path,
    dpi=int(72 * zoom),  # 标准 PDF DPI 是 72
    first_page=page_num,
    last_page=page_num,
    fmt='png'
)
img = images[0]

# 转换为 base64
buffer = BytesIO()
img.save(buffer, format='PNG')
base64_str = base64.b64encode(buffer.getvalue()).decode()
```

### 3. 文字提取（重要差异）

**pdf2image 本身不提供文字提取**，需要配合 OCR：

```python
import pytesseract

def extract_text(self, page_num: int, rect: Optional[dict] = None) -> str:
    # 先渲染为图片
    images = convert_from_path(
        self.file_path,
        first_page=page_num,
        last_page=page_num
    )
    img = images[0]

    # 如果指定了区域，裁剪
    if rect:
        # 注意坐标单位转换（points -> pixels）
        dpi = 200  # 你渲染时用的 DPI
        scale = dpi / 72
        crop_box = (
            int(rect["x1"] * scale),
            int(rect["y1"] * scale),
            int(rect["x2"] * scale),
            int(rect["y2"] * scale),
        )
        img = img.crop(crop_box)

    # OCR 识别
    text = pytesseract.image_to_string(img, lang='chi_sim+eng')
    return text
```

### 4. 搜索功能

pdf2image 没有搜索功能，需要：
- 方案 A：先用 OCR 提取每页文字，再在 Python 中搜索
- 方案 B：结合 pytesseract 的 bounding box 功能定位文字位置

```python
def search_text(self, query: str, page_num: Optional[int] = None) -> list:
    results = []
    pages_to_search = [page_num] if page_num else range(1, self.page_count + 1)

    for pn in pages_to_search:
        # 获取页面图片
        images = convert_from_path(self.file_path, first_page=pn, last_page=pn)
        img = images[0]

        # OCR 获取带位置信息的数据
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

        # 搜索关键词，匹配位置
        for i, text in enumerate(data['text']):
            if query.lower() in text.lower():
                results.append({
                    "page": pn,
                    "rect": {
                        "x1": data['left'][i],
                        "y1": data['top'][i],
                        "x2": data['left'][i] + data['width'][i],
                        "y2": data['top'][i] + data['height'][i],
                    }
                })

    return results
```

## 注意事项

1. **性能**：pdf2image + poppler 比 PyMuPDF 慢，特别是大文件
2. **内存**：convert_from_path 会加载所有请求的页面到内存，注意分页加载
3. **坐标系统**：pdf2image 返回的是像素坐标，你的接口要求 points（72 DPI），需要转换
4. **OCR 依赖**：文字提取需要 Tesseract OCR 引擎，用户需要额外安装

## 推荐的实现策略

1. 保持现有 `pdf_engine.py` 文件，修改内部实现
2. 添加 `poppler_path` 参数（Windows 用户需要）
3. 考虑添加缓存机制（避免重复渲染同一页）
4. 对非扫描型 PDF，考虑用 `pdfplumber` 等库提取文字（比 OCR 快且准）

## 参考链接

- [pdf2image 文档](https://github.com/Belval/pdf2image)
- [pytesseract 文档](https://github.com/madmaze/pytesseract)
- [poppler 下载](https://poppler.freedesktop.org/)
