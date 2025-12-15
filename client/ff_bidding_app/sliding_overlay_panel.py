"""
Sliding Overlay Panel Widget for PySide6

A reusable component that provides a panel that slides in from the right edge
of the parent widget, overlaying the content with smooth animation.

Features:
- Smooth slide-in/out animation using QPropertyAnimation
- Semi-transparent overlay background
- Close button and toggle functionality
- Configurable panel width
- Higher z-order for floating appearance

Usage:
    # Create overlay panel
    overlay = SlidingOverlayPanel(parent_widget, panel_width=400)

    # Add content to the panel
    overlay.set_content(your_widget)

    # Show/hide the panel
    overlay.toggle()
    overlay.show_panel()
    overlay.hide_panel()
"""

from PySide6 import QtWidgets, QtCore, QtGui


class SlidingOverlayPanel(QtWidgets.QWidget):
    """A panel that slides in from the right edge as an overlay."""

    # Signals
    panel_shown = QtCore.Signal()
    panel_hidden = QtCore.Signal()
    dock_requested = QtCore.Signal()  # Emitted when dock button is clicked

    def __init__(self, parent=None, panel_width=400, animation_duration=300, show_dock_button=False):
        """Initialize the sliding overlay panel.

        Args:
            parent: Parent widget (the panel will overlay this widget)
            panel_width: Width of the panel in pixels (default: 400)
            animation_duration: Animation duration in milliseconds (default: 300)
            show_dock_button: Whether to show a dock button in the header (default: False)
        """
        super().__init__(parent)

        self.panel_width = panel_width
        self.animation_duration = animation_duration
        self._is_visible = False
        self._show_dock_button = show_dock_button

        # Set up the widget properties
        self.setAutoFillBackground(True)

        # Set higher z-order to appear on top
        self.raise_()

        # Initially hide the panel off-screen to the right
        self.hide()

        self._build_ui()
        self._setup_animation()

    def _build_ui(self):
        """Build the panel UI."""
        # Main layout for the panel
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Header with close button
        header = QtWidgets.QWidget()
        header.setObjectName("panelHeader")
        header.setStyleSheet("""
            QWidget#panelHeader {
                background-color: #353535;
                border-bottom: 1px solid #555555;
            }
        """)
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(10, 5, 10, 5)

        # Title label (optional)
        self.title_label = QtWidgets.QLabel("Panel")
        title_font = self.title_label.font()
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        # Dock button (optional)
        if self._show_dock_button:
            self.dock_button = QtWidgets.QPushButton("⬒")  # Unicode dock/pin icon
            self.dock_button.setFixedSize(24, 24)
            self.dock_button.setToolTip("Dock panel")
            self.dock_button.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    color: #e0e0e0;
                    font-size: 14px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #4a9eff;
                    border-radius: 12px;
                }
            """)
            self.dock_button.clicked.connect(self._on_dock_clicked)
            header_layout.addWidget(self.dock_button)

        # Close button
        self.close_button = QtWidgets.QPushButton("✕")
        self.close_button.setFixedSize(24, 24)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #e0e0e0;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff4444;
                border-radius: 12px;
            }
        """)
        self.close_button.clicked.connect(self.hide_panel)
        header_layout.addWidget(self.close_button)

        self.main_layout.addWidget(header)

        # Content container
        self.content_container = QtWidgets.QWidget()
        self.content_container.setObjectName("contentContainer")
        self.content_layout = QtWidgets.QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(0, 0, 0, 0)

        self.main_layout.addWidget(self.content_container, 1)

        # Apply styling
        self.setStyleSheet("""
            SlidingOverlayPanel {
                background-color: #2b2b2b;
                border-left: 2px solid #555555;
            }
            QWidget#contentContainer {
                background-color: #2b2b2b;
            }
        """)

    def _setup_animation(self):
        """Set up the slide animation."""
        self.slide_animation = QtCore.QPropertyAnimation(self, b"pos")
        self.slide_animation.setDuration(self.animation_duration)
        self.slide_animation.setEasingCurve(QtCore.QEasingCurve.InOutCubic)

        # Connect animation signals
        self.slide_animation.finished.connect(self._on_animation_finished)

    def _on_animation_finished(self):
        """Handle animation completion."""
        if not self._is_visible:
            # Hide the widget completely when slide-out animation finishes
            self.hide()
            self.panel_hidden.emit()
        else:
            self.panel_shown.emit()

    def set_title(self, title):
        """Set the panel title.

        Args:
            title: Title text to display in the header
        """
        self.title_label.setText(title)

    def set_content(self, widget):
        """Set the content widget for the panel.

        Args:
            widget: QWidget to display in the panel content area
        """
        # Clear existing content
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        # Add new content
        self.content_layout.addWidget(widget)

    def show_panel(self):
        """Show the panel with slide-in animation."""
        if self._is_visible:
            return

        self._is_visible = True

        # Ensure panel is positioned and sized correctly
        self._update_geometry()

        # Make widget visible
        self.show()
        self.raise_()  # Bring to front

        # Calculate positions
        parent_rect = self.parent().rect()
        start_x = parent_rect.width()  # Start off-screen to the right
        end_x = parent_rect.width() - self.panel_width  # End position

        # Animate from right to visible position
        self.slide_animation.setStartValue(QtCore.QPoint(start_x, 0))
        self.slide_animation.setEndValue(QtCore.QPoint(end_x, 0))
        self.slide_animation.start()

    def hide_panel(self):
        """Hide the panel with slide-out animation."""
        if not self._is_visible:
            return

        self._is_visible = False

        # Calculate positions
        parent_rect = self.parent().rect()
        start_x = parent_rect.width() - self.panel_width  # Current position
        end_x = parent_rect.width()  # End off-screen to the right

        # Animate from current position to off-screen
        self.slide_animation.setStartValue(QtCore.QPoint(start_x, 0))
        self.slide_animation.setEndValue(QtCore.QPoint(end_x, 0))
        self.slide_animation.start()

    def toggle(self):
        """Toggle the panel visibility."""
        if self._is_visible:
            self.hide_panel()
        else:
            self.show_panel()

    def is_panel_visible(self):
        """Check if the panel is currently visible.

        Returns:
            bool: True if panel is visible, False otherwise
        """
        return self._is_visible

    def _update_geometry(self):
        """Update panel geometry to match parent size."""
        if not self.parent():
            return

        parent_rect = self.parent().rect()

        # Set panel size to full height and specified width
        self.setGeometry(
            parent_rect.width(),  # Start off-screen
            0,
            self.panel_width,
            parent_rect.height()
        )

    def resizeEvent(self, event):
        """Handle parent resize events."""
        super().resizeEvent(event)

        # Update panel position and size when parent is resized
        if self._is_visible and not self.slide_animation.state() == QtCore.QAbstractAnimation.Running:
            self._update_geometry()
            parent_rect = self.parent().rect()
            self.move(parent_rect.width() - self.panel_width, 0)

    def _on_dock_clicked(self):
        """Handle dock button click."""
        self.dock_requested.emit()

    def set_dock_button_visible(self, visible):
        """Set whether the dock button is visible.

        Args:
            visible: True to show, False to hide
        """
        if hasattr(self, 'dock_button'):
            self.dock_button.setVisible(visible)

    def set_dock_button_tooltip(self, tooltip):
        """Set the dock button tooltip.

        Args:
            tooltip: Tooltip text
        """
        if hasattr(self, 'dock_button'):
            self.dock_button.setToolTip(tooltip)

    def set_dock_button_icon(self, icon_text):
        """Set the dock button icon text.

        Args:
            icon_text: Unicode character or text for the button
        """
        if hasattr(self, 'dock_button'):
            self.dock_button.setText(icon_text)


class OverlayBackground(QtWidgets.QWidget):
    """Semi-transparent background overlay that appears behind the sliding panel."""

    clicked = QtCore.Signal()

    def __init__(self, parent=None, opacity=0.5):
        """Initialize the overlay background.

        Args:
            parent: Parent widget
            opacity: Background opacity (0.0 to 1.0, default: 0.5)
        """
        super().__init__(parent)

        self.opacity = opacity

        # Set up the widget
        self.setAutoFillBackground(True)
        self.hide()

        # Set semi-transparent black background
        palette = self.palette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(0, 0, 0, int(255 * opacity)))
        self.setPalette(palette)

        # Set window flags to allow click-through on transparent areas
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)

    def mousePressEvent(self, event):
        """Handle mouse press to emit clicked signal."""
        self.clicked.emit()
        super().mousePressEvent(event)

    def show_overlay(self):
        """Show the overlay background."""
        if not self.parent():
            return

        # Resize to match parent
        self.setGeometry(self.parent().rect())
        self.show()
        self.raise_()

    def hide_overlay(self):
        """Hide the overlay background."""
        self.hide()

    def resizeEvent(self, event):
        """Handle parent resize events."""
        super().resizeEvent(event)

        # Update size to match parent
        if self.parent() and self.isVisible():
            self.setGeometry(self.parent().rect())


class SlidingOverlayPanelWithBackground(QtWidgets.QWidget):
    """
    Combined sliding panel with semi-transparent background overlay.

    This widget combines SlidingOverlayPanel with OverlayBackground to provide
    a complete overlay solution with background dimming.
    """

    # Signals
    panel_shown = QtCore.Signal()
    panel_hidden = QtCore.Signal()
    dock_requested = QtCore.Signal()  # Emitted when dock button is clicked

    def __init__(self, parent=None, panel_width=400, animation_duration=300,
                 background_opacity=0.3, close_on_background_click=True, show_dock_button=False):
        """Initialize the sliding overlay panel with background.

        Args:
            parent: Parent widget
            panel_width: Width of the panel in pixels (default: 400)
            animation_duration: Animation duration in milliseconds (default: 300)
            background_opacity: Opacity of the background overlay (0.0 to 1.0, default: 0.3)
            close_on_background_click: Close panel when background is clicked (default: True)
            show_dock_button: Whether to show a dock button in the header (default: False)
        """
        super().__init__(parent)

        self.close_on_background_click = close_on_background_click

        # Create background overlay
        self.background = OverlayBackground(parent, opacity=background_opacity)
        if close_on_background_click:
            self.background.clicked.connect(self.hide_panel)

        # Create sliding panel with dock button support
        self.panel = SlidingOverlayPanel(parent, panel_width, animation_duration, show_dock_button)

        # Connect panel signals to our signals
        self.panel.panel_shown.connect(self.panel_shown.emit)
        self.panel.panel_hidden.connect(self.panel_hidden.emit)
        self.panel.dock_requested.connect(self.dock_requested.emit)

        # Connect to background hide when panel is hidden
        self.panel.panel_hidden.connect(self.background.hide_overlay)

    def set_title(self, title):
        """Set the panel title."""
        self.panel.set_title(title)

    def set_content(self, widget):
        """Set the panel content widget."""
        self.panel.set_content(widget)

    def show_panel(self):
        """Show the panel with background overlay."""
        self.background.show_overlay()
        self.panel.show_panel()

    def hide_panel(self):
        """Hide the panel and background overlay."""
        self.panel.hide_panel()
        # Background will be hidden when panel animation finishes

    def toggle(self):
        """Toggle the panel visibility."""
        if self.panel.is_panel_visible():
            self.hide_panel()
        else:
            self.show_panel()

    def is_panel_visible(self):
        """Check if the panel is currently visible."""
        return self.panel.is_panel_visible()

    def set_dock_button_visible(self, visible):
        """Set whether the dock button is visible."""
        self.panel.set_dock_button_visible(visible)

    def set_dock_button_tooltip(self, tooltip):
        """Set the dock button tooltip."""
        self.panel.set_dock_button_tooltip(tooltip)

    def set_dock_button_icon(self, icon_text):
        """Set the dock button icon text."""
        self.panel.set_dock_button_icon(icon_text)
