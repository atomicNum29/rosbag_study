"""Explicit light palette, independent of the desktop's dark-mode preference."""
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def apply_light_theme():
    app = QApplication.instance()
    app.setStyle("Fusion")
    palette = QPalette()
    colors = {
        "Window": "#f3f5f7", "WindowText": "#202b38", "Base": "#ffffff",
        "AlternateBase": "#eef2f6", "Text": "#202b38", "Button": "#ffffff",
        "ButtonText": "#202b38", "Highlight": "#2367ad", "HighlightedText": "#ffffff",
        "ToolTipBase": "#ffffff", "ToolTipText": "#202b38", "Link": "#2367ad",
    }
    for role, color in colors.items():
        palette.setColor(getattr(QPalette.ColorRole, role), QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#89929e"))
    app.setPalette(palette)
