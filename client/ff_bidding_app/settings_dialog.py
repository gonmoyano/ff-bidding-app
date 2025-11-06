"""
Settings Dialog
Dialog for configuring application-wide settings.
"""

from PySide6 import QtWidgets, QtCore


class SettingsDialog(QtWidgets.QDialog):
    """Dialog for configuring application settings."""

    def __init__(self, app_settings, parent=None):
        """Initialize the settings dialog.

        Args:
            app_settings: AppSettings instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.app_settings = app_settings
        self.setWindowTitle("Application Settings")
        self.setModal(True)
        self.setMinimumWidth(500)

        self._build_ui()

    def _build_ui(self):
        """Build the dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)

        # Title
        title_label = QtWidgets.QLabel("Application Settings")
        title_font = title_label.font()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Separator
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(separator)

        # Form layout for settings
        form_layout = QtWidgets.QFormLayout()
        form_layout.setContentsMargins(20, 20, 20, 20)
        form_layout.setSpacing(15)

        # DPI Scale setting
        dpi_group = QtWidgets.QGroupBox("Display Scaling")
        dpi_layout = QtWidgets.QVBoxLayout(dpi_group)

        dpi_label = QtWidgets.QLabel(
            "Adjust the size of UI elements. Requires application restart."
        )
        dpi_label.setWordWrap(True)
        dpi_label.setStyleSheet("color: #888888; font-size: 11px;")
        dpi_layout.addWidget(dpi_label)

        # DPI scale combo box
        dpi_combo_layout = QtWidgets.QHBoxLayout()
        dpi_combo_label = QtWidgets.QLabel("Scale Factor:")
        self.dpi_combo = QtWidgets.QComboBox()
        self.dpi_combo.addItem("100% (Default)", 1.0)
        self.dpi_combo.addItem("125%", 1.25)
        self.dpi_combo.addItem("150%", 1.5)
        self.dpi_combo.addItem("175%", 1.75)
        self.dpi_combo.addItem("200%", 2.0)

        # Set current value
        current_dpi = self.app_settings.get_dpi_scale()
        for i in range(self.dpi_combo.count()):
            if abs(self.dpi_combo.itemData(i) - current_dpi) < 0.01:
                self.dpi_combo.setCurrentIndex(i)
                break

        dpi_combo_layout.addWidget(dpi_combo_label)
        dpi_combo_layout.addWidget(self.dpi_combo)
        dpi_combo_layout.addStretch()
        dpi_layout.addLayout(dpi_combo_layout)

        layout.addWidget(dpi_group)

        # Currency setting
        currency_group = QtWidgets.QGroupBox("Currency")
        currency_layout = QtWidgets.QVBoxLayout(currency_group)

        currency_label = QtWidgets.QLabel(
            "Select the currency symbol to use throughout the application."
        )
        currency_label.setWordWrap(True)
        currency_label.setStyleSheet("color: #888888; font-size: 11px;")
        currency_layout.addWidget(currency_label)

        # Currency combo box
        currency_combo_layout = QtWidgets.QHBoxLayout()
        currency_combo_label = QtWidgets.QLabel("Currency Symbol:")
        self.currency_combo = QtWidgets.QComboBox()
        self.currency_combo.addItem("$ - US Dollar", "$")
        self.currency_combo.addItem("€ - Euro", "€")
        self.currency_combo.addItem("£ - British Pound", "£")
        self.currency_combo.addItem("¥ - Japanese Yen / Chinese Yuan", "¥")
        self.currency_combo.addItem("₹ - Indian Rupee", "₹")
        self.currency_combo.addItem("₽ - Russian Ruble", "₽")
        self.currency_combo.addItem("R$ - Brazilian Real", "R$")
        self.currency_combo.addItem("Custom...", "custom")

        # Set current value
        current_currency = self.app_settings.get_currency()
        found = False
        for i in range(self.currency_combo.count() - 1):  # Exclude "Custom..."
            if self.currency_combo.itemData(i) == current_currency:
                self.currency_combo.setCurrentIndex(i)
                found = True
                break

        if not found:
            # Set to Custom and show the custom value
            self.currency_combo.setCurrentIndex(self.currency_combo.count() - 1)

        currency_combo_layout.addWidget(currency_combo_label)
        currency_combo_layout.addWidget(self.currency_combo)
        currency_combo_layout.addStretch()
        currency_layout.addLayout(currency_combo_layout)

        # Custom currency input
        self.custom_currency_layout = QtWidgets.QHBoxLayout()
        custom_label = QtWidgets.QLabel("Custom Symbol:")
        self.custom_currency_input = QtWidgets.QLineEdit()
        self.custom_currency_input.setMaxLength(5)
        self.custom_currency_input.setPlaceholderText("Enter custom symbol")
        if not found:
            self.custom_currency_input.setText(current_currency)
        self.custom_currency_layout.addWidget(custom_label)
        self.custom_currency_layout.addWidget(self.custom_currency_input)
        self.custom_currency_layout.addStretch()
        currency_layout.addLayout(self.custom_currency_layout)

        # Show/hide custom input based on selection
        self._toggle_custom_currency()
        self.currency_combo.currentIndexChanged.connect(self._toggle_custom_currency)

        layout.addWidget(currency_group)

        # Spacer
        layout.addStretch()

        # Button box
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _toggle_custom_currency(self):
        """Show/hide custom currency input based on selection."""
        is_custom = self.currency_combo.currentData() == "custom"
        custom_label = self.custom_currency_layout.itemAt(0).widget()
        custom_label.setVisible(is_custom)
        self.custom_currency_input.setVisible(is_custom)

    def get_dpi_scale(self):
        """Get the selected DPI scale factor.

        Returns:
            float: DPI scale factor
        """
        return self.dpi_combo.currentData()

    def get_currency(self):
        """Get the selected currency symbol.

        Returns:
            str: Currency symbol
        """
        if self.currency_combo.currentData() == "custom":
            return self.custom_currency_input.text().strip() or "$"
        return self.currency_combo.currentData()
