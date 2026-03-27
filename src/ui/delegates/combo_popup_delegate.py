"""
Combo popup item painting.

Fusion + QComboBox popups draw hover/focus frames with the style engine; those
frames stay dark in dark mode and ignore QSS. This delegate suppresses those
states for the base paint and draws an accent border using the app palette.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem

from core.settings import get_setting
from ui.app_style import DARK_PALETTE, LIGHT_PALETTE


class ComboPopupDelegate(QStyledItemDelegate):
    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index,
    ) -> None:
        theme = get_setting("theme", "dark") or "dark"
        pal = DARK_PALETTE if theme == "dark" else LIGHT_PALETTE

        orig_hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        orig_focus = bool(option.state & QStyle.StateFlag.State_HasFocus)
        is_sel = bool(option.state & QStyle.StateFlag.State_Selected)

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.state &= ~QStyle.StateFlag.State_HasFocus
        opt.state &= ~QStyle.StateFlag.State_MouseOver
        if orig_hover and not is_sel:
            opt.backgroundBrush = QBrush(QColor(pal["hover_list"]))

        super().paint(painter, opt, index)

        if orig_hover or orig_focus:
            painter.save()
            painter.setPen(QPen(QColor(pal["accent"]), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            r = option.rect.adjusted(2, 2, -2, -2)
            painter.drawRoundedRect(r, 3, 3)
            painter.restore()
