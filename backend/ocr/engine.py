from paddleocr import PaddleOCR

class Engine:
    def __init__(self, ocr_model=None):
        self.ocr_model = ocr_model or PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False
        )

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
