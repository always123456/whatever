"""PDF 简历文本抽取：仅支持文字层 PDF（扫描件/图片型返回明确报错，OCR 后续再加）。"""

import io

from pypdf import PdfReader


class PdfParseError(Exception):
    """PDF 无法解析（损坏 / 加密 / 非 PDF / 无文字层）。"""


MAX_PDF_BYTES = 10 * 1024 * 1024  # 10MB


def parse_pdf_text(data: bytes) -> str:
    """把 PDF 字节流抽成纯文本（按页拼接）。空文本 / 解析失败抛 PdfParseError。"""
    if not data:
        raise PdfParseError("文件为空")
    if len(data) > MAX_PDF_BYTES:
        raise PdfParseError("文件过大（上限 10MB）")
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as e:  # noqa: BLE001  损坏/非 PDF 一律报错
        raise PdfParseError(f"PDF 解析失败：{e}") from e
    if reader.is_encrypted:
        raise PdfParseError("PDF 已加密，无法读取")
    pages = []
    for i, page in enumerate(reader.pages, 1):
        try:
            text = page.extract_text() or ""
        except Exception as e:  # noqa: BLE001
            raise PdfParseError(f"第 {i} 页提取失败：{e}") from e
        pages.append(text.strip())
    text = "\n".join(p for p in pages if p).strip()
    if not text:
        raise PdfParseError("未提取到文字（可能是扫描件/图片型 PDF，暂不支持）")
    return text
