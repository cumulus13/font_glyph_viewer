#!/usr/bin/env python3
# File: font_viewer.py
# Description: Cross-Platform System Font Inspector & Previewer with Enter-to-Copy
# License: MIT

import sys
import os
import math
import configparser
from pathlib import Path
from typing import Any

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QFrame
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QFontDatabase


class ConfigManager:
    """Manages reading, writing, and auto-creating configuration settings."""
    
    def __init__(self, app_name: str = "font_viewer"):
        self.app_name = app_name
        self.config_path = self._get_config_path()
        self.config = self._load_config()

    def _get_config_path(self) -> Path:
        if sys.platform == 'win32':
            base_dir = Path(os.path.expandvars("%USERPROFILE%")) / f".{self.app_name}"
        else:
            base_dir = Path.home() / f".{self.app_name}"
            
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir / f"{self.app_name}.ini"

    def create_default_config(self, config_file: Path):
        print(f"Creating config file: {config_file}")
        config = configparser.ConfigParser()
        
        config['display'] = {
            'page_size': '15',
            'font_size': '22',
            'text_color': '#FFFF00',
            'bg_color': '#181825',
            'card_bg': '#1E1E2E',
            'card_border': '#313244',
            'preview_text': r'\ue0b0 \ue0b6 \uf046 Sample 123 ABC'
        }
        
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(f"# {self.app_name.replace('_', ' ').title()} Configuration\n")
                f.write("# preview_text: You can use raw unicode escapes here like \\ue0b0\n")
                f.write("# text_color: Hex color code for the font preview (default is yellow #FFFF00)\n\n")
                config.write(f)
        except Exception as e:
            print(f"Warning: Could not create config file: {e}")

    def _load_config(self) -> configparser.ConfigParser:
        parser = configparser.ConfigParser()
        if not self.config_path.exists():
            self.create_default_config(self.config_path)
        else:
            print(f"Using config file: {self.config_path}")
        parser.read(self.config_path, encoding='utf-8')
        return parser

    def get(self, section: str, key: str, fallback: Any = None) -> str:
        return self.config.get(section, key, fallback=fallback)

    def getint(self, section: str, key: str, fallback: int = 10) -> int:
        try:
            return self.config.getint(section, key, fallback=fallback)
        except ValueError:
            return fallback


class SearchLineEdit(QLineEdit):
    """Subclassed QLineEdit to capture navigation and exit keys while typing."""
    
    def __init__(self, main_win):
        super().__init__()
        self.main_win = main_win

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.main_win.close()
            event.accept()
            return
            
        if event.key() in (Qt.Key_Up, Qt.Key_Down, Qt.Key_PageUp, Qt.Key_PageDown):
            self.main_win.handle_global_navigation(event.key())
            event.accept()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.main_win.cards and 0 <= self.main_win.selected_index < len(self.main_win.cards):
                self.main_win.cards[self.main_win.selected_index].copy_to_clipboard()
            event.accept()
        else:
            super().keyPressEvent(event)


class FontCard(QFrame):
    """Widget card displaying an individual font and its preview."""
    
    def __init__(self, font_name: str, preview_text: str, font_size: int, text_color: str, card_bg: str, card_border: str):
        super().__init__()
        self.font_name = font_name
        self.card_bg = card_bg
        self.card_border = card_border
        
        self.setFrameShape(QFrame.StyledPanel)
        self.set_selected(False)

        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        header_layout = QHBoxLayout()
        name_label = QLabel(font_name)
        name_label.setFont(QFont("Consolas", 10, QFont.Bold))
        name_label.setStyleSheet("color: #89B4FA; border: none; background: transparent;")

        self.copy_btn = QPushButton("Copy Name")
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.setFocusPolicy(Qt.NoFocus)
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #313244;
                color: #CDD6F4;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #45475A;
            }
        """)
        self.copy_btn.clicked.connect(self.copy_to_clipboard)

        header_layout.addWidget(name_label)
        header_layout.addStretch()
        header_layout.addWidget(self.copy_btn)

        preview_label = QLabel(preview_text)
        preview_label.setFont(QFont(font_name, font_size))
        preview_label.setStyleSheet(f"color: {text_color}; border: none; background: transparent;")
        preview_label.setWordWrap(True)

        layout.addLayout(header_layout)
        layout.addWidget(preview_label)

    def set_selected(self, is_selected: bool):
        if is_selected:
            self.setStyleSheet(f"""
                FontCard {{
                    background-color: {self.card_bg};
                    border: 2px solid #A6E3A1;
                    border-radius: 8px;
                    padding: 5px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                FontCard {{
                    background-color: {self.card_bg};
                    border: 1px solid {self.card_border};
                    border-radius: 8px;
                    padding: 6px;
                }}
                FontCard:hover {{
                    border: 1px solid #89B4FA;
                }}
            """)

    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.font_name)
        orig_text = self.copy_btn.text()
        self.copy_btn.setText("Copied!")
        QTimer.singleShot(1000, lambda: self.copy_btn.setText(orig_text))


class FontViewerWindow(QWidget):
    """Main Application Window."""

    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        
        self.all_fonts = sorted(QFontDatabase().families())
        self.filtered_fonts = list(self.all_fonts)
        self.current_page = 1
        
        self.cards = []
        self.selected_index = 0

        self.init_ui()
        self.setFocusPolicy(Qt.StrongFocus)

    def init_ui(self):
        self.setWindowTitle("Cross-Platform System Font Inspector")
        self.resize(850, 700)

        bg_color = self.config.get('display', 'bg_color', '#181825')
        self.setStyleSheet(f"background-color: {bg_color};")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # Top Control Bar
        top_bar = QHBoxLayout()
        self.search_input = SearchLineEdit(self)
        self.search_input.setPlaceholderText("Filter fonts... Press 'f' to focus, 'Enter' to copy, 'Esc' to quit.")
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
        top_bar.addWidget(self.search_input)
        main_layout.addLayout(top_bar)

        # Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFocusPolicy(Qt.NoFocus)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.scroll_content = QWidget()
        self.card_layout = QVBoxLayout(self.scroll_content)
        self.card_layout.setSpacing(10)
        self.card_layout.setAlignment(Qt.AlignTop)

        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area)

        # Pagination Bar
        bottom_bar = QHBoxLayout()

        self.prev_btn = QPushButton("◀ Previous")
        self.next_btn = QPushButton("Next ▶")
        self.prev_btn.setFocusPolicy(Qt.NoFocus)
        self.next_btn.setFocusPolicy(Qt.NoFocus)
        
        nav_btn_style = """
            QPushButton {
                background-color: #313244;
                color: #CDD6F4;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45475A;
            }
            QPushButton:disabled {
                background-color: #181825;
                color: #585B70;
            }
        """
        self.prev_btn.setStyleSheet(nav_btn_style)
        self.next_btn.setStyleSheet(nav_btn_style)

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
        """Global key handler for when the search box does NOT have focus."""
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
                if self.cards and 0 <= self.selected_index < len(self.cards):
                    self.cards[self.selected_index].copy_to_clipboard()
                    event.accept()
                    return

        if event.key() in (Qt.Key_Up, Qt.Key_Down, Qt.Key_PageUp, Qt.Key_PageDown):
            self.handle_global_navigation(event.key())
            event.accept()
        else:
            super().keyPressEvent(event)

    def handle_global_navigation(self, key):
        if key == Qt.Key_Down:
            if self.selected_index < len(self.cards) - 1:
                self.selected_index += 1
                self.update_selection_highlight()
        elif key == Qt.Key_Up:
            if self.selected_index > 0:
                self.selected_index -= 1
                self.update_selection_highlight()
        elif key == Qt.Key_PageDown:
            self.go_next_page()
        elif key == Qt.Key_PageUp:
            self.go_prev_page()

    def update_selection_highlight(self):
        if not self.cards:
            return
        for i, card in enumerate(self.cards):
            card.set_selected(i == self.selected_index)
        self.scroll_area.ensureWidgetVisible(self.cards[self.selected_index])

    def get_max_pages(self) -> int:
        page_size = self.config.getint('display', 'page_size', 15)
        return max(1, math.ceil(len(self.filtered_fonts) / page_size))

    def on_search_changed(self, text: str):
        query = text.strip().lower()
        if not query:
            self.filtered_fonts = list(self.all_fonts)
        else:
            self.filtered_fonts = [f for f in self.all_fonts if query in f.lower()]
        
        self.current_page = 1
        self.render_page()

    def render_page(self):
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.cards.clear()

        page_size = self.config.getint('display', 'page_size', 15)
        font_size = self.config.getint('display', 'font_size', 22)
        text_color = self.config.get('display', 'text_color', '#FFFF00')
        card_bg = self.config.get('display', 'card_bg', '#1E1E2E')
        card_border = self.config.get('display', 'card_border', '#313244')
        
        raw_preview = self.config.get('display', 'preview_text', r'\ue0b0 \ue0b6 \uf046 Sample 123 ABC')
        try:
            preview_text = raw_preview.encode('utf-8').decode('unicode_escape')
        except Exception:
            preview_text = raw_preview

        max_pages = self.get_max_pages()
        self.current_page = max(1, min(self.current_page, max_pages))

        start_idx = (self.current_page - 1) * page_size
        end_idx = start_idx + page_size
        page_fonts = self.filtered_fonts[start_idx:end_idx]

        for font_name in page_fonts:
            card = FontCard(
                font_name=font_name,
                preview_text=preview_text,
                font_size=font_size,
                text_color=text_color,
                card_bg=card_bg,
                card_border=card_border
            )
            self.card_layout.addWidget(card)
            self.cards.append(card)

        self.page_info.setText(f"Page {self.current_page} of {max_pages} ({len(self.filtered_fonts)} fonts found)")
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < max_pages)
        
        self.selected_index = 0
        self.update_selection_highlight()

    def go_prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.render_page()

    def go_next_page(self):
        if self.current_page < self.get_max_pages():
            self.current_page += 1
            self.render_page()


def main():
    app = QApplication(sys.argv)
    window = FontViewerWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()