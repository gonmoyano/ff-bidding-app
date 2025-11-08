"""
Complete Example: Using MultiEntityReferenceWidget in a QTableWidget

This example demonstrates how to integrate the MultiEntityReferenceWidget
into a VFX Breakdown table for ShotGrid, including:
- Setting up the table with the custom widget
- Handling entity changes
- Updating ShotGrid data
- Best practices for table cell widgets

Author: Claude Code
"""

import sys
from PySide6 import QtWidgets, QtCore, QtGui
from multi_entity_reference_widget import MultiEntityReferenceWidget

# Try relative import first, fall back to absolute
try:
    from .settings import AppSettings
except ImportError:
    from settings import AppSettings


class VFXBreakdownTable(QtWidgets.QWidget):
    """
    Example VFX Breakdown table using MultiEntityReferenceWidget for sg_bid_assets field.
    """

    def __init__(self, sg_session=None, parent=None):
        """
        Initialize the VFX Breakdown table.

        Args:
            sg_session: ShotGrid API session (optional for demo)
            parent: Parent widget
        """
        super().__init__(parent)
        self.sg_session = sg_session

        # Sample breakdown data (in production, this comes from ShotGrid)
        self.breakdown_data = [
            {
                "id": 1,
                "code": "BRK_001",
                "sg_vfx_description": "Character enters forest scene",
                "sg_bid_assets": [
                    {"type": "CustomEntity07", "id": 101, "name": "cre_deer"},
                    {"type": "CustomEntity07", "id": 102, "name": "cre_fray"},
                ],
            },
            {
                "id": 2,
                "code": "BRK_002",
                "sg_vfx_description": "Vehicle chase sequence",
                "sg_bid_assets": [
                    {"type": "CustomEntity07", "id": 103, "name": "veh_family_car"},
                ],
            },
            {
                "id": 3,
                "code": "BRK_003",
                "sg_vfx_description": "Empty breakdown for testing",
                "sg_bid_assets": [],
            },
        ]

        self._setup_ui()
        self._populate_table()

    def _setup_ui(self):
        """Build the UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QtWidgets.QLabel("VFX Breakdown - Bid Assets Reference")
        title.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        layout.addWidget(title)

        # Info label
        info = QtWidgets.QLabel(
            "The 'Bid Assets' column uses MultiEntityReferenceWidget. "
            "Try adding/removing assets and see console output."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #a0a0a0; padding: 5px;")
        layout.addWidget(info)

        # Create table
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "Breakdown Code",
            "VFX Description",
            "Bid Assets",
            "Actions"
        ])

        # Table styling
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #2b2b2b;
                gridline-color: #555555;
                border: 1px solid #555555;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #3a3a3a;
                color: #e0e0e0;
                padding: 5px;
                border: 1px solid #555555;
                font-weight: bold;
            }
        """)

        # Column widths (with DPI scaling)
        app_settings = AppSettings()
        dpi_scale = app_settings.get_dpi_scale()
        self.table.setColumnWidth(0, int(120 * dpi_scale))
        self.table.setColumnWidth(1, int(250 * dpi_scale))
        self.table.setColumnWidth(2, int(300 * dpi_scale))
        self.table.setColumnWidth(3, int(100 * dpi_scale))

        # Table properties
        self.table.verticalHeader().setDefaultSectionSize(80)
        self.table.horizontalHeader().setStretchLastSection(True)

        layout.addWidget(self.table)

        # Button panel
        button_layout = QtWidgets.QHBoxLayout()

        save_btn = QtWidgets.QPushButton("Save Changes to ShotGrid")
        save_btn.clicked.connect(self._save_to_shotgrid)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a7c4e;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a8c5e;
            }
        """)
        button_layout.addWidget(save_btn)

        refresh_btn = QtWidgets.QPushButton("Refresh from ShotGrid")
        refresh_btn.clicked.connect(self._refresh_from_shotgrid)
        button_layout.addWidget(refresh_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Status label
        self.status_label = QtWidgets.QLabel("Ready")
        self.status_label.setStyleSheet("color: #7fb3d5; padding: 5px;")
        layout.addWidget(self.status_label)

    def _populate_table(self):
        """Populate table with breakdown data."""
        self.table.setRowCount(len(self.breakdown_data))

        for row, breakdown in enumerate(self.breakdown_data):
            # Column 0: Breakdown Code
            code_item = QtWidgets.QTableWidgetItem(breakdown["code"])
            code_item.setFlags(code_item.flags() & ~QtCore.Qt.ItemIsEditable)
            self.table.setItem(row, 0, code_item)

            # Column 1: VFX Description
            desc_item = QtWidgets.QTableWidgetItem(breakdown["sg_vfx_description"])
            self.table.setItem(row, 1, desc_item)

            # Column 2: Bid Assets (MultiEntityReferenceWidget)
            assets_widget = MultiEntityReferenceWidget(
                entities=breakdown["sg_bid_assets"],
                allow_add=True
            )
            # Connect to change handler with row context
            assets_widget.entitiesChanged.connect(
                lambda entities, r=row: self._on_assets_changed(r, entities)
            )
            self.table.setCellWidget(row, 2, assets_widget)

            # Column 3: Actions
            actions_widget = self._create_actions_widget(row)
            self.table.setCellWidget(row, 3, actions_widget)

    def _create_actions_widget(self, row):
        """Create action buttons for a row.

        Args:
            row (int): Row index

        Returns:
            QWidget: Widget with action buttons
        """
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)

        view_btn = QtWidgets.QPushButton("View")
        view_btn.clicked.connect(lambda: self._view_breakdown(row))
        view_btn.setMaximumWidth(60)
        layout.addWidget(view_btn)

        return widget

    def _on_assets_changed(self, row, entities):
        """Handle when bid assets are changed for a breakdown.

        Args:
            row (int): Table row index
            entities (list): Updated list of entity dicts
        """
        breakdown = self.breakdown_data[row]
        old_assets = breakdown["sg_bid_assets"]
        breakdown["sg_bid_assets"] = entities

        print(f"\n[Row {row}] Bid Assets changed for '{breakdown['code']}':")
        print(f"  Old: {[e['name'] for e in old_assets]}")
        print(f"  New: {[e['name'] for e in entities]}")
        print(f"  Entity IDs: {[e['id'] for e in entities]}")

        # Update status
        self.status_label.setText(
            f"Modified: {breakdown['code']} - {len(entities)} asset(s) linked"
        )

    def _view_breakdown(self, row):
        """View breakdown details.

        Args:
            row (int): Row index
        """
        breakdown = self.breakdown_data[row]

        # Get current widget to retrieve latest data
        widget = self.table.cellWidget(row, 2)
        if isinstance(widget, MultiEntityReferenceWidget):
            current_assets = widget.get_entities()
        else:
            current_assets = breakdown["sg_bid_assets"]

        msg = f"Breakdown: {breakdown['code']}\n"
        msg += f"Description: {breakdown['sg_vfx_description']}\n"
        msg += f"\nLinked Bid Assets ({len(current_assets)}):\n"

        for asset in current_assets:
            msg += f"  • {asset['name']} (ID: {asset['id']}, Type: {asset['type']})\n"

        QtWidgets.QMessageBox.information(self, "Breakdown Details", msg)

    def _save_to_shotgrid(self):
        """Save changes to ShotGrid."""
        print("\n" + "="*60)
        print("SAVING TO SHOTGRID")
        print("="*60)

        for row, breakdown in enumerate(self.breakdown_data):
            # Get current data from widget
            widget = self.table.cellWidget(row, 2)
            if isinstance(widget, MultiEntityReferenceWidget):
                current_assets = widget.get_entities()

                # Update ShotGrid (pseudo-code)
                if self.sg_session:
                    try:
                        # Real ShotGrid update
                        self.sg_session.sg.update(
                            "CustomEntity02",  # Breakdown items entity type
                            breakdown["id"],
                            {
                                "sg_bid_assets": [
                                    {"type": e["type"], "id": e["id"]}
                                    for e in current_assets
                                ]
                            }
                        )
                        print(f"✓ Updated {breakdown['code']} with {len(current_assets)} assets")
                    except Exception as e:
                        print(f"✗ Failed to update {breakdown['code']}: {e}")
                else:
                    # Demo mode - just log
                    print(f"[DEMO] Would update {breakdown['code']}:")
                    print(f"  sg_bid_assets = {current_assets}")

        print("="*60)
        self.status_label.setText("✓ Changes saved to ShotGrid")
        QtWidgets.QMessageBox.information(
            self,
            "Success",
            "All changes have been saved to ShotGrid.\n"
            "(In demo mode, changes are logged to console)"
        )

    def _refresh_from_shotgrid(self):
        """Refresh data from ShotGrid."""
        print("\n[Refresh] Reloading data from ShotGrid...")

        if self.sg_session:
            # Real refresh logic
            # self.breakdown_data = self.sg_session.get_breakdowns(...)
            pass
        else:
            # Demo mode
            print("[DEMO] Would query ShotGrid for latest breakdown data")

        self._populate_table()
        self.status_label.setText("✓ Data refreshed from ShotGrid")


def main():
    """Run the example application."""
    app = QtWidgets.QApplication(sys.argv)

    # Apply dark theme
    app.setStyle("Fusion")
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(53, 53, 53))
    palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(25, 25, 25))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(53, 53, 53))
    palette.setColor(QtGui.QPalette.ToolTipBase, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.ToolTipText, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.Text, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor(53, 53, 53))
    palette.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.Link, QtGui.QColor(42, 130, 218))
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(42, 130, 218))
    palette.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.black)
    app.setPalette(palette)

    # Create main window
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("ShotGrid VFX Breakdown - Multi-Entity Reference Demo")
    window.setGeometry(100, 100, 1000, 600)

    # Set central widget
    table_widget = VFXBreakdownTable(sg_session=None)  # Pass real sg_session in production
    window.setCentralWidget(table_widget)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
