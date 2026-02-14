class Normalize():
    def __init__(self, dpi):
        self.dpi = dpi

    def normalize_to_pdf_coords(self, ocr_lines, page_height) -> list:
        """
        将 OCR 像素坐标转换为 PDF 点坐标。

        Args:
            ocr_lines (list[dict]): Engine.process_image() 的输出，每个元素格式为：
                {
                    "text": str,
                    "confidence": float,
                    "bbox": [[x1,y1], [x2,y2], ...],  # 像素坐标
                }
            page_height (float): PDF 页面高度，单位为点 (points)

        Returns:
            list[dict]: 转换后的结果，bbox 变为 PDF 点坐标（y 轴已翻转）：
                {
                    "text": str,
                    "confidence": float,
                    "bbox": [[pdf_x1, pdf_y1], [pdf_x2, pdf_y2], ...],  # 点坐标
                }
        """
        # 像素 → 点 的缩放因子：PDF 标准 1 点 = 1/72 英寸
        scale_factor = 72 / self.dpi

        normalized_lines = []
        for line in ocr_lines:
            pdf_bbox = []
            for x, y in line["bbox"]:
                pdf_x = x * scale_factor
                # PDF 坐标系 y 轴向下为正，但常规显示 y 轴向上，所以需要翻转
                pdf_y = page_height - (y * scale_factor)
                pdf_bbox.append([pdf_x, pdf_y])

            normalized_lines.append({
                "text": line["text"],
                "confidence": line["confidence"],
                "bbox": pdf_bbox
            })

        return normalized_lines

# 不在模块级别创建实例。
# DPI 参数应该和 Renderer 渲染时使用的 DPI 保持一致，
# 由 pipeline 统一传入，避免硬编码导致坐标计算错误。
