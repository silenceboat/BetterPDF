class OCRPipeline:
    def __init__(self, pdf_path, output_folder, dpi=150):
        self.pdf_path = pdf_path
        self.output_folder = output_folder
        self.dpi = dpi

        from .engine import Engine
        from .normalize import Normalize
        from .rendering import Renderer

        self.renderer = Renderer(pdf_path, output_folder)
        self.engine = Engine()
        self.normalizer = Normalize(dpi)

    def run(self, first_page=1, last_page=None) -> list:
        """
        执行完整的 OCR 流水线：渲染 → 识别 → 坐标转换。

        Args:
            first_page (int): 起始页码（1-based）
            last_page (int|None): 结束页码，None 表示到最后一页

        Returns:
            list[list[dict]]: 按页分组的识别结果，bbox 为 PDF 点坐标
        """
        # Step 1: PDF → PNG 图片
        image_paths = self.renderer.render_pdf_to_images(first_page, last_page, self.dpi)

        # Step 2: PNG 图片 → OCR 识别结果（按页分组）
        ocr_results = self.engine.process_images(image_paths)

        # Step 3: 逐页将像素坐标转换为 PDF 点坐标
        from PIL import Image
        normalized_results = []
        for image_path, page_lines in zip(image_paths, ocr_results):
            # 从渲染出的图片反推 PDF 页面高度（点）
            _, height_px = Image.open(image_path).size
            page_height = height_px * 72 / self.dpi

            normalized_lines = self.normalizer.normalize_to_pdf_coords(page_lines, page_height)
            normalized_results.append(normalized_lines)

        return normalized_results
