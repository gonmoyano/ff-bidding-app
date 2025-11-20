from PySide6 import QtWidgets, QtCore, QtGui
import logging

try:
    from .logger import logger
    from .folder_pane_widget import FolderPaneWidget
except (ImportError, ValueError, SystemError):
    logger = logging.getLogger("FFPackageManager")
    from folder_pane_widget import FolderPaneWidget


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
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

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

        # Splitter for image viewer and details pane
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)

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

        self.splitter.addWidget(self.graphics_view)

        # Right pane: Details panel
        self.details_pane = self._create_details_pane()
        self.splitter.addWidget(self.details_pane)

        # Set initial sizes (80% image, 20% details)
        self.splitter.setSizes([960, 240])
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        layout.addWidget(self.splitter)

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
        self.folders_containing_this = []  # List of folder names containing this image

        self.setFixedSize(180, 200)
        self.setCursor(QtCore.Qt.PointingHandCursor)

        # Enable drag
        self.drag_start_position = None

        # Tooltip timer for hover delay
        self.tooltip_timer = QtCore.QTimer()
        self.tooltip_timer.setSingleShot(True)
        self.tooltip_timer.timeout.connect(self._show_tooltip)

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
            self.drag_start_position = event.pos()
            self.clicked.emit(self.version_data)

    def mouseMoveEvent(self, event):
        """Handle mouse move to start drag operation."""
        if not (event.buttons() & QtCore.Qt.LeftButton):
            return
        if not self.drag_start_position:
            return

        # Check if we've moved far enough to start a drag
        if (event.pos() - self.drag_start_position).manhattanLength() < QtWidgets.QApplication.startDragDistance():
            return

        # Start drag operation
        drag = QtGui.QDrag(self)
        mime_data = QtCore.QMimeData()

        # Store the version ID in mime data
        version_id = self.version_data.get('id')
        if version_id:
            mime_data.setData("application/x-image-version-id", str(version_id).encode())
            drag.setMimeData(mime_data)

            # Set drag pixmap (use thumbnail if available)
            if self.thumbnail_label.pixmap():
                pixmap = self.thumbnail_label.pixmap().scaled(
                    80, 80,
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation
                )
                drag.setPixmap(pixmap)
                drag.setHotSpot(pixmap.rect().center())

            # Execute drag
            drag.exec(QtCore.Qt.CopyAction)

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
        self._update_border()

    def set_folders_containing(self, folder_names):
        """Set which folders contain this image.

        Args:
            folder_names: List of folder names that contain this image
        """
        self.folders_containing_this = folder_names
        self._update_border()

    def _update_border(self):
        """Update the border based on selection and folder states."""
        # Priority: selected > in folders > default
        if self.selected:
            # Blue border for selection
            border_color = "#4a9eff"
        elif len(self.folders_containing_this) >= 2:
            # Orange border for 2+ folders
            border_color = "#ff8c00"
        elif len(self.folders_containing_this) == 1:
            # Green border for 1 folder
            border_color = "#00cc00"
        else:
            # Default border
            border_color = "#444"

        self.thumbnail_label.setStyleSheet(f"""
            QLabel {{
                background-color: #2b2b2b;
                border: 2px solid {border_color};
                border-radius: 4px;
            }}
        """)

    def _show_tooltip(self):
        """Show tooltip with folder information."""
        if self.folders_containing_this:
            folder_list = "\n".join([f"  • {name}" for name in self.folders_containing_this])
            tooltip_text = f"Dropped to {len(self.folders_containing_this)} folder(s):\n{folder_list}"
            QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), tooltip_text, self)

    def enterEvent(self, event):
        """Handle mouse enter to show tooltip after delay."""
        super().enterEvent(event)
        if self.folders_containing_this:
            self.tooltip_timer.start(1000)  # 1 second delay

    def leaveEvent(self, event):
        """Handle mouse leave to cancel tooltip."""
        super().leaveEvent(event)
        self.tooltip_timer.stop()
        QtWidgets.QToolTip.hideText()


class ImageViewerWidget(QtWidgets.QWidget):
    """Widget for viewing image versions with thumbnails."""

    def __init__(self, sg_session, parent=None, packages_tab=None):
        super().__init__(parent)
        self.sg_session = sg_session
        self.packages_tab = packages_tab  # Reference to PackagesTab
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

        # Flags to prevent concurrent operations
        self._is_rebuilding = False
        self._is_rearranging = False

        # Debounce timer for resize events
        self.resize_timer = QtCore.QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self._rebuild_thumbnails_delayed)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI with thumbnails and filters."""
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create splitter for thumbnails and folder pane
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        # Left: Thumbnails with filters
        self.thumbnail_dock = self._create_thumbnail_dock()
        self.splitter.addWidget(self.thumbnail_dock)

        # Right: Folder pane
        self.folder_pane = FolderPaneWidget(self)
        self.splitter.addWidget(self.folder_pane)

        # Connect folder drop signal to update thumbnail states
        self.folder_pane.imageDropped.connect(self.update_thumbnail_states)

        # Set initial sizes (70% thumbnails, 30% folder pane)
        self.splitter.setSizes([700, 300])
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        # Connect splitter moved signal to adjust thumbnail columns
        self.splitter.splitterMoved.connect(self._on_splitter_moved)

        main_layout.addWidget(self.splitter)

    def _on_splitter_moved(self, pos, index):
        """Handle splitter moved to adjust thumbnail grid."""
        # Use debounced timer to avoid rebuilding during drag
        self.resize_timer.stop()
        self.resize_timer.start(500)  # Wait 500ms after last move

    def _rebuild_thumbnails_delayed(self):
        """Rearrange thumbnails after resize timer expires."""
        # Only rearrange if we actually have thumbnails
        if self.thumbnail_widgets:
            self._rearrange_thumbnails()

    def _create_thumbnail_dock(self):
        """Create the thumbnail view with filters."""
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


    def _on_filter_changed(self, filter_type, state):
        """Handle filter checkbox changes."""
        self.filter_states[filter_type] = (state == QtCore.Qt.Checked)
        self._apply_filters()


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

    def _rearrange_thumbnails(self):
        """Rearrange existing thumbnails in grid without recreating them."""
        # Prevent concurrent operations
        if self._is_rearranging or self._is_rebuilding:
            return

        try:
            self._is_rearranging = True

            if not hasattr(self, 'thumbnail_container') or not self.thumbnail_container:
                return

            if not self.thumbnail_widgets:
                return

            # Calculate new column count
            thumbnail_width = 180 + 10
            available_width = self.thumbnail_container.width()

            if available_width <= 0:
                available_width = 800

            columns = max(1, available_width // thumbnail_width)

            if columns == 0:
                columns = 2

            # Rearrange existing widgets in layout
            for idx, thumbnail in enumerate(self.thumbnail_widgets):
                row = idx // columns
                col = idx % columns

                # Remove from current position and add to new position
                self.thumbnail_layout.removeWidget(thumbnail)
                self.thumbnail_layout.addWidget(thumbnail, row, col)

        except Exception as e:
            logger.error(f"Error rearranging thumbnails: {e}", exc_info=True)
        finally:
            self._is_rearranging = False

    def _rebuild_thumbnails(self):
        """Rebuild the thumbnail grid (only for filter/content changes)."""
        # Prevent concurrent operations
        if self._is_rebuilding or self._is_rearranging:
            return

        try:
            self._is_rebuilding = True

            # Disconnect signals before clearing to prevent issues
            for thumbnail in self.thumbnail_widgets:
                try:
                    thumbnail.clicked.disconnect()
                except:
                    pass
                thumbnail.deleteLater()
            self.thumbnail_widgets.clear()

            # Clear layout
            while self.thumbnail_layout.count():
                item = self.thumbnail_layout.takeAt(0)
                if item.widget():
                    widget = item.widget()
                    widget.setParent(None)
                    widget.deleteLater()

            # Process pending delete events
            QtCore.QCoreApplication.processEvents()

            # Add thumbnails in flat layout
            self._add_thumbnails_flat()
        except Exception as e:
            logger.error(f"Error rebuilding thumbnails: {e}", exc_info=True)
        finally:
            self._is_rebuilding = False

    def _add_thumbnails_flat(self):
        """Add thumbnails in a flat grid (no grouping)."""
        # Safety check
        if not hasattr(self, 'thumbnail_container') or not self.thumbnail_container:
            logger.warning("Thumbnail container not available")
            return

        # Calculate columns based on available width
        # Each thumbnail is 180px wide + 10px spacing
        thumbnail_width = 180 + 10
        available_width = self.thumbnail_container.width()

        # Safety check for width
        if available_width <= 0:
            available_width = 800  # Reasonable default

        # Calculate columns dynamically, minimum 1, maximum reasonable number
        columns = max(1, available_width // thumbnail_width)

        # If columns is 0 or container width is too small, use a default
        if columns == 0 or available_width < thumbnail_width:
            columns = 2  # Default fallback

        for idx, version in enumerate(self.filtered_versions):
            row = idx // columns
            col = idx % columns

            thumbnail = ThumbnailWidget(version, self.sg_session, self)
            thumbnail.clicked.connect(self._on_thumbnail_clicked)
            self.thumbnail_layout.addWidget(thumbnail, row, col)
            self.thumbnail_widgets.append(thumbnail)


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

    def update_folder_pane(self):
        """Update the folder pane with assets and scenes from VFX Breakdown."""
        if not self.packages_tab:
            logger.info("No packages_tab reference, skipping folder pane update")
            return

        # Get breakdown widget from packages_tab
        breakdown_widget = getattr(self.packages_tab, 'breakdown_widget', None)
        if not breakdown_widget:
            logger.info("No breakdown_widget found")
            return

        # Get breakdown model
        model = getattr(breakdown_widget, 'model', None)
        if not model:
            logger.info("No model found in breakdown_widget")
            return

        # Get all bidding scenes data
        all_scenes = getattr(model, 'all_bidding_scenes_data', [])
        if not all_scenes:
            logger.info("No bidding scenes data available")
            return

        # Extract unique assets and scenes
        unique_assets = set()
        unique_scenes = set()

        for scene in all_scenes:
            # Extract assets from sg_bid_assets
            bid_assets = scene.get('sg_bid_assets', [])
            if bid_assets:
                if isinstance(bid_assets, list):
                    for asset in bid_assets:
                        if isinstance(asset, dict):
                            asset_name = asset.get('name')
                            if asset_name:
                                unique_assets.add(asset_name)
                        elif isinstance(asset, str):
                            unique_assets.add(asset)

            # Extract scene code from sg_sequence_code
            scene_code = scene.get('sg_sequence_code')
            if scene_code:
                if isinstance(scene_code, str):
                    unique_scenes.add(scene_code)
                elif isinstance(scene_code, dict):
                    scene_name = scene_code.get('name')
                    if scene_name:
                        unique_scenes.add(scene_name)

        logger.info(f"Found {len(unique_assets)} unique assets and {len(unique_scenes)} unique scenes")

        # Update folder pane
        self.folder_pane.set_assets(list(unique_assets))
        self.folder_pane.set_scenes(list(unique_scenes))

        # Load saved mappings if available
        self._load_folder_mappings()

    def _load_folder_mappings(self):
        """Load saved image-to-folder mappings from settings."""
        if not self.packages_tab:
            return

        # Try to get mappings from current package
        current_package = getattr(self.packages_tab, 'current_package_name', None)
        if not current_package:
            return

        packages = getattr(self.packages_tab, 'packages', {})
        package_data = packages.get(current_package, {})
        folder_mappings = package_data.get('folder_mappings', None)

        if folder_mappings:
            self.folder_pane.load_folder_mappings(folder_mappings)
            logger.info("Loaded folder mappings from package")
            # Update thumbnail states to reflect loaded mappings
            self.update_thumbnail_states()

    def save_folder_mappings(self):
        """Save image-to-folder mappings to current package."""
        if not self.packages_tab:
            return

        current_package = getattr(self.packages_tab, 'current_package_name', None)
        if not current_package:
            return

        packages = getattr(self.packages_tab, 'packages', {})
        if current_package not in packages:
            return

        # Get mappings from folder pane
        mappings = self.folder_pane.get_folder_mappings()

        # Save to package data
        packages[current_package]['folder_mappings'] = mappings
        logger.info("Saved folder mappings to package")

    def update_thumbnail_states(self):
        """Update all thumbnail border states based on folder mappings."""
        if not self.folder_pane:
            return

        # Get current mappings
        mappings = self.folder_pane.get_folder_mappings()

        # Build reverse mapping: image_id -> list of folder names
        image_to_folders = {}

        # Check assets
        for asset_name, image_ids in mappings.get('assets', {}).items():
            for image_id in image_ids:
                if image_id not in image_to_folders:
                    image_to_folders[image_id] = []
                image_to_folders[image_id].append(f"Asset: {asset_name}")

        # Check scenes
        for scene_code, image_ids in mappings.get('scenes', {}).items():
            for image_id in image_ids:
                if image_id not in image_to_folders:
                    image_to_folders[image_id] = []
                image_to_folders[image_id].append(f"Scene: {scene_code}")

        # Update all thumbnails
        for thumbnail in self.thumbnail_widgets:
            image_id = thumbnail.version_data.get('id')
            folders = image_to_folders.get(image_id, [])
            thumbnail.set_folders_containing(folders)
