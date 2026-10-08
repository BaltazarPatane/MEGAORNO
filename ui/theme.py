"""Paleta, iconos vectoriales y componentes comunes de MEGAORNO."""
from PySide6.QtCore import Qt, QSize, QByteArray
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QLabel, QFrame, QVBoxLayout, QPushButton

BLUE = '#286ca4'
GREEN = '#339875'
INK = '#203440'
MUTED = '#74818a'

STYLE = """
* { font-family: 'Segoe UI', 'Open Sans', sans-serif; font-size: 13px; color: #263c49; }
QMainWindow, QWidget#root { background: #f2f4f6; }
QWidget { background: transparent; }
QFrame#card, QWidget#card { background: white; border: 1px solid #e1e7eb; border-radius: 14px; }
QFrame#header { background: white; border-bottom: 1px solid #e1e7eb; }
QLabel { border: none; background: transparent; }
QLabel#brand { font-size: 20px; font-weight: 800; letter-spacing: 2px; }
QLabel#eyebrow { font-size: 10px; font-weight: 700; letter-spacing: 2px; color: #71818b; }
QLabel#pageTitle { font-size: 24px; font-weight: 700; color: #203440; }
QLabel#sectionTitle { font-size: 15px; font-weight: 700; }
QLabel#muted { color: #74818a; }
QLabel#metric { font-size: 25px; font-weight: 650; color: #203440; }
QLabel#badge { color: #287f65; background: #eaf5ef; border-radius: 12px; padding: 6px 12px; font-size: 11px; font-weight: 650; }
QPushButton, QToolButton { background: #ffffff; border: 1px solid #dce3e8; border-radius: 8px; padding: 9px 15px; font-weight: 600; }
QPushButton:hover, QToolButton:hover { background: #edf4f8; border-color: #9ebcd1; }
QPushButton:pressed, QToolButton:pressed { background: #e0ecf4; }
QPushButton:disabled { color: #a1acb3; background: #f3f5f6; border-color: #e8ecef; }
QPushButton[primary="true"] { background: #286ca4; color: white; border-color: #286ca4; }
QPushButton[primary="true"]:hover { background: #215d90; }
QPushButton[primary="true"]:disabled { background: #a6bdcf; border-color: #a6bdcf; }
QPushButton#dark { background: #263e4d; border-color: #263e4d; color: white; }
QPushButton#power { border-radius: 19px; padding: 8px; }
QPushButton#power:hover { color: #b54848; border-color: #e6b9b9; background: #fff3f2; }
QPushButton#link { border: none; color: #286ca4; background: transparent; padding: 5px 0; text-align: left; }
QLineEdit, QSpinBox, QDoubleSpinBox, QDateTimeEdit, QComboBox, QPlainTextEdit, QTextEdit { background: white; border: 1px solid #dce3e8; border-radius: 7px; padding: 8px 10px; selection-background-color: #d5e8f6; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus { border: 1px solid #286ca4; }
QLineEdit:disabled { background: #f4f6f8; color: #9aa6ae; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: white; border: 1px solid #dae2e8; selection-background-color: #eaf2f8; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid #bfccd5; border-radius: 4px; background: white; }
QCheckBox::indicator:checked { background: #339875; border: 3px solid #cde7dc; }
QCheckBox:disabled { color: #a1acb3; }
QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab { color: #75828c; padding: 15px 25px; border: none; border-bottom: 3px solid transparent; font-weight: 600; }
QTabBar::tab:selected { color: #286ca4; border-bottom: 3px solid #286ca4; }
QTabBar::tab:hover { color: #286ca4; background: #eaf0f4; }
QTableView { background: white; alternate-background-color: #f6f8fa; gridline-color: #edf0f3; border: 1px solid #e4e9ed; border-radius: 8px; selection-background-color: #e3eff7; selection-color: #263c49; }
QTableView::item { padding: 7px; border-bottom: 1px solid #edf0f3; }
QHeaderView::section { background: #f4f7f9; border: none; border-bottom: 1px solid #dce3e8; padding: 10px 9px; color: #607581; font-weight: 600; font-size: 11px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #f1f4f6; width: 8px; margin: 0; }
QScrollBar:horizontal { background: #f1f4f6; height: 8px; margin: 0; }
QScrollBar::handle { background: #c4cfd7; border-radius: 4px; min-height: 26px; min-width: 26px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QMenu { background: white; border: 1px solid #dce3e8; padding: 6px; border-radius: 8px; }
QMenu::item { padding: 10px 35px 10px 14px; border-radius: 5px; }
QMenu::item:selected { background: #edf4f8; }
QToolTip { background: #243e50; color: white; border: none; padding: 7px; }
QDialog { background: #f5f7f9; }
"""


def label(text='', name=None, wrap=False):
    w = QLabel(text)
    if name: w.setObjectName(name)
    w.setWordWrap(wrap)
    return w


def button(text, callback=None, primary=False):
    w = QPushButton(text)
    w.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary: w.setProperty('primary', True)
    if callback: w.clicked.connect(callback)
    return w


def card(margins=20):
    w = QFrame(); w.setObjectName('card')
    layout = QVBoxLayout(w); layout.setContentsMargins(margins,margins,margins,margins); layout.setSpacing(12)
    return w, layout


def icon(name, color=INK, size=20):
    paths = {
        'power': '<path d="M12 3v9M6.4 5.6a8 8 0 1 0 11.2 0"/>',
        'export': '<path d="M12 3v12m-4-4 4 4 4-4M5 15v5h14v-5"/>',
        'folder': '<path d="M3 7V5h7l2 2h9v13H3zM3 9h18"/>',
        'arrow': '<path d="M5 12h14m-5-5 5 5-5 5"/>',
        'fit': '<path d="M4 9V4h5m6 0h5v5M4 15v5h5m6 0h5v-5"/>',
        'chevron': '<path d="m7 9 5 5 5-5"/>',
        'mark': '<path d="M3 18V6l6 8 6-8v12M19 6h3v12h-3"/>',
    }
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><g fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{paths.get(name,paths["mark"])}</g></svg>'
    pix = QPixmap(size*2,size*2); pix.fill(Qt.GlobalColor.transparent)
    p=QPainter(pix); QSvgRenderer(QByteArray(svg.encode())).render(p); p.end(); pix.setDevicePixelRatio(2)
    return QIcon(pix)

# Use vector arrows consistently across native Qt platform themes.
from pathlib import Path
_ICON_DIR=Path(__file__).resolve().parent/'icons'
STYLE += f"""
QComboBox::down-arrow {{ image: url("{(_ICON_DIR/'chevron.svg').as_posix()}"); width: 12px; height: 12px; }}
QSpinBox::up-button {{ subcontrol-origin: border; subcontrol-position: top right; width: 21px; border: none; }}
QSpinBox::down-button {{ subcontrol-origin: border; subcontrol-position: bottom right; width: 21px; border: none; }}
QSpinBox::up-arrow {{ image: url("{(_ICON_DIR/'up.svg').as_posix()}"); width: 10px; height: 10px; }}
QSpinBox::down-arrow {{ image: url("{(_ICON_DIR/'chevron.svg').as_posix()}"); width: 10px; height: 10px; }}
"""
