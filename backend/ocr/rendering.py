import os
import fitz  # PyMuPDF

class Renderer:
    def __init__(self, pdf_path, output_folder):
        """
        Args:
            pdf_path (str): PDF 文件路径，必须在创建时指定
            output_folder (str): 渲染图片的输出目录
        """
        self.pdf_path = pdf_path
        self.output_folder = output_folder

    def render_pdf_to_images(self, first_page=1, last_page=None, dpi=150) -> list:
        """
        将 PDF 指定页面渲染为 PNG 图片。

        Args:
            first_page (int): 起始页码（1-based）
            last_page (int|None): 结束页码，None 表示到最后一页
            dpi (int): 渲染分辨率

        Returns:
            list[str]: 生成的 PNG 图片文件路径列表，按页码顺序排列
        """
        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)

        image_paths = []
        doc = fitz.open(self.pdf_path)
        try:
            page_count = len(doc)
            if page_count == 0:
                return image_paths

            start = max(1, int(first_page))
            end = page_count if last_page is None else min(int(last_page), page_count)
            if start > end:
                return image_paths

            # PDF points are at 72 DPI; scale matrix to target DPI.
            scale = float(dpi) / 72.0
            matrix = fitz.Matrix(scale, scale)

            for page_num in range(start, end + 1):
                page = doc[page_num - 1]
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                page_name = os.path.splitext(os.path.basename(self.pdf_path))[0] + f'_page{page_num}_dpi{dpi}.png'
                page_save_path = os.path.join(self.output_folder, page_name)
                pix.save(page_save_path)
                image_paths.append(page_save_path)
        finally:
            doc.close()

        return image_paths

# 不在模块级别创建实例。
# Renderer 必须知道 pdf_path 和 output_folder 才能工作，
# 这些参数在模块加载时不可知，应由 pipeline 按需创建。
