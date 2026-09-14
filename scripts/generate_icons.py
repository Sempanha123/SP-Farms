"""Generate high-resolution application icons for SP-Farms.

Creates:
- assets/icons/sp_farms.ico (multi-resolution Windows icon: 16, 32, 48, 64, 128, 256)
- assets/icons/sp_farms.png (256x256 master PNG)
- assets/icons/sp_farms_64.png
- assets/icons/sp_farms_32.png
"""

from __future__ import annotations

import struct
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)


def create_sp_farms_icon(size: int = 256) -> QImage:
    """Draw an original, cute, modern SP-Farms icon with mint/lime accent."""
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    scale = size / 256.0

    # Background rounded squircle with soft slate/charcoal gradient
    bg_rect = QRectF(12 * scale, 12 * scale, 232 * scale, 232 * scale)
    corner_radius = 48 * scale

    bg_gradient = QLinearGradient(0, 0, size, size)
    bg_gradient.setColorAt(0.0, QColor(24, 30, 36))  # Soft dark slate
    bg_gradient.setColorAt(1.0, QColor(14, 18, 22))  # Deep charcoal

    bg_path = QPainterPath()
    bg_path.addRoundedRect(bg_rect, corner_radius, corner_radius)
    painter.fillPath(bg_path, QBrush(bg_gradient))

    # Subtle border rim
    rim_pen = QPen(QColor(42, 54, 66, 200), 2.5 * scale)
    painter.strokePath(bg_path, rim_pen)

    # Sprout / Leaf glyph (Farms theme) with mint / lime gradient
    # Primary accent: Mint (#10B981) to Lime (#84CC16)
    accent_gradient = QLinearGradient(60 * scale, 190 * scale, 180 * scale, 50 * scale)
    accent_gradient.setColorAt(0.0, QColor(16, 185, 129))  # Emerald/Mint
    accent_gradient.setColorAt(0.6, QColor(34, 197, 94))   # Mint green
    accent_gradient.setColorAt(1.0, QColor(132, 204, 22))  # Lime accent

    # Stem / core sprout path
    leaf_path = QPainterPath()
    leaf_path.moveTo(128 * scale, 195 * scale)
    leaf_path.cubicTo(
        125 * scale, 160 * scale,
        105 * scale, 120 * scale,
        65 * scale, 105 * scale,
    )
    leaf_path.cubicTo(
        65 * scale, 140 * scale,
        85 * scale, 175 * scale,
        128 * scale, 195 * scale,
    )

    painter.fillPath(leaf_path, QBrush(accent_gradient))

    # Right main leaf
    right_leaf = QPainterPath()
    right_leaf.moveTo(128 * scale, 195 * scale)
    right_leaf.cubicTo(
        135 * scale, 150 * scale,
        165 * scale, 95 * scale,
        195 * scale, 65 * scale,
    )
    right_leaf.cubicTo(
        200 * scale, 105 * scale,
        185 * scale, 155 * scale,
        128 * scale, 195 * scale,
    )
    painter.fillPath(right_leaf, QBrush(accent_gradient))

    # Center seedling node / network dot (representing automation / accounts)
    node_brush = QBrush(QColor(245, 250, 247))
    painter.setBrush(node_brush)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(QPointF(128 * scale, 95 * scale), 14 * scale, 14 * scale)

    # Accent pulse ring around the node
    ring_pen = QPen(QColor(132, 204, 22, 180), 3 * scale)
    painter.setPen(ring_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(QPointF(128 * scale, 95 * scale), 24 * scale, 24 * scale)

    painter.end()
    return image


def save_ico(images: list[QImage], output_path: Path) -> None:
    """Pack multiple QImages into a standard Windows .ico binary container."""
    # Convert images to PNG byte streams
    png_datas: list[bytes] = []
    for img in images:
        from PySide6.QtCore import QBuffer, QIODevice
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buffer, "PNG")
        png_datas.append(buffer.data().data())
        buffer.close()

    # ICO Header: 2 bytes reserved (0), 2 bytes type (1=ICO), 2 bytes count
    num_images = len(images)
    header = struct.pack("<HHH", 0, 1, num_images)

    # Compute directory entries and data offsets
    # Directory entry size is 16 bytes
    dir_offset = 6 + (16 * num_images)
    entries: list[bytes] = []
    current_data_offset = dir_offset

    for i, img in enumerate(images):
        width = img.width() if img.width() < 256 else 0
        height = img.height() if img.height() < 256 else 0
        b_color_count = 0
        b_reserved = 0
        w_planes = 1
        w_bit_count = 32
        dw_bytes_in_res = len(png_datas[i])
        dw_image_offset = current_data_offset

        entry = struct.pack(
            "<BBBBHHII",
            width,
            height,
            b_color_count,
            b_reserved,
            w_planes,
            w_bit_count,
            dw_bytes_in_res,
            dw_image_offset,
        )
        entries.append(entry)
        current_data_offset += dw_bytes_in_res

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as stream:
        stream.write(header)
        for entry in entries:
            stream.write(entry)
        for png_data in png_datas:
            stream.write(png_data)


def main() -> None:
    # Ensure QGuiApplication exists for QImage / QPainter
    _app = QGuiApplication.instance() or QGuiApplication([])

    base_dir = Path(__file__).resolve().parent.parent
    icons_dir = base_dir / "assets" / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)

    sizes = [16, 32, 48, 64, 128, 256]
    images: list[QImage] = []

    master = create_sp_farms_icon(256)
    master.save(str(icons_dir / "sp_farms.png"), "PNG")
    master.save(str(icons_dir / "app_icon.png"), "PNG")

    for s in sizes:
        if s == 256:
            images.append(master)
        else:
            img = master.scaled(
                s,
                s,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            images.append(img)
            if s in (32, 64):
                img.save(str(icons_dir / f"sp_farms_{s}.png"), "PNG")

    ico_path = icons_dir / "sp_farms.ico"
    save_ico(images, ico_path)
    print(f"Generated {ico_path} with sizes {sizes}")
    print(f"Generated master PNG at {icons_dir / 'sp_farms.png'}")


if __name__ == "__main__":
    main()
