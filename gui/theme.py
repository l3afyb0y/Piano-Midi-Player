"""Shared Qt stylesheet for Piano Player."""

APP_STYLE = """
QMainWindow, QWidget {
    background-color: #171a1f;
    color: #dce4ef;
    font-family: "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: 12px;
}
QGroupBox {
    border: 1px solid #2b313c;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 10px;
    background-color: #1d222b;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #8fb4db;
    font-weight: 600;
    background-color: #1d222b;
}
QLabel {
    color: #dce4ef;
    background: transparent;
}
QPushButton {
    background-color: #2a3340;
    border: 1px solid #3b4a5c;
    border-radius: 6px;
    padding: 6px 12px;
    color: #e8f0fa;
}
QPushButton:hover {
    background-color: #324154;
}
QPushButton:pressed {
    background-color: #3a4a60;
}
QPushButton:checked {
    background-color: #c94c4c;
    border-color: #df6a6a;
}
QPushButton:disabled {
    background-color: #202732;
    color: #6f7f93;
    border-color: #2f3b4a;
}
QComboBox, QSpinBox {
    background-color: #242d39;
    border: 1px solid #3b4a5c;
    border-radius: 6px;
    padding: 4px 8px;
    color: #dce4ef;
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
QListWidget {
    background-color: #202833;
    border: 1px solid #334254;
    border-radius: 6px;
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
