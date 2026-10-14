import argparse
from pathlib import Path

import pymupdf


def _rendered_content_rect(page: pymupdf.Page) -> pymupdf.Rect | None:
    pixmap = page.get_pixmap(
        matrix=pymupdf.Matrix(0.2, 0.2),
        colorspace=pymupdf.csGRAY,
        alpha=False,
    )
    pixels = pixmap.samples
    x0, y0 = pixmap.width, pixmap.height
    x1 = y1 = -1

    for y in range(pixmap.height):
        row_start = y * pixmap.width
        for x in range(pixmap.width):
            if pixels[row_start + x] < 230:
                x0 = min(x0, x)
                y0 = min(y0, y)
                x1 = max(x1, x)
                y1 = max(y1, y)

    if x1 < x0 or y1 < y0:
        return None

    rect = pymupdf.Rect(
        x0 * page.rect.width / pixmap.width,
        y0 * page.rect.height / pixmap.height,
        (x1 + 1) * page.rect.width / pixmap.width,
        (y1 + 1) * page.rect.height / pixmap.height,
    )
    return rect * page.derotation_matrix


def auto_crop_pdf(input_path, output_path):
    doc = pymupdf.open(input_path)
    for page in doc:
        bboxlog = page.get_bboxlog()
        media_box = page.mediabox
        has_full_page_image = any(
            kind in ("fill-image", "fill-imgmask")
            and (pymupdf.Rect(bbox) & media_box).get_area()
            >= media_box.get_area() * 0.9
            for kind, bbox in bboxlog
        )

        content_rects = []
        if has_full_page_image:
            rendered_rect = _rendered_content_rect(page)
            if rendered_rect is not None:
                content_rects.append(rendered_rect)

        if not content_rects:
            content_rects = [
                pymupdf.Rect(bbox)
                for kind, bbox in bboxlog
                if kind != "ignore-text"
            ]

        if content_rects:
            rect = content_rects[0]
            for content_rect in content_rects[1:]:
                rect.include_rect(content_rect)

            rect.x0 = max(media_box.x0, rect.x0 - 5)
            rect.y0 = max(media_box.y0, rect.y0 - 5)
            rect.x1 = min(media_box.x1, rect.x1 + 5)
            rect.y1 = min(media_box.y1, rect.y1 + 5)

            page.set_cropbox(rect)

    doc.save(output_path)
    doc.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Automatically crop the pages of a PDF to their visible content."
    )
    parser.add_argument("input_path", type=Path, help="PDF file to crop")
    parser.add_argument("output_path", type=Path, help="Path for the cropped PDF")
    args = parser.parse_args()

    auto_crop_pdf(args.input_path, args.output_path)
