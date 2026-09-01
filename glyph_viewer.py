#!/usr/bin/env python3

# File: glyph_viewer.py
# Author: Hadi Cahyadi <cumulus13@gmail.com>
# Date: 2026-09-01
# Description: Paginated Nerd Font PUA Glyph Inspector with Unified FontViewer-style Shortcuts
# License: MIT

import sys
import os
import math
import configparser
from pathlib import Path
from typing import Any

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QGridLayout, QFrame, QScrollArea
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont


class GlyphConfig:
    def __init__(self):
        self.config_path = self._get_path()
        self.config = self._load()

    def _get_path(self) -> Path:
        base = Path(os.path.expandvars("%USERPROFILE%")) if sys.platform == 'win32' else Path.home()
        d = base / ".glyph_viewer"
        d.mkdir(parents=True, exist_ok=True)
        return d / "glyph_viewer.ini"

    def _load(self) -> configparser.ConfigParser:
        parser = configparser.ConfigParser()
        if not self.config_path.exists():
            parser['display'] = {
                'font_family': 'CaskaydiaCove Nerd Font',
                'start_hex': 'e000',
                'end_hex': 'f8ff',
                'page_size': '48',
                'bg_color': '#181825',
                'card_bg': '#1E1E2E',
                'card_border': '#313244',
                'text_color': '#FFFF00'
            }
            with open(self.config_path, 'w', encoding='utf-8') as f:
                parser.write(f)
        else:
            parser.read(self.config_path, encoding='utf-8')
        return parser

    def get(self, section, key, fallback=None):
        return self.config.get(section, key, fallback=fallback)

    def getint(self, section, key, fallback=10):
        try:
            return self.config.getint(section, key, fallback=fallback)
        except ValueError:
            return fallback


class SearchLineEdit(QLineEdit):
    """Subclassed QLineEdit to intercept navigation, pagination, and exit keys instantly."""
    def __init__(self, main_win):
        super().__init__()
        self.main_win = main_win

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.main_win.close()
            event.accept()
            return
            
        if event.key() in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right, Qt.Key_PageUp, Qt.Key_PageDown):
            self.main_win.handle_global_navigation(event.key())
            event.accept()
            return
            
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.main_win.copy_selected_glyph()
            event.accept()
            return
            
        super().keyPressEvent(event)


class GlyphCard(QFrame):
    def __init__(self, code_point: int, font_family: str, text_color: str, card_bg: str, card_border: str):
        super().__init__()
        self.code_point = code_point
        self.hex_str = f"{code_point:04x}"
        self.char = chr(code_point)
        self.card_bg = card_bg
        self.card_border = card_border
        
        self.setFrameShape(QFrame.StyledPanel)
        self.setFixedSize(95, 90)
        self.set_selected(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setAlignment(Qt.AlignCenter)

        self.icon_lbl = QLabel(self.char)
        self.icon_lbl.setFont(QFont(font_family, 26))
        self.icon_lbl.setStyleSheet(f"color: {text_color}; border: none; background: transparent;")
        self.icon_lbl.setAlignment(Qt.AlignCenter)

        self.hex_lbl = QLabel(f"U+{self.hex_str.upper()}")
        self.hex_lbl.setFont(QFont("Consolas", 8, QFont.Bold))
        self.hex_lbl.setStyleSheet("color: #A6ADC8; border: none; background: transparent;")
        self.hex_lbl.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.icon_lbl)
        layout.addWidget(self.hex_lbl)

    def set_selected(self, is_selected: bool):
        if is_selected:
            self.setStyleSheet(f"""
                GlyphCard {{
                    background-color: {self.card_bg};
                    border: 2px solid #A6E3A1;
                    border-radius: 6px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                GlyphCard {{
                    background-color: {self.card_bg};
                    border: 1px solid {self.card_border};
                    border-radius: 6px;
                }}
                GlyphCard:hover {{
                    border: 1px solid #89B4FA;
                    background-color: #313244;
                }}
            """)

    def mousePressEvent(self, event):
        self.copy_glyph()

    def copy_glyph(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(f"\\{self.hex_str}")
        original_text = self.hex_lbl.text()
        self.hex_lbl.setText("Copied!")
        self.hex_lbl.setStyleSheet("color: #A6E3A1; border: none; background: transparent;")
        QTimer.singleShot(1000, lambda: [
            self.hex_lbl.setText(original_text),
            self.hex_lbl.setStyleSheet("color: #A6ADC8; border: none; background: transparent;")
        ])


class GlyphViewerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.config = GlyphConfig()
        
        self.font_family = self.config.get('display', 'font_family', 'CaskaydiaCove Nerd Font')
        self.start_code = int(self.config.get('display', 'start_hex', 'e000'), 16)
        self.end_code = int(self.config.get('display', 'end_hex', 'f8ff'), 16)
        self.page_size = self.config.getint('display', 'page_size', 48)
        
        self.all_code_points = list(range(self.start_code, self.end_code + 1))
        self.filtered_code_points = list(self.all_code_points)
        self.current_page = 1
        
        self.cards = []
        self.selected_index = 0

        self.init_ui()
        self.setFocusPolicy(Qt.StrongFocus)

    def init_ui(self):
        self.setWindowTitle(f"Nerd Font PUA Viewer - [{self.font_family}]")
        self.resize(720, 750)

        bg_color = self.config.get('display', 'bg_color', '#181825')
        self.setStyleSheet(f"background-color: {bg_color};")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # Search Bar
        self.search_input = SearchLineEdit(self)
        self.search_input.setPlaceholderText("Filter hex... Press 'f' to focus, Arrows/PageUp/PageDown to navigate, Enter to copy, Esc to quit.")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #1E1E2E;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #89B4FA;
            }
        """)
        self.search_input.textChanged.connect(self.on_search_changed)
        main_layout.addWidget(self.search_input)

        # Grid Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFocusPolicy(Qt.NoFocus)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.scroll_content = QWidget()
        self.grid_layout = QGridLayout(self.scroll_content)
        self.grid_layout.setSpacing(10)
        self.grid_layout.setAlignment(Qt.AlignTop)

        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area)

        # Pagination Bar
        bottom_bar = QHBoxLayout()
        self.prev_btn = QPushButton("◀ Previous Page")
        self.next_btn = QPushButton("Next Page ▶")
        
        btn_style = """
            QPushButton {
                background-color: #313244; color: #CDD6F4; border: none;
                border-radius: 6px; padding: 8px 16px; font-weight: bold;
            }
            QPushButton:hover { background-color: #45475A; }
            QPushButton:disabled { background-color: #181825; color: #585B70; }
        """
        self.prev_btn.setStyleSheet(btn_style)
        self.next_btn.setStyleSheet(btn_style)
        self.prev_btn.setFocusPolicy(Qt.NoFocus)
        self.next_btn.setFocusPolicy(Qt.NoFocus)

        self.prev_btn.clicked.connect(self.go_prev_page)
        self.next_btn.clicked.connect(self.go_next_page)

        self.page_info = QLabel("Page 1 of 1")
        self.page_info.setStyleSheet("color: #CDD6F4; font-weight: bold; font-size: 13px;")

        bottom_bar.addWidget(self.prev_btn)
        bottom_bar.addStretch()
        bottom_bar.addWidget(self.page_info)
        bottom_bar.addStretch()
        bottom_bar.addWidget(self.next_btn)

        main_layout.addLayout(bottom_bar)
        self.render_page()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
            event.accept()
            return

        if not self.search_input.hasFocus():
            if event.key() == Qt.Key_F:
                self.search_input.setFocus()
                self.search_input.selectAll()
                event.accept()
                return
            elif event.key() in (Qt.Key_C, Qt.Key_Return, Qt.Key_Enter):
                self.copy_selected_glyph()
                event.accept()
                return

        if event.key() in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right, Qt.Key_PageUp, Qt.Key_PageDown):
            self.handle_global_navigation(event.key())
            event.accept()
        else:
            super().keyPressEvent(event)

    def handle_global_navigation(self, key):
        cols = 6
        max_idx = len(self.cards) - 1
        if max_idx < 0:
            return

        if key == Qt.Key_Down:
            if self.selected_index + cols <= max_idx:
                self.selected_index += cols
            else:
                self.go_next_page()
                return
        elif key == Qt.Key_Up:
            if self.selected_index - cols >= 0:
                self.selected_index -= cols
            else:
                self.go_prev_page()
                return
        elif key == Qt.Key_Right:
            if self.selected_index < max_idx:
                self.selected_index += 1
            else:
                self.go_next_page()
                return
        elif key == Qt.Key_Left:
            if self.selected_index > 0:
                self.selected_index -= 1
            else:
                self.go_prev_page()
                return
        elif key == Qt.Key_PageDown:
            self.go_next_page()
            return
        elif key == Qt.Key_PageUp:
            self.go_prev_page()
            return

        self.update_selection_highlight()

    def update_selection_highlight(self):
        if not self.cards:
            return
        self.selected_index = max(0, min(self.selected_index, len(self.cards) - 1))
        for i, card in enumerate(self.cards):
            card.set_selected(i == self.selected_index)
        self.scroll_area.ensureWidgetVisible(self.cards[self.selected_index])

    def copy_selected_glyph(self):
        if self.cards and 0 <= self.selected_index < len(self.cards):
            self.cards[self.selected_index].copy_glyph()

    def get_max_pages(self) -> int:
        return max(1, math.ceil(len(self.filtered_code_points) / self.page_size))

    def on_search_changed(self, text: str):
        query = text.strip().lower()
        if not query:
            self.filtered_code_points = list(self.all_code_points)
        else:
            self.filtered_code_points = [
                code for code in self.all_code_points 
                if query in f"{code:04x}".lower()
            ]
        self.current_page = 1
        self.render_page()

    def render_page(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.cards.clear()

        max_pages = self.get_max_pages()
        self.current_page = max(1, min(self.current_page, max_pages))

        start_idx = (self.current_page - 1) * self.page_size
        end_idx = start_idx + self.page_size
        page_codes = self.filtered_code_points[start_idx:end_idx]

        text_color = self.config.get('display', 'text_color', '#FFFF00')
        card_bg = self.config.get('display', 'card_bg', '#1E1E2E')
        card_border = self.config.get('display', 'card_border', '#313244')

        cols = 6
        for idx, code in enumerate(page_codes):
            row = idx // cols
            col = idx % cols
            card = GlyphCard(code, self.font_family, text_color, card_bg, card_border)
            self.grid_layout.addWidget(card, row, col)
            self.cards.append(card)

        total_found = len(self.filtered_code_points)
        if page_codes:
            self.page_info.setText(f"Page {self.current_page} of {max_pages} ({total_found} glyphs matched)")
        else:
            self.page_info.setText(f"Page 1 of 1 (0 glyphs matched)")

        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < max_pages)
        
        self.selected_index = 0
        self.update_selection_highlight()

    def go_prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.render_page()
            self.selected_index = len(self.cards) - 1  # Land on bottom of previous page
            self.update_selection_highlight()

    def go_next_page(self):
        if self.current_page < self.get_max_pages():
            self.current_page += 1
            self.render_page()


def main():
    app = QApplication(sys.argv)
    window = GlyphViewerWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()