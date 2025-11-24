"""
Settings Dialog
Dialog for configuring application-wide settings.
"""

import shutil
from pathlib import Path
from PySide6 import QtWidgets, QtCore


class SettingsDialog(QtWidgets.QDialog):
    """Dialog for configuring application settings."""

    def __init__(self, app_settings, parent=None):
        """Initialize the settings dialog.

        Args:
            app_settings: AppSettings instance
            parent: Parent widget (should be the main app window)
        """
        super().__init__(parent)
        self.app_settings = app_settings
        self.parent_app = parent  # Store reference to main app
        self.setWindowTitle("Application Settings")
        self.setModal(True)
        self.setMinimumWidth(500)

        # Store original DPI scale to restore on cancel
        self.original_dpi_scale = app_settings.get_dpi_scale()

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
            "Adjust the size of UI elements (50% - 200%). Changes apply in real-time."
        )
        dpi_label.setWordWrap(True)
        dpi_label.setStyleSheet("color: #888888; font-size: 11px;")
        dpi_layout.addWidget(dpi_label)

        # DPI scale slider with percentage display
        slider_layout = QtWidgets.QHBoxLayout()
        slider_label = QtWidgets.QLabel("Scale Factor:")

        self.dpi_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.dpi_slider.setMinimum(50)   # 50%
        self.dpi_slider.setMaximum(200)  # 200%
        self.dpi_slider.setSingleStep(5)
        self.dpi_slider.setPageStep(25)
        self.dpi_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.dpi_slider.setTickInterval(25)

        # Set current value
        current_dpi = self.app_settings.get_dpi_scale()
        self.dpi_slider.setValue(int(current_dpi * 100))

        # Percentage label that updates in real-time
        self.dpi_percentage_label = QtWidgets.QLabel(f"{int(current_dpi * 100)}%")
        self.dpi_percentage_label.setMinimumWidth(50)
        self.dpi_percentage_label.setStyleSheet("font-weight: bold; color: #0078d4;")

        # Connect slider to update label and apply preview
        self.dpi_slider.valueChanged.connect(self._on_dpi_slider_changed)

        slider_layout.addWidget(slider_label)
        slider_layout.addWidget(self.dpi_slider)
        slider_layout.addWidget(self.dpi_percentage_label)
        dpi_layout.addLayout(slider_layout)

        # Add min/max labels
        limits_layout = QtWidgets.QHBoxLayout()
        limits_layout.addWidget(QtWidgets.QLabel("50%"))
        limits_layout.addStretch()
        limits_layout.addWidget(QtWidgets.QLabel("100%"))
        limits_layout.addStretch()
        limits_layout.addWidget(QtWidgets.QLabel("200%"))
        limits_layout.setContentsMargins(45, 0, 50, 5)
        for i in range(limits_layout.count()):
            widget = limits_layout.itemAt(i).widget()
            if widget:
                widget.setStyleSheet("color: #666666; font-size: 10px;")
        dpi_layout.addLayout(limits_layout)

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

        # Thumbnail Cache setting
        cache_group = QtWidgets.QGroupBox("Thumbnail Cache")
        cache_layout = QtWidgets.QVBoxLayout(cache_group)

        cache_label = QtWidgets.QLabel(
            "Thumbnails are cached locally for faster loading. "
            "Clear the cache if images appear outdated or corrupted."
        )
        cache_label.setWordWrap(True)
        cache_label.setStyleSheet("color: #888888; font-size: 11px;")
        cache_layout.addWidget(cache_label)

        # Cache folder path
        cache_path_layout = QtWidgets.QHBoxLayout()
        cache_path_label = QtWidgets.QLabel("Cache Folder:")
        self.cache_path_input = QtWidgets.QLineEdit()
        self.cache_path_input.setReadOnly(True)
        current_cache_path = self.app_settings.get_thumbnail_cache_path()
        self.cache_path_input.setText(str(current_cache_path))

        browse_btn = QtWidgets.QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_cache_folder)

        cache_path_layout.addWidget(cache_path_label)
        cache_path_layout.addWidget(self.cache_path_input, 1)
        cache_path_layout.addWidget(browse_btn)
        cache_layout.addLayout(cache_path_layout)

        # Cache stats and actions
        cache_actions_layout = QtWidgets.QHBoxLayout()

        # Cache stats label
        self.cache_stats_label = QtWidgets.QLabel()
        self.cache_stats_label.setStyleSheet("color: #666666; font-size: 10px;")
        self._update_cache_stats()
        cache_actions_layout.addWidget(self.cache_stats_label)

        cache_actions_layout.addStretch()

        # Clear cache button
        clear_cache_btn = QtWidgets.QPushButton("Clear Cache")
        clear_cache_btn.setToolTip("Delete all cached thumbnails")
        clear_cache_btn.clicked.connect(self._clear_cache)
        cache_actions_layout.addWidget(clear_cache_btn)

        # Refresh cache button
        refresh_cache_btn = QtWidgets.QPushButton("Refresh All")
        refresh_cache_btn.setToolTip("Re-download all thumbnails from ShotGrid")
        refresh_cache_btn.clicked.connect(self._refresh_all_thumbnails)
        cache_actions_layout.addWidget(refresh_cache_btn)

        cache_layout.addLayout(cache_actions_layout)

        # Cache max age setting
        cache_age_layout = QtWidgets.QHBoxLayout()
        cache_age_label = QtWidgets.QLabel("Cache expires after:")
        self.cache_age_spinbox = QtWidgets.QSpinBox()
        self.cache_age_spinbox.setMinimum(1)
        self.cache_age_spinbox.setMaximum(365)
        self.cache_age_spinbox.setValue(self.app_settings.get_thumbnail_cache_max_age_days())
        self.cache_age_spinbox.setSuffix(" days")
        cache_age_layout.addWidget(cache_age_label)
        cache_age_layout.addWidget(self.cache_age_spinbox)
        cache_age_layout.addStretch()
        cache_layout.addLayout(cache_age_layout)

        layout.addWidget(cache_group)

        # Spacer
        layout.addStretch()

        # Button box
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _on_dpi_slider_changed(self, value):
        """Handle DPI slider value change - update label and apply preview to main app."""
        # Update percentage label
        self.dpi_percentage_label.setText(f"{value}%")

        # Apply real-time preview to the parent app (not this dialog)
        if self.parent_app and hasattr(self.parent_app, '_apply_app_font_scaling'):
            scale_factor = value / 100.0
            self.parent_app._apply_app_font_scaling(scale_factor)

    def reject(self):
        """Handle Cancel - restore original DPI scale."""
        # Restore original scaling to parent app
        if self.parent_app and hasattr(self.parent_app, '_apply_app_font_scaling'):
            self.parent_app._apply_app_font_scaling(self.original_dpi_scale)

        super().reject()

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
        return self.dpi_slider.value() / 100.0

    def get_currency(self):
        """Get the selected currency symbol.

        Returns:
            str: Currency symbol
        """
        if self.currency_combo.currentData() == "custom":
            return self.custom_currency_input.text().strip() or "$"
        return self.currency_combo.currentData()

    def get_thumbnail_cache_path(self):
        """Get the thumbnail cache folder path.

        Returns:
            Path: Cache folder path
        """
        return Path(self.cache_path_input.text())

    def get_thumbnail_cache_max_age_days(self):
        """Get the cache max age in days.

        Returns:
            int: Max age in days
        """
        return self.cache_age_spinbox.value()

    def _browse_cache_folder(self):
        """Open a folder browser to select cache folder."""
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select Thumbnail Cache Folder",
            self.cache_path_input.text()
        )
        if folder:
            self.cache_path_input.setText(folder)
            self._update_cache_stats()

    def _update_cache_stats(self):
        """Update the cache statistics label."""
        cache_path = Path(self.cache_path_input.text())
        if cache_path.exists():
            # Count files and calculate size
            files = list(cache_path.glob("*.png")) + list(cache_path.glob("*.jpg"))
            total_size = sum(f.stat().st_size for f in files if f.exists())

            # Format size
            if total_size < 1024:
                size_str = f"{total_size} B"
            elif total_size < 1024 * 1024:
                size_str = f"{total_size / 1024:.1f} KB"
            else:
                size_str = f"{total_size / (1024 * 1024):.1f} MB"

            self.cache_stats_label.setText(f"{len(files)} cached images ({size_str})")
        else:
            self.cache_stats_label.setText("Cache folder does not exist")

    def _clear_cache(self):
        """Clear all cached thumbnails."""
        cache_path = Path(self.cache_path_input.text())

        if not cache_path.exists():
            QtWidgets.QMessageBox.information(
                self,
                "Cache Empty",
                "The cache folder does not exist or is already empty."
            )
            return

        # Confirm deletion
        reply = QtWidgets.QMessageBox.question(
            self,
            "Clear Cache",
            "Are you sure you want to delete all cached thumbnails?\n\n"
            "Thumbnails will be re-downloaded from ShotGrid when needed.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            try:
                # Delete all image files in the cache
                files = list(cache_path.glob("*.png")) + list(cache_path.glob("*.jpg"))
                for f in files:
                    f.unlink()

                self._update_cache_stats()
                QtWidgets.QMessageBox.information(
                    self,
                    "Cache Cleared",
                    f"Deleted {len(files)} cached thumbnails."
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to clear cache:\n{str(e)}"
                )

    def _refresh_all_thumbnails(self):
        """Signal the parent app to refresh all thumbnails."""
        # Clear cache first
        cache_path = Path(self.cache_path_input.text())
        if cache_path.exists():
            files = list(cache_path.glob("*.png")) + list(cache_path.glob("*.jpg"))
            for f in files:
                try:
                    f.unlink()
                except:
                    pass

        self._update_cache_stats()

        # Notify user
        QtWidgets.QMessageBox.information(
            self,
            "Cache Cleared",
            "Cache has been cleared. Thumbnails will be re-downloaded when you next load images.\n\n"
            "Close this dialog and refresh images to download fresh thumbnails."
        )
