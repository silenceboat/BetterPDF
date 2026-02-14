from pdf2image import convert_from_path
import os

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

        pages = convert_from_path(self.pdf_path, first_page=first_page, last_page=last_page, dpi=dpi)

        image_paths = []
        for i, page in enumerate(pages, start=first_page):
            page_name = os.path.splitext(os.path.basename(self.pdf_path))[0] + f'_page{i}_dpi{dpi}.png'
            page_save_path = os.path.join(self.output_folder, page_name)
            page.save(page_save_path, 'PNG')
            image_paths.append(page_save_path)

        return image_paths

# 不在模块级别创建实例。
# Renderer 必须知道 pdf_path 和 output_folder 才能工作，
# 这些参数在模块加载时不可知，应由 pipeline 按需创建。
