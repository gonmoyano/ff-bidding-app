"""
Reports Tab
Contains dockable report widgets using QDockWidget pattern.
"""

from PySide6 import QtCore, QtGui, QtWidgets

try:
    from .logger import logger
    from .settings import AppSettings
except ImportError:
    import logging
    logger = logging.getLogger("FFPackageManager")
    from settings import AppSettings


class ReportDock(QtWidgets.QDockWidget):
    """A dockable report widget."""

    def __init__(self, title, widget, parent=None):
        """Initialize the report dock.

        Args:
            title: Title of the dock
            widget: Widget to display in the dock
            parent: Parent widget
        """
        super().__init__(title, parent)
        self.setObjectName(title)
        self.setWidget(widget)
        self.setFeatures(
            QtWidgets.QDockWidget.DockWidgetClosable |
            QtWidgets.QDockWidget.DockWidgetMovable |
            QtWidgets.QDockWidget.DockWidgetFloatable
        )


class ReportsTab(QtWidgets.QMainWindow):
    """Reports tab with dockable report widgets."""

    SETTINGS_KEY = "reportsTab/dockState"

    def __init__(self, sg_session, parent=None):
        """Initialize the Reports tab.

        Args:
            sg_session: ShotgridClient instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.sg_session = sg_session
        self.parent_app = parent

        # Settings
        self.app_settings = AppSettings()

        # Current context
        self.current_project_id = None
        self.current_bid_id = None

        # No central widget - docks can take full space
        self.setCentralWidget(None)

        # Enable tabbing/nesting
        self.setDockOptions(
            QtWidgets.QMainWindow.AllowTabbedDocks |
            QtWidgets.QMainWindow.AllowNestedDocks |
            QtWidgets.QMainWindow.AnimatedDocks
        )

        # Force tabs on TOP for every dock area
        self.setTabPosition(
            QtCore.Qt.AllDockWidgetAreas,
            QtWidgets.QTabWidget.North
        )

        # Create report docks
        self._create_report_docks()

        # Set up corner ownership for dock areas
        self.setCorner(QtCore.Qt.TopLeftCorner, QtCore.Qt.LeftDockWidgetArea)
        self.setCorner(QtCore.Qt.BottomLeftCorner, QtCore.Qt.LeftDockWidgetArea)
        self.setCorner(QtCore.Qt.TopRightCorner, QtCore.Qt.RightDockWidgetArea)
        self.setCorner(QtCore.Qt.BottomRightCorner, QtCore.Qt.RightDockWidgetArea)

        # Load saved layout
        QtCore.QTimer.singleShot(0, self.load_layout)

        logger.info("ReportsTab initialized")

    def _create_report_docks(self):
        """Create the individual report dock widgets."""
        # Budget Summary Report
        self.budget_summary_dock = ReportDock(
            "Budget Summary",
            self._create_budget_summary_widget(),
            self
        )

        # Line Items Report
        self.line_items_dock = ReportDock(
            "Line Items Report",
            self._create_line_items_report_widget(),
            self
        )

        # Rate Card Report
        self.rate_card_dock = ReportDock(
            "Rate Card",
            self._create_rate_card_widget(),
            self
        )

        # Delivery Status Report
        self.delivery_status_dock = ReportDock(
            "Delivery Status",
            self._create_delivery_status_widget(),
            self
        )

        # Add docks to areas
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.budget_summary_dock)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.line_items_dock)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.rate_card_dock)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.delivery_status_dock)

        # Tab the bottom docks together
        self.tabifyDockWidget(self.rate_card_dock, self.delivery_status_dock)
        self.rate_card_dock.raise_()

    def _create_budget_summary_widget(self):
        """Create the Budget Summary report widget."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QtWidgets.QLabel("Budget Summary")
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 5px;")
        layout.addWidget(title)

        # Placeholder content
        content = QtWidgets.QTextEdit()
        content.setPlaceholderText("Budget summary report will be displayed here...\n\n"
                                   "This will show:\n"
                                   "- Total budget breakdown\n"
                                   "- Cost per category\n"
                                   "- Budget vs actual\n"
                                   "- Variance analysis")
        content.setReadOnly(True)
        layout.addWidget(content)

        # Refresh button
        refresh_btn = QtWidgets.QPushButton("Refresh Report")
        refresh_btn.clicked.connect(lambda: self._refresh_budget_summary())
        layout.addWidget(refresh_btn)

        return widget

    def _create_line_items_report_widget(self):
        """Create the Line Items report widget."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QtWidgets.QLabel("Line Items Report")
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 5px;")
        layout.addWidget(title)

        # Placeholder content
        content = QtWidgets.QTextEdit()
        content.setPlaceholderText("Line items report will be displayed here...\n\n"
                                   "This will show:\n"
                                   "- All line items in current price list\n"
                                   "- Quantities and rates\n"
                                   "- Subtotals and totals\n"
                                   "- Grouped by category")
        content.setReadOnly(True)
        layout.addWidget(content)

        # Refresh button
        refresh_btn = QtWidgets.QPushButton("Refresh Report")
        refresh_btn.clicked.connect(lambda: self._refresh_line_items_report())
        layout.addWidget(refresh_btn)

        return widget

    def _create_rate_card_widget(self):
        """Create the Rate Card report widget."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QtWidgets.QLabel("Rate Card Report")
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 5px;")
        layout.addWidget(title)

        # Placeholder content
        content = QtWidgets.QTextEdit()
        content.setPlaceholderText("Rate card report will be displayed here...\n\n"
                                   "This will show:\n"
                                   "- All rates in current rate card\n"
                                   "- Rate categories\n"
                                   "- Hourly/daily rates\n"
                                   "- Comparison with previous rates")
        content.setReadOnly(True)
        layout.addWidget(content)

        # Refresh button
        refresh_btn = QtWidgets.QPushButton("Refresh Report")
        refresh_btn.clicked.connect(lambda: self._refresh_rate_card_report())
        layout.addWidget(refresh_btn)

        return widget

    def _create_delivery_status_widget(self):
        """Create the Delivery Status report widget."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QtWidgets.QLabel("Delivery Status Report")
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 5px;")
        layout.addWidget(title)

        # Placeholder content
        content = QtWidgets.QTextEdit()
        content.setPlaceholderText("Delivery status report will be displayed here...\n\n"
                                   "This will show:\n"
                                   "- Delivery milestones\n"
                                   "- Completion status\n"
                                   "- Pending deliverables\n"
                                   "- Timeline overview")
        content.setReadOnly(True)
        layout.addWidget(content)

        # Refresh button
        refresh_btn = QtWidgets.QPushButton("Refresh Report")
        refresh_btn.clicked.connect(lambda: self._refresh_delivery_status())
        layout.addWidget(refresh_btn)

        return widget

    def _refresh_budget_summary(self):
        """Refresh the budget summary report."""
        logger.info("Refreshing budget summary report")
        # TODO: Implement actual report generation
        pass

    def _refresh_line_items_report(self):
        """Refresh the line items report."""
        logger.info("Refreshing line items report")
        # TODO: Implement actual report generation
        pass

    def _refresh_rate_card_report(self):
        """Refresh the rate card report."""
        logger.info("Refreshing rate card report")
        # TODO: Implement actual report generation
        pass

    def _refresh_delivery_status(self):
        """Refresh the delivery status report."""
        logger.info("Refreshing delivery status report")
        # TODO: Implement actual report generation
        pass

    def set_rfq(self, rfq_data):
        """Set the current RFQ and update all reports.

        Args:
            rfq_data: Dictionary containing RFQ (CustomEntity04) data, or None
        """
        logger.info(f"set_rfq() called with rfq_data={rfq_data}")

        if rfq_data:
            # Get the linked Bid from the RFQ
            bid = rfq_data.get('sg_bid')
            if bid:
                if isinstance(bid, list) and bid:
                    self.current_bid_id = bid[0].get('id')
                elif isinstance(bid, dict):
                    self.current_bid_id = bid.get('id')
                else:
                    self.current_bid_id = None
            else:
                self.current_bid_id = None

            # Get project from RFQ
            project = rfq_data.get('project')
            if project:
                if isinstance(project, dict):
                    self.current_project_id = project.get('id')
                else:
                    self.current_project_id = None
            else:
                self.current_project_id = None

            # Refresh all reports with new context
            if self.current_bid_id and self.current_project_id:
                self._refresh_all_reports()
        else:
            self.current_bid_id = None
            self.current_project_id = None

    def _refresh_all_reports(self):
        """Refresh all reports."""
        logger.info("Refreshing all reports")
        self._refresh_budget_summary()
        self._refresh_line_items_report()
        self._refresh_rate_card_report()
        self._refresh_delivery_status()

    def save_layout(self):
        """Save the current dock layout to settings."""
        settings = QtCore.QSettings()
        settings.setValue(self.SETTINGS_KEY, self.saveState())
        logger.info("Saved reports dock layout")

    def load_layout(self):
        """Load the saved dock layout from settings."""
        settings = QtCore.QSettings()
        state = settings.value(self.SETTINGS_KEY)
        if state is not None:
            self.restoreState(state)
            logger.info("Loaded reports dock layout")
        else:
            logger.info("No saved layout found, using default")

    def reset_layout(self):
        """Reset dock layout to default."""
        settings = QtCore.QSettings()
        settings.remove(self.SETTINGS_KEY)

        # Remove all docks
        for dock in (self.budget_summary_dock, self.line_items_dock,
                     self.rate_card_dock, self.delivery_status_dock):
            self.removeDockWidget(dock)

        # Re-add in default positions
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.budget_summary_dock)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.line_items_dock)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.rate_card_dock)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.delivery_status_dock)

        # Tab the bottom docks together
        self.tabifyDockWidget(self.rate_card_dock, self.delivery_status_dock)
        self.rate_card_dock.raise_()

        logger.info("Reset reports dock layout to default")

    def get_view_menu_actions(self):
        """Get toggle view actions for all docks.

        Returns:
            List of QActions for toggling dock visibility
        """
        return [
            self.budget_summary_dock.toggleViewAction(),
            self.line_items_dock.toggleViewAction(),
            self.rate_card_dock.toggleViewAction(),
            self.delivery_status_dock.toggleViewAction(),
        ]

    def closeEvent(self, event: QtGui.QCloseEvent):
        """Handle close event - save layout."""
        self.save_layout()
        super().closeEvent(event)
