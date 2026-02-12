"""
Markdown Preview Widget - Renders markdown content with clickable PDF links.

This widget provides:
- Rendered markdown display
- Clickable PDF links [[pdf:doc_id#page=N]]
"""

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTextBrowser, QWidget


class MarkdownPreviewWidget(QTextBrowser):
    """
    Widget for previewing markdown content with PDF link support.

    Signals:
        pdfLinkClicked(str): Emitted when a PDF link is clicked
    """

    pdfLinkClicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setOpenExternalLinks(False)
        self.setOpenLinks(False)
        self.anchorClicked.connect(self._on_anchor_clicked)

        self._raw_markdown = ""

    def set_markdown(self, markdown: str) -> None:
        """
        Set the markdown content to display.

        Args:
            markdown: The markdown text to render
        """
        self._raw_markdown = markdown
        html = self._markdown_to_html(markdown)
        self.setHtml(html)

    def _markdown_to_html(self, markdown: str) -> str:
        """Convert markdown to HTML with PDF link support."""
        text = markdown

        # Escape HTML special characters
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")

        # Convert PDF links [[pdf:doc_id#page=N]] to HTML links
        pdf_link_pattern = r"\[\[pdf:([^#]+)#page=(\d+)\]\]"

        def replace_pdf_link(match):
            doc_id = match.group(1)
            page = match.group(2)
            link_text = f"📄 Page {page}"
            return f'<a href="pdf://{doc_id}#{page}" style="color: #1976d2; text-decoration: none; background-color: #e3f2fd; padding: 2px 6px; border-radius: 4px;">{link_text}</a>'

        text = re.sub(pdf_link_pattern, replace_pdf_link, text)

        # Convert headers
        text = re.sub(r"^### (.+)$", r"<h3>\1</h3>", text, flags=re.MULTILINE)
        text = re.sub(r"^## (.+)$", r"<h2>\1</h2>", text, flags=re.MULTILINE)
        text = re.sub(r"^# (.+)$", r"<h1>\1</h1>", text, flags=re.MULTILINE)

        # Convert bold and italic
        text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)

        # Convert code
        text = re.sub(r"`(.+?)`", r"<code style='background-color: #f5f5f5; padding: 2px 4px; border-radius: 3px; font-family: monospace;'>\1</code>", text)

        # Convert bullet lists
        lines = text.split("\n")
        result = []
        in_list = False

        for line in lines:
            if line.startswith("- "):
                if not in_list:
                    result.append("<ul>")
                    in_list = True
                result.append(f"<li>{line[2:]}</li>")
            elif re.match(r"^\d+\. ", line):
                if not in_list:
                    result.append("<ol>")
                    in_list = True
                content = re.sub(r"^\d+\. ", "", line)
                result.append(f"<li>{content}</li>")
            else:
                if in_list:
                    result.append("</ul>" if result[-1].startswith("<li>") else "</ol>")
                    in_list = False
                result.append(line)

        if in_list:
            result.append("</ul>" if result[-1].startswith("<li>") else "</ol>")

        text = "\n".join(result)

        # Convert paragraphs (lines separated by blank lines)
        paragraphs = text.split("\n\n")
        wrapped = []
        for p in paragraphs:
            p = p.strip()
            if p and not p.startswith("<"):
                wrapped.append(f"<p>{p}</p>")
            else:
                wrapped.append(p)
        text = "\n".join(wrapped)

        # Wrap in a div with styling
        html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    font-size: 14px;
                    line-height: 1.6;
                    color: #212121;
                    padding: 16px;
                }}
                h1, h2, h3 {{
                    color: #212121;
                    margin-top: 24px;
                    margin-bottom: 12px;
                }}
                h1 {{ font-size: 24px; border-bottom: 1px solid #e0e0e0; padding-bottom: 8px; }}
                h2 {{ font-size: 20px; }}
                h3 {{ font-size: 16px; }}
                ul, ol {{ margin: 12px 0; padding-left: 24px; }}
                li {{ margin: 4px 0; }}
                p {{ margin: 12px 0; }}
                a:hover {{ text-decoration: underline !important; }}
            </style>
        </head>
        <body>
            {text}
        </body>
        </html>
        """

        return html

    def _on_anchor_clicked(self, url) -> None:
        """Handle clicked anchors."""
        url_str = url.toString()
        if url_str.startswith("pdf://"):
            # Extract doc_id and page from pdf://doc_id#page=N
            pdf_ref = url_str[6:]  # Remove pdf:// prefix
            self.pdfLinkClicked.emit(pdf_ref)
