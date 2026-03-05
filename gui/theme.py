"""Shared Qt stylesheet for Piano Player."""

APP_STYLE = """
QMainWindow, QWidget {
    background-color: #171a1f;
    color: #dce4ef;
    font-family: "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: 13px;
}
QGroupBox {
    border: 1px solid #2b313c;
    border-radius: 8px;
    margin-top: 16px;
    padding-top: 12px;
    background-color: #1d222b;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    top: -1px;
    padding: 2px 10px;
    color: #8fb4db;
    font-weight: 600;
    border: 1px solid #2a3340;
    border-radius: 5px;
    background-color: #151b25;
}
QLabel {
    color: #dce4ef;
    background: transparent;
}
QLabel#hintLabel {
    color: #94a4b8;
    font-size: 11px;
}
QLabel#statusBadge {
    background-color: #222c37;
    border: 1px solid #334254;
    border-radius: 5px;
    padding: 2px 8px;
}
QLabel#statusBadge[ok="true"] {
    background-color: #243a2f;
    border-color: #3f7058;
    color: #c9f5de;
}
QLabel#statusBadge[ok="false"] {
    background-color: #2b2f36;
    border-color: #414854;
    color: #c8d0dc;
}
QLabel#timeCode {
    font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace;
    font-weight: 600;
    letter-spacing: 0.5px;
}
QMenuBar {
    background-color: #151a21;
    border: 1px solid #2b313c;
}
QMenuBar::item {
    background: transparent;
    padding: 5px 10px;
}
QMenuBar::item:selected {
    background: #2d3a4b;
}
QMenu {
    background-color: #1f2630;
    border: 1px solid #364250;
}
QMenu::item:selected {
    background-color: #365d87;
}
QPushButton {
    background-color: #2a3340;
    border: 1px solid #3b4a5c;
    border-radius: 6px;
    padding: 6px 12px;
    color: #e8f0fa;
    min-height: 30px;
}
QPushButton:hover {
    background-color: #324154;
}
QPushButton:pressed {
    background-color: #3a4a60;
}
QPushButton:checked {
    background-color: #375f87;
    border-color: #5c8dba;
}
QPushButton[variant="record"] {
    border-color: #7d4a4a;
    color: #ff9393;
    font-weight: 600;
}
QPushButton[variant="record"]:checked {
    background-color: #c94c4c;
    border-color: #df6a6a;
    color: #fff4f4;
}
QPushButton[variant="transport"] {
    min-width: 84px;
}
QPushButton[variant="toggle"]:checked {
    background-color: #3a6d65;
    border-color: #58a296;
}
QPushButton:disabled {
    background-color: #202732;
    color: #6f7f93;
    border-color: #2f3b4a;
}
QPushButton[compact="true"] {
    min-height: 24px;
    padding: 3px 10px;
}
QComboBox, QSpinBox {
    background-color: #242d39;
    border: 1px solid #3b4a5c;
    border-radius: 6px;
    padding: 4px 8px;
    color: #dce4ef;
}
QLineEdit {
    background-color: #242d39;
    border: 1px solid #3b4a5c;
    border-radius: 6px;
    padding: 4px 8px;
    color: #dce4ef;
}
QLineEdit::placeholder {
    color: #8fa1b6;
}
QPushButton:focus, QComboBox:focus, QSpinBox:focus, QLineEdit:focus {
    border: 1px solid #66a3dc;
}
QComboBox::drop-down {
    border: none;
}
QComboBox QAbstractItemView {
    background-color: #242d39;
    selection-background-color: #3f6f9f;
    color: #e8f0fa;
}
QSlider::groove:horizontal {
    border: 1px solid #3a4554;
    height: 6px;
    background: #252f3a;
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: #4f83b5;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #7ab0e0;
    border: 1px solid #5a91c2;
    width: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QSplitter::handle {
    background-color: transparent;
    border: none;
}
QListWidget {
    background-color: #202833;
    border: 1px solid #334254;
    border-radius: 6px;
}
QListWidget::item {
    padding: 4px 6px;
}
QListWidget::item:hover {
    background-color: #2f4a66;
}
QListWidget::item:selected {
    background-color: #365d87;
}
QCheckBox {
    spacing: 6px;
    background: transparent;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
}
QCheckBox::indicator:unchecked {
    border: 1px solid #4b5d74;
    background: #202833;
    border-radius: 3px;
}
QCheckBox::indicator:checked {
    border: 1px solid #4b5d74;
    background: #4f83b5;
    border-radius: 3px;
}
"""
