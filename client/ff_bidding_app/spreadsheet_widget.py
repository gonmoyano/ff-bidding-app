"""
Spreadsheet Widget
A full-featured spreadsheet widget inspired by Google Sheets with Excel formula support.
Includes cell formatting, merging, borders, and other Excel-like features.
"""

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt
import string
import re
import json

try:
    from .logger import logger
    from .formula_evaluator import FormulaEvaluator
except ImportError:
    import logging
    logger = logging.getLogger("FFPackageManager")
    from formula_evaluator import FormulaEvaluator


# =============================================================================
# Color Palette Constants
# =============================================================================

# Standard color palette (similar to Google Sheets)
COLOR_PALETTE = [
    "#000000", "#434343", "#666666", "#999999", "#B7B7B7", "#CCCCCC", "#D9D9D9", "#EFEFEF", "#F3F3F3", "#FFFFFF",
    "#980000", "#FF0000", "#FF9900", "#FFFF00", "#00FF00", "#00FFFF", "#4A86E8", "#0000FF", "#9900FF", "#FF00FF",
    "#E6B8AF", "#F4CCCC", "#FCE5CD", "#FFF2CC", "#D9EAD3", "#D0E0E3", "#C9DAF8", "#CFE2F3", "#D9D2E9", "#EAD1DC",
    "#DD7E6B", "#EA9999", "#F9CB9C", "#FFE599", "#B6D7A8", "#A2C4C9", "#A4C2F4", "#9FC5E8", "#B4A7D6", "#D5A6BD",
    "#CC4125", "#E06666", "#F6B26B", "#FFD966", "#93C47D", "#76A5AF", "#6D9EEB", "#6FA8DC", "#8E7CC3", "#C27BA0",
]


# =============================================================================
# Color Picker Widgets
# =============================================================================

class ColorPaletteWidget(QtWidgets.QWidget):
    """Grid of color swatches for quick color selection."""

    colorSelected = QtCore.Signal(str)  # Hex color string

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_palette()

    def _build_palette(self):
        """Build color swatch grid."""
        layout = QtWidgets.QGridLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(4, 4, 4, 4)

        cols = 10
        for i, color in enumerate(COLOR_PALETTE):
            btn = QtWidgets.QPushButton()
            btn.setFixedSize(20, 20)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    border: 1px solid #555;
                    min-width: 20px;
                    max-width: 20px;
                    min-height: 20px;
                    max-height: 20px;
                    padding: 0px;
                    margin: 0px;
                }}
                QPushButton:hover {{
                    border: 2px solid #FFF;
                }}
            """)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, c=color: self.colorSelected.emit(c))
            layout.addWidget(btn, i // cols, i % cols)


class ColorPickerButton(QtWidgets.QToolButton):
    """Button with color indicator and dropdown color picker."""

    colorChanged = QtCore.Signal(str)  # Emits hex color string

    def __init__(self, icon_text, tooltip, default_color="#000000", is_background=False, parent=None):
        super().__init__(parent)
        self._current_color = default_color
        self._icon_text = icon_text
        self._is_background = is_background
        self.setToolTip(tooltip)
        self.setPopupMode(QtWidgets.QToolButton.MenuButtonPopup)
        self._setup_ui()
        self._setup_menu()

        # Connect main button click to apply current color
        self.clicked.connect(lambda: self.colorChanged.emit(self._current_color))

    def _setup_ui(self):
        """Setup button appearance."""
        self.setFixedSize(32, 28)
        self._update_icon()

    def _update_icon(self):
        """Update button icon with color indicator."""
        if self._is_background:
            # Background color - paint bucket style
            self.setStyleSheet(f"""
                QToolButton {{
                    background-color: {self._current_color};
                    border: 1px solid #555;
                    border-radius: 3px;
                    font-weight: bold;
                    color: {'#000000' if self._is_light_color(self._current_color) else '#FFFFFF'};
                }}
                QToolButton:hover {{
                    border: 1px solid #888;
                }}
                QToolButton::menu-indicator {{
                    width: 8px;
                    subcontrol-position: right center;
                }}
            """)
            self.setText("▐")
        else:
            # Font color - A with colored underline
            self.setStyleSheet(f"""
                QToolButton {{
                    border: 1px solid #555;
                    border-radius: 3px;
                    font-weight: bold;
                    color: #FFFFFF;
                    border-bottom: 3px solid {self._current_color};
                }}
                QToolButton:hover {{
                    border: 1px solid #888;
                    border-bottom: 3px solid {self._current_color};
                }}
                QToolButton::menu-indicator {{
                    width: 8px;
                    subcontrol-position: right center;
                }}
            """)
            self.setText("A")

    def _is_light_color(self, hex_color):
        """Check if color is light (for text contrast)."""
        try:
            color = QtGui.QColor(hex_color)
            luminance = (0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()) / 255
            return luminance > 0.5
        except Exception:
            return False

    def _setup_menu(self):
        """Create color palette menu."""
        menu = QtWidgets.QMenu(self)

        # Color palette widget
        palette_widget = ColorPaletteWidget()
        palette_widget.colorSelected.connect(self._on_color_selected)

        palette_action = QtWidgets.QWidgetAction(menu)
        palette_action.setDefaultWidget(palette_widget)
        menu.addAction(palette_action)

        menu.addSeparator()

        # No color option (for background)
        if self._is_background:
            no_color_action = menu.addAction("No Fill")
            no_color_action.triggered.connect(lambda: self._on_color_selected(""))

        # Custom color option
        custom_action = menu.addAction("Custom Color...")
        custom_action.triggered.connect(self._show_color_dialog)

        self.setMenu(menu)

    def _on_color_selected(self, color):
        """Handle color selection."""
        self._current_color = color
        self._update_icon()
        self.colorChanged.emit(color)
        # Close the menu
        if self.menu():
            self.menu().hide()

    def _show_color_dialog(self):
        """Show Qt color dialog for custom color."""
        initial = QtGui.QColor(self._current_color) if self._current_color else QtGui.QColor("#FFFFFF")
        color = QtWidgets.QColorDialog.getColor(initial, self, "Select Color")
        if color.isValid():
            self._on_color_selected(color.name())

    def get_current_color(self):
        """Get the currently selected color."""
        return self._current_color

    def set_current_color(self, color):
        """Set the current color without emitting signal."""
        self._current_color = color
        self._update_icon()


# =============================================================================
# Borders Dropdown Button
# =============================================================================

class BordersDropdownButton(QtWidgets.QToolButton):
    """Dropdown button for border options."""

    bordersChanged = QtCore.Signal(dict)

    BORDER_OPTIONS = [
        ("No Border", "none", {}),
        ("All Borders", "all", {"top": True, "bottom": True, "left": True, "right": True}),
        ("Outside Borders", "outside", {"outside": True}),
        ("─  Top Border", "top", {"top": True}),
        ("─  Bottom Border", "bottom", {"bottom": True}),
        ("│  Left Border", "left", {"left": True}),
        ("│  Right Border", "right", {"right": True}),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("⊞")
        self.setToolTip("Borders")
        self.setFixedSize(28, 28)
        self.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.setStyleSheet("""
            QToolButton {
                border: 1px solid #555;
                border-radius: 3px;
                font-size: 14px;
            }
            QToolButton:hover {
                border: 1px solid #888;
            }
        """)
        self._setup_menu()

    def _setup_menu(self):
        """Setup border options menu."""
        menu = QtWidgets.QMenu(self)

        for label, border_type, config in self.BORDER_OPTIONS:
            action = menu.addAction(label)
            action.triggered.connect(lambda checked, c=config, t=border_type: self._on_border_selected(c, t))

        self.setMenu(menu)

    def _on_border_selected(self, config, border_type):
        """Handle border selection."""
        self.bordersChanged.emit({"type": border_type, "config": config})


# =============================================================================
# Find and Replace Dialog
# =============================================================================

class FindReplaceDialog(QtWidgets.QDialog):
    """Find and Replace dialog for spreadsheet."""

    def __init__(self, spreadsheet_widget, parent=None):
        super().__init__(parent)
        self.spreadsheet_widget = spreadsheet_widget
        self.setWindowTitle("Find and Replace")
        self.setModal(False)
        self.setMinimumWidth(400)
        self._current_match_index = -1
        self._matches = []
        self._build_ui()

    def _build_ui(self):
        """Build dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)

        # Find section
        find_layout = QtWidgets.QHBoxLayout()
        find_layout.addWidget(QtWidgets.QLabel("Find:"))
        self.find_input = QtWidgets.QLineEdit()
        self.find_input.setPlaceholderText("Search text...")
        self.find_input.textChanged.connect(self._on_find_text_changed)
        self.find_input.returnPressed.connect(self._find_next)
        find_layout.addWidget(self.find_input)
        layout.addLayout(find_layout)

        # Replace section
        replace_layout = QtWidgets.QHBoxLayout()
        replace_layout.addWidget(QtWidgets.QLabel("Replace:"))
        self.replace_input = QtWidgets.QLineEdit()
        self.replace_input.setPlaceholderText("Replace with...")
        replace_layout.addWidget(self.replace_input)
        layout.addLayout(replace_layout)

        # Options
        options_layout = QtWidgets.QHBoxLayout()
        self.case_sensitive_cb = QtWidgets.QCheckBox("Case sensitive")
        self.whole_cell_cb = QtWidgets.QCheckBox("Match entire cell")
        options_layout.addWidget(self.case_sensitive_cb)
        options_layout.addWidget(self.whole_cell_cb)
        options_layout.addStretch()
        layout.addLayout(options_layout)

        # Match info
        self.match_label = QtWidgets.QLabel("0 of 0 matches")
        self.match_label.setStyleSheet("color: #808080; padding: 5px;")
        layout.addWidget(self.match_label)

        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        self.find_prev_btn = QtWidgets.QPushButton("◀ Previous")
        self.find_next_btn = QtWidgets.QPushButton("Next ▶")
        self.replace_btn = QtWidgets.QPushButton("Replace")
        self.replace_all_btn = QtWidgets.QPushButton("Replace All")

        btn_layout.addWidget(self.find_prev_btn)
        btn_layout.addWidget(self.find_next_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.replace_btn)
        btn_layout.addWidget(self.replace_all_btn)
        layout.addLayout(btn_layout)

        # Connect signals
        self.find_next_btn.clicked.connect(self._find_next)
        self.find_prev_btn.clicked.connect(self._find_previous)
        self.replace_btn.clicked.connect(self._replace_current)
        self.replace_all_btn.clicked.connect(self._replace_all)
        self.case_sensitive_cb.stateChanged.connect(self._on_find_text_changed)
        self.whole_cell_cb.stateChanged.connect(self._on_find_text_changed)

        # Close button
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

    def _on_find_text_changed(self):
        """Rebuild matches when search text or options change."""
        self._find_matches()
        self._update_match_label()

    def _find_matches(self):
        """Find all cells matching the search text."""
        self._matches = []
        self._current_match_index = -1

        search_text = self.find_input.text()
        if not search_text:
            return

        model = self.spreadsheet_widget.model
        case_sensitive = self.case_sensitive_cb.isChecked()
        whole_cell = self.whole_cell_cb.isChecked()

        if not case_sensitive:
            search_text = search_text.lower()

        for row in range(model.rowCount()):
            for col in range(model.columnCount()):
                # Get both raw value and displayed value
                raw_value = model._data.get((row, col), "")
                formula = model._formulas.get((row, col), "")

                cell_text = str(raw_value) if raw_value else ""
                if formula:
                    # Also search in formula text
                    cell_text = formula

                if not case_sensitive:
                    cell_text = cell_text.lower()

                if whole_cell:
                    if cell_text == search_text:
                        self._matches.append((row, col))
                else:
                    if search_text in cell_text:
                        self._matches.append((row, col))

    def _update_match_label(self):
        """Update the match count label."""
        total = len(self._matches)
        if total == 0:
            self.match_label.setText("0 matches found")
        else:
            current = self._current_match_index + 1 if self._current_match_index >= 0 else 0
            self.match_label.setText(f"{current} of {total} matches")

    def _find_next(self):
        """Navigate to next match."""
        if not self._matches:
            self._find_matches()
            if not self._matches:
                return

        self._current_match_index = (self._current_match_index + 1) % len(self._matches)
        self._navigate_to_match()

    def _find_previous(self):
        """Navigate to previous match."""
        if not self._matches:
            self._find_matches()
            if not self._matches:
                return

        self._current_match_index = (self._current_match_index - 1) % len(self._matches)
        self._navigate_to_match()

    def _navigate_to_match(self):
        """Navigate to the current match."""
        if 0 <= self._current_match_index < len(self._matches):
            row, col = self._matches[self._current_match_index]
            index = self.spreadsheet_widget.model.index(row, col)
            self.spreadsheet_widget.table_view.setCurrentIndex(index)
            self.spreadsheet_widget.table_view.scrollTo(index)
            self._update_match_label()

    def _replace_current(self):
        """Replace the current match."""
        if not self._matches or self._current_match_index < 0:
            return

        row, col = self._matches[self._current_match_index]
        self._replace_cell(row, col)

        # Re-find matches and stay at current position
        self._find_matches()
        if self._current_match_index >= len(self._matches):
            self._current_match_index = len(self._matches) - 1
        self._update_match_label()

    def _replace_cell(self, row, col):
        """Replace text in a single cell."""
        model = self.spreadsheet_widget.model
        search_text = self.find_input.text()
        replace_text = self.replace_input.text()
        case_sensitive = self.case_sensitive_cb.isChecked()
        whole_cell = self.whole_cell_cb.isChecked()

        # Get current value
        raw_value = model._data.get((row, col), "")
        formula = model._formulas.get((row, col), "")

        if formula:
            # Replace in formula
            if whole_cell:
                new_value = replace_text
            else:
                if case_sensitive:
                    new_value = formula.replace(search_text, replace_text)
                else:
                    new_value = re.sub(re.escape(search_text), replace_text, formula, flags=re.IGNORECASE)
        else:
            # Replace in value
            cell_text = str(raw_value) if raw_value else ""
            if whole_cell:
                new_value = replace_text
            else:
                if case_sensitive:
                    new_value = cell_text.replace(search_text, replace_text)
                else:
                    new_value = re.sub(re.escape(search_text), replace_text, cell_text, flags=re.IGNORECASE)

        # Set new value
        index = model.index(row, col)
        model.setData(index, new_value, Qt.EditRole)

    def _replace_all(self):
        """Replace all matches."""
        if not self._matches:
            self._find_matches()

        if not self._matches:
            return

        # Replace in reverse order to maintain positions
        for row, col in reversed(self._matches):
            self._replace_cell(row, col)

        # Clear matches
        replaced_count = len(self._matches)
        self._matches = []
        self._current_match_index = -1
        self._update_match_label()

        QtWidgets.QMessageBox.information(
            self, "Replace All",
            f"Replaced {replaced_count} occurrence(s)."
        )


# =============================================================================
# Formatting Toolbar
# =============================================================================

class FormattingToolbar(QtWidgets.QWidget):
    """Formatting toolbar similar to Google Sheets/Excel."""

    # Signals
    undoRequested = QtCore.Signal()
    redoRequested = QtCore.Signal()
    boldToggled = QtCore.Signal(bool)
    italicToggled = QtCore.Signal(bool)
    underlineToggled = QtCore.Signal(bool)
    strikethroughToggled = QtCore.Signal(bool)
    fontColorChanged = QtCore.Signal(str)
    bgColorChanged = QtCore.Signal(str)
    alignmentChanged = QtCore.Signal(str)
    wrapToggled = QtCore.Signal(bool)
    formatChanged = QtCore.Signal(str)  # Emits Excel-compatible format string

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        """Build toolbar with formatting buttons."""
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(5, 3, 5, 3)
        layout.setSpacing(3)

        # Undo/Redo buttons
        self.undo_btn = self._create_tool_button("↶", "Undo (Ctrl+Z)")
        self.redo_btn = self._create_tool_button("↷", "Redo (Ctrl+Y)")
        self.undo_btn.clicked.connect(self.undoRequested.emit)
        self.redo_btn.clicked.connect(self.redoRequested.emit)
        layout.addWidget(self.undo_btn)
        layout.addWidget(self.redo_btn)

        layout.addWidget(self._create_separator())

        # Font style buttons (toggleable)
        self.bold_btn = self._create_toggle_button("B", "Bold (Ctrl+B)")
        self.bold_btn.setStyleSheet(self.bold_btn.styleSheet() + "font-weight: bold;")
        self.italic_btn = self._create_toggle_button("I", "Italic (Ctrl+I)")
        self.italic_btn.setStyleSheet(self.italic_btn.styleSheet() + "font-style: italic;")
        self.underline_btn = self._create_toggle_button("U", "Underline (Ctrl+U)")
        self.underline_btn.setStyleSheet(self.underline_btn.styleSheet() + "text-decoration: underline;")
        self.strikethrough_btn = self._create_toggle_button("S", "Strikethrough")
        self.strikethrough_btn.setStyleSheet(self.strikethrough_btn.styleSheet() + "text-decoration: line-through;")

        self.bold_btn.toggled.connect(self.boldToggled.emit)
        self.italic_btn.toggled.connect(self.italicToggled.emit)
        self.underline_btn.toggled.connect(self.underlineToggled.emit)
        self.strikethrough_btn.toggled.connect(self.strikethroughToggled.emit)

        layout.addWidget(self.bold_btn)
        layout.addWidget(self.italic_btn)
        layout.addWidget(self.underline_btn)
        layout.addWidget(self.strikethrough_btn)

        layout.addWidget(self._create_separator())

        # Color pickers
        self.font_color_btn = ColorPickerButton("A", "Font Color", default_color="#FFFFFF", is_background=False)
        self.bg_color_btn = ColorPickerButton("▐", "Fill Color", default_color="#4472C4", is_background=True)
        self.font_color_btn.colorChanged.connect(self.fontColorChanged.emit)
        self.bg_color_btn.colorChanged.connect(self.bgColorChanged.emit)
        layout.addWidget(self.font_color_btn)
        layout.addWidget(self.bg_color_btn)

        layout.addWidget(self._create_separator())

        # Alignment buttons (mutually exclusive)
        self.align_left_btn = self._create_toggle_button("≡", "Align Left")
        self.align_center_btn = self._create_toggle_button("≡", "Align Center")
        self.align_right_btn = self._create_toggle_button("≡", "Align Right")

        # Make alignment buttons work as a group
        self.align_left_btn.clicked.connect(lambda: self._set_alignment("left"))
        self.align_center_btn.clicked.connect(lambda: self._set_alignment("center"))
        self.align_right_btn.clicked.connect(lambda: self._set_alignment("right"))

        layout.addWidget(self.align_left_btn)
        layout.addWidget(self.align_center_btn)
        layout.addWidget(self.align_right_btn)

        layout.addWidget(self._create_separator())

        # Text wrap toggle
        self.wrap_btn = self._create_toggle_button("↵", "Wrap Text")
        self.wrap_btn.toggled.connect(self.wrapToggled.emit)
        layout.addWidget(self.wrap_btn)

        layout.addWidget(self._create_separator())

        # Format dropdown button
        self.format_btn = self._create_format_dropdown_button()
        layout.addWidget(self.format_btn)

        layout.addStretch()

    def _create_tool_button(self, text, tooltip):
        """Create a standard tool button."""
        btn = QtWidgets.QToolButton()
        btn.setText(text)
        btn.setToolTip(tooltip)
        btn.setFixedSize(28, 28)
        btn.setStyleSheet("""
            QToolButton {
                border: 1px solid #555;
                border-radius: 3px;
                font-size: 14px;
            }
            QToolButton:hover {
                background-color: #444;
                border: 1px solid #888;
            }
            QToolButton:pressed {
                background-color: #555;
            }
        """)
        return btn

    def _create_toggle_button(self, text, tooltip):
        """Create a toggleable tool button."""
        btn = QtWidgets.QToolButton()
        btn.setText(text)
        btn.setToolTip(tooltip)
        btn.setCheckable(True)
        btn.setFixedSize(28, 28)
        btn.setStyleSheet("""
            QToolButton {
                border: 1px solid #555;
                border-radius: 3px;
                font-size: 12px;
            }
            QToolButton:hover {
                background-color: #444;
                border: 1px solid #888;
            }
            QToolButton:checked {
                background-color: #4472C4;
                border: 1px solid #5588DD;
            }
        """)
        return btn

    def _create_separator(self):
        """Create a vertical separator."""
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.VLine)
        sep.setFrameShadow(QtWidgets.QFrame.Sunken)
        sep.setFixedWidth(10)
        return sep

    def _set_alignment(self, alignment):
        """Set alignment and update button states."""
        self.align_left_btn.setChecked(alignment == "left")
        self.align_center_btn.setChecked(alignment == "center")
        self.align_right_btn.setChecked(alignment == "right")
        self.alignmentChanged.emit(alignment)

    def _create_format_dropdown_button(self):
        """Create a dropdown button for cell number format selection."""
        btn = QtWidgets.QToolButton()
        btn.setText("123")
        btn.setToolTip("Number Format")
        btn.setFixedSize(40, 28)
        btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        btn.setStyleSheet("""
            QToolButton {
                border: 1px solid #555;
                border-radius: 3px;
                font-size: 11px;
                padding-left: 2px;
            }
            QToolButton:hover {
                background-color: #444;
                border: 1px solid #888;
            }
            QToolButton::menu-indicator {
                image: none;
                subcontrol-position: right center;
                subcontrol-origin: padding;
                width: 8px;
            }
        """)

        # Create the format menu
        menu = QtWidgets.QMenu(btn)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                border: 1px solid #555;
                padding: 5px;
            }
            QMenu::item {
                padding: 5px 25px 5px 10px;
                color: #ffffff;
            }
            QMenu::item:selected {
                background-color: #4472C4;
            }
            QMenu::separator {
                height: 1px;
                background: #555;
                margin: 5px 0;
            }
        """)

        # General format
        format_general = menu.addAction("General")
        format_general.triggered.connect(lambda: self.formatChanged.emit("General"))
        menu.addSeparator()

        # Number formats submenu
        number_menu = menu.addMenu("Number")
        format_number = number_menu.addAction("1,234.56  (#,##0.00)")
        format_number.triggered.connect(lambda: self.formatChanged.emit("#,##0.00"))
        format_number_no_dec = number_menu.addAction("1,235  (#,##0)")
        format_number_no_dec.triggered.connect(lambda: self.formatChanged.emit("#,##0"))

        # Currency format (uses project settings)
        format_currency = menu.addAction("Currency")
        format_currency.triggered.connect(lambda: self.formatChanged.emit("CURRENCY"))

        # Accounting format (uses project currency)
        format_accounting = menu.addAction("Accounting")
        format_accounting.triggered.connect(lambda: self.formatChanged.emit("ACCOUNTING"))
        menu.addSeparator()

        # Percentage formats submenu
        percentage_menu = menu.addMenu("Percentage")
        format_percentage = percentage_menu.addAction("12.34%  (0.00%)")
        format_percentage.triggered.connect(lambda: self.formatChanged.emit("0.00%"))
        format_percentage_no_dec = percentage_menu.addAction("12%  (0%)")
        format_percentage_no_dec.triggered.connect(lambda: self.formatChanged.emit("0%"))
        menu.addSeparator()

        # Text format
        format_text = menu.addAction("Text  (@)")
        format_text.triggered.connect(lambda: self.formatChanged.emit("@"))

        btn.setMenu(menu)
        self._format_menu = menu  # Keep reference
        return btn

    def update_from_cell_meta(self, cell_meta):
        """Update toolbar state based on cell metadata."""
        # Block signals to prevent feedback loops
        self.bold_btn.blockSignals(True)
        self.italic_btn.blockSignals(True)
        self.underline_btn.blockSignals(True)
        self.strikethrough_btn.blockSignals(True)
        self.wrap_btn.blockSignals(True)
        self.align_left_btn.blockSignals(True)
        self.align_center_btn.blockSignals(True)
        self.align_right_btn.blockSignals(True)

        # Update button states
        self.bold_btn.setChecked(cell_meta.get("bold", False))
        self.italic_btn.setChecked(cell_meta.get("italic", False))
        self.underline_btn.setChecked(cell_meta.get("underline", False))
        self.strikethrough_btn.setChecked(cell_meta.get("strikethrough", False))
        self.wrap_btn.setChecked(cell_meta.get("wrap", False))

        # Update alignment
        align_h = cell_meta.get("align_h", "left")
        self.align_left_btn.setChecked(align_h == "left")
        self.align_center_btn.setChecked(align_h == "center")
        self.align_right_btn.setChecked(align_h == "right")

        # Update colors (always update, reset to default if not set)
        font_color = cell_meta.get("font_color") or "#FFFFFF"
        bg_color = cell_meta.get("bg_color") or ""
        self.font_color_btn.set_current_color(font_color)
        self.bg_color_btn.set_current_color(bg_color if bg_color else "#4472C4")

        # Unblock signals
        self.bold_btn.blockSignals(False)
        self.italic_btn.blockSignals(False)
        self.underline_btn.blockSignals(False)
        self.strikethrough_btn.blockSignals(False)
        self.wrap_btn.blockSignals(False)
        self.align_left_btn.blockSignals(False)
        self.align_center_btn.blockSignals(False)
        self.align_right_btn.blockSignals(False)


# =============================================================================
# Formatted Cell Delegate
# =============================================================================

class FormattedCellDelegate(QtWidgets.QStyledItemDelegate):
    """Delegate for rendering cells with formatting (bold, italic, colors, borders, etc.)."""

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self._model = model

    def paint(self, painter, option, index):
        """Paint cell with formatting from cell_meta."""
        row, col = index.row(), index.column()

        # Check if this cell is part of a merged region (and not the anchor)
        merged_info = self._model.get_merged_cell_info(row, col)
        if merged_info and not merged_info.get('is_anchor'):
            # This cell is merged into another cell, don't paint content
            return

        painter.save()

        # Get cell metadata
        cell_meta = self._model.get_cell_meta(row, col)

        # 1. Paint background color
        bg_color = cell_meta.get('bg_color')
        if bg_color:
            painter.fillRect(option.rect, QtGui.QColor(bg_color))
        elif option.state & QtWidgets.QStyle.State_Selected:
            # Use transparent for selection (we draw border instead)
            pass
        else:
            # Default background
            pass

        # 2. Paint borders
        self._paint_borders(painter, option.rect, cell_meta.get('borders', {}))

        # 3. Set up font with formatting
        font = QtGui.QFont(option.font)
        if cell_meta.get('bold'):
            font.setBold(True)
        if cell_meta.get('italic'):
            font.setItalic(True)
        if cell_meta.get('underline'):
            font.setUnderline(True)
        if cell_meta.get('strikethrough'):
            font.setStrikeOut(True)
        painter.setFont(font)

        # 4. Set text color
        font_color = cell_meta.get('font_color')
        if font_color:
            painter.setPen(QtGui.QColor(font_color))
        elif option.state & QtWidgets.QStyle.State_Selected:
            painter.setPen(option.palette.highlightedText().color())
        else:
            painter.setPen(QtGui.QColor("#FFFFFF"))  # Default white text

        # 5. Calculate alignment
        align_h = cell_meta.get('align_h', '')
        alignment = Qt.AlignVCenter

        if align_h == 'left':
            alignment |= Qt.AlignLeft
        elif align_h == 'center':
            alignment |= Qt.AlignHCenter
        elif align_h == 'right':
            alignment |= Qt.AlignRight
        else:
            # Auto-detect: numbers right, text left
            value = index.data(Qt.DisplayRole)
            try:
                if value:
                    float(str(value).replace(',', '').replace('$', '').replace('%', ''))
                alignment |= Qt.AlignRight
            except (ValueError, TypeError):
                alignment |= Qt.AlignLeft

        # 6. Get display text
        value = index.data(Qt.DisplayRole)
        text = str(value) if value else ""

        # 7. Draw text with wrapping option
        text_rect = option.rect.adjusted(4, 2, -4, -2)
        if cell_meta.get('wrap'):
            painter.drawText(text_rect, alignment | Qt.TextWordWrap, text)
        else:
            # Elide text if too long
            metrics = QtGui.QFontMetrics(font)
            elided_text = metrics.elidedText(text, Qt.ElideRight, text_rect.width())
            painter.drawText(text_rect, alignment, elided_text)

        painter.restore()

    def _paint_borders(self, painter, rect, borders):
        """Paint cell borders."""
        if not borders:
            return

        for side in ['top', 'bottom', 'left', 'right']:
            border = borders.get(side)
            if border:
                pen = self._get_border_pen(border)
                painter.setPen(pen)
                if side == 'top':
                    painter.drawLine(rect.topLeft(), rect.topRight())
                elif side == 'bottom':
                    painter.drawLine(rect.bottomLeft(), rect.bottomRight())
                elif side == 'left':
                    painter.drawLine(rect.topLeft(), rect.bottomLeft())
                elif side == 'right':
                    painter.drawLine(rect.topRight(), rect.bottomRight())

    def _get_border_pen(self, border):
        """Get QPen for border style."""
        style = border.get('style', 'thin')
        color = QtGui.QColor(border.get('color', '#000000'))

        pen = QtGui.QPen(color)
        if style == 'thin':
            pen.setWidth(1)
        elif style == 'medium':
            pen.setWidth(2)
        elif style == 'thick':
            pen.setWidth(3)
        elif style == 'dashed':
            pen.setStyle(Qt.DashLine)
            pen.setWidth(1)
        elif style == 'double':
            pen.setWidth(3)
        return pen

    def sizeHint(self, option, index):
        """Return size hint, accounting for text wrapping."""
        row, col = index.row(), index.column()
        cell_meta = self._model.get_cell_meta(row, col)

        if cell_meta.get('wrap'):
            # Calculate height needed for wrapped text
            value = index.data(Qt.DisplayRole)
            text = str(value) if value else ""
            font = option.font
            if cell_meta.get('bold'):
                font.setBold(True)
            metrics = QtGui.QFontMetrics(font)
            text_rect = metrics.boundingRect(
                QtCore.QRect(0, 0, option.rect.width() - 8, 10000),
                Qt.TextWordWrap | Qt.AlignLeft,
                text
            )
            return QtCore.QSize(option.rect.width(), max(25, text_rect.height() + 8))

        return super().sizeHint(option, index)


# =============================================================================
# Formatting Commands (for Undo/Redo)
# =============================================================================

class CellFormattingCommand:
    """Command pattern for undo/redo of cell formatting changes."""

    def __init__(self, model, cells, property_name, old_values, new_value):
        """
        Args:
            model: SpreadsheetModel instance
            cells: List of (row, col) tuples
            property_name: Formatting property being changed (e.g., 'bold', 'font_color')
            old_values: Dict mapping (row, col) to old value
            new_value: New value to apply to all cells
        """
        self.model = model
        self.cells = cells
        self.property_name = property_name
        self.old_values = old_values
        self.new_value = new_value

    def undo(self):
        """Restore old formatting values."""
        for (row, col), old_value in self.old_values.items():
            self.model.set_cell_meta_property(row, col, self.property_name, old_value)
        self._emit_changes()

    def redo(self):
        """Apply new formatting value."""
        for (row, col) in self.cells:
            self.model.set_cell_meta_property(row, col, self.property_name, self.new_value)
        self._emit_changes()

    def _emit_changes(self):
        """Emit dataChanged for affected cells."""
        for (row, col) in self.cells:
            index = self.model.index(row, col)
            self.model.dataChanged.emit(index, index, [Qt.DisplayRole])


class MergeCellsCommand:
    """Command pattern for merge/unmerge cells."""

    def __init__(self, model, merge_range, is_merge=True, previous_merged=None):
        """
        Args:
            model: SpreadsheetModel
            merge_range: Dict with start_row, start_col, end_row, end_col
            is_merge: True for merge, False for unmerge
            previous_merged: Previous merged cells list (for undo of unmerge)
        """
        self.model = model
        self.merge_range = merge_range
        self.is_merge = is_merge
        self.previous_merged = previous_merged or []

    def undo(self):
        if self.is_merge:
            self.model._unmerge_cells_internal(self.merge_range)
        else:
            self.model._merged_cells = self.previous_merged.copy()
        self.model.layoutChanged.emit()

    def redo(self):
        if self.is_merge:
            self.model._merge_cells_internal(self.merge_range)
        else:
            self.model._unmerge_cells_internal(self.merge_range)
        self.model.layoutChanged.emit()


class CellDataFormatCommand:
    """Command pattern for undo/redo of cell data format changes (Currency, Percentage, etc.)."""

    def __init__(self, model, cells, old_formats, new_format):
        """Initialize data format command.

        Args:
            model: SpreadsheetModel instance
            cells: List of (row, col) tuples
            old_formats: Dict mapping (row, col) to old format string (or None)
            new_format: New format string to apply to all cells
        """
        self.model = model
        self.cells = cells
        self.old_formats = old_formats
        self.new_format = new_format

    def undo(self):
        """Restore old format values."""
        for (row, col) in self.cells:
            old_format = self.old_formats.get((row, col))
            if old_format:
                self.model._formats[(row, col)] = old_format
            else:
                self.model._formats.pop((row, col), None)
            # Clear cache for this cell
            self.model._evaluated_cache.pop((row, col), None)
        self._emit_changes()

    def redo(self):
        """Apply new format value."""
        for (row, col) in self.cells:
            if self.new_format:
                self.model._formats[(row, col)] = self.new_format
            else:
                self.model._formats.pop((row, col), None)
            # Clear cache for this cell
            self.model._evaluated_cache.pop((row, col), None)
        self._emit_changes()

    def _emit_changes(self):
        """Emit dataChanged for affected cells."""
        if self.cells:
            min_row = min(r for r, c in self.cells)
            max_row = max(r for r, c in self.cells)
            min_col = min(c for r, c in self.cells)
            max_col = max(c for r, c in self.cells)
            self.model.dataChanged.emit(
                self.model.index(min_row, min_col),
                self.model.index(max_row, max_col),
                [Qt.DisplayRole]
            )


class SpreadsheetTableView(QtWidgets.QTableView):
    """Custom table view with Excel-like selection and fill handle."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fill_handle_rect = QtCore.QRect()
        self._is_dragging_fill_handle = False
        self._drag_start_index = None
        self._drag_current_index = None
        self.setMouseTracking(True)

        # Clipboard data for cut/copy/paste
        self._clipboard_data = None
        self._clipboard_is_cut = False

        # Formula edit mode tracking
        self._formula_edit_cell = None  # The cell being edited (row, col)
        self._formula_reference_start = None  # Start cell for range selection during formula edit
        self._is_dragging_formula_ref = False  # True when drag-selecting cells for formula reference
        self._formula_ref_drag_end = None  # Current end cell during drag
        self._formula_editor_ref = None  # Reference to the editor during formula reference selection
        self._formula_ref_insert_pos = 0  # Cursor position where reference was inserted
        self._formula_ref_insert_len = 0  # Length of the last inserted reference

        # Ensure the table view can receive keyboard events
        self.setFocusPolicy(Qt.StrongFocus)

        # Install event filter on viewport to intercept mouse events during formula editing
        self.viewport().installEventFilter(self)

    def _get_cell_reference(self, row, col):
        """Get Excel-style cell reference (e.g., 'A1', 'B2') from row and column indices."""
        # Convert column index to letter(s)
        col_name = ""
        col_idx = col + 1  # Make it 1-based
        while col_idx > 0:
            col_idx -= 1
            col_name = chr(65 + (col_idx % 26)) + col_name
            col_idx //= 26
        # Row is 1-based in Excel notation
        return f"{col_name}{row + 1}"

    def _get_range_reference(self, start_row, start_col, end_row, end_col):
        """Get Excel-style range reference (e.g., 'A1:C5') from start and end indices."""
        start_ref = self._get_cell_reference(start_row, start_col)
        end_ref = self._get_cell_reference(end_row, end_col)
        if start_ref == end_ref:
            return start_ref
        return f"{start_ref}:{end_ref}"

    def _find_cell_editor(self):
        """Find the active cell editor widget.

        During editing, Qt creates a QLineEdit as a child of the viewport.
        We search for it to get the current editor.
        """
        # First check if we're in editing state
        if self.state() != QtWidgets.QAbstractItemView.EditingState:
            return None

        # Look for QLineEdit child widgets in the viewport
        from qtpy.QtWidgets import QLineEdit
        for child in self.viewport().children():
            if isinstance(child, QLineEdit):
                return child

        # Fallback: try QApplication.focusWidget()
        from qtpy.QtWidgets import QApplication
        editor = QApplication.focusWidget()
        if editor and hasattr(editor, 'text') and hasattr(editor, 'insert'):
            return editor

        return None

    def _is_in_formula_edit_mode(self):
        """Check if we're currently editing a cell with a formula (starts with '=')."""
        editor = self._find_cell_editor()
        if editor and hasattr(editor, 'text'):
            text = editor.text()
            if text.startswith('='):
                return True

        # Not in formula edit mode - clear stored reference
        self._formula_editor_ref = None
        self._formula_reference_start = None
        return False

    def _get_current_editor(self):
        """Get the current editor widget if in edit mode."""
        return self._find_cell_editor()

    def _insert_cell_reference(self, ref_text, replace_last=False):
        """Insert a cell reference into the current formula editor.

        Args:
            ref_text: The cell reference text to insert (e.g., "A1" or "A1:B5")
            replace_last: If True, replace the last inserted reference instead of inserting
        """
        # Use stored editor reference if available, otherwise find it
        editor = self._formula_editor_ref if self._formula_editor_ref else self._get_current_editor()
        if editor and hasattr(editor, 'insert'):
            if replace_last and self._formula_ref_insert_len > 0:
                # Remove the previously inserted reference before inserting the new one
                # Select from insert position to insert position + length, then replace
                current_pos = editor.cursorPosition() if hasattr(editor, 'cursorPosition') else 0
                # The cursor should be right after the last inserted reference
                start_pos = self._formula_ref_insert_pos
                end_pos = start_pos + self._formula_ref_insert_len

                # Select and delete the old reference
                if hasattr(editor, 'setSelection'):
                    editor.setSelection(start_pos, self._formula_ref_insert_len)
                    editor.del_()  # Delete selected text
                elif hasattr(editor, 'setText') and hasattr(editor, 'text'):
                    # Fallback: manually edit the text
                    text = editor.text()
                    new_text = text[:start_pos] + text[end_pos:]
                    editor.setText(new_text)
                    editor.setCursorPosition(start_pos)

            # Track where we're inserting
            self._formula_ref_insert_pos = editor.cursorPosition() if hasattr(editor, 'cursorPosition') else 0

            # QLineEdit has insert() method that inserts at cursor position
            editor.insert(ref_text)

            # Track the length of the inserted reference
            self._formula_ref_insert_len = len(ref_text)

            # Restore focus and ensure cursor is visible
            self._restore_editor_cursor(editor)
            return True
        return False

    def _restore_editor_cursor(self, editor):
        """Restore focus and cursor visibility to an editor widget."""
        if not editor or not hasattr(editor, 'setFocus'):
            return

        from qtpy.QtWidgets import QApplication

        # Store cursor position before any operations
        cursor_pos = editor.cursorPosition() if hasattr(editor, 'cursorPosition') else 0

        # Process any pending events first
        QApplication.processEvents()

        # Set focus with OtherFocusReason (must use FocusReason, not FocusPolicy)
        editor.setFocus(Qt.OtherFocusReason)

        # Restore cursor position explicitly
        if hasattr(editor, 'setCursorPosition'):
            editor.setCursorPosition(cursor_pos)

        # Deselect to ensure no selection interferes with cursor
        if hasattr(editor, 'deselect'):
            editor.deselect()

        # Force the widget to repaint
        editor.update()

        # Schedule another focus restoration after Qt event loop settles
        def delayed_restore():
            if editor and hasattr(editor, 'setFocus'):
                try:
                    editor.setFocus(Qt.OtherFocusReason)
                    if hasattr(editor, 'setCursorPosition'):
                        editor.setCursorPosition(cursor_pos)
                    if hasattr(editor, 'deselect'):
                        editor.deselect()
                except RuntimeError:
                    pass  # Widget may have been deleted

        QtCore.QTimer.singleShot(10, delayed_restore)

    def closeEditor(self, editor, hint):
        """Override to prevent editor from closing during formula reference selection.

        When selecting cells for a formula reference, we want to keep the editor
        open until the user explicitly commits (Enter) or cancels (Escape).
        """
        from qtpy.QtWidgets import QAbstractItemDelegate

        # Check if we should block closing (formula edit mode active)
        should_block = False

        # If we have a stored formula editor reference, check if this is that editor
        if self._formula_editor_ref is not None:
            if editor == self._formula_editor_ref:
                should_block = True

        # Also check if editor contains a formula
        if hasattr(editor, 'text'):
            text = editor.text()
            if text.startswith('='):
                should_block = True
                # Store reference for future use
                self._formula_editor_ref = editor

        # If we should block, only allow explicit submit (Enter) or cancel (Escape)
        if should_block:
            # SubmitModelCache = Enter key pressed
            # RevertModelCache = Escape key pressed
            if hint in (QAbstractItemDelegate.SubmitModelCache, QAbstractItemDelegate.RevertModelCache):
                # User explicitly committed or cancelled - allow close
                self._formula_editor_ref = None
                self._formula_reference_start = None
                self._is_dragging_formula_ref = False
                super().closeEditor(editor, hint)
            else:
                # Block close - keep editor open for formula reference selection
                # Re-focus the editor and ensure cursor is visible
                self._restore_editor_cursor(editor)
            return

        # Normal close behavior
        self._formula_editor_ref = None
        self._formula_reference_start = None
        self._is_dragging_formula_ref = False
        super().closeEditor(editor, hint)

    def eventFilter(self, obj, event):
        """Event filter to intercept mouse events during formula editing.

        This catches mouse events on the viewport BEFORE they cause
        focus changes that would close the editor.
        """
        from qtpy.QtCore import QEvent
        from qtpy.QtWidgets import QLineEdit, QApplication

        if obj == self.viewport():
            # Handle mouse press - formula reference selection
            if event.type() == QEvent.MouseButtonPress:
                # Try multiple ways to find the editor
                editor = None

                # Method 1: Use stored reference
                if self._formula_editor_ref is not None:
                    editor = self._formula_editor_ref

                # Method 2: Check if we're in editing state and find QLineEdit child
                if editor is None and self.state() == QtWidgets.QAbstractItemView.EditingState:
                    for child in self.viewport().children():
                        if isinstance(child, QLineEdit):
                            editor = child
                            break

                # Method 3: Check focused widget
                if editor is None:
                    focused = QApplication.focusWidget()
                    if isinstance(focused, QLineEdit):
                        editor = focused

                # Check if editor has formula
                if editor and hasattr(editor, 'text') and editor.text().startswith('='):
                    # Store editor reference
                    self._formula_editor_ref = editor

                    # Get the clicked position
                    pos = event.pos()
                    clicked_index = self.indexAt(pos)

                    if clicked_index.isValid():
                        current_idx = self.currentIndex()
                        # Don't insert reference if clicking on the cell being edited
                        if clicked_index.row() != current_idx.row() or clicked_index.column() != current_idx.column():
                            clicked_row = clicked_index.row()
                            clicked_col = clicked_index.column()

                            # Check for Shift+click for range selection
                            if event.modifiers() & Qt.ShiftModifier and self._formula_reference_start:
                                # Shift+click: expand to range from first cell to this cell
                                start_row, start_col = self._formula_reference_start
                                min_row, max_row = min(start_row, clicked_row), max(start_row, clicked_row)
                                min_col, max_col = min(start_col, clicked_col), max(start_col, clicked_col)

                                # Update the end point for green outline
                                self._formula_ref_drag_end = (clicked_row, clicked_col)

                                # Replace the single cell reference with the range reference
                                ref = self._get_range_reference(min_row, min_col, max_row, max_col)
                                self._insert_cell_reference(ref, replace_last=True)
                            else:
                                # Regular click: set as new start cell and insert single reference
                                self._formula_reference_start = (clicked_row, clicked_col)
                                self._formula_ref_drag_end = None  # Clear any previous range end

                                # Reset insert tracking for new reference
                                self._formula_ref_insert_pos = 0
                                self._formula_ref_insert_len = 0

                                # Insert single cell reference
                                ref = self._get_cell_reference(clicked_row, clicked_col)
                                self._insert_cell_reference(ref)

                            # Update viewport to show green outline
                            self.viewport().update()

                            # Consume the event - don't let it propagate
                            return True

        return super().eventFilter(obj, event)

    def paintEvent(self, event):
        """Paint the table and add blue border with fill handle."""
        super().paintEvent(event)

        # Get current selection
        current = self.currentIndex()
        selection = self.selectionModel().selectedIndexes() if self.selectionModel() else []

        if not current.isValid() and not selection:
            return

        painter = QtGui.QPainter(self.viewport())

        # If dragging fill handle, draw preview of fill range
        if self._is_dragging_fill_handle and self._drag_start_index and self._drag_current_index and self._drag_current_index != self._drag_start_index:
            start_row = self._drag_start_index.row()
            start_col = self._drag_start_index.column()
            end_row = self._drag_current_index.row()
            end_col = self._drag_current_index.column()

            # Only support vertical fill (same column)
            if start_col == end_col and end_row > start_row:
                painter.setBrush(QtGui.QColor(68, 114, 196, 30))  # Light blue with alpha
                painter.setPen(Qt.NoPen)

                for row in range(start_row + 1, end_row + 1):
                    cell_rect = self.visualRect(self.model().index(row, start_col))
                    if not cell_rect.isEmpty():
                        painter.drawRect(cell_rect)

        # If in formula edit mode with a reference start, draw green outline
        if self._formula_reference_start and self._formula_editor_ref:
            start_row, start_col = self._formula_reference_start

            if self._formula_ref_drag_end:
                # Range selection (Shift+click was used)
                end_row, end_col = self._formula_ref_drag_end
                min_row = min(start_row, end_row)
                max_row = max(start_row, end_row)
                min_col = min(start_col, end_col)
                max_col = max(start_col, end_col)
            else:
                # Single cell selection
                min_row = max_row = start_row
                min_col = max_col = start_col

            # Get visual rect of the selection
            top_left_rect = self.visualRect(self.model().index(min_row, min_col))
            bottom_right_rect = self.visualRect(self.model().index(max_row, max_col))

            if not top_left_rect.isEmpty() and not bottom_right_rect.isEmpty():
                ref_rect = top_left_rect.united(bottom_right_rect)

                # Draw a distinct colored border (green) around formula reference
                painter.setPen(QtGui.QPen(QtGui.QColor("#4CAF50"), 2))
                painter.setBrush(QtGui.QColor(76, 175, 80, 40))  # Light green with alpha
                painter.drawRect(ref_rect.adjusted(1, 1, -1, -1))

        # Draw border around all selected cells
        if selection:
            # Find bounding rectangle of selection
            min_row = min(idx.row() for idx in selection)
            max_row = max(idx.row() for idx in selection)
            min_col = min(idx.column() for idx in selection)
            max_col = max(idx.column() for idx in selection)

            # Get visual rect of bounding selection
            top_left_rect = self.visualRect(self.model().index(min_row, min_col))
            bottom_right_rect = self.visualRect(self.model().index(max_row, max_col))

            if not top_left_rect.isEmpty() and not bottom_right_rect.isEmpty():
                # Combine into selection bounding rect
                selection_rect = top_left_rect.united(bottom_right_rect)

                # Draw blue border around entire selection
                painter.setPen(QtGui.QPen(QtGui.QColor("#4472C4"), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(selection_rect.adjusted(1, 1, -1, -1))

                # Draw fill handle at bottom-right of selection
                handle_size = 6
                handle_x = selection_rect.right() - handle_size // 2
                handle_y = selection_rect.bottom() - handle_size // 2
                self._fill_handle_rect = QtCore.QRect(handle_x, handle_y, handle_size, handle_size)

                painter.setBrush(QtGui.QColor("#4472C4"))
                painter.setPen(Qt.NoPen)
                painter.drawRect(self._fill_handle_rect)
        elif current.isValid():
            # Single cell selected - draw border around it
            rect = self.visualRect(current)
            if not rect.isEmpty():
                painter.setPen(QtGui.QPen(QtGui.QColor("#4472C4"), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(rect.adjusted(1, 1, -1, -1))

                # Draw fill handle
                handle_size = 6
                handle_x = rect.right() - handle_size // 2
                handle_y = rect.bottom() - handle_size // 2
                self._fill_handle_rect = QtCore.QRect(handle_x, handle_y, handle_size, handle_size)

                painter.setBrush(QtGui.QColor("#4472C4"))
                painter.setPen(Qt.NoPen)
                painter.drawRect(self._fill_handle_rect)

        painter.end()

    def mousePressEvent(self, event):
        """Handle mouse press for fill handle dragging."""
        if event.button() == Qt.LeftButton:
            # Check if clicked on fill handle
            if self._fill_handle_rect.contains(event.pos()):
                self._is_dragging_fill_handle = True
                self._drag_start_index = self.currentIndex()
                self._drag_current_index = self._drag_start_index
                # Don't call super() - we don't want to change selection
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move for fill handle dragging."""
        if self._is_dragging_fill_handle and self._drag_start_index:
            # During drag, update cursor and track position
            self.setCursor(Qt.CrossCursor)

            # Get the index under the mouse
            index = self.indexAt(event.pos())
            if index.isValid() and index != self._drag_current_index:
                self._drag_current_index = index
                self.viewport().update()

            # Don't call super() - we don't want selection to change
            event.accept()
            return

        # Update cursor when hovering over fill handle (not dragging)
        if self._fill_handle_rect.contains(event.pos()):
            self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release to complete fill operation."""
        # Handle fill handle drag completion
        if self._is_dragging_fill_handle and self._drag_start_index and self._drag_current_index:
            if self._drag_current_index != self._drag_start_index:
                self._perform_fill_operation()

            self._is_dragging_fill_handle = False
            self._drag_start_index = None
            self._drag_current_index = None
            self.setCursor(Qt.ArrowCursor)  # Reset cursor
            self.viewport().update()
            # Don't call super() - we handled the event
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def _perform_fill_operation(self):
        """Perform the fill operation from start to current cell."""
        if not self._drag_start_index or not self._drag_current_index:
            return

        model = self.model()
        if not model:
            return

        start_row = self._drag_start_index.row()
        start_col = self._drag_start_index.column()
        end_row = self._drag_current_index.row()
        end_col = self._drag_current_index.column()

        # Only support vertical fill for now (same column)
        if start_col != end_col:
            return

        # Ensure we're dragging down
        if end_row <= start_row:
            return

        # Get the source cell's data
        source_data = model.data(self._drag_start_index, Qt.EditRole)
        source_formula = None

        if hasattr(model, '_formulas'):
            source_formula = model._formulas.get((start_row, start_col))

        # Fill the cells
        for row in range(start_row + 1, end_row + 1):
            if source_formula:
                # It's a formula - adjust row references
                row_offset = row - start_row
                new_formula = self._adjust_formula_for_fill(source_formula, row_offset)
                target_index = model.index(row, start_col)
                model.setData(target_index, new_formula, Qt.EditRole)
            else:
                # It's a value - copy as is
                target_index = model.index(row, start_col)
                model.setData(target_index, source_data, Qt.EditRole)

        logger.info(f"Filled cells from ({start_row},{start_col}) to ({end_row},{end_col})")

    def _adjust_formula_for_fill(self, formula, row_offset):
        """Adjust formula references when filling down.

        Args:
            formula: Original formula string
            row_offset: Number of rows to offset (positive = down)

        Returns:
            Adjusted formula string
        """
        # Pattern to match cell references like A1, B2, $A$1, etc.
        pattern = r'(\$?)([A-Z]+)(\$?)(\d+)'

        def replace_ref(match):
            col_abs = match.group(1)  # $ before column
            col_letter = match.group(2)
            row_abs = match.group(3)  # $ before row
            row_num = int(match.group(4))

            # If not absolute row reference, adjust the row
            if not row_abs:
                new_row_num = row_num + row_offset
                return f"{col_abs}{col_letter}{row_abs}{new_row_num}"

            return match.group(0)

        return re.sub(pattern, replace_ref, formula)

    def keyPressEvent(self, event):
        """Handle special keyboard events.

        Clipboard shortcuts (Ctrl+C/V/X) must be handled here because QTableView's
        base class has built-in clipboard handling that intercepts these keys
        before QShortcut can process them.
        """
        key = event.key()
        modifiers = event.modifiers()

        # Check for Ctrl/Cmd modifier (ControlModifier works for both Ctrl and Cmd)
        has_ctrl = modifiers & Qt.ControlModifier

        # Clipboard shortcuts - handle directly to prevent QTableView base class interception
        if has_ctrl:
            if key == Qt.Key_C:
                self._copy_selection()
                event.accept()
                return
            elif key == Qt.Key_V:
                self._paste_selection()
                event.accept()
                return
            elif key == Qt.Key_X:
                self._cut_selection()
                event.accept()
                return
            elif key == Qt.Key_Z:
                self._undo()
                event.accept()
                return
            elif key == Qt.Key_Y:
                self._redo()
                event.accept()
                return
            elif key in (Qt.Key_H, Qt.Key_F):
                # Ctrl+H or Ctrl+F (Find & Replace)
                self._show_find_replace()
                event.accept()
                return

        # F2 (Edit cell)
        if key == Qt.Key_F2:
            current = self.currentIndex()
            if current.isValid():
                self.edit(current)
            event.accept()
            return

        # Escape (Cancel editing)
        if key == Qt.Key_Escape:
            if self.state() == QtWidgets.QAbstractItemView.EditingState:
                self.closeEditor(self.indexWidget(self.currentIndex()), QtWidgets.QAbstractItemDelegate.RevertModelCache)
            event.accept()
            return

        # Delete/Backspace (Clear cell contents)
        if key in (Qt.Key_Delete, Qt.Key_Backspace):
            # Only delete if not currently editing a cell
            if self.state() != QtWidgets.QAbstractItemView.EditingState:
                self._delete_selection()
                event.accept()
                return

        super().keyPressEvent(event)

    def _toggle_formatting(self, prop):
        """Toggle a formatting property on selected cells."""
        model = self.model()
        if not model or not hasattr(model, 'apply_formatting_to_selection'):
            return

        selection = self.selectionModel().selectedIndexes()
        if not selection:
            return

        # Get current value from first selected cell
        first_idx = selection[0]
        cell_meta = model.get_cell_meta(first_idx.row(), first_idx.column())
        current_value = cell_meta.get(prop, False)

        # Toggle the value
        new_value = not current_value

        # Apply to all selected cells
        cells = [(idx.row(), idx.column()) for idx in selection]
        model.apply_formatting_to_selection(cells, prop, new_value)

        logger.info(f"Toggled {prop} to {new_value} on {len(cells)} cells")

    def _show_find_replace(self):
        """Show Find & Replace dialog via parent widget."""
        parent = self.parent()
        while parent:
            if hasattr(parent, 'show_find_replace'):
                parent.show_find_replace()
                return
            parent = parent.parent()

    def _undo(self):
        """Undo the last change."""
        model = self.model()
        if model and hasattr(model, 'undo'):
            model.undo()

    def _redo(self):
        """Redo the last undone change."""
        model = self.model()
        if model and hasattr(model, 'redo'):
            model.redo()

    def _copy_selection(self):
        """Copy selected cells to clipboard."""
        selection = self.selectionModel().selectedIndexes() if self.selectionModel() else []
        if not selection:
            logger.debug("No selection to copy")
            return

        model = self.model()
        if not model:
            logger.debug("No model for copy")
            return

        # Sort by row then column
        selection = sorted(selection, key=lambda idx: (idx.row(), idx.column()))

        # Find bounding rectangle
        min_row = min(idx.row() for idx in selection)
        max_row = max(idx.row() for idx in selection)
        min_col = min(idx.column() for idx in selection)
        max_col = max(idx.column() for idx in selection)

        # Build a set of selected (row, col) for efficient lookup
        selected_cells = {(idx.row(), idx.column()) for idx in selection}

        # Build clipboard data structure: dict of relative (row, col) -> cell data
        # Each cell entry contains: value, format, meta (decoration)
        clipboard_cells = {}
        clipboard_formats = {}
        clipboard_metas = {}
        clipboard_text_rows = []

        for row in range(min_row, max_row + 1):
            row_values = []
            for col in range(min_col, max_col + 1):
                # Check if this cell is in selection
                if (row, col) in selected_cells:
                    index = model.index(row, col)
                    value = model.data(index, Qt.EditRole)
                    if value is None:
                        value = ""
                    rel_pos = (row - min_row, col - min_col)
                    clipboard_cells[rel_pos] = value

                    # Copy data format (Currency, Percentage, etc.)
                    cell_format = model._formats.get((row, col))
                    if cell_format:
                        clipboard_formats[rel_pos] = cell_format

                    # Copy cell meta (bold, italic, colors, etc.)
                    cell_meta = model.get_cell_meta(row, col)
                    if cell_meta:
                        clipboard_metas[rel_pos] = cell_meta.copy()

                    display_value = model.data(index, Qt.DisplayRole)
                    row_values.append(str(display_value) if display_value else "")
                else:
                    row_values.append("")
            clipboard_text_rows.append("\t".join(row_values))

        # Store in internal clipboard
        self._clipboard_data = {
            'cells': clipboard_cells,
            'formats': clipboard_formats,
            'metas': clipboard_metas,
            'rows': max_row - min_row + 1,
            'cols': max_col - min_col + 1,
            'source_row': min_row,
            'source_col': min_col
        }
        self._clipboard_is_cut = False

        # Also copy to system clipboard as tab-separated text
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText("\n".join(clipboard_text_rows))

        logger.info(f"Copied {len(clipboard_cells)} cells from ({min_row},{min_col}) to ({max_row},{max_col})")

    def _cut_selection(self):
        """Cut selected cells to clipboard."""
        selection = self.selectionModel().selectedIndexes() if self.selectionModel() else []
        if not selection:
            return

        # First copy the data
        self._copy_selection()

        # Mark as cut operation
        self._clipboard_is_cut = True

        # Store the original selection for clearing after paste
        self._cut_selection_indexes = list(selection)

        logger.info(f"Cut {len(selection)} cells")

    def _paste_selection(self):
        """Paste clipboard data to current cell or selection.

        Behavior:
        - Uses the top-left cell of selection as the pivot for pasting
        - If selection is larger than source, repeats the pattern (like Google Sheets)
        - If a single cell is selected and clipboard has multiple cells, expands
          the paste area to include all clipboard cells (pasting down/right from
          the selected cell)
        - Formulas are adjusted based on each target cell's position
        """
        model = self.model()
        if not model:
            logger.debug("Paste: No model")
            return

        # Get selected cells - use top-left as pivot
        selection = self.selectionModel().selectedIndexes() if self.selectionModel() else []
        if not selection:
            current = self.currentIndex()
            if not current.isValid():
                logger.debug("Paste: No valid selection or current index")
                return
            selection = [current]

        # Find the bounding box of the selection
        sel_min_row = min(idx.row() for idx in selection)
        sel_max_row = max(idx.row() for idx in selection)
        sel_min_col = min(idx.column() for idx in selection)
        sel_max_col = max(idx.column() for idx in selection)
        sel_rows = sel_max_row - sel_min_row + 1
        sel_cols = sel_max_col - sel_min_col + 1

        # Check if we need to expand paste area for single-cell destination
        # When pasting multi-cell data to a single cell, expand to fit all clipboard data
        single_cell_destination = (sel_rows == 1 and sel_cols == 1)

        logger.debug(f"Paste: selection bounds=({sel_min_row},{sel_min_col}) to ({sel_max_row},{sel_max_col})")

        # Collect all changes for a single undo command
        changes = []

        # Try internal clipboard first (multi-cell)
        if self._clipboard_data and 'cells' in self._clipboard_data:
            cells = self._clipboard_data['cells']
            formats = self._clipboard_data.get('formats', {})
            metas = self._clipboard_data.get('metas', {})
            source_row = self._clipboard_data.get('source_row', 0)
            source_col = self._clipboard_data.get('source_col', 0)
            clip_rows = self._clipboard_data.get('rows', 1)
            clip_cols = self._clipboard_data.get('cols', 1)

            logger.debug(f"Paste: clipboard has {len(cells)} cells, size {clip_rows}x{clip_cols}")

            # When pasting multi-cell data to a single cell, expand paste area
            # to include all clipboard cells starting from the destination
            if single_cell_destination and (clip_rows > 1 or clip_cols > 1):
                # Expand the paste area to match clipboard dimensions
                paste_rows = clip_rows
                paste_cols = clip_cols
                logger.debug(f"Paste: expanding single-cell destination to {paste_rows}x{paste_cols}")
            else:
                # Use selected area dimensions
                paste_rows = sel_rows
                paste_cols = sel_cols

            # Build a list of source values in order for repeating
            source_values = []
            for r in range(clip_rows):
                for c in range(clip_cols):
                    value = cells.get((r, c), "")
                    cell_format = formats.get((r, c))
                    cell_meta = metas.get((r, c))
                    source_values.append({
                        'value': value,
                        'format': cell_format,
                        'meta': cell_meta,
                        'rel_row': r,
                        'rel_col': c
                    })

            # Paste to target cells
            source_idx = 0
            for rel_row in range(paste_rows):
                for rel_col in range(paste_cols):
                    target_row = sel_min_row + rel_row
                    target_col = sel_min_col + rel_col

                    # For non-expanded paste, check if cell is in original selection
                    if not single_cell_destination or (clip_rows == 1 and clip_cols == 1):
                        if not any(idx.row() == target_row and idx.column() == target_col for idx in selection):
                            continue

                    # Check bounds
                    if target_row >= model.rowCount() or target_col >= model.columnCount():
                        continue

                    # Get the source value (cycling through the pattern)
                    src = source_values[source_idx % len(source_values)]
                    value = src['value']

                    # Calculate offset for formula adjustment
                    row_offset = target_row - source_row - src['rel_row']
                    col_offset = target_col - source_col - src['rel_col']

                    # If it's a formula, adjust references
                    new_formula = None
                    new_value = None
                    if isinstance(value, str) and value.startswith('='):
                        new_formula = self._adjust_formula_for_paste(value, row_offset, col_offset)
                    else:
                        new_value = value

                    # Get old values
                    old_value = model._data.get((target_row, target_col), None)
                    old_formula = model._formulas.get((target_row, target_col), None)
                    old_format = model._formats.get((target_row, target_col), None)
                    old_meta = model._cell_meta.get((target_row, target_col), None)
                    if old_meta:
                        old_meta = old_meta.copy()

                    changes.append({
                        'row': target_row,
                        'col': target_col,
                        'old_value': old_value,
                        'new_value': new_value,
                        'old_formula': old_formula,
                        'new_formula': new_formula,
                        'old_format': old_format,
                        'new_format': src.get('format'),
                        'old_meta': old_meta,
                        'new_meta': src.get('meta')
                    })

                    source_idx += 1

            # If it was a cut operation, also add deletions for source cells
            if self._clipboard_is_cut and hasattr(self, '_cut_selection_indexes'):
                for source_index in self._cut_selection_indexes:
                    src_row, src_col = source_index.row(), source_index.column()
                    old_value = model._data.get((src_row, src_col), None)
                    old_formula = model._formulas.get((src_row, src_col), None)
                    old_format = model._formats.get((src_row, src_col), None)
                    old_meta = model._cell_meta.get((src_row, src_col), None)
                    if old_meta:
                        old_meta = old_meta.copy()
                    changes.append({
                        'row': src_row,
                        'col': src_col,
                        'old_value': old_value,
                        'new_value': None,
                        'old_formula': old_formula,
                        'new_formula': None,
                        'old_format': old_format,
                        'new_format': None,
                        'old_meta': old_meta,
                        'new_meta': None
                    })
                self._clipboard_is_cut = False
                self._cut_selection_indexes = []

        else:
            # Try system clipboard (tab-separated text)
            clipboard = QtWidgets.QApplication.clipboard()
            text = clipboard.text()
            if text:
                # Parse tab-separated values
                rows = text.split('\n')
                # Remove trailing empty row if present
                if rows and rows[-1] == '':
                    rows = rows[:-1]

                # Calculate clipboard dimensions
                clip_rows = len(rows)
                clip_cols = max(len(row.split('\t')) for row in rows) if rows else 1

                # Build source values list with position info
                source_values = []
                for rel_row, row_text in enumerate(rows):
                    cols = row_text.split('\t')
                    for rel_col, cell_value in enumerate(cols):
                        source_values.append({
                            'value': cell_value,
                            'rel_row': rel_row,
                            'rel_col': rel_col
                        })

                if not source_values:
                    return

                # When pasting multi-cell data to a single cell, expand paste area
                if single_cell_destination and (clip_rows > 1 or clip_cols > 1):
                    paste_rows = clip_rows
                    paste_cols = clip_cols
                    logger.debug(f"Paste (system): expanding single-cell destination to {paste_rows}x{paste_cols}")
                else:
                    paste_rows = sel_rows
                    paste_cols = sel_cols

                # Paste to target cells
                source_idx = 0
                for rel_row in range(paste_rows):
                    for rel_col in range(paste_cols):
                        target_row = sel_min_row + rel_row
                        target_col = sel_min_col + rel_col

                        # For non-expanded paste, check if cell is in original selection
                        if not single_cell_destination or (clip_rows == 1 and clip_cols == 1):
                            if not any(idx.row() == target_row and idx.column() == target_col for idx in selection):
                                continue

                        # Check bounds
                        if target_row >= model.rowCount() or target_col >= model.columnCount():
                            continue

                        # Get the source value (cycling through the pattern)
                        src = source_values[source_idx % len(source_values)]
                        cell_value = src['value']

                        # Get old values
                        old_value = model._data.get((target_row, target_col), None)
                        old_formula = model._formulas.get((target_row, target_col), None)

                        # Determine if new value is formula or value
                        new_formula = None
                        new_value = None
                        if cell_value.startswith('='):
                            new_formula = cell_value
                        else:
                            new_value = cell_value

                        changes.append({
                            'row': target_row,
                            'col': target_col,
                            'old_value': old_value,
                            'new_value': new_value,
                            'old_formula': old_formula,
                            'new_formula': new_formula
                        })

                        source_idx += 1

        # Execute paste via command
        if changes:
            command = SpreadsheetPasteCommand(changes, model)
            model._in_undo_redo = True
            try:
                command.redo()
            finally:
                model._in_undo_redo = False

            # Add to undo stack
            model.undo_stack.append(command)
            model.redo_stack.clear()

            # Clear dependent cache
            model._clear_dependent_cache()

            logger.info(f"Pasted {len(changes)} cells")

    def _paste_values_only(self):
        """Paste only values and formulas from clipboard, without formats or cell meta.

        Similar to _paste_selection but ignores formats and cell meta (decorations).
        """
        model = self.model()
        if not model:
            logger.debug("Paste Values: No model")
            return

        # Get selected cells - use top-left as pivot
        selection = self.selectionModel().selectedIndexes() if self.selectionModel() else []
        if not selection:
            current = self.currentIndex()
            if not current.isValid():
                logger.debug("Paste Values: No valid selection or current index")
                return
            selection = [current]

        # Find the bounding box of the selection
        sel_min_row = min(idx.row() for idx in selection)
        sel_max_row = max(idx.row() for idx in selection)
        sel_min_col = min(idx.column() for idx in selection)
        sel_max_col = max(idx.column() for idx in selection)
        sel_rows = sel_max_row - sel_min_row + 1
        sel_cols = sel_max_col - sel_min_col + 1

        single_cell_destination = (sel_rows == 1 and sel_cols == 1)

        changes = []

        # Try internal clipboard first
        if self._clipboard_data and 'cells' in self._clipboard_data:
            cells = self._clipboard_data['cells']
            source_row = self._clipboard_data.get('source_row', 0)
            source_col = self._clipboard_data.get('source_col', 0)
            clip_rows = self._clipboard_data.get('rows', 1)
            clip_cols = self._clipboard_data.get('cols', 1)

            if single_cell_destination and (clip_rows > 1 or clip_cols > 1):
                paste_rows = clip_rows
                paste_cols = clip_cols
            else:
                paste_rows = sel_rows
                paste_cols = sel_cols

            source_values = []
            for r in range(clip_rows):
                for c in range(clip_cols):
                    value = cells.get((r, c), "")
                    source_values.append({
                        'value': value,
                        'rel_row': r,
                        'rel_col': c
                    })

            source_idx = 0
            for rel_row in range(paste_rows):
                for rel_col in range(paste_cols):
                    target_row = sel_min_row + rel_row
                    target_col = sel_min_col + rel_col

                    if not single_cell_destination or (clip_rows == 1 and clip_cols == 1):
                        if not any(idx.row() == target_row and idx.column() == target_col for idx in selection):
                            continue

                    if target_row >= model.rowCount() or target_col >= model.columnCount():
                        continue

                    src = source_values[source_idx % len(source_values)]
                    value = src['value']

                    row_offset = target_row - source_row - src['rel_row']
                    col_offset = target_col - source_col - src['rel_col']

                    new_formula = None
                    new_value = None
                    if isinstance(value, str) and value.startswith('='):
                        new_formula = self._adjust_formula_for_paste(value, row_offset, col_offset)
                    else:
                        new_value = value

                    old_value = model._data.get((target_row, target_col), None)
                    old_formula = model._formulas.get((target_row, target_col), None)

                    # Only paste values, preserve existing formats and meta
                    changes.append({
                        'row': target_row,
                        'col': target_col,
                        'old_value': old_value,
                        'new_value': new_value,
                        'old_formula': old_formula,
                        'new_formula': new_formula,
                        # Keep existing format and meta (no change)
                        'old_format': model._formats.get((target_row, target_col)),
                        'new_format': model._formats.get((target_row, target_col)),
                        'old_meta': model._cell_meta.get((target_row, target_col)),
                        'new_meta': model._cell_meta.get((target_row, target_col))
                    })

                    source_idx += 1

        if changes:
            command = SpreadsheetPasteCommand(changes, model)
            model._in_undo_redo = True
            try:
                command.redo()
            finally:
                model._in_undo_redo = False

            model.undo_stack.append(command)
            model.redo_stack.clear()
            model._clear_dependent_cache()

            logger.info(f"Pasted values only for {len(changes)} cells")

    def _paste_format_only(self):
        """Paste only cell format (decorations) from clipboard, without values.

        Pastes cell meta (bg color, text color, font options like bold, italic)
        and data formats (Currency, Percentage, etc.) to selected cells.
        """
        model = self.model()
        if not model:
            logger.debug("Paste Format: No model")
            return

        # Check if we have format data in clipboard
        if not self._clipboard_data or ('formats' not in self._clipboard_data and 'metas' not in self._clipboard_data):
            logger.debug("Paste Format: No format data in clipboard")
            return

        # Get selected cells - use top-left as pivot
        selection = self.selectionModel().selectedIndexes() if self.selectionModel() else []
        if not selection:
            current = self.currentIndex()
            if not current.isValid():
                logger.debug("Paste Format: No valid selection or current index")
                return
            selection = [current]

        # Find the bounding box of the selection
        sel_min_row = min(idx.row() for idx in selection)
        sel_max_row = max(idx.row() for idx in selection)
        sel_min_col = min(idx.column() for idx in selection)
        sel_max_col = max(idx.column() for idx in selection)
        sel_rows = sel_max_row - sel_min_row + 1
        sel_cols = sel_max_col - sel_min_col + 1

        single_cell_destination = (sel_rows == 1 and sel_cols == 1)

        formats = self._clipboard_data.get('formats', {})
        metas = self._clipboard_data.get('metas', {})
        clip_rows = self._clipboard_data.get('rows', 1)
        clip_cols = self._clipboard_data.get('cols', 1)

        if single_cell_destination and (clip_rows > 1 or clip_cols > 1):
            paste_rows = clip_rows
            paste_cols = clip_cols
        else:
            paste_rows = sel_rows
            paste_cols = sel_cols

        # Build source format/meta list for cycling
        source_formats = []
        for r in range(clip_rows):
            for c in range(clip_cols):
                cell_format = formats.get((r, c))
                cell_meta = metas.get((r, c))
                source_formats.append({
                    'format': cell_format,
                    'meta': cell_meta
                })

        changes = []
        source_idx = 0
        for rel_row in range(paste_rows):
            for rel_col in range(paste_cols):
                target_row = sel_min_row + rel_row
                target_col = sel_min_col + rel_col

                if not single_cell_destination or (clip_rows == 1 and clip_cols == 1):
                    if not any(idx.row() == target_row and idx.column() == target_col for idx in selection):
                        continue

                if target_row >= model.rowCount() or target_col >= model.columnCount():
                    continue

                src = source_formats[source_idx % len(source_formats)]

                # Keep existing values/formulas, only change format and meta
                old_format = model._formats.get((target_row, target_col))
                old_meta = model._cell_meta.get((target_row, target_col))
                if old_meta:
                    old_meta = old_meta.copy()

                changes.append({
                    'row': target_row,
                    'col': target_col,
                    # Keep values unchanged
                    'old_value': model._data.get((target_row, target_col)),
                    'new_value': model._data.get((target_row, target_col)),
                    'old_formula': model._formulas.get((target_row, target_col)),
                    'new_formula': model._formulas.get((target_row, target_col)),
                    # Update format and meta
                    'old_format': old_format,
                    'new_format': src.get('format'),
                    'old_meta': old_meta,
                    'new_meta': src.get('meta')
                })

                source_idx += 1

        if changes:
            command = SpreadsheetPasteCommand(changes, model)
            model._in_undo_redo = True
            try:
                command.redo()
            finally:
                model._in_undo_redo = False

            model.undo_stack.append(command)
            model.redo_stack.clear()
            model._clear_dependent_cache()

            logger.info(f"Pasted format only for {len(changes)} cells")

    def _delete_selection(self):
        """Delete the content of selected cells."""
        selection = self.selectionModel().selectedIndexes() if self.selectionModel() else []
        if not selection:
            return

        model = self.model()
        if not model:
            return

        # Collect deletions for a single undo command
        deletions = []
        for index in selection:
            row, col = index.row(), index.column()
            old_value = model._data.get((row, col), None)
            old_formula = model._formulas.get((row, col), None)

            # Only include cells that have content
            if old_value is not None or old_formula is not None:
                deletions.append({
                    'row': row,
                    'col': col,
                    'old_value': old_value,
                    'old_formula': old_formula
                })

        if not deletions:
            return

        # Execute delete via command
        command = SpreadsheetDeleteCommand(deletions, model)
        model._in_undo_redo = True
        try:
            command.redo()
        finally:
            model._in_undo_redo = False

        # Add to undo stack
        model.undo_stack.append(command)
        model.redo_stack.clear()

        # Clear dependent cache
        model._clear_dependent_cache()

        logger.info(f"Deleted {len(deletions)} cells")

    def _adjust_formula_for_paste(self, formula, row_offset, col_offset):
        """Adjust formula references when pasting to a different cell.

        Args:
            formula: Original formula string
            row_offset: Number of rows to offset (positive = down, negative = up)
            col_offset: Number of columns to offset (positive = right, negative = left)

        Returns:
            Adjusted formula string
        """
        # Pattern to match cell references like A1, B2, $A$1, etc.
        pattern = r'(\$?)([A-Z]+)(\$?)(\d+)'

        def replace_ref(match):
            col_abs = match.group(1)  # $ before column
            col_letter = match.group(2)
            row_abs = match.group(3)  # $ before row
            row_num = int(match.group(4))

            # Adjust row if not absolute
            if not row_abs:
                new_row_num = row_num + row_offset
                if new_row_num < 1:
                    new_row_num = 1
            else:
                new_row_num = row_num

            # Adjust column if not absolute
            if not col_abs:
                # Convert column letter to index, adjust, and convert back
                col_idx = 0
                for char in col_letter:
                    col_idx = col_idx * 26 + (ord(char) - 65 + 1)
                col_idx -= 1  # Make 0-based

                new_col_idx = col_idx + col_offset
                if new_col_idx < 0:
                    new_col_idx = 0

                # Convert back to letter
                new_col_letter = ""
                temp_idx = new_col_idx + 1
                while temp_idx > 0:
                    temp_idx -= 1
                    new_col_letter = chr(65 + (temp_idx % 26)) + new_col_letter
                    temp_idx //= 26
            else:
                new_col_letter = col_letter

            return f"{col_abs}{new_col_letter}{row_abs}{new_row_num}"

        return re.sub(pattern, replace_ref, formula)


class SpreadsheetEditCommand:
    """Command pattern for undo/redo of single cell edits in spreadsheet."""

    def __init__(self, model, row, col, old_value, new_value, old_formula, new_formula):
        """Initialize the edit command.

        Args:
            model: SpreadsheetModel instance
            row: Row index
            col: Column index
            old_value: Previous value in _data
            new_value: New value in _data
            old_formula: Previous formula in _formulas (or None)
            new_formula: New formula in _formulas (or None)
        """
        self.model = model
        self.row = row
        self.col = col
        self.old_value = old_value
        self.new_value = new_value
        self.old_formula = old_formula
        self.new_formula = new_formula

    def undo(self):
        """Undo the edit - restore old value/formula."""
        self._apply_cell_data(self.old_value, self.old_formula)

    def redo(self):
        """Redo the edit - apply new value/formula."""
        self._apply_cell_data(self.new_value, self.new_formula)

    def _apply_cell_data(self, value, formula):
        """Apply value or formula to the cell."""
        # Clear cache
        self.model._evaluated_cache.pop((self.row, self.col), None)

        if formula:
            # It's a formula
            self.model._formulas[(self.row, self.col)] = formula
            self.model._data.pop((self.row, self.col), None)
        else:
            # It's a value
            if value:
                self.model._data[(self.row, self.col)] = value
            else:
                self.model._data.pop((self.row, self.col), None)
            self.model._formulas.pop((self.row, self.col), None)

        # Clear dependent cache and emit change
        self.model._clear_dependent_cache()
        index = self.model.index(self.row, self.col)
        self.model.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])


class SpreadsheetPasteCommand:
    """Command pattern for undo/redo of paste operations in spreadsheet."""

    def __init__(self, changes, model):
        """Initialize paste command.

        Args:
            changes: List of dicts with keys: row, col, old_value, new_value,
                    old_formula, new_formula, old_format, new_format,
                    old_meta, new_meta
            model: SpreadsheetModel instance
        """
        self.changes = changes
        self.model = model

    def undo(self):
        """Undo all paste changes."""
        for change in self.changes:
            self._apply_cell_data(
                change['row'], change['col'],
                change['old_value'], change['old_formula'],
                change.get('old_format'), change.get('old_meta')
            )

    def redo(self):
        """Redo all paste changes."""
        for change in self.changes:
            self._apply_cell_data(
                change['row'], change['col'],
                change['new_value'], change['new_formula'],
                change.get('new_format'), change.get('new_meta')
            )

    def _apply_cell_data(self, row, col, value, formula, cell_format=None, cell_meta=None):
        """Apply value, formula, format, and meta to a cell."""
        # Clear cache
        self.model._evaluated_cache.pop((row, col), None)

        if formula:
            # It's a formula
            self.model._formulas[(row, col)] = formula
            self.model._data.pop((row, col), None)
        else:
            # It's a value
            if value:
                self.model._data[(row, col)] = value
            else:
                self.model._data.pop((row, col), None)
            self.model._formulas.pop((row, col), None)

        # Apply data format (Currency, Percentage, etc.)
        if cell_format:
            self.model._formats[(row, col)] = cell_format
        else:
            self.model._formats.pop((row, col), None)

        # Apply cell meta (bold, italic, colors, etc.)
        if cell_meta:
            self.model._cell_meta[(row, col)] = cell_meta.copy()
        else:
            self.model._cell_meta.pop((row, col), None)

        # Emit change for this cell
        index = self.model.index(row, col)
        self.model.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])


class SpreadsheetDeleteCommand:
    """Command pattern for undo/redo of delete operations in spreadsheet."""

    def __init__(self, deletions, model):
        """Initialize delete command.

        Args:
            deletions: List of dicts with keys: row, col, old_value, old_formula
            model: SpreadsheetModel instance
        """
        self.deletions = deletions
        self.model = model

    def undo(self):
        """Undo deletions - restore old values."""
        for deletion in self.deletions:
            self._apply_cell_data(
                deletion['row'], deletion['col'],
                deletion['old_value'], deletion['old_formula']
            )

    def redo(self):
        """Redo deletions - clear cells again."""
        for deletion in self.deletions:
            self._apply_cell_data(
                deletion['row'], deletion['col'],
                None, None
            )

    def _apply_cell_data(self, row, col, value, formula):
        """Apply value or formula to a cell."""
        self.model._evaluated_cache.pop((row, col), None)

        if formula:
            self.model._formulas[(row, col)] = formula
            self.model._data.pop((row, col), None)
        else:
            if value:
                self.model._data[(row, col)] = value
            else:
                self.model._data.pop((row, col), None)
            self.model._formulas.pop((row, col), None)

        index = self.model.index(row, col)
        self.model.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])


class SpreadsheetModel(QtCore.QAbstractTableModel):
    """Model for spreadsheet data with formula support, undo/redo, and cell formatting."""

    # Signal emitted when status messages should be shown
    statusMessageChanged = QtCore.Signal(str, bool)  # message, is_error

    # Signal emitted when row count changes (for filtering)
    rowCountChanged = QtCore.Signal(int, int)  # visible_rows, total_rows

    # Signal emitted when cell metadata changes (for toolbar updates)
    cellMetaChanged = QtCore.Signal(dict)  # cell_meta dict

    # Special marker for text values that should be detected in numeric columns
    TEXT_VALUE_MARKER = "__TEXT_VALUE__"

    # Excel-compatible format codes
    FORMAT_GENERAL = "General"
    FORMAT_NUMBER = "#,##0.00"
    FORMAT_NUMBER_NO_DECIMAL = "#,##0"
    FORMAT_CURRENCY = "CURRENCY"  # Dynamic currency using project settings
    FORMAT_PERCENTAGE = "0.00%"
    FORMAT_PERCENTAGE_NO_DECIMAL = "0%"
    FORMAT_DATE_MDY = "mm/dd/yyyy"
    FORMAT_DATE_DMY = "dd/mm/yyyy"
    FORMAT_DATE_YMD = "yyyy-mm-dd"
    FORMAT_TIME = "hh:mm:ss"
    FORMAT_DATETIME = "yyyy-mm-dd hh:mm:ss"
    FORMAT_TEXT = "@"
    FORMAT_ACCOUNTING = "ACCOUNTING"  # Dynamic accounting using project currency

    def __init__(self, rows=100, cols=26, parent=None):
        """Initialize the spreadsheet model.

        Args:
            rows: Number of rows
            cols: Number of columns
            parent: Parent widget
        """
        super().__init__(parent)
        self._rows = rows
        self._cols = cols
        self._data = {}  # Dict of (row, col) -> value
        self._formulas = {}  # Dict of (row, col) -> formula string
        self._formats = {}  # Dict of (row, col) -> Excel-compatible format string
        self._evaluated_cache = {}  # Dict of (row, col) -> evaluated result
        self.formula_evaluator = None

        # NEW: Cell metadata for formatting (bold, italic, colors, borders, etc.)
        self._cell_meta = {}  # Dict of (row, col) -> cell_meta dict

        # NEW: Sheet-level metadata
        self._column_widths = {}  # Dict of col -> width in pixels
        self._row_heights = {}  # Dict of row -> height in pixels
        self._merged_cells = []  # List of {"start_row", "start_col", "end_row", "end_col"}
        self._frozen_rows = 0  # Number of frozen rows from top
        self._frozen_cols = 0  # Number of frozen columns from left

        # Column type configuration
        self._numeric_only_columns = set()  # Columns that only allow numeric values
        self._no_conversion_columns = set()  # Columns where data should not be converted

        # Undo/redo stacks
        self.undo_stack = []
        self.redo_stack = []
        self._in_undo_redo = False  # Flag to prevent creating undo commands during undo/redo

        # Search and filter state
        self.global_search_text = ""
        self._visible_rows = list(range(rows))  # Mapping from visible row index to actual row index
        self._all_rows = list(range(rows))  # All row indices

        # Sorting state
        self.sort_column = None
        self.sort_direction = None  # 'asc' or 'desc'
        self.compound_sort_columns = []  # List of (column_index, direction) tuples

        # Currency settings (from bid/project configuration)
        self._currency_symbol = "$"  # Default currency symbol
        self._currency_position = "prepend"  # "prepend" (before value) or "append" (after value)

    def set_currency_settings(self, symbol, position):
        """Set the currency symbol and position for formatting.

        Args:
            symbol: Currency symbol (e.g., "$", "€", "£")
            position: "prepend" (before value) or "append" (after value)
        """
        self._currency_symbol = symbol or "$"
        self._currency_position = position or "prepend"
        # Clear cache to force re-formatting
        self._evaluated_cache.clear()
        # Emit dataChanged to refresh display
        self.layoutChanged.emit()

    def get_currency_settings(self):
        """Get the current currency settings.

        Returns:
            tuple: (symbol, position)
        """
        return self._currency_symbol, self._currency_position

    def rowCount(self, parent=QtCore.QModelIndex()):
        """Return the number of rows."""
        return self._rows

    def columnCount(self, parent=QtCore.QModelIndex()):
        """Return the number of columns."""
        return self._cols

    def data(self, index, role=Qt.DisplayRole):
        """Return data for the given index and role."""
        if not index.isValid():
            return None

        row, col = index.row(), index.column()

        if role == Qt.DisplayRole or role == Qt.EditRole:
            # Check if there's a formula
            if (row, col) in self._formulas:
                formula = self._formulas[(row, col)]
                if role == Qt.EditRole:
                    # When editing, show the formula
                    return formula
                else:
                    # When displaying, show the evaluated result
                    return self._get_evaluated_value(row, col, formula)
            else:
                # Regular value
                value = self._data.get((row, col), "")
                if role == Qt.EditRole:
                    # When editing, show raw value
                    return value
                else:
                    # When displaying, apply format if set
                    if value != "" and value is not None:
                        cell_format = self._formats.get((row, col))
                        if cell_format and cell_format != self.FORMAT_GENERAL:
                            return self._apply_format(value, cell_format)
                    return value

        elif role == Qt.TextAlignmentRole:
            # Check if the cell contains a number
            value = self._data.get((row, col), "")
            if (row, col) in self._formulas:
                # Formulas are right-aligned
                return Qt.AlignRight | Qt.AlignVCenter
            try:
                float(str(value).replace(',', '').replace('$', ''))
                return Qt.AlignRight | Qt.AlignVCenter
            except (ValueError, AttributeError):
                return Qt.AlignLeft | Qt.AlignVCenter

        return None

    def set_numeric_only_columns(self, columns):
        """Set which columns should only allow numeric values.

        Args:
            columns: List or set of column indices that only allow numbers
        """
        self._numeric_only_columns = set(columns)

    def set_no_conversion_columns(self, columns):
        """Set which columns should not have data type conversion.

        Args:
            columns: List or set of column indices where data should stay as-is
        """
        self._no_conversion_columns = set(columns)

    def _get_evaluated_value(self, row, col, formula):
        """Evaluate a formula and return the result."""
        if not self.formula_evaluator:
            return formula

        try:
            # Check cache first
            if (row, col) in self._evaluated_cache:
                return self._evaluated_cache[(row, col)]

            # Evaluate the formula
            result = self.formula_evaluator.evaluate(formula, row, col)
            result_str = str(result) if result is not None else ""

            # Check if result contains text value marker
            if self.TEXT_VALUE_MARKER in result_str:
                if col in self._numeric_only_columns:
                    # Numeric column - show error for text values
                    formatted = "#TYPE! (text not allowed in this column)"
                    self._evaluated_cache[(row, col)] = formatted
                    return formatted
                else:
                    # Non-numeric column - extract and return the actual text value
                    # Format is "__TEXT_VALUE__:actual_value" or quoted version
                    import re
                    # Match pattern like "__TEXT_VALUE__:value" or "\"__TEXT_VALUE__:value\""
                    match = re.search(r'__TEXT_VALUE__:(.+?)(?:"|$)', result_str)
                    if match:
                        formatted = match.group(1)
                    else:
                        # Fallback: just remove the marker prefix
                        formatted = result_str.replace(f'"{self.TEXT_VALUE_MARKER}:', '').rstrip('"')
                    self._evaluated_cache[(row, col)] = formatted
                    return formatted

            # For numeric-only columns, validate that result is actually numeric
            if col in self._numeric_only_columns:
                try:
                    if result_str and not result_str.startswith('#'):
                        float(str(result).replace(',', '').replace('$', ''))
                except (ValueError, TypeError):
                    formatted = "#TYPE! (text not allowed in this column)"
                    self._evaluated_cache[(row, col)] = formatted
                    return formatted

            # For no-conversion columns, return as-is without formatting
            if col in self._no_conversion_columns:
                formatted = str(result) if result is not None else ""
                self._evaluated_cache[(row, col)] = formatted
                return formatted

            # Apply cell format if set, otherwise use auto-detection
            cell_format = self._formats.get((row, col))
            formatted = self._apply_format(result, cell_format)

            # Cache the result
            self._evaluated_cache[(row, col)] = formatted
            return formatted

        except Exception:
            return "#ERROR"

    def _apply_format(self, value, cell_format=None):
        """Apply Excel-compatible format to a value.

        Args:
            value: The value to format
            cell_format: Excel-compatible format string (or None for auto-detection)

        Returns:
            Formatted string
        """
        if value is None or value == "":
            return ""

        # If no format specified, auto-detect based on value type
        if not cell_format or cell_format == self.FORMAT_GENERAL:
            if isinstance(value, (int, float)):
                # Default number format with commas and 2 decimals
                return f"{value:,.2f}"
            return str(value)

        # Apply specific formats
        try:
            if cell_format == self.FORMAT_TEXT:
                return str(value)

            # Convert to number if needed
            if isinstance(value, str):
                try:
                    value = float(value.replace(',', '').replace('$', '').replace('%', ''))
                except ValueError:
                    return str(value)

            if cell_format == self.FORMAT_NUMBER:
                return f"{value:,.2f}"
            elif cell_format == self.FORMAT_NUMBER_NO_DECIMAL:
                return f"{value:,.0f}"
            elif cell_format == self.FORMAT_CURRENCY:
                # Use dynamic currency settings from project/bid configuration
                formatted_value = f"{value:,.2f}"
                if self._currency_position == "append":
                    return f"{formatted_value} {self._currency_symbol}"
                else:
                    return f"{self._currency_symbol}{formatted_value}"
            elif cell_format == self.FORMAT_PERCENTAGE:
                return f"{value * 100:.2f}%"
            elif cell_format == self.FORMAT_PERCENTAGE_NO_DECIMAL:
                return f"{value * 100:.0f}%"
            elif cell_format == self.FORMAT_ACCOUNTING:
                # Use dynamic currency for accounting format
                if value >= 0:
                    if self._currency_position == "append":
                        return f"{value:,.2f} {self._currency_symbol} "
                    else:
                        return f"{self._currency_symbol} {value:,.2f} "
                else:
                    if self._currency_position == "append":
                        return f"({abs(value):,.2f}) {self._currency_symbol}"
                    else:
                        return f"{self._currency_symbol} ({abs(value):,.2f})"
            elif cell_format.startswith("#") or cell_format.startswith("0"):
                # Generic number format - use default
                return f"{value:,.2f}"
            else:
                return f"{value:,.2f}"
        except (ValueError, TypeError):
            return str(value)

    def get_cell_format(self, row, col):
        """Get the format for a cell.

        Args:
            row: Row index
            col: Column index

        Returns:
            Excel-compatible format string or None
        """
        return self._formats.get((row, col))

    def set_cell_format(self, row, col, cell_format):
        """Set the format for a cell.

        Args:
            row: Row index
            col: Column index
            cell_format: Excel-compatible format string (or None to clear)
        """
        if cell_format:
            self._formats[(row, col)] = cell_format
        else:
            self._formats.pop((row, col), None)

        # Clear cache to force re-formatting
        self._evaluated_cache.pop((row, col), None)

        # Emit dataChanged to refresh display
        index = self.index(row, col)
        self.dataChanged.emit(index, index, [Qt.DisplayRole])

    def detect_format(self, value):
        """Auto-detect format based on value content.

        Args:
            value: The value to analyze

        Returns:
            Suggested Excel-compatible format string
        """
        if value is None or value == "":
            return self.FORMAT_GENERAL

        value_str = str(value).strip()

        # Check for percentage
        if value_str.endswith('%'):
            return self.FORMAT_PERCENTAGE

        # Check for currency symbols
        if value_str.startswith('$') or '$' in value_str:
            return self.FORMAT_CURRENCY_USD
        if value_str.startswith('€') or '€' in value_str:
            return self.FORMAT_CURRENCY_EUR
        if value_str.startswith('£') or '£' in value_str:
            return self.FORMAT_CURRENCY_GBP

        # Check if numeric
        try:
            cleaned = value_str.replace(',', '').replace('$', '').replace('€', '').replace('£', '')
            float(cleaned)
            return self.FORMAT_NUMBER
        except ValueError:
            pass

        return self.FORMAT_GENERAL

    def setData(self, index, value, role=Qt.EditRole):
        """Set data for the given index."""
        if not index.isValid():
            return False

        if role == Qt.EditRole:
            row, col = index.row(), index.column()

            # Get old values for undo
            old_value = self._data.get((row, col), None)
            old_formula = self._formulas.get((row, col), None)

            # Clear the cache for this cell
            self._evaluated_cache.pop((row, col), None)

            # Check if it's a formula (starts with =)
            value_str = str(value).strip() if value else ""
            new_formula = None
            new_value = None

            if value_str.startswith('='):
                # Store as formula
                new_formula = value_str
                self._formulas[(row, col)] = value_str
                self._data.pop((row, col), None)
            else:
                # Store as regular value
                new_value = value_str
                if value_str:
                    self._data[(row, col)] = value_str
                else:
                    self._data.pop((row, col), None)
                self._formulas.pop((row, col), None)

            # Create undo command (if not in undo/redo operation)
            if not self._in_undo_redo:
                # Only create command if there's an actual change
                if old_value != new_value or old_formula != new_formula:
                    command = SpreadsheetEditCommand(
                        self, row, col,
                        old_value, new_value,
                        old_formula, new_formula
                    )
                    self.undo_stack.append(command)
                    self.redo_stack.clear()  # Clear redo stack on new edit

            # Clear cache for dependent cells
            self._clear_dependent_cache()

            self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
            return True

        return False

    def _clear_dependent_cache(self):
        """Clear the evaluation cache for cells that depend on changed cells."""
        # For simplicity, clear the entire cache
        # A more sophisticated implementation would track dependencies
        self._evaluated_cache.clear()

    def flags(self, index):
        """Return item flags for the given index."""
        if not index.isValid():
            return Qt.NoItemFlags

        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        """Return header data."""
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                # Column headers: A, B, C, ..., Z, AA, AB, ...
                return self._column_name(section)
            else:
                # Row headers: 1, 2, 3, ...
                return str(section + 1)
        return None

    def _column_name(self, index):
        """Convert column index to spreadsheet column name (A, B, C, ..., AA, AB, ...)."""
        name = ""
        index += 1  # Make it 1-based
        while index > 0:
            index -= 1
            name = chr(65 + (index % 26)) + name
            index //= 26
        return name

    @staticmethod
    def letter_to_col(letter):
        """Convert column letter to index (A->0, B->1, ..., Z->25, AA->26)."""
        col = 0
        for char in letter:
            col = col * 26 + (ord(char) - 65 + 1)
        return col - 1

    def get_cell_value(self, row, col):
        """Get the raw value of a cell (not the formula)."""
        if (row, col) in self._formulas:
            # Evaluate the formula
            formula = self._formulas[(row, col)]
            return self._get_evaluated_value(row, col, formula)
        else:
            value = self._data.get((row, col), "")
            # Try to convert to number if possible
            try:
                return float(str(value).replace(',', '').replace('$', ''))
            except (ValueError, AttributeError):
                return value if value else ""

    def get_cell_formula(self, row, col):
        """Get the formula of a cell if it exists."""
        return self._formulas.get((row, col), None)

    def set_formula_evaluator(self, evaluator):
        """Set the formula evaluator."""
        self.formula_evaluator = evaluator
        # Clear cache when evaluator changes
        self._evaluated_cache.clear()

    # ------------------------------------------------------------------
    # Search and Sorting Methods
    # ------------------------------------------------------------------

    def set_global_search(self, search_text):
        """Set the global search filter text.

        Args:
            search_text: Search string to filter rows
        """
        self.global_search_text = search_text.lower().strip()
        self.apply_filters()

    def apply_filters(self):
        """Apply current search filter and re-emit data."""
        self.beginResetModel()

        # If no search text, show all rows
        if not self.global_search_text:
            self._visible_rows = list(self._all_rows)
        else:
            # Filter rows based on search text
            self._visible_rows = []
            for row_idx in self._all_rows:
                if self._row_matches_search(row_idx):
                    self._visible_rows.append(row_idx)

        # Apply sorting after filtering
        self._apply_sort()

        self.endResetModel()

        # Emit row count change signal
        self.rowCountChanged.emit(len(self._visible_rows), len(self._all_rows))

    def _row_matches_search(self, row_idx):
        """Check if a row matches the current search text.

        Args:
            row_idx: The actual row index

        Returns:
            bool: True if the row matches the search
        """
        if not self.global_search_text:
            return True

        # Check all columns in this row
        for col_idx in range(self._cols):
            # Get the cell value
            value = self._data.get((row_idx, col_idx), "")
            if not value and (row_idx, col_idx) in self._formulas:
                # Get evaluated value for formulas
                formula = self._formulas[(row_idx, col_idx)]
                value = self._get_evaluated_value(row_idx, col_idx, formula)

            # Check if search text is in the value
            if value and self.global_search_text in str(value).lower():
                return True

        return False

    def set_sort(self, column_index, direction):
        """Set single-column sorting.

        Args:
            column_index: Column index to sort by
            direction: 'asc' or 'desc'
        """
        self.sort_column = column_index
        self.sort_direction = direction
        self.compound_sort_columns = []  # Clear compound sort when single sort is applied
        self.apply_filters()

    def set_compound_sort(self, sort_columns):
        """Set multi-column (compound) sorting.

        Args:
            sort_columns: List of (column_index, direction) tuples, e.g., [(0, 'asc'), (2, 'desc')]
        """
        self.compound_sort_columns = sort_columns
        self.sort_column = None
        self.sort_direction = None
        self.apply_filters()

    def clear_sort(self):
        """Clear all sorting."""
        self.sort_column = None
        self.sort_direction = None
        self.compound_sort_columns = []
        self.apply_filters()

    def _apply_sort(self):
        """Apply current sorting to visible rows."""
        if self.compound_sort_columns:
            # Apply compound (multi-column) sort
            self._visible_rows = self._sort_rows_compound(self._visible_rows, self.compound_sort_columns)
        elif self.sort_column is not None:
            # Apply single-column sort
            self._visible_rows = self._sort_rows_single(self._visible_rows, self.sort_column, self.sort_direction)

    def _sort_rows_single(self, rows, column_index, direction):
        """Sort rows by a single column.

        Args:
            rows: List of row indices to sort
            column_index: Column index to sort by
            direction: 'asc' or 'desc'

        Returns:
            Sorted list of row indices
        """
        def get_sort_value(row_idx):
            value = self._data.get((row_idx, column_index), "")
            if not value and (row_idx, column_index) in self._formulas:
                formula = self._formulas[(row_idx, column_index)]
                value = self._get_evaluated_value(row_idx, column_index, formula)

            # Try to convert to number for numeric sorting
            try:
                return (0, float(str(value).replace(',', '').replace('$', '')))
            except (ValueError, TypeError):
                return (1, str(value).lower() if value else "")

        reverse = direction == 'desc'
        return sorted(rows, key=get_sort_value, reverse=reverse)

    def _sort_rows_compound(self, rows, sort_columns):
        """Sort rows by multiple columns.

        Args:
            rows: List of row indices to sort
            sort_columns: List of (column_index, direction) tuples

        Returns:
            Sorted list of row indices
        """
        def get_compound_key(row_idx):
            keys = []
            for col_idx, direction in sort_columns:
                value = self._data.get((row_idx, col_idx), "")
                if not value and (row_idx, col_idx) in self._formulas:
                    formula = self._formulas[(row_idx, col_idx)]
                    value = self._get_evaluated_value(row_idx, col_idx, formula)

                # Try to convert to number for numeric sorting
                try:
                    num_val = float(str(value).replace(',', '').replace('$', ''))
                    # For descending, negate the numeric value
                    if direction == 'desc':
                        num_val = -num_val
                    keys.append((0, num_val))
                except (ValueError, TypeError):
                    str_val = str(value).lower() if value else ""
                    # For string sorting with desc, we'll handle it differently
                    keys.append((1, str_val, direction))
            return keys

        # Custom comparator for compound sort
        def compare_rows(row_a, row_b):
            key_a = get_compound_key(row_a)
            key_b = get_compound_key(row_b)

            for i, (col_idx, direction) in enumerate(sort_columns):
                ka = key_a[i]
                kb = key_b[i]

                # Compare type first (numbers before strings)
                if ka[0] != kb[0]:
                    return ka[0] - kb[0]

                # Same type comparison
                if ka[0] == 0:  # Numeric (already direction-adjusted)
                    if ka[1] < kb[1]:
                        return -1
                    elif ka[1] > kb[1]:
                        return 1
                else:  # String
                    str_a, dir_a = ka[1], ka[2]
                    str_b, _ = kb[1], kb[2]
                    if str_a < str_b:
                        return -1 if dir_a == 'asc' else 1
                    elif str_a > str_b:
                        return 1 if dir_a == 'asc' else -1

            return 0

        import functools
        return sorted(rows, key=functools.cmp_to_key(compare_rows))

    def get_visible_row_count(self):
        """Get the number of currently visible (filtered) rows.

        Returns:
            int: Number of visible rows
        """
        return len(self._visible_rows)

    def get_total_row_count(self):
        """Get the total number of rows (before filtering).

        Returns:
            int: Total number of rows
        """
        return len(self._all_rows)

    def undo(self):
        """Undo the last change."""
        if not self.undo_stack:
            return False

        command = self.undo_stack.pop()
        self._in_undo_redo = True
        try:
            command.undo()
        finally:
            self._in_undo_redo = False

        self.redo_stack.append(command)

        # Clear cache after undo
        self._clear_dependent_cache()

        self.statusMessageChanged.emit("Undone", False)
        return True

    def redo(self):
        """Redo the last undone change."""
        if not self.redo_stack:
            return False

        command = self.redo_stack.pop()
        self._in_undo_redo = True
        try:
            command.redo()
        finally:
            self._in_undo_redo = False

        self.undo_stack.append(command)

        # Clear cache after redo
        self._clear_dependent_cache()

        self.statusMessageChanged.emit("Redone", False)
        return True

    def clear_undo_history(self):
        """Clear the undo/redo history."""
        self.undo_stack.clear()
        self.redo_stack.clear()

    # =========================================================================
    # Cell Metadata Methods (for formatting)
    # =========================================================================

    def get_cell_meta(self, row, col):
        """Get metadata for a cell, returning empty dict if none.

        Args:
            row: Row index
            col: Column index

        Returns:
            dict: Cell metadata with formatting properties
        """
        return self._cell_meta.get((row, col), {})

    def set_cell_meta(self, row, col, meta):
        """Set complete metadata for a cell.

        Args:
            row: Row index
            col: Column index
            meta: Dict with formatting properties, or None to clear
        """
        if meta:
            self._cell_meta[(row, col)] = meta
        else:
            self._cell_meta.pop((row, col), None)

    def set_cell_meta_property(self, row, col, prop, value):
        """Set a single property in cell metadata.

        Args:
            row: Row index
            col: Column index
            prop: Property name (e.g., 'bold', 'font_color')
            value: Property value, or None to remove
        """
        if (row, col) not in self._cell_meta:
            self._cell_meta[(row, col)] = {}
        if value is None:
            self._cell_meta[(row, col)].pop(prop, None)
            # Clean up empty metadata
            if not self._cell_meta[(row, col)]:
                del self._cell_meta[(row, col)]
        else:
            self._cell_meta[(row, col)][prop] = value

    def apply_formatting_to_selection(self, cells, prop, value):
        """Apply a formatting property to multiple cells with undo support.

        Args:
            cells: List of (row, col) tuples
            prop: Property name (e.g., 'bold', 'font_color')
            value: Value to set
        """
        old_values = {}
        for (row, col) in cells:
            old_values[(row, col)] = self.get_cell_meta(row, col).get(prop)

        command = CellFormattingCommand(self, cells, prop, old_values, value)
        self._in_undo_redo = True
        try:
            command.redo()
        finally:
            self._in_undo_redo = False

        self.undo_stack.append(command)
        self.redo_stack.clear()

    def apply_borders_to_selection(self, cells, border_config):
        """Apply border configuration to selected cells.

        Args:
            cells: List of (row, col) tuples
            border_config: Dict with 'type' and 'config' keys
        """
        border_type = border_config.get('type', 'none')
        config = border_config.get('config', {})

        # Default border style
        border_style = {"style": "thin", "color": "#000000"}

        if border_type == 'none':
            # Remove all borders from selected cells
            for (row, col) in cells:
                meta = self.get_cell_meta(row, col).copy()
                meta.pop('borders', None)
                self.set_cell_meta(row, col, meta if meta else None)
        elif border_type == 'all':
            # All borders on every cell
            for (row, col) in cells:
                meta = self.get_cell_meta(row, col).copy()
                meta['borders'] = {
                    'top': border_style.copy(),
                    'bottom': border_style.copy(),
                    'left': border_style.copy(),
                    'right': border_style.copy()
                }
                self.set_cell_meta(row, col, meta)
        elif border_type == 'outside':
            # Only outside borders of selection
            if not cells:
                return
            rows = [c[0] for c in cells]
            cols = [c[1] for c in cells]
            min_row, max_row = min(rows), max(rows)
            min_col, max_col = min(cols), max(cols)

            for (row, col) in cells:
                meta = self.get_cell_meta(row, col).copy()
                borders = meta.get('borders', {})
                if row == min_row:
                    borders['top'] = border_style.copy()
                if row == max_row:
                    borders['bottom'] = border_style.copy()
                if col == min_col:
                    borders['left'] = border_style.copy()
                if col == max_col:
                    borders['right'] = border_style.copy()
                if borders:
                    meta['borders'] = borders
                    self.set_cell_meta(row, col, meta)
        else:
            # Single side borders (top, bottom, left, right)
            for (row, col) in cells:
                meta = self.get_cell_meta(row, col).copy()
                borders = meta.get('borders', {})
                if border_type in config or border_type in ['top', 'bottom', 'left', 'right']:
                    borders[border_type] = border_style.copy()
                meta['borders'] = borders
                self.set_cell_meta(row, col, meta)

        # Emit changes
        for (row, col) in cells:
            index = self.index(row, col)
            self.dataChanged.emit(index, index, [Qt.DisplayRole])

    # =========================================================================
    # Merged Cells Methods
    # =========================================================================

    def get_merged_cell_info(self, row, col):
        """Check if cell is part of a merged region.

        Args:
            row: Row index
            col: Column index

        Returns:
            dict with merge info if cell is merged, None otherwise
            Keys: 'is_anchor', 'anchor', 'span', 'range'
        """
        for merge in self._merged_cells:
            if (merge['start_row'] <= row <= merge['end_row'] and
                    merge['start_col'] <= col <= merge['end_col']):
                return {
                    'is_anchor': row == merge['start_row'] and col == merge['start_col'],
                    'anchor': (merge['start_row'], merge['start_col']),
                    'span': (merge['end_row'] - merge['start_row'] + 1,
                             merge['end_col'] - merge['start_col'] + 1),
                    'range': merge
                }
        return None

    def merge_cells(self, merge_range):
        """Merge cells in the given range with undo support.

        Args:
            merge_range: Dict with start_row, start_col, end_row, end_col

        Returns:
            bool: True if merge was successful
        """
        # Validate no overlapping merges
        for existing in self._merged_cells:
            if self._ranges_overlap(merge_range, existing):
                return False

        command = MergeCellsCommand(self, merge_range, is_merge=True)
        self._in_undo_redo = True
        try:
            command.redo()
        finally:
            self._in_undo_redo = False

        self.undo_stack.append(command)
        self.redo_stack.clear()
        return True

    def unmerge_cells(self, merge_range):
        """Unmerge cells in the given range with undo support.

        Args:
            merge_range: Dict with start_row, start_col, end_row, end_col
        """
        previous_merged = self._merged_cells.copy()
        command = MergeCellsCommand(self, merge_range, is_merge=False, previous_merged=previous_merged)
        self._in_undo_redo = True
        try:
            command.redo()
        finally:
            self._in_undo_redo = False

        self.undo_stack.append(command)
        self.redo_stack.clear()

    def _merge_cells_internal(self, merge_range):
        """Internal merge without undo support."""
        self._merged_cells.append(merge_range)

        # Clear data from non-anchor cells (keep only top-left)
        start_row, start_col = merge_range['start_row'], merge_range['start_col']
        for row in range(merge_range['start_row'], merge_range['end_row'] + 1):
            for col in range(merge_range['start_col'], merge_range['end_col'] + 1):
                if row != start_row or col != start_col:
                    self._data.pop((row, col), None)
                    self._formulas.pop((row, col), None)

    def _unmerge_cells_internal(self, merge_range):
        """Internal unmerge without undo support."""
        self._merged_cells = [m for m in self._merged_cells
                              if not self._ranges_equal(m, merge_range)]

    def _ranges_overlap(self, range1, range2):
        """Check if two ranges overlap."""
        return not (range1['end_row'] < range2['start_row'] or
                    range1['start_row'] > range2['end_row'] or
                    range1['end_col'] < range2['start_col'] or
                    range1['start_col'] > range2['end_col'])

    def _ranges_equal(self, range1, range2):
        """Check if two ranges are equal."""
        return (range1['start_row'] == range2['start_row'] and
                range1['start_col'] == range2['start_col'] and
                range1['end_row'] == range2['end_row'] and
                range1['end_col'] == range2['end_col'])

    # =========================================================================
    # Column/Row Size Methods
    # =========================================================================

    def set_column_width(self, col, width):
        """Set width for a column.

        Args:
            col: Column index
            width: Width in pixels
        """
        self._column_widths[col] = width

    def get_column_width(self, col, default=100):
        """Get width for a column.

        Args:
            col: Column index
            default: Default width if not set

        Returns:
            int: Column width in pixels
        """
        return self._column_widths.get(col, default)

    def set_row_height(self, row, height):
        """Set height for a row.

        Args:
            row: Row index
            height: Height in pixels
        """
        self._row_heights[row] = height

    def get_row_height(self, row, default=25):
        """Get height for a row.

        Args:
            row: Row index
            default: Default height if not set

        Returns:
            int: Row height in pixels
        """
        return self._row_heights.get(row, default)

    # =========================================================================
    # Freeze Panes Methods
    # =========================================================================

    def set_frozen_panes(self, rows, cols):
        """Set frozen rows and columns.

        Args:
            rows: Number of rows to freeze from top
            cols: Number of columns to freeze from left
        """
        self._frozen_rows = rows
        self._frozen_cols = cols

    def get_frozen_panes(self):
        """Get frozen rows and columns.

        Returns:
            tuple: (frozen_rows, frozen_cols)
        """
        return self._frozen_rows, self._frozen_cols

    # =========================================================================
    # Metadata Export/Import for Persistence
    # =========================================================================

    def get_all_cell_meta(self):
        """Get all cell metadata for persistence.

        Returns:
            dict: Cell metadata keyed by "row,col" strings
        """
        return {f"{row},{col}": meta for (row, col), meta in self._cell_meta.items()}

    def get_sheet_meta(self):
        """Get sheet-level metadata for persistence.

        Returns:
            dict: Sheet metadata with column_widths, row_heights, merged_cells, freeze settings
        """
        return {
            'column_widths': {str(k): v for k, v in self._column_widths.items()},
            'row_heights': {str(k): v for k, v in self._row_heights.items()},
            'merged_cells': self._merged_cells,
            'frozen_rows': self._frozen_rows,
            'frozen_cols': self._frozen_cols
        }

    def load_cell_meta(self, cell_meta_dict):
        """Load cell metadata from persistence.

        Args:
            cell_meta_dict: Dict with "row,col" keys and meta dicts as values
        """
        self._cell_meta = {}
        for key, meta in cell_meta_dict.items():
            try:
                row, col = map(int, key.split(','))
                self._cell_meta[(row, col)] = meta
            except (ValueError, AttributeError):
                continue

    def load_sheet_meta(self, sheet_meta):
        """Load sheet-level metadata from persistence.

        Args:
            sheet_meta: Dict with column_widths, row_heights, merged_cells, freeze settings
        """
        # Column widths
        col_widths = sheet_meta.get('column_widths', {})
        self._column_widths = {int(k): v for k, v in col_widths.items()}

        # Row heights
        row_heights = sheet_meta.get('row_heights', {})
        self._row_heights = {int(k): v for k, v in row_heights.items()}

        # Merged cells
        self._merged_cells = sheet_meta.get('merged_cells', [])

        # Freeze panes
        self._frozen_rows = sheet_meta.get('frozen_rows', 0)
        self._frozen_cols = sheet_meta.get('frozen_cols', 0)


class SpreadsheetSortDialog(QtWidgets.QDialog):
    """Dialog for setting up compound (multi-column) sorting in spreadsheets."""

    def __init__(self, column_names, current_sort=None, parent=None):
        """Initialize the compound sort dialog.

        Args:
            column_names: List of column display names (A, B, C, ...)
            current_sort: Current sort configuration [(col_idx, direction), ...]
            parent: Parent widget
        """
        super().__init__(parent)
        self.column_names = column_names
        self.current_sort = current_sort or []

        self.setWindowTitle("Compound Sorting")
        self.setModal(True)
        self.setMinimumWidth(400)

        self._build_ui()
        self._load_current_sort()

    def _build_ui(self):
        """Build the dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)

        # Instructions
        instructions = QtWidgets.QLabel(
            "Add columns to sort by. Rows will be sorted by the first column, "
            "then by the second column for ties, and so on."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #808080; padding: 5px;")
        layout.addWidget(instructions)

        # Sort levels container
        self.sort_levels_widget = QtWidgets.QWidget()
        self.sort_levels_layout = QtWidgets.QVBoxLayout(self.sort_levels_widget)
        self.sort_levels_layout.setContentsMargins(0, 0, 0, 0)
        self.sort_levels_layout.setSpacing(5)
        layout.addWidget(self.sort_levels_widget)

        # Add level button
        add_level_btn = QtWidgets.QPushButton("+ Add Sort Level")
        add_level_btn.clicked.connect(self._add_sort_level)
        layout.addWidget(add_level_btn)

        layout.addStretch()

        # Button box
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Track sort level widgets
        self.sort_level_widgets = []

    def _add_sort_level(self, column_idx=0, direction='asc'):
        """Add a new sort level row.

        Args:
            column_idx: Default column index
            direction: Default direction ('asc' or 'desc')
        """
        level_widget = QtWidgets.QWidget()
        level_layout = QtWidgets.QHBoxLayout(level_widget)
        level_layout.setContentsMargins(0, 0, 0, 0)

        # Level label
        level_num = len(self.sort_level_widgets) + 1
        level_label = QtWidgets.QLabel(f"Level {level_num}:")
        level_label.setMinimumWidth(50)
        level_layout.addWidget(level_label)

        # Column dropdown
        column_combo = QtWidgets.QComboBox()
        for i, name in enumerate(self.column_names):
            column_combo.addItem(name, i)
        column_combo.setCurrentIndex(column_idx)
        level_layout.addWidget(column_combo, stretch=1)

        # Direction dropdown
        direction_combo = QtWidgets.QComboBox()
        direction_combo.addItem("Ascending (A-Z, 0-9)", 'asc')
        direction_combo.addItem("Descending (Z-A, 9-0)", 'desc')
        direction_combo.setCurrentIndex(0 if direction == 'asc' else 1)
        level_layout.addWidget(direction_combo, stretch=1)

        # Remove button
        remove_btn = QtWidgets.QPushButton("X")
        remove_btn.setMaximumWidth(30)
        remove_btn.clicked.connect(lambda: self._remove_sort_level(level_widget))
        level_layout.addWidget(remove_btn)

        self.sort_levels_layout.addWidget(level_widget)
        self.sort_level_widgets.append({
            'widget': level_widget,
            'column_combo': column_combo,
            'direction_combo': direction_combo
        })

        self._update_level_labels()

    def _remove_sort_level(self, level_widget):
        """Remove a sort level.

        Args:
            level_widget: The widget to remove
        """
        # Find and remove the level
        for i, level in enumerate(self.sort_level_widgets):
            if level['widget'] == level_widget:
                self.sort_levels_layout.removeWidget(level_widget)
                level_widget.deleteLater()
                self.sort_level_widgets.pop(i)
                break

        self._update_level_labels()

    def _update_level_labels(self):
        """Update the level labels after add/remove."""
        for i, level in enumerate(self.sort_level_widgets):
            # Find the label in the widget's layout
            layout = level['widget'].layout()
            if layout and layout.count() > 0:
                label_item = layout.itemAt(0)
                if label_item and label_item.widget():
                    label_item.widget().setText(f"Level {i + 1}:")

    def _load_current_sort(self):
        """Load the current sort configuration into the dialog."""
        for col_idx, direction in self.current_sort:
            self._add_sort_level(col_idx, direction)

        # Add at least one empty level if none exist
        if not self.sort_level_widgets:
            self._add_sort_level()

    def get_sort_configuration(self):
        """Get the configured sort specification.

        Returns:
            List of (column_index, direction) tuples
        """
        sort_config = []
        for level in self.sort_level_widgets:
            col_idx = level['column_combo'].currentData()
            direction = level['direction_combo'].currentData()
            sort_config.append((col_idx, direction))
        return sort_config


class SpreadsheetWidget(QtWidgets.QWidget):
    """Full-featured spreadsheet widget with Excel formula support and cell formatting."""

    def __init__(self, rows=10, cols=26, app_settings=None, parent=None):
        """Initialize the spreadsheet widget.

        Args:
            rows: Number of rows (default: 10)
            cols: Number of columns
            app_settings: AppSettings instance for currency formatting
            parent: Parent widget
        """
        super().__init__(parent)
        self.app_settings = app_settings
        self._find_replace_dialog = None

        # Create layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Create custom table view FIRST (before toolbar)
        self.table_view = SpreadsheetTableView()
        self.table_view.setAlternatingRowColors(False)  # Disable alternating colors
        self.table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        self.table_view.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)  # Multi-cell selection

        # Custom selection styling - blue background with white text
        self.table_view.setStyleSheet("""
            QTableView {
                selection-background-color: transparent;
                selection-color: white;
            }
            QTableView::item {
                color: white;
            }
            QTableView::item:selected {
                background-color: transparent;
                color: white;
            }
            QTableView::item:focus {
                color: white;
            }
            QTableView QLineEdit {
                color: white;
                background-color: #3d3d3d;
                selection-background-color: #4472C4;
                selection-color: white;
            }
        """)

        # Enable context menu
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._show_context_menu)

        # Install event filter on table_view and its viewport to intercept keyboard shortcuts
        self.table_view.installEventFilter(self)
        self.table_view.viewport().installEventFilter(self)

        # Create model
        self.model = SpreadsheetModel(rows, cols)
        self.table_view.setModel(self.model)

        # Set up formatted cell delegate for styled rendering
        self.formatted_delegate = FormattedCellDelegate(self.model)
        self.table_view.setItemDelegate(self.formatted_delegate)

        # Configure table view
        self.table_view.horizontalHeader().setDefaultSectionSize(100)
        self.table_view.horizontalHeader().setStretchLastSection(False)
        self.table_view.verticalHeader().setDefaultSectionSize(25)

        # Enable grid
        self.table_view.setShowGrid(True)
        self.table_view.setGridStyle(Qt.SolidLine)

        # Set up resizable headers
        self._setup_resizable_headers()

        # Create formatting toolbar (ABOVE search toolbar)
        self.formatting_toolbar = FormattingToolbar()
        layout.addWidget(self.formatting_toolbar)

        # Create search/formula toolbar (after table_view exists)
        self._create_toolbar()
        layout.addWidget(self.toolbar)

        # Add table view
        layout.addWidget(self.table_view)

        # Create formula evaluator
        self.formula_evaluator = None

        # Connect formatting toolbar signals
        self._connect_formatting_signals()

        # Update initial row count label
        self._update_row_count_label(rows, rows)

        # Setup keyboard shortcuts
        self._setup_shortcuts()

        logger.info(f"SpreadsheetWidget initialized with {rows} rows and {cols} columns")

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts for undo/redo, copy/paste, and formatting.

        Shortcuts are stored as instance variables to prevent garbage collection.
        Uses WidgetWithChildrenShortcut context to ensure shortcuts only activate
        when this widget or its children have focus (fixes issues with embedded QMainWindow).
        """
        # Store all shortcuts as instance variables to prevent garbage collection
        self._shortcuts = []

        # Undo shortcut (Ctrl+Z)
        undo_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Z"), self)
        undo_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        undo_shortcut.activated.connect(self.table_view._undo)
        self._shortcuts.append(undo_shortcut)

        # Redo shortcut (Ctrl+Y)
        redo_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Y"), self)
        redo_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        redo_shortcut.activated.connect(self.table_view._redo)
        self._shortcuts.append(redo_shortcut)

        # Copy shortcut (Ctrl+C)
        copy_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+C"), self)
        copy_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        copy_shortcut.activated.connect(self.table_view._copy_selection)
        self._shortcuts.append(copy_shortcut)

        # Cut shortcut (Ctrl+X)
        cut_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+X"), self)
        cut_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        cut_shortcut.activated.connect(self.table_view._cut_selection)
        self._shortcuts.append(cut_shortcut)

        # Paste shortcut (Ctrl+V)
        paste_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+V"), self)
        paste_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        paste_shortcut.activated.connect(self.table_view._paste_selection)
        self._shortcuts.append(paste_shortcut)

        # Bold shortcut (Ctrl+B)
        bold_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+B"), self)
        bold_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        bold_shortcut.activated.connect(lambda: self.table_view._toggle_formatting('bold'))
        self._shortcuts.append(bold_shortcut)

        # Italic shortcut (Ctrl+I)
        italic_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+I"), self)
        italic_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        italic_shortcut.activated.connect(lambda: self.table_view._toggle_formatting('italic'))
        self._shortcuts.append(italic_shortcut)

        # Underline shortcut (Ctrl+U)
        underline_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+U"), self)
        underline_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        underline_shortcut.activated.connect(lambda: self.table_view._toggle_formatting('underline'))
        self._shortcuts.append(underline_shortcut)

        logger.info("SpreadsheetWidget shortcuts set up with WidgetWithChildrenShortcut context: Ctrl+Z, Ctrl+Y, Ctrl+C, Ctrl+X, Ctrl+V, Ctrl+B, Ctrl+I, Ctrl+U")

    def eventFilter(self, obj, event):
        """Event filter to handle Enter and Delete key presses.

        Copy/paste/cut/undo/redo are handled via QShortcut in _setup_shortcuts().
        """
        # Check for key events from table_view or its viewport
        is_table_event = (obj == self.table_view or obj == self.table_view.viewport())
        if is_table_event and event.type() == QtCore.QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                # Enter pressed - move to next row
                current = self.table_view.currentIndex()
                if current.isValid():
                    next_row = current.row() + 1
                    if next_row < self.model.rowCount():
                        next_index = self.model.index(next_row, current.column())
                        self.table_view.setCurrentIndex(next_index)
                return True
            elif event.key() == Qt.Key_Delete:
                self.table_view._delete_selection()
                return True

        return super().eventFilter(obj, event)

    def _setup_resizable_headers(self):
        """Set up resizable column and row headers with persistence."""
        # Column header (horizontal) - enable interactive resizing
        h_header = self.table_view.horizontalHeader()
        h_header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        h_header.sectionResized.connect(self._on_column_resized)

        # Row header (vertical) - enable interactive resizing
        v_header = self.table_view.verticalHeader()
        v_header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        v_header.sectionResized.connect(self._on_row_resized)

    def _on_column_resized(self, col, old_size, new_size):
        """Handle column resize for persistence."""
        self.model.set_column_width(col, new_size)

    def _on_row_resized(self, row, old_size, new_size):
        """Handle row resize for persistence."""
        self.model.set_row_height(row, new_size)

    def _connect_formatting_signals(self):
        """Connect formatting toolbar signals to model operations."""
        tb = self.formatting_toolbar

        # Undo/Redo
        tb.undoRequested.connect(self.model.undo)
        tb.redoRequested.connect(self.model.redo)

        # Font styles
        tb.boldToggled.connect(lambda v: self._apply_formatting('bold', v))
        tb.italicToggled.connect(lambda v: self._apply_formatting('italic', v))
        tb.underlineToggled.connect(lambda v: self._apply_formatting('underline', v))
        tb.strikethroughToggled.connect(lambda v: self._apply_formatting('strikethrough', v))

        # Colors
        tb.fontColorChanged.connect(lambda c: self._apply_formatting('font_color', c if c else None))
        tb.bgColorChanged.connect(lambda c: self._apply_formatting('bg_color', c if c else None))

        # Alignment
        tb.alignmentChanged.connect(lambda a: self._apply_formatting('align_h', a))

        # Wrap
        tb.wrapToggled.connect(lambda v: self._apply_formatting('wrap', v))

        # Number format
        tb.formatChanged.connect(self._apply_cell_format)

    def _apply_formatting(self, prop, value):
        """Apply formatting property to selected cells."""
        selection = self.table_view.selectionModel().selectedIndexes()
        if not selection:
            return

        cells = [(idx.row(), idx.column()) for idx in selection]
        self.model.apply_formatting_to_selection(cells, prop, value)

    def _apply_borders(self, border_config):
        """Apply border configuration to selected cells."""
        selection = self.table_view.selectionModel().selectedIndexes()
        if not selection:
            return

        cells = [(idx.row(), idx.column()) for idx in selection]
        self.model.apply_borders_to_selection(cells, border_config)

    def _apply_cell_format(self, cell_format):
        """Apply number format to selected cells.

        Args:
            cell_format: Excel-compatible format string (e.g., '#,##0.00', '$#,##0.00', '0%')
        """
        selection = self.table_view.selectionModel().selectedIndexes()
        if not selection:
            return

        # Apply format to all selected cells
        for idx in selection:
            self.model.set_cell_format(idx.row(), idx.column(), cell_format)

        # Emit dataChanged to trigger save and refresh display
        if selection:
            self.model.dataChanged.emit(
                self.model.index(min(idx.row() for idx in selection), min(idx.column() for idx in selection)),
                self.model.index(max(idx.row() for idx in selection), max(idx.column() for idx in selection)),
                [QtCore.Qt.DisplayRole]
            )
            logger.info(f"Applied format '{cell_format}' to {len(selection)} cells")

    def _toggle_merge(self):
        """Toggle merge for selected cells."""
        selection = self.table_view.selectionModel().selectedIndexes()
        if not selection:
            return

        # Get bounding rectangle of selection
        rows = [idx.row() for idx in selection]
        cols = [idx.column() for idx in selection]
        merge_range = {
            'start_row': min(rows),
            'start_col': min(cols),
            'end_row': max(rows),
            'end_col': max(cols)
        }

        # Check if selection is a single cell - can't merge
        if merge_range['start_row'] == merge_range['end_row'] and merge_range['start_col'] == merge_range['end_col']:
            return

        # Check if already merged at anchor
        anchor = self.model.get_merged_cell_info(merge_range['start_row'], merge_range['start_col'])
        if anchor and anchor.get('is_anchor'):
            # Unmerge
            self.model.unmerge_cells(anchor['range'])
        else:
            # Merge
            self.model.merge_cells(merge_range)

        # Update cell spans in view
        self._update_merged_cell_spans()

    def _update_merged_cell_spans(self):
        """Update table view to reflect merged cells."""
        # Clear existing spans
        self.table_view.clearSpans()

        # Apply spans for merged cells
        for merge in self.model._merged_cells:
            row_span = merge['end_row'] - merge['start_row'] + 1
            col_span = merge['end_col'] - merge['start_col'] + 1
            self.table_view.setSpan(
                merge['start_row'], merge['start_col'],
                row_span, col_span
            )

    def show_find_replace(self):
        """Show the Find & Replace dialog."""
        if not self._find_replace_dialog:
            self._find_replace_dialog = FindReplaceDialog(self, parent=self)
        self._find_replace_dialog.show()
        self._find_replace_dialog.raise_()
        self._find_replace_dialog.find_input.setFocus()

    def apply_saved_sizes(self):
        """Apply saved column widths and row heights from model."""
        # Apply column widths
        for col, width in self.model._column_widths.items():
            self.table_view.horizontalHeader().resizeSection(col, width)

        # Apply row heights
        for row, height in self.model._row_heights.items():
            self.table_view.verticalHeader().resizeSection(row, height)

        # Apply merged cells
        self._update_merged_cell_spans()

    def _create_toolbar(self):
        """Create the toolbar with spreadsheet controls."""
        self.toolbar = QtWidgets.QWidget()
        toolbar_layout = QtWidgets.QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(5, 5, 5, 5)
        toolbar_layout.setSpacing(5)

        # Toolbar styling - use default dark theme (purple applied via CostsTab)

        # Search box
        search_label = QtWidgets.QLabel("Search:")
        toolbar_layout.addWidget(search_label)

        self.search_box = QtWidgets.QLineEdit()
        self.search_box.setPlaceholderText("Search across all cells...")
        self.search_box.setMaximumWidth(200)
        self.search_box.textChanged.connect(self._on_search_changed)
        toolbar_layout.addWidget(self.search_box)

        # Clear button
        self.clear_btn = QtWidgets.QPushButton("Clear")
        self.clear_btn.clicked.connect(self._clear_filters)
        toolbar_layout.addWidget(self.clear_btn)

        # Compound Sorting button
        self.compound_sort_btn = QtWidgets.QPushButton("Compound Sorting")
        self.compound_sort_btn.clicked.connect(self._open_compound_sort_dialog)
        toolbar_layout.addWidget(self.compound_sort_btn)

        # Separator
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.VLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        toolbar_layout.addWidget(separator)

        # Formula bar label
        formula_label = QtWidgets.QLabel("fx")
        formula_label.setStyleSheet("font-weight: bold; padding: 2px;")
        toolbar_layout.addWidget(formula_label)

        # Formula bar
        self.formula_bar = QtWidgets.QLineEdit()
        self.formula_bar.setPlaceholderText("Enter formula or value...")
        self.formula_bar.returnPressed.connect(self._on_formula_bar_enter)
        toolbar_layout.addWidget(self.formula_bar, 1)

        # Row count label
        self.row_count_label = QtWidgets.QLabel("Showing 0 of 0 rows")
        self.row_count_label.setStyleSheet("color: #808080; padding: 2px 4px;")
        toolbar_layout.addWidget(self.row_count_label)

        # Connect row count updates
        self.model.rowCountChanged.connect(self._update_row_count_label)

        # Connect selection change to update formula bar
        self.table_view.selectionModel().currentChanged.connect(self._on_selection_changed)

    def _on_selection_changed(self, current, previous):
        """Update formula bar and formatting toolbar when selection changes."""
        if not current.isValid():
            self.formula_bar.clear()
            return

        row, col = current.row(), current.column()

        # Update formula bar with cell content
        value = self.model.data(current, Qt.EditRole)
        self.formula_bar.setText(str(value) if value else "")

        # Update formatting toolbar state
        cell_meta = self.model.get_cell_meta(row, col)
        self.formatting_toolbar.update_from_cell_meta(cell_meta)

    def _on_formula_bar_enter(self):
        """Handle Enter key in formula bar."""
        # Get current selection
        current = self.table_view.currentIndex()
        if not current.isValid():
            return

        # Set the value
        value = self.formula_bar.text()
        self.model.setData(current, value, Qt.EditRole)

        # Move to next row
        next_row = current.row() + 1
        if next_row < self.model.rowCount():
            next_index = self.model.index(next_row, current.column())
            self.table_view.setCurrentIndex(next_index)

    def _on_search_changed(self, text):
        """Handle search text change."""
        self.model.set_global_search(text)

    def _clear_filters(self):
        """Clear all search and sorting filters."""
        self.search_box.clear()
        self.model.global_search_text = ""
        self.model.clear_sort()
        self._update_header_sort_indicators()

    def _open_compound_sort_dialog(self):
        """Open the compound sort dialog."""
        # Get column names (A, B, C, ...)
        column_names = [self.model._column_name(i) for i in range(self.model.columnCount())]

        # Get current sort configuration
        current_sort = self.model.compound_sort_columns.copy()
        if not current_sort and self.model.sort_column is not None:
            current_sort = [(self.model.sort_column, self.model.sort_direction or 'asc')]

        # Create and show the dialog
        dialog = SpreadsheetSortDialog(column_names, current_sort, parent=self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            sort_config = dialog.get_sort_configuration()
            if sort_config:
                self.model.set_compound_sort(sort_config)
            else:
                self.model.clear_sort()
            self._update_header_sort_indicators()

    def _update_row_count_label(self, visible, total):
        """Update the row count label.

        Args:
            visible: Number of visible rows
            total: Total number of rows
        """
        self.row_count_label.setText(f"Showing {visible} of {total} rows")

    def _update_header_sort_indicators(self):
        """Update column header sort indicators."""
        header = self.table_view.horizontalHeader()

        # Clear all indicators first
        for col in range(self.model.columnCount()):
            header.setSortIndicatorShown(False)

        # Show indicators for sorted columns
        if self.model.compound_sort_columns:
            # For compound sort, show indicator on first sorted column
            if self.model.compound_sort_columns:
                col_idx, direction = self.model.compound_sort_columns[0]
                header.setSortIndicatorShown(True)
                header.setSortIndicator(
                    col_idx,
                    Qt.AscendingOrder if direction == 'asc' else Qt.DescendingOrder
                )
        elif self.model.sort_column is not None:
            header.setSortIndicatorShown(True)
            header.setSortIndicator(
                self.model.sort_column,
                Qt.AscendingOrder if self.model.sort_direction == 'asc' else Qt.DescendingOrder
            )

    def _show_context_menu(self, position):
        """Show context menu on right-click."""
        # Get the index at the clicked position
        index = self.table_view.indexAt(position)
        if not index.isValid():
            return

        # Create context menu
        menu = QtWidgets.QMenu(self)

        # Row operations
        insert_row_above = menu.addAction("Insert Row Above")
        insert_row_below = menu.addAction("Insert Row Below")
        delete_row = menu.addAction("Delete Row")
        menu.addSeparator()

        # Column operations
        insert_col_left = menu.addAction("Insert Column Left")
        insert_col_right = menu.addAction("Insert Column Right")
        delete_column = menu.addAction("Delete Column")
        menu.addSeparator()

        # Clipboard operations
        copy_action = menu.addAction("Copy (Ctrl+C)")
        cut_action = menu.addAction("Cut (Ctrl+X)")
        paste_action = menu.addAction("Paste (Ctrl+V)")
        paste_values_action = menu.addAction("Paste Values")
        paste_format_action = menu.addAction("Paste Cell Format")
        menu.addSeparator()
        clear_format_action = menu.addAction("Clear Cell Format")
        menu.addSeparator()

        # Format submenu
        format_menu = menu.addMenu("Format")

        # General format
        format_general = format_menu.addAction("General")
        format_menu.addSeparator()

        # Number formats
        number_menu = format_menu.addMenu("Number")
        format_number = number_menu.addAction("1,234.56  (#,##0.00)")
        format_number_no_dec = number_menu.addAction("1,235  (#,##0)")

        # Currency format (uses project settings)
        format_currency = format_menu.addAction("Currency")

        # Accounting format (uses project currency)
        format_accounting = format_menu.addAction("Accounting")
        format_menu.addSeparator()

        # Percentage formats
        percentage_menu = format_menu.addMenu("Percentage")
        format_percentage = percentage_menu.addAction("12.34%  (0.00%)")
        format_percentage_no_dec = percentage_menu.addAction("12%  (0%)")
        format_menu.addSeparator()

        # Text format
        format_text = format_menu.addAction("Text  (@)")

        # Show current format with checkmark
        current_format = self.model.get_cell_format(index.row(), index.column())
        format_actions = {
            SpreadsheetModel.FORMAT_GENERAL: format_general,
            SpreadsheetModel.FORMAT_NUMBER: format_number,
            SpreadsheetModel.FORMAT_NUMBER_NO_DECIMAL: format_number_no_dec,
            SpreadsheetModel.FORMAT_CURRENCY: format_currency,
            SpreadsheetModel.FORMAT_ACCOUNTING: format_accounting,
            SpreadsheetModel.FORMAT_PERCENTAGE: format_percentage,
            SpreadsheetModel.FORMAT_PERCENTAGE_NO_DECIMAL: format_percentage_no_dec,
            SpreadsheetModel.FORMAT_TEXT: format_text,
        }
        if current_format in format_actions:
            format_actions[current_format].setCheckable(True)
            format_actions[current_format].setChecked(True)

        # Show menu and get action
        action = menu.exec_(self.table_view.viewport().mapToGlobal(position))

        if action == insert_row_above:
            self._insert_row_above(index.row())
        elif action == insert_row_below:
            self._insert_row_below(index.row())
        elif action == delete_row:
            self._delete_row(index.row())
        elif action == insert_col_left:
            self._insert_column_left(index.column())
        elif action == insert_col_right:
            self._insert_column_right(index.column())
        elif action == delete_column:
            self._delete_column(index.column())
        # Clipboard actions
        elif action == copy_action:
            self.table_view._copy_selection()
        elif action == cut_action:
            self.table_view._cut_selection()
        elif action == paste_action:
            self.table_view._paste_selection()
        elif action == paste_values_action:
            self.table_view._paste_values_only()
        elif action == paste_format_action:
            self.table_view._paste_format_only()
        elif action == clear_format_action:
            self._clear_cell_format()
        # Format actions
        elif action == format_general:
            self._set_cell_format(index, SpreadsheetModel.FORMAT_GENERAL)
        elif action == format_number:
            self._set_cell_format(index, SpreadsheetModel.FORMAT_NUMBER)
        elif action == format_number_no_dec:
            self._set_cell_format(index, SpreadsheetModel.FORMAT_NUMBER_NO_DECIMAL)
        elif action == format_currency:
            self._set_cell_format(index, SpreadsheetModel.FORMAT_CURRENCY)
        elif action == format_accounting:
            self._set_cell_format(index, SpreadsheetModel.FORMAT_ACCOUNTING)
        elif action == format_percentage:
            self._set_cell_format(index, SpreadsheetModel.FORMAT_PERCENTAGE)
        elif action == format_percentage_no_dec:
            self._set_cell_format(index, SpreadsheetModel.FORMAT_PERCENTAGE_NO_DECIMAL)
        elif action == format_text:
            self._set_cell_format(index, SpreadsheetModel.FORMAT_TEXT)

    def _set_cell_format(self, index, cell_format):
        """Set the format for selected cells with undo support.

        Args:
            index: QModelIndex of the clicked cell (used as fallback if no selection)
            cell_format: Excel-compatible format string
        """
        # Determine which cells to apply format to
        selection = self.table_view.selectionModel().selectedIndexes()
        if selection:
            cells = [(idx.row(), idx.column()) for idx in selection]
        else:
            # Fallback to the clicked cell
            cells = [(index.row(), index.column())]

        # Collect old formats for undo
        old_formats = {}
        for (row, col) in cells:
            old_formats[(row, col)] = self.model._formats.get((row, col))

        # Create undo command
        command = CellDataFormatCommand(self.model, cells, old_formats, cell_format)

        # Execute command and add to undo stack
        self.model._in_undo_redo = True
        try:
            command.redo()
        finally:
            self.model._in_undo_redo = False

        self.model.undo_stack.append(command)
        self.model.redo_stack.clear()

        logger.info(f"Set format '{cell_format}' for {len(cells)} cells")

    def _clear_cell_format(self):
        """Clear all cell formatting (data format and cell meta) from selected cells.

        Removes data format (Currency, Percentage, etc.) and cell meta
        (bg color, text color, font options like bold, italic).
        """
        selection = self.table_view.selectionModel().selectedIndexes()
        if not selection:
            return

        cells = [(idx.row(), idx.column()) for idx in selection]

        # Collect changes for undo
        changes = []
        for (row, col) in cells:
            old_format = self.model._formats.get((row, col))
            old_meta = self.model._cell_meta.get((row, col))
            if old_meta:
                old_meta = old_meta.copy()

            # Only add to changes if there's something to clear
            if old_format or old_meta:
                changes.append({
                    'row': row,
                    'col': col,
                    # Keep values unchanged
                    'old_value': self.model._data.get((row, col)),
                    'new_value': self.model._data.get((row, col)),
                    'old_formula': self.model._formulas.get((row, col)),
                    'new_formula': self.model._formulas.get((row, col)),
                    # Clear format and meta
                    'old_format': old_format,
                    'new_format': None,
                    'old_meta': old_meta,
                    'new_meta': None
                })

        if changes:
            command = SpreadsheetPasteCommand(changes, self.model)
            self.model._in_undo_redo = True
            try:
                command.redo()
            finally:
                self.model._in_undo_redo = False

            self.model.undo_stack.append(command)
            self.model.redo_stack.clear()
            self.model._clear_dependent_cache()

            logger.info(f"Cleared format for {len(changes)} cells")

    def _insert_row_above(self, row):
        """Insert a new row above the specified row."""
        self.model.beginInsertRows(QtCore.QModelIndex(), row, row)

        # Shift all data down
        self.model._rows += 1
        new_data = {}
        new_formulas = {}
        new_formats = {}

        for (r, c), value in self.model._data.items():
            if r >= row:
                new_data[(r + 1, c)] = value
            else:
                new_data[(r, c)] = value

        for (r, c), formula in self.model._formulas.items():
            # Update formula references to account for the inserted row
            updated_formula = self._update_formula_for_row_insertion(formula, row)
            if r >= row:
                new_formulas[(r + 1, c)] = updated_formula
            else:
                new_formulas[(r, c)] = updated_formula

        # Shift formats
        for (r, c), fmt in self.model._formats.items():
            if r >= row:
                new_formats[(r + 1, c)] = fmt
            else:
                new_formats[(r, c)] = fmt

        self.model._data = new_data
        self.model._formulas = new_formulas
        self.model._formats = new_formats
        self.model._evaluated_cache.clear()

        self.model.endInsertRows()

        # Emit dataChanged to trigger save to ShotGrid
        self.model.dataChanged.emit(
            self.model.index(0, 0),
            self.model.index(self.model.rowCount() - 1, self.model.columnCount() - 1),
            [QtCore.Qt.DisplayRole, QtCore.Qt.EditRole]
        )
        logger.info(f"Inserted row above row {row + 1}")

    def _insert_row_below(self, row):
        """Insert a new row below the specified row."""
        self._insert_row_above(row + 1)

    def _delete_row(self, row):
        """Delete the specified row."""
        if self.model._rows <= 1:
            logger.warning("Cannot delete the last row")
            return

        self.model.beginRemoveRows(QtCore.QModelIndex(), row, row)

        # Shift all data up
        self.model._rows -= 1
        new_data = {}
        new_formulas = {}
        new_formats = {}

        for (r, c), value in self.model._data.items():
            if r == row:
                continue  # Skip the deleted row
            elif r > row:
                new_data[(r - 1, c)] = value
            else:
                new_data[(r, c)] = value

        for (r, c), formula in self.model._formulas.items():
            if r == row:
                continue  # Skip the deleted row
            elif r > row:
                # Update formula to adjust for row shift
                updated_formula = self._update_formula_for_row_deletion(formula, row)
                new_formulas[(r - 1, c)] = updated_formula
            else:
                # Update formula even if not shifting position
                updated_formula = self._update_formula_for_row_deletion(formula, row)
                new_formulas[(r, c)] = updated_formula

        # Shift formats
        for (r, c), fmt in self.model._formats.items():
            if r == row:
                continue  # Skip the deleted row
            elif r > row:
                new_formats[(r - 1, c)] = fmt
            else:
                new_formats[(r, c)] = fmt

        self.model._data = new_data
        self.model._formulas = new_formulas
        self.model._formats = new_formats
        self.model._evaluated_cache.clear()

        self.model.endRemoveRows()

        # Emit dataChanged to trigger save to ShotGrid
        self.model.dataChanged.emit(
            self.model.index(0, 0),
            self.model.index(self.model.rowCount() - 1, self.model.columnCount() - 1),
            [QtCore.Qt.DisplayRole, QtCore.Qt.EditRole]
        )
        logger.info(f"Deleted row {row + 1}")

    def _delete_column(self, col):
        """Delete the specified column."""
        if self.model._cols <= 1:
            logger.warning("Cannot delete the last column")
            return

        self.model.beginRemoveColumns(QtCore.QModelIndex(), col, col)

        # Shift all data left
        self.model._cols -= 1
        new_data = {}
        new_formulas = {}
        new_formats = {}

        for (r, c), value in self.model._data.items():
            if c == col:
                continue  # Skip the deleted column
            elif c > col:
                new_data[(r, c - 1)] = value
            else:
                new_data[(r, c)] = value

        for (r, c), formula in self.model._formulas.items():
            if c == col:
                continue  # Skip the deleted column
            elif c > col:
                # Update formula to adjust for column shift
                updated_formula = self._update_formula_for_column_deletion(formula, col)
                new_formulas[(r, c - 1)] = updated_formula
            else:
                # Update formula even if not shifting position
                updated_formula = self._update_formula_for_column_deletion(formula, col)
                new_formulas[(r, c)] = updated_formula

        # Shift formats
        for (r, c), fmt in self.model._formats.items():
            if c == col:
                continue  # Skip the deleted column
            elif c > col:
                new_formats[(r, c - 1)] = fmt
            else:
                new_formats[(r, c)] = fmt

        self.model._data = new_data
        self.model._formulas = new_formulas
        self.model._formats = new_formats
        self.model._evaluated_cache.clear()

        self.model.endRemoveColumns()

        # Emit dataChanged to trigger save to ShotGrid
        self.model.dataChanged.emit(
            self.model.index(0, 0),
            self.model.index(self.model.rowCount() - 1, self.model.columnCount() - 1),
            [QtCore.Qt.DisplayRole, QtCore.Qt.EditRole]
        )
        logger.info(f"Deleted column {self.model._column_name(col)}")

    def _insert_column_left(self, col):
        """Insert a new column to the left of the specified column."""
        self.model.beginInsertColumns(QtCore.QModelIndex(), col, col)

        # Shift all data right
        self.model._cols += 1
        new_data = {}
        new_formulas = {}
        new_formats = {}

        for (r, c), value in self.model._data.items():
            if c >= col:
                new_data[(r, c + 1)] = value
            else:
                new_data[(r, c)] = value

        for (r, c), formula in self.model._formulas.items():
            # Update formula references to account for the inserted column
            updated_formula = self._update_formula_for_column_insertion(formula, col)
            if c >= col:
                new_formulas[(r, c + 1)] = updated_formula
            else:
                new_formulas[(r, c)] = updated_formula

        # Shift formats
        for (r, c), fmt in self.model._formats.items():
            if c >= col:
                new_formats[(r, c + 1)] = fmt
            else:
                new_formats[(r, c)] = fmt

        self.model._data = new_data
        self.model._formulas = new_formulas
        self.model._formats = new_formats
        self.model._evaluated_cache.clear()

        self.model.endInsertColumns()

        # Emit dataChanged to trigger save to ShotGrid
        self.model.dataChanged.emit(
            self.model.index(0, 0),
            self.model.index(self.model.rowCount() - 1, self.model.columnCount() - 1),
            [QtCore.Qt.DisplayRole, QtCore.Qt.EditRole]
        )
        logger.info(f"Inserted column left of {self.model._column_name(col)}")

    def _insert_column_right(self, col):
        """Insert a new column to the right of the specified column."""
        self._insert_column_left(col + 1)

    def _update_formula_for_row_deletion(self, formula, deleted_row):
        """Update cell references in a formula after a row deletion.

        Args:
            formula: The formula string (e.g., "=SUM(A1:A10)")
            deleted_row: The row that was deleted (0-based)

        Returns:
            Updated formula string
        """
        import re

        # Pattern to match cell references like A1, B2, $A$1, etc.
        pattern = r'(\$?)([A-Z]+)(\$?)(\d+)'

        def replace_ref(match):
            col_abs = match.group(1)  # $ before column
            col_letter = match.group(2)
            row_abs = match.group(3)  # $ before row
            row_num = int(match.group(4))

            # Convert to 0-based
            row_idx = row_num - 1

            # If not absolute row reference and row > deleted_row, decrement
            if not row_abs and row_idx > deleted_row:
                new_row_num = row_num - 1
                return f"{col_abs}{col_letter}{row_abs}{new_row_num}"

            return match.group(0)

        return re.sub(pattern, replace_ref, formula)

    def _update_formula_for_column_deletion(self, formula, deleted_col):
        """Update cell references in a formula after a column deletion.

        Args:
            formula: The formula string (e.g., "=SUM(A1:B10)")
            deleted_col: The column that was deleted (0-based)

        Returns:
            Updated formula string
        """
        import re

        # Pattern to match cell references like A1, B2, $A$1, etc.
        pattern = r'(\$?)([A-Z]+)(\$?)(\d+)'

        def replace_ref(match):
            col_abs = match.group(1)  # $ before column
            col_letter = match.group(2)
            row_abs = match.group(3)  # $ before row
            row_num = match.group(4)

            # Convert column letter to index
            col_idx = self.model.letter_to_col(col_letter)

            # If not absolute column reference and col > deleted_col, shift left
            if not col_abs and col_idx > deleted_col:
                new_col_letter = self.model._column_name(col_idx - 1)
                return f"{col_abs}{new_col_letter}{row_abs}{row_num}"

            return match.group(0)

        return re.sub(pattern, replace_ref, formula)

    def _update_formula_for_row_insertion(self, formula, inserted_row):
        """Update cell references in a formula after a row insertion.

        Args:
            formula: The formula string (e.g., "=SUM(A1:A10)")
            inserted_row: The row where a new row was inserted (0-based)

        Returns:
            Updated formula string with row references shifted down
        """
        import re

        # Pattern to match cell references like A1, B2, $A$1, etc.
        pattern = r'(\$?)([A-Z]+)(\$?)(\d+)'

        def replace_ref(match):
            col_abs = match.group(1)  # $ before column
            col_letter = match.group(2)
            row_abs = match.group(3)  # $ before row
            row_num = int(match.group(4))

            # Convert to 0-based
            row_idx = row_num - 1

            # If not absolute row reference and row >= inserted_row, increment
            if not row_abs and row_idx >= inserted_row:
                new_row_num = row_num + 1
                return f"{col_abs}{col_letter}{row_abs}{new_row_num}"

            return match.group(0)

        return re.sub(pattern, replace_ref, formula)

    def _update_formula_for_column_insertion(self, formula, inserted_col):
        """Update cell references in a formula after a column insertion.

        Args:
            formula: The formula string (e.g., "=SUM(A1:B10)")
            inserted_col: The column where a new column was inserted (0-based)

        Returns:
            Updated formula string with column references shifted right
        """
        import re

        # Pattern to match cell references like A1, B2, $A$1, etc.
        pattern = r'(\$?)([A-Z]+)(\$?)(\d+)'

        def replace_ref(match):
            col_abs = match.group(1)  # $ before column
            col_letter = match.group(2)
            row_abs = match.group(3)  # $ before row
            row_num = match.group(4)

            # Convert column letter to index
            col_idx = self.model.letter_to_col(col_letter)

            # If not absolute column reference and col >= inserted_col, shift right
            if not col_abs and col_idx >= inserted_col:
                new_col_letter = self.model._column_name(col_idx + 1)
                return f"{col_abs}{new_col_letter}{row_abs}{row_num}"

            return match.group(0)

        return re.sub(pattern, replace_ref, formula)

    def set_formula_evaluator(self, evaluator):
        """Set the formula evaluator."""
        self.formula_evaluator = evaluator
        self.model.set_formula_evaluator(evaluator)

    def get_cell_value(self, row, col):
        """Get the evaluated value of a cell."""
        return self.model.get_cell_value(row, col)

    def set_cell_value(self, row, col, value):
        """Set the value of a cell."""
        index = self.model.index(row, col)
        self.model.setData(index, value, Qt.EditRole)

    def set_currency_settings(self, symbol, position):
        """Set the currency symbol and position for formatting.

        Args:
            symbol: Currency symbol (e.g., "$", "€", "£")
            position: "prepend" (before value) or "append" (after value)
        """
        self.model.set_currency_settings(symbol, position)

    def get_data_as_dict(self):
        """Export all data as a dictionary including formats."""
        data = {}
        for row in range(self.model.rowCount()):
            for col in range(self.model.columnCount()):
                value = self.model._data.get((row, col))
                formula = self.model._formulas.get((row, col))
                cell_format = self.model._formats.get((row, col))
                if value or formula or cell_format:
                    cell_data = {
                        'value': value,
                        'formula': formula,
                    }
                    if cell_format:
                        cell_data['format'] = cell_format
                    data[(row, col)] = cell_data
        return data

    def load_data_from_dict(self, data):
        """Load data from a dictionary including formats."""
        self.model._data.clear()
        self.model._formulas.clear()
        self.model._formats.clear()
        self.model._evaluated_cache.clear()

        for (row, col), cell_data in data.items():
            if cell_data.get('formula'):
                self.model._formulas[(row, col)] = cell_data['formula']
            elif cell_data.get('value'):
                self.model._data[(row, col)] = cell_data['value']

            # Load format if present
            if cell_data.get('format'):
                self.model._formats[(row, col)] = cell_data['format']

        # Refresh the view
        self.model.layoutChanged.emit()
