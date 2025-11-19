from PySide6 import QtWidgets, QtCore, QtGui
import logging

try:
    from .logger import logger
except (ImportError, ValueError, SystemError):
    logger = logging.getLogger("FFPackageManager")


class ImageViewerDialog(QtWidgets.QDialog):
    """Dialog for viewing an enlarged image with zoom and pan capabilities."""

    def __init__(self, version_data, sg_session, parent=None):
        super().__init__(parent)
        self.version_data = version_data
        self.sg_session = sg_session
        self.current_zoom = 1.0
        self.image_pixmap = None

        version_code = version_data.get('code', 'Image Viewer')
        self.setWindowTitle(f"Image Viewer - {version_code}")
        self.resize(1200, 800)

        self._setup_ui()
        self._load_full_image()

    def _setup_ui(self):
        """Setup the dialog UI."""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Splitter for viewer dock and details pane
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        # Left dock: Viewer elements
        viewer_dock = self._create_viewer_dock()
        self.splitter.addWidget(viewer_dock)

        # Right pane: Details panel
        self.details_pane = self._create_details_pane()
        self.splitter.addWidget(self.details_pane)

        # Set initial sizes (80% viewer, 20% details)
        self.splitter.setSizes([960, 240])
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        main_layout.addWidget(self.splitter)

    def _create_viewer_dock(self):
        """Create the left dock with all viewer elements."""
        viewer_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(viewer_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QtWidgets.QHBoxLayout()

        # Zoom controls
        zoom_in_btn = QtWidgets.QPushButton("Zoom In (+)")
        zoom_in_btn.clicked.connect(self._zoom_in)
        toolbar.addWidget(zoom_in_btn)

        zoom_out_btn = QtWidgets.QPushButton("Zoom Out (-)")
        zoom_out_btn.clicked.connect(self._zoom_out)
        toolbar.addWidget(zoom_out_btn)

        zoom_reset_btn = QtWidgets.QPushButton("Reset (0)")
        zoom_reset_btn.clicked.connect(self._zoom_reset)
        toolbar.addWidget(zoom_reset_btn)

        fit_btn = QtWidgets.QPushButton("Fit to Window")
        fit_btn.clicked.connect(self._fit_to_window)
        toolbar.addWidget(fit_btn)

        toolbar.addStretch()

        # Toggle details pane button
        self.toggle_details_btn = QtWidgets.QPushButton("Hide Details")
        self.toggle_details_btn.clicked.connect(self._toggle_details_pane)
        toolbar.addWidget(self.toggle_details_btn)

        # Zoom level label
        self.zoom_label = QtWidgets.QLabel("100%")
        self.zoom_label.setStyleSheet("font-weight: bold;")
        toolbar.addWidget(self.zoom_label)

        layout.addLayout(toolbar)

        # Graphics view for displaying image
        self.graphics_view = QtWidgets.QGraphicsView()
        self.graphics_scene = QtWidgets.QGraphicsScene()
        self.graphics_view.setScene(self.graphics_scene)
        self.graphics_view.setRenderHint(QtGui.QPainter.Antialiasing)
        self.graphics_view.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        self.graphics_view.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        self.graphics_view.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(30, 30, 30)))

        # Enable wheel zoom
        self.graphics_view.wheelEvent = self._wheel_event

        layout.addWidget(self.graphics_view)

        # Status bar with image info
        self.status_label = QtWidgets.QLabel("Loading...")
        self.status_label.setStyleSheet("padding: 5px; background-color: #2b2b2b;")
        layout.addWidget(self.status_label)

        # Close button
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

        return viewer_widget

    def _create_details_pane(self):
        """Create the details pane."""
        details_widget = QtWidgets.QWidget()
        details_layout = QtWidgets.QVBoxLayout(details_widget)
        details_layout.setContentsMargins(5, 5, 5, 5)

        # Title
        title_label = QtWidgets.QLabel("Selected Image Details")
        title_font = title_label.font()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        details_layout.addWidget(title_label)

        # Details text area
        self.details_text = QtWidgets.QTextEdit()
        self.details_text.setReadOnly(True)
        details_layout.addWidget(self.details_text)

        # Set minimum width for details pane
        details_widget.setMinimumWidth(250)

        # Populate with version data
        self._update_details()

        return details_widget

    def _toggle_details_pane(self):
        """Toggle the visibility of the details pane."""
        if self.details_pane.isVisible():
            self.details_pane.hide()
            self.toggle_details_btn.setText("Show Details")
        else:
            self.details_pane.show()
            self.toggle_details_btn.setText("Hide Details")

    def _update_details(self):
        """Update the details panel with version information."""
        details = f"<b>Version:</b> {self.version_data.get('code', 'Unknown')}<br>"
        details += f"<b>ID:</b> {self.version_data.get('id', 'N/A')}<br>"

        version_type = self.version_data.get('sg_version_type', '')
        if isinstance(version_type, dict):
            version_type = version_type.get('name', 'Unknown')
        details += f"<b>Type:</b> {version_type}<br>"

        status = self.version_data.get('sg_status_list', 'N/A')
        details += f"<b>Status:</b> {status}<br>"

        entity = self.version_data.get('entity', {})
        if entity:
            details += f"<b>Asset:</b> {entity.get('name', 'Unknown')}<br>"

        task = self.version_data.get('sg_task', {})
        if task:
            details += f"<b>Task:</b> {task.get('name', 'Unknown')}<br>"

        user = self.version_data.get('user', {})
        if user:
            details += f"<b>Created By:</b> {user.get('name', 'Unknown')}<br>"

        created_at = self.version_data.get('created_at', 'N/A')
        details += f"<b>Created:</b> {created_at}<br>"

        updated_at = self.version_data.get('updated_at', 'N/A')
        details += f"<b>Updated:</b> {updated_at}<br>"

        description = self.version_data.get('description', '')
        if description:
            details += f"<br><b>Description:</b><br>{description}"

        self.details_text.setHtml(details)

    def _update_details_with_image_info(self, width, height, size_kb):
        """Update the details panel with additional image information."""
        # Get current HTML
        current_html = self.details_text.toHtml()

        # Find the insertion point (after Updated field, before Description or at end)
        if "<b>Description:</b>" in current_html:
            # Insert before description
            parts = current_html.split("<b>Description:</b>")
            image_info = f"<br><b>Image Dimensions:</b> {width}x{height} pixels<br>"
            image_info += f"<b>File Size:</b> {size_kb:.1f} KB<br>"
            new_html = parts[0] + image_info + "<br><b>Description:</b>" + parts[1]
        else:
            # Append at end
            # Remove closing tags
            new_html = current_html.rstrip()
            if new_html.endswith("</body></html>"):
                new_html = new_html[:-14]
            image_info = f"<br><b>Image Dimensions:</b> {width}x{height} pixels<br>"
            image_info += f"<b>File Size:</b> {size_kb:.1f} KB"
            new_html += image_info + "</body></html>"

        self.details_text.setHtml(new_html)

    def _load_full_image(self):
        """Load the full-resolution image from ShotGrid."""
        try:
            # First try to get the uploaded movie/image
            image_url = None
            image_data = self.version_data.get('image')

            # Check for uploaded movie (could be an image file)
            uploaded_movie = self.version_data.get('sg_uploaded_movie')
            if uploaded_movie:
                if isinstance(uploaded_movie, dict):
                    image_url = uploaded_movie.get('url') or uploaded_movie.get('link_type')
                elif isinstance(uploaded_movie, str):
                    image_url = uploaded_movie

            # If no uploaded movie, use the thumbnail (scaled up)
            if not image_url and image_data:
                if isinstance(image_data, str):
                    image_url = image_data
                elif isinstance(image_data, dict):
                    image_url = image_data.get('url') or image_data.get('link_type')

            if not image_url:
                self.status_label.setText("No image available")
                return

            # Download image in background
            from PySide6.QtCore import QThread, QObject, Signal
            import requests

            class ImageLoader(QObject):
                finished = Signal(bytes)
                error = Signal(str)

                def __init__(self, url):
                    super().__init__()
                    self.url = url

                def run(self):
                    try:
                        response = requests.get(self.url, timeout=30)
                        if response.status_code == 200:
                            self.finished.emit(response.content)
                        else:
                            self.error.emit(f"HTTP {response.status_code}")
                    except Exception as e:
                        logger.error(f"Failed to download image: {e}")
                        self.error.emit(str(e))

            self.loader = ImageLoader(image_url)
            self.loader_thread = QThread()
            self.loader.moveToThread(self.loader_thread)
            self.loader_thread.started.connect(self.loader.run)
            self.loader.finished.connect(self._on_image_loaded)
            self.loader.error.connect(self._on_image_error)
            self.loader_thread.start()

        except Exception as e:
            logger.error(f"Error loading full image: {e}")
            self.status_label.setText(f"Error: {str(e)}")

    def _on_image_loaded(self, image_data):
        """Handle image loaded."""
        try:
            # Create pixmap from image data
            self.image_pixmap = QtGui.QPixmap()
            self.image_pixmap.loadFromData(image_data)

            if not self.image_pixmap.isNull():
                # Add to scene
                self.graphics_scene.clear()
                self.pixmap_item = self.graphics_scene.addPixmap(self.image_pixmap)

                # Fit to window initially
                self._fit_to_window()

                # Update status
                width = self.image_pixmap.width()
                height = self.image_pixmap.height()
                size_kb = len(image_data) / 1024
                self.status_label.setText(
                    f"Image: {width}x{height} pixels | Size: {size_kb:.1f} KB | "
                    f"Version: {self.version_data.get('code', 'Unknown')}"
                )

                # Update details with image dimensions
                self._update_details_with_image_info(width, height, size_kb)
            else:
                self.status_label.setText("Failed to load image")

            # Clean up thread
            if hasattr(self, 'loader_thread'):
                self.loader_thread.quit()
                self.loader_thread.wait()

        except Exception as e:
            logger.error(f"Error displaying image: {e}")
            self.status_label.setText(f"Error: {str(e)}")

    def _on_image_error(self, error_msg):
        """Handle image load error."""
        self.status_label.setText(f"Failed to load image: {error_msg}")

        # Clean up thread
        if hasattr(self, 'loader_thread'):
            self.loader_thread.quit()
            self.loader_thread.wait()

    def _wheel_event(self, event):
        """Handle mouse wheel for zooming."""
        # Zoom in/out based on wheel direction
        zoom_factor = 1.15

        if event.angleDelta().y() > 0:
            # Zoom in
            self.graphics_view.scale(zoom_factor, zoom_factor)
            self.current_zoom *= zoom_factor
        else:
            # Zoom out
            self.graphics_view.scale(1 / zoom_factor, 1 / zoom_factor)
            self.current_zoom /= zoom_factor

        self._update_zoom_label()

    def _zoom_in(self):
        """Zoom in the image."""
        zoom_factor = 1.25
        self.graphics_view.scale(zoom_factor, zoom_factor)
        self.current_zoom *= zoom_factor
        self._update_zoom_label()

    def _zoom_out(self):
        """Zoom out the image."""
        zoom_factor = 1.25
        self.graphics_view.scale(1 / zoom_factor, 1 / zoom_factor)
        self.current_zoom /= zoom_factor
        self._update_zoom_label()

    def _zoom_reset(self):
        """Reset zoom to 100%."""
        self.graphics_view.resetTransform()
        self.current_zoom = 1.0
        self._update_zoom_label()

    def _fit_to_window(self):
        """Fit image to window."""
        if self.image_pixmap and not self.image_pixmap.isNull():
            self.graphics_view.fitInView(
                self.graphics_scene.sceneRect(),
                QtCore.Qt.KeepAspectRatio
            )
            # Calculate the zoom level
            view_rect = self.graphics_view.viewport().rect()
            scene_rect = self.graphics_scene.sceneRect()

            x_ratio = view_rect.width() / scene_rect.width() if scene_rect.width() > 0 else 1
            y_ratio = view_rect.height() / scene_rect.height() if scene_rect.height() > 0 else 1
            self.current_zoom = min(x_ratio, y_ratio)
            self._update_zoom_label()

    def _update_zoom_label(self):
        """Update the zoom level label."""
        zoom_percent = int(self.current_zoom * 100)
        self.zoom_label.setText(f"{zoom_percent}%")

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        if event.key() == QtCore.Qt.Key_Plus or event.key() == QtCore.Qt.Key_Equal:
            self._zoom_in()
        elif event.key() == QtCore.Qt.Key_Minus:
            self._zoom_out()
        elif event.key() == QtCore.Qt.Key_0:
            self._zoom_reset()
        elif event.key() == QtCore.Qt.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)


class ThumbnailWidget(QtWidgets.QWidget):
    """Widget for displaying a single image thumbnail."""

    clicked = QtCore.Signal(dict)  # Emits version data when clicked

    def __init__(self, version_data, sg_session=None, parent=None):
        super().__init__(parent)
        self.version_data = version_data
        self.sg_session = sg_session
        self.selected = False

        self.setFixedSize(180, 200)
        self.setCursor(QtCore.Qt.PointingHandCursor)

        self._setup_ui()
        self._load_thumbnail()

    def _setup_ui(self):
        """Setup the thumbnail UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Thumbnail image placeholder
        self.thumbnail_label = QtWidgets.QLabel()
        self.thumbnail_label.setFixedSize(170, 140)
        self.thumbnail_label.setAlignment(QtCore.Qt.AlignCenter)
        self.thumbnail_label.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                border: 2px solid #444;
                border-radius: 4px;
            }
        """)

        # Set placeholder or load thumbnail
        self.thumbnail_label.setText("Loading...")
        self.thumbnail_label.setStyleSheet(self.thumbnail_label.styleSheet() + "color: #888;")

        layout.addWidget(self.thumbnail_label)

        # Version name
        version_code = self.version_data.get('code', 'Unknown')
        name_label = QtWidgets.QLabel(version_code)
        name_label.setWordWrap(True)
        name_label.setMaximumWidth(170)
        name_label.setAlignment(QtCore.Qt.AlignCenter)
        name_label.setStyleSheet("font-size: 11px; color: #ddd;")
        layout.addWidget(name_label)

        # Version type
        version_type = self.version_data.get('sg_version_type', '')
        if isinstance(version_type, dict):
            version_type = version_type.get('name', '')
        type_label = QtWidgets.QLabel(version_type or 'Unknown Type')
        type_label.setAlignment(QtCore.Qt.AlignCenter)
        type_label.setStyleSheet("font-size: 9px; color: #888;")
        layout.addWidget(type_label)

    def _load_thumbnail(self):
        """Load thumbnail from ShotGrid."""
        try:
            # Check if version has an image thumbnail
            image_data = self.version_data.get('image')

            if not image_data:
                self.thumbnail_label.setText("No Preview")
                return

            # If image_data is a URL string, download it
            if isinstance(image_data, str):
                thumbnail_url = image_data
            elif isinstance(image_data, dict):
                # Get URL from the dict
                thumbnail_url = image_data.get('url') or image_data.get('link_type')
            else:
                self.thumbnail_label.setText("No Preview")
                return

            if not thumbnail_url:
                self.thumbnail_label.setText("No Preview")
                return

            # Download thumbnail in a separate thread to avoid blocking UI
            from PySide6.QtCore import QThread, QObject, Signal
            import requests

            class ThumbnailLoader(QObject):
                finished = Signal(bytes)
                error = Signal()

                def __init__(self, url):
                    super().__init__()
                    self.url = url

                def run(self):
                    try:
                        response = requests.get(self.url, timeout=10)
                        if response.status_code == 200:
                            self.finished.emit(response.content)
                        else:
                            self.error.emit()
                    except Exception as e:
                        logger.error(f"Failed to download thumbnail: {e}")
                        self.error.emit()

            # Load thumbnail in background
            self.loader = ThumbnailLoader(thumbnail_url)
            self.loader_thread = QThread()
            self.loader.moveToThread(self.loader_thread)
            self.loader_thread.started.connect(self.loader.run)
            self.loader.finished.connect(self._on_thumbnail_loaded)
            self.loader.error.connect(self._on_thumbnail_error)
            self.loader_thread.start()

        except Exception as e:
            logger.error(f"Error loading thumbnail: {e}")
            self.thumbnail_label.setText("No Preview")

    def _on_thumbnail_loaded(self, image_data):
        """Handle thumbnail loaded."""
        try:
            # Create pixmap from image data
            pixmap = QtGui.QPixmap()
            pixmap.loadFromData(image_data)

            if not pixmap.isNull():
                # Scale to fit label while maintaining aspect ratio
                scaled_pixmap = pixmap.scaled(
                    170, 140,
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation
                )
                self.thumbnail_label.setPixmap(scaled_pixmap)
                self.thumbnail_label.setText("")
            else:
                self.thumbnail_label.setText("No Preview")

            # Clean up thread
            if hasattr(self, 'loader_thread'):
                self.loader_thread.quit()
                self.loader_thread.wait()

        except Exception as e:
            logger.error(f"Error displaying thumbnail: {e}")
            self.thumbnail_label.setText("No Preview")

    def _on_thumbnail_error(self):
        """Handle thumbnail load error."""
        self.thumbnail_label.setText("No Preview")

        # Clean up thread
        if hasattr(self, 'loader_thread'):
            self.loader_thread.quit()
            self.loader_thread.wait()

    def mousePressEvent(self, event):
        """Handle mouse press to select thumbnail."""
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit(self.version_data)

    def mouseDoubleClickEvent(self, event):
        """Handle double-click to open enlarged view."""
        if event.button() == QtCore.Qt.LeftButton:
            self._open_enlarged_view()

    def _open_enlarged_view(self):
        """Open an enlarged view dialog for this image."""
        dialog = ImageViewerDialog(self.version_data, self.sg_session, self)
        dialog.exec()

    def set_selected(self, selected):
        """Set the selected state."""
        self.selected = selected
        if selected:
            self.thumbnail_label.setStyleSheet("""
                QLabel {
                    background-color: #2b2b2b;
                    border: 2px solid #4a9eff;
                    border-radius: 4px;
                }
            """)
        else:
            self.thumbnail_label.setStyleSheet("""
                QLabel {
                    background-color: #2b2b2b;
                    border: 2px solid #444;
                    border-radius: 4px;
                }
            """)


class ImageViewerWidget(QtWidgets.QWidget):
    """Widget for viewing image versions with thumbnails and grouping."""

    def __init__(self, sg_session, parent=None):
        super().__init__(parent)
        self.sg_session = sg_session
        self.current_project_id = None
        self.all_versions = []
        self.filtered_versions = []
        self.thumbnail_widgets = []
        self.selected_thumbnail = None

        # Filter states
        self.filter_states = {
            'Concept Art': True,
            'Storyboard': True,
            'Reference': True,
            'Video': True
        }

        # Grouping state
        self.grouping_mode = 'None'  # 'None', 'Asset', 'Scene'

        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI with two docks."""
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create splitter for two docks
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        # Left dock: Thumbnails with filters
        left_dock = self._create_thumbnail_dock()
        self.splitter.addWidget(left_dock)

        # Right dock: Grouping options
        right_dock = self._create_grouping_dock()
        self.splitter.addWidget(right_dock)

        # Set initial sizes (70% thumbnails, 30% grouping)
        self.splitter.setSizes([700, 300])
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        main_layout.addWidget(self.splitter)

    def _create_thumbnail_dock(self):
        """Create the left dock with thumbnails and filters."""
        dock_widget = QtWidgets.QWidget()
        dock_layout = QtWidgets.QVBoxLayout(dock_widget)
        dock_layout.setContentsMargins(5, 5, 5, 5)

        # Header with title and filter controls
        header_layout = QtWidgets.QHBoxLayout()

        title_label = QtWidgets.QLabel("Image Thumbnails")
        title_font = title_label.font()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # Filter label
        filter_label = QtWidgets.QLabel("Filter:")
        header_layout.addWidget(filter_label)

        # Filter checkboxes
        self.filter_checkboxes = {}
        for filter_type in ['Concept Art', 'Storyboard', 'Reference', 'Video']:
            checkbox = QtWidgets.QCheckBox(filter_type)
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(lambda state, ft=filter_type: self._on_filter_changed(ft, state))
            header_layout.addWidget(checkbox)
            self.filter_checkboxes[filter_type] = checkbox

        dock_layout.addLayout(header_layout)

        # Thumbnail scroll area
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        # Container for thumbnails
        self.thumbnail_container = QtWidgets.QWidget()
        self.thumbnail_layout = QtWidgets.QGridLayout(self.thumbnail_container)
        self.thumbnail_layout.setSpacing(10)
        self.thumbnail_layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)

        scroll_area.setWidget(self.thumbnail_container)
        dock_layout.addWidget(scroll_area)

        return dock_widget

    def _create_grouping_dock(self):
        """Create the right dock with grouping options."""
        dock_widget = QtWidgets.QWidget()
        dock_layout = QtWidgets.QVBoxLayout(dock_widget)
        dock_layout.setContentsMargins(5, 5, 5, 5)

        # Header
        title_label = QtWidgets.QLabel("Grouping & Details")
        title_font = title_label.font()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        dock_layout.addWidget(title_label)

        # Grouping options
        group_box = QtWidgets.QGroupBox("Group By")
        group_layout = QtWidgets.QVBoxLayout(group_box)

        self.grouping_buttons = QtWidgets.QButtonGroup()

        # None (no grouping)
        none_radio = QtWidgets.QRadioButton("None")
        none_radio.setChecked(True)
        none_radio.toggled.connect(lambda checked: checked and self._on_grouping_changed('None'))
        self.grouping_buttons.addButton(none_radio)
        group_layout.addWidget(none_radio)

        # Group by Asset
        asset_radio = QtWidgets.QRadioButton("Asset Name")
        asset_radio.toggled.connect(lambda checked: checked and self._on_grouping_changed('Asset'))
        self.grouping_buttons.addButton(asset_radio)
        group_layout.addWidget(asset_radio)

        # Group by Scene
        scene_radio = QtWidgets.QRadioButton("Scene")
        scene_radio.toggled.connect(lambda checked: checked and self._on_grouping_changed('Scene'))
        self.grouping_buttons.addButton(scene_radio)
        group_layout.addWidget(scene_radio)

        dock_layout.addWidget(group_box)

        # Selected image details
        details_box = QtWidgets.QGroupBox("Selected Image Details")
        details_layout = QtWidgets.QVBoxLayout(details_box)

        self.details_text = QtWidgets.QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(200)
        self.details_text.setText("No image selected")
        details_layout.addWidget(self.details_text)

        dock_layout.addWidget(details_box)

        dock_layout.addStretch()

        return dock_widget

    def _on_filter_changed(self, filter_type, state):
        """Handle filter checkbox changes."""
        self.filter_states[filter_type] = (state == QtCore.Qt.Checked)
        self._apply_filters()

    def _on_grouping_changed(self, grouping_mode):
        """Handle grouping mode changes."""
        self.grouping_mode = grouping_mode
        logger.info(f"Grouping mode changed to: {grouping_mode}")
        self._rebuild_thumbnails()

    def _apply_filters(self):
        """Apply current filters and rebuild thumbnails."""
        logger.info(f"Applying filters: {self.filter_states}")

        # Filter versions based on type
        self.filtered_versions = []
        for version in self.all_versions:
            version_type = self._get_version_type(version)
            if self.filter_states.get(version_type, True):
                self.filtered_versions.append(version)

        logger.info(f"Filtered versions: {len(self.filtered_versions)} of {len(self.all_versions)}")
        self._rebuild_thumbnails()

    def _get_version_type(self, version):
        """Get the type category for a version."""
        sg_version_type = version.get('sg_version_type', '')
        if isinstance(sg_version_type, dict):
            version_type = sg_version_type.get('name', '').lower()
        else:
            version_type = str(sg_version_type).lower()

        # Map to filter categories
        if 'concept' in version_type or 'art' in version_type:
            return 'Concept Art'
        elif 'storyboard' in version_type:
            return 'Storyboard'
        elif 'reference' in version_type or 'ref' in version_type:
            return 'Reference'
        elif 'video' in version_type or 'movie' in version_type:
            return 'Video'
        else:
            # Default to Concept Art if unknown
            return 'Concept Art'

    def _rebuild_thumbnails(self):
        """Rebuild the thumbnail grid."""
        # Clear existing thumbnails
        for thumbnail in self.thumbnail_widgets:
            thumbnail.deleteLater()
        self.thumbnail_widgets.clear()

        # Clear layout
        while self.thumbnail_layout.count():
            item = self.thumbnail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add thumbnails based on grouping
        if self.grouping_mode == 'None':
            self._add_thumbnails_flat()
        elif self.grouping_mode == 'Asset':
            self._add_thumbnails_grouped_by_asset()
        elif self.grouping_mode == 'Scene':
            self._add_thumbnails_grouped_by_scene()

    def _add_thumbnails_flat(self):
        """Add thumbnails in a flat grid (no grouping)."""
        columns = 4  # Number of thumbnails per row

        for idx, version in enumerate(self.filtered_versions):
            row = idx // columns
            col = idx % columns

            thumbnail = ThumbnailWidget(version, self.sg_session, self)
            thumbnail.clicked.connect(self._on_thumbnail_clicked)
            self.thumbnail_layout.addWidget(thumbnail, row, col)
            self.thumbnail_widgets.append(thumbnail)

    def _add_thumbnails_grouped_by_asset(self):
        """Add thumbnails grouped by asset name."""
        # Group versions by asset/entity
        grouped = {}
        for version in self.filtered_versions:
            entity = version.get('entity', {})
            if entity:
                entity_name = entity.get('name', 'Unknown')
            else:
                entity_name = 'No Asset'

            if entity_name not in grouped:
                grouped[entity_name] = []
            grouped[entity_name].append(version)

        # Add grouped thumbnails
        current_row = 0
        for asset_name in sorted(grouped.keys()):
            # Add asset header
            header_label = QtWidgets.QLabel(f"Asset: {asset_name}")
            header_label.setStyleSheet("font-weight: bold; font-size: 11px; padding: 5px; background-color: #3a3a3a;")
            self.thumbnail_layout.addWidget(header_label, current_row, 0, 1, 4)
            current_row += 1

            # Add thumbnails for this asset
            versions = grouped[asset_name]
            for idx, version in enumerate(versions):
                col = idx % 4
                if col == 0 and idx > 0:
                    current_row += 1

                thumbnail = ThumbnailWidget(version, self.sg_session, self)
                thumbnail.clicked.connect(self._on_thumbnail_clicked)
                self.thumbnail_layout.addWidget(thumbnail, current_row, col)
                self.thumbnail_widgets.append(thumbnail)

            current_row += 1

    def _add_thumbnails_grouped_by_scene(self):
        """Add thumbnails grouped by scene."""
        # Group versions by task/scene
        grouped = {}
        for version in self.filtered_versions:
            task = version.get('sg_task', {})
            if task:
                scene_name = task.get('name', 'Unknown Scene')
            else:
                scene_name = 'No Scene'

            if scene_name not in grouped:
                grouped[scene_name] = []
            grouped[scene_name].append(version)

        # Add grouped thumbnails
        current_row = 0
        for scene_name in sorted(grouped.keys()):
            # Add scene header
            header_label = QtWidgets.QLabel(f"Scene: {scene_name}")
            header_label.setStyleSheet("font-weight: bold; font-size: 11px; padding: 5px; background-color: #3a3a3a;")
            self.thumbnail_layout.addWidget(header_label, current_row, 0, 1, 4)
            current_row += 1

            # Add thumbnails for this scene
            versions = grouped[scene_name]
            for idx, version in enumerate(versions):
                col = idx % 4
                if col == 0 and idx > 0:
                    current_row += 1

                thumbnail = ThumbnailWidget(version, self.sg_session, self)
                thumbnail.clicked.connect(self._on_thumbnail_clicked)
                self.thumbnail_layout.addWidget(thumbnail, current_row, col)
                self.thumbnail_widgets.append(thumbnail)

            current_row += 1

    def _on_thumbnail_clicked(self, version_data):
        """Handle thumbnail click."""
        logger.info(f"Thumbnail clicked: {version_data.get('code')}")

        # Deselect previous
        if self.selected_thumbnail:
            self.selected_thumbnail.set_selected(False)

        # Select new
        for thumbnail in self.thumbnail_widgets:
            if thumbnail.version_data.get('id') == version_data.get('id'):
                thumbnail.set_selected(True)
                self.selected_thumbnail = thumbnail
                break

        # Update details
        self._update_details(version_data)

    def _update_details(self, version_data):
        """Update the details panel with version information."""
        details = f"<b>Version:</b> {version_data.get('code', 'Unknown')}<br>"
        details += f"<b>ID:</b> {version_data.get('id', 'N/A')}<br>"

        version_type = version_data.get('sg_version_type', '')
        if isinstance(version_type, dict):
            version_type = version_type.get('name', 'Unknown')
        details += f"<b>Type:</b> {version_type}<br>"

        status = version_data.get('sg_status_list', 'N/A')
        details += f"<b>Status:</b> {status}<br>"

        entity = version_data.get('entity', {})
        if entity:
            details += f"<b>Asset:</b> {entity.get('name', 'Unknown')}<br>"

        task = version_data.get('sg_task', {})
        if task:
            details += f"<b>Task:</b> {task.get('name', 'Unknown')}<br>"

        user = version_data.get('user', {})
        if user:
            details += f"<b>Created By:</b> {user.get('name', 'Unknown')}<br>"

        created_at = version_data.get('created_at', 'N/A')
        details += f"<b>Created:</b> {created_at}<br>"

        description = version_data.get('description', '')
        if description:
            details += f"<br><b>Description:</b><br>{description}"

        self.details_text.setHtml(details)

    def load_project_versions(self, project_id):
        """Load all image versions for the given project."""
        self.current_project_id = project_id

        if not project_id or not self.sg_session:
            logger.info("No project ID or SG session")
            self.all_versions = []
            self._rebuild_thumbnails()
            return

        logger.info(f"Loading image versions for project {project_id}")

        # Get all image versions for the project
        self.all_versions = self.sg_session.get_all_image_versions_for_project(project_id)
        logger.info(f"Loaded {len(self.all_versions)} image versions for project")

        # Apply filters and rebuild
        self._apply_filters()

    def _is_image_version(self, version):
        """Check if version is an image type."""
        sg_version_type = version.get('sg_version_type')

        if sg_version_type:
            if isinstance(sg_version_type, dict):
                version_type = sg_version_type.get('name', '').lower()
            else:
                version_type = str(sg_version_type).lower()

            # Check for image-related keywords
            return any(keyword in version_type for keyword in [
                'concept', 'art', 'storyboard', 'reference', 'image', 'ref', 'video', 'movie'
            ])

        # Fallback to task/code checking
        code = version.get('code', '').lower()
        task = version.get('sg_task', {})
        task_name = task.get('name', '').lower() if task else ''

        image_keywords = ['concept', 'art', 'storyboard', 'reference', 'image', 'ref', 'video', 'movie']
        return any(keyword in code or keyword in task_name for keyword in image_keywords)

    def clear(self):
        """Clear all thumbnails."""
        self.all_versions = []
        self.filtered_versions = []
        self._rebuild_thumbnails()
        self.details_text.setText("No image selected")
