"""
Example usage of SlidingOverlayPanel and SlidingOverlayPanelWithBackground

This file demonstrates how to use the sliding overlay panel component in your
PySide6 applications.
"""

import sys
from PySide6 import QtWidgets, QtCore
from sliding_overlay_panel import SlidingOverlayPanel, SlidingOverlayPanelWithBackground


class SimpleExample(QtWidgets.QWidget):
    """Simple example showing basic overlay panel usage."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sliding Overlay Panel - Simple Example")
        self.setMinimumSize(800, 600)

        # Main layout
        layout = QtWidgets.QVBoxLayout(self)

        # Toggle button
        toggle_btn = QtWidgets.QPushButton("Toggle Overlay Panel")
        toggle_btn.clicked.connect(self._toggle_panel)
        layout.addWidget(toggle_btn)

        # Main content area
        content = QtWidgets.QTextEdit()
        content.setPlaceholderText("Main content area - the panel will slide over this content")
        layout.addWidget(content)

        # Create overlay panel (without background)
        self.overlay = SlidingOverlayPanel(parent=self, panel_width=300)
        self.overlay.set_title("Settings")

        # Add content to overlay panel
        panel_content = self._create_panel_content()
        self.overlay.set_content(panel_content)

    def _create_panel_content(self):
        """Create content for the overlay panel."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        layout.addWidget(QtWidgets.QLabel("Panel Content"))

        # Some example controls
        layout.addWidget(QtWidgets.QLabel("Option 1:"))
        layout.addWidget(QtWidgets.QCheckBox("Enable feature"))

        layout.addWidget(QtWidgets.QLabel("Option 2:"))
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        layout.addWidget(slider)

        layout.addStretch()

        return widget

    def _toggle_panel(self):
        """Toggle the overlay panel."""
        self.overlay.toggle()


class ExampleWithBackground(QtWidgets.QWidget):
    """Example showing overlay panel with semi-transparent background."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sliding Overlay Panel - With Background")
        self.setMinimumSize(800, 600)

        # Main layout
        layout = QtWidgets.QVBoxLayout(self)

        # Toggle button
        toggle_btn = QtWidgets.QPushButton("Show Package Manager")
        toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5eb3ff;
            }
        """)
        toggle_btn.clicked.connect(self._toggle_panel)
        layout.addWidget(toggle_btn)

        # Main content area with tabs
        tab_widget = QtWidgets.QTabWidget()
        tab_widget.addTab(QtWidgets.QTextEdit("Bid Tracker content..."), "Bid Tracker")
        tab_widget.addTab(QtWidgets.QTextEdit("Documents content..."), "Documents")
        tab_widget.addTab(QtWidgets.QTextEdit("Images content..."), "Images")
        layout.addWidget(tab_widget)

        # Create overlay panel with background
        self.overlay = SlidingOverlayPanelWithBackground(
            parent=self,
            panel_width=400,
            animation_duration=300,
            background_opacity=0.3,
            close_on_background_click=True
        )
        self.overlay.set_title("Package Manager")

        # Add content to overlay panel
        panel_content = self._create_package_manager_content()
        self.overlay.set_content(panel_content)

        # Connect signals
        self.overlay.panel_shown.connect(lambda: toggle_btn.setText("Hide Package Manager ◀"))
        self.overlay.panel_hidden.connect(lambda: toggle_btn.setText("Show Package Manager ▶"))

    def _create_package_manager_content(self):
        """Create Package Manager content for the overlay panel."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)

        # Package selector
        selector_layout = QtWidgets.QHBoxLayout()
        selector_layout.addWidget(QtWidgets.QLabel("Current Package:"))
        package_combo = QtWidgets.QComboBox()
        package_combo.addItems(["(No Package)", "Package 1", "Package 2", "Package 3"])
        selector_layout.addWidget(package_combo, 1)
        layout.addLayout(selector_layout)

        # Buttons
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addWidget(QtWidgets.QPushButton("Create"))
        buttons_layout.addWidget(QtWidgets.QPushButton("Rename"))
        buttons_layout.addWidget(QtWidgets.QPushButton("Delete"))
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

        # Package data tree (placeholder)
        tree = QtWidgets.QTreeWidget()
        tree.setHeaderLabels(["Name", "Type", "Status"])
        tree.setAlternatingRowColors(True)

        # Add some sample items
        for i in range(5):
            item = QtWidgets.QTreeWidgetItem(tree)
            item.setText(0, f"Item {i+1}")
            item.setText(1, "Type")
            item.setText(2, "Active")

        layout.addWidget(tree, 1)

        # Data to fetch section
        fetch_group = QtWidgets.QGroupBox("Data to Fetch")
        fetch_layout = QtWidgets.QVBoxLayout(fetch_group)
        fetch_layout.addWidget(QtWidgets.QCheckBox("Bid Tracker"))
        fetch_layout.addWidget(QtWidgets.QCheckBox("Documents"))
        fetch_layout.addWidget(QtWidgets.QCheckBox("Images"))
        layout.addWidget(fetch_group)

        return widget

    def _toggle_panel(self):
        """Toggle the overlay panel."""
        self.overlay.toggle()


class MultiPanelExample(QtWidgets.QWidget):
    """Example showing multiple overlay panels."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sliding Overlay Panel - Multiple Panels")
        self.setMinimumSize(1000, 600)

        # Main layout
        layout = QtWidgets.QVBoxLayout(self)

        # Button bar
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self._create_styled_button("Settings", self._show_settings))
        button_layout.addWidget(self._create_styled_button("Filters", self._show_filters))
        button_layout.addWidget(self._create_styled_button("Help", self._show_help))
        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Main content
        content = QtWidgets.QTextEdit()
        content.setPlaceholderText("Main content area...")
        layout.addWidget(content)

        # Create multiple overlay panels
        self._create_settings_panel()
        self._create_filters_panel()
        self._create_help_panel()

    def _create_styled_button(self, text, callback):
        """Create a styled button."""
        btn = QtWidgets.QPushButton(text)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5eb3ff;
            }
        """)
        btn.clicked.connect(callback)
        return btn

    def _create_settings_panel(self):
        """Create settings overlay panel."""
        self.settings_panel = SlidingOverlayPanelWithBackground(
            parent=self, panel_width=350, background_opacity=0.3
        )
        self.settings_panel.set_title("Settings")

        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        layout.addWidget(QtWidgets.QLabel("Application Settings"))
        layout.addWidget(QtWidgets.QCheckBox("Enable dark mode"))
        layout.addWidget(QtWidgets.QCheckBox("Auto-save"))
        layout.addStretch()

        self.settings_panel.set_content(content)

    def _create_filters_panel(self):
        """Create filters overlay panel."""
        self.filters_panel = SlidingOverlayPanelWithBackground(
            parent=self, panel_width=300, background_opacity=0.3
        )
        self.filters_panel.set_title("Filters")

        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        layout.addWidget(QtWidgets.QLabel("Filter Options"))
        layout.addWidget(QtWidgets.QCheckBox("Show completed"))
        layout.addWidget(QtWidgets.QCheckBox("Show pending"))
        layout.addWidget(QtWidgets.QCheckBox("Show archived"))
        layout.addStretch()

        self.filters_panel.set_content(content)

    def _create_help_panel(self):
        """Create help overlay panel."""
        self.help_panel = SlidingOverlayPanelWithBackground(
            parent=self, panel_width=400, background_opacity=0.3
        )
        self.help_panel.set_title("Help")

        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        help_text = QtWidgets.QTextEdit()
        help_text.setReadOnly(True)
        help_text.setPlainText(
            "This is a help panel that slides in from the right.\n\n"
            "You can add any help content here, including:\n"
            "- Documentation\n"
            "- Tutorials\n"
            "- FAQ\n"
            "- Contact information"
        )
        layout.addWidget(help_text)

        self.help_panel.set_content(content)

    def _show_settings(self):
        """Show settings panel."""
        # Hide other panels first
        self.filters_panel.hide_panel()
        self.help_panel.hide_panel()
        # Show settings
        self.settings_panel.show_panel()

    def _show_filters(self):
        """Show filters panel."""
        self.settings_panel.hide_panel()
        self.help_panel.hide_panel()
        self.filters_panel.show_panel()

    def _show_help(self):
        """Show help panel."""
        self.settings_panel.hide_panel()
        self.filters_panel.hide_panel()
        self.help_panel.show_panel()


def main():
    """Run the examples."""
    app = QtWidgets.QApplication(sys.argv)

    # Apply dark theme
    app.setStyle("Fusion")
    dark_palette = QtWidgets.QApplication.palette()
    dark_palette.setColor(QtWidgets.QPalette.Window, QtCore.Qt.GlobalColor.darkGray)
    dark_palette.setColor(QtWidgets.QPalette.WindowText, QtCore.Qt.GlobalColor.white)
    app.setPalette(dark_palette)

    # Create examples
    print("Choose an example to run:")
    print("1. Simple Example (basic overlay panel)")
    print("2. Example with Background (overlay with semi-transparent background)")
    print("3. Multi-Panel Example (multiple overlay panels)")

    choice = input("Enter your choice (1-3): ").strip()

    if choice == "1":
        window = SimpleExample()
    elif choice == "2":
        window = ExampleWithBackground()
    elif choice == "3":
        window = MultiPanelExample()
    else:
        print("Invalid choice. Running Example with Background...")
        window = ExampleWithBackground()

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
