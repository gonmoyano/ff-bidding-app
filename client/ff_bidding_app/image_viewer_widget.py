from PySide6 import QtWidgets, QtCore, QtGui
import logging
import os

try:
    from .logger import logger
    from .folder_pane_widget import FolderPaneWidget
    from .sliding_overlay_panel import SlidingOverlayPanel
except (ImportError, ValueError, SystemError):
    logger = logging.getLogger("FFPackageManager")
    from folder_pane_widget import FolderPaneWidget
    from sliding_overlay_panel import SlidingOverlayPanel


class UploadTypeDialog(QtWidgets.QDialog):
    """Dialog for selecting the type of image to upload."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_type = None
        self.setWindowTitle("Select Image Type")
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Title
        title_label = QtWidgets.QLabel("Select the type of image you're uploading:")
        title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(title_label)

        # Type buttons
        button_layout = QtWidgets.QVBoxLayout()
        button_layout.setSpacing(5)

        types = [
            ("Concept Art", "concept_art"),
            ("Storyboard", "storyboard"),
            ("Reference", "reference"),
            ("Video", "video")
        ]

        for label, type_value in types:
            btn = QtWidgets.QPushButton(label)
            btn.setMinimumHeight(40)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3a3a3a;
                    color: white;
                    border: 1px solid #555;
                    border-radius: 4px;
                    padding: 8px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #4a9eff;
                    border: 1px solid #5eb3ff;
                }
            """)
            btn.clicked.connect(lambda checked, t=type_value: self._on_type_selected(t))
            button_layout.addWidget(btn)

        layout.addLayout(button_layout)

        # Cancel button
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)
        layout.addWidget(cancel_btn)

        self.setMinimumWidth(300)

    def _on_type_selected(self, type_value):
        """Handle type selection."""
        self.selected_type = type_value
        self.accept()

    def get_selected_type(self):
        """Get the selected type."""
        return self.selected_type


class UploadThumbnailWidget(QtWidgets.QWidget):
    """Widget for uploading new images to ShotGrid."""

    imageUploaded = QtCore.Signal(dict)  # Emits new version data when uploaded

    def __init__(self, sg_session, project_id, parent=None):
        super().__init__(parent)
        self.sg_session = sg_session
        self.project_id = project_id
        self.setFixedSize(180, 200)
        self.setAcceptDrops(True)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self._setup_ui()

    def _setup_ui(self):
        """Setup the upload widget UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Upload area
        upload_area = QtWidgets.QLabel()
        upload_area.setFixedSize(170, 140)
        upload_area.setAlignment(QtCore.Qt.AlignCenter)
        upload_area.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                border: 2px dashed #4a9eff;
                border-radius: 4px;
                color: #888;
                font-size: 11px;
            }
        """)
        upload_area.setText("Drag and drop\nor click to\nupload image")
        upload_area.setWordWrap(True)
        layout.addWidget(upload_area)

        # Upload icon (optional - using text for now)
        icon_label = QtWidgets.QLabel("⬆")
        icon_label.setAlignment(QtCore.Qt.AlignCenter)
        icon_label.setStyleSheet("color: #4a9eff; font-size: 24px;")

        # Add icon to upload area
        icon_layout = QtWidgets.QVBoxLayout(upload_area)
        icon_layout.setContentsMargins(0, 20, 0, 0)
        icon_layout.addWidget(icon_label)
        icon_layout.addStretch()

        # Label
        label = QtWidgets.QLabel("Upload New Image")
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setStyleSheet("font-size: 10px; color: #aaa;")
        layout.addWidget(label)

    def mousePressEvent(self, event):
        """Handle mouse press to open file browser."""
        if event.button() == QtCore.Qt.LeftButton:
            self._browse_for_file()
        super().mousePressEvent(event)

    def dragEnterEvent(self, event):
        """Handle drag enter event."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("background-color: rgba(74, 159, 255, 50);")
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        """Handle drag leave event."""
        self.setStyleSheet("")

    def dropEvent(self, event):
        """Handle drop event."""
        self.setStyleSheet("")
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                file_path = urls[0].toLocalFile()
                if self._is_valid_image(file_path):
                    event.acceptProposedAction()
                    self._upload_image(file_path)
                else:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Invalid File",
                        "Please drop a valid image file (PNG, JPG, JPEG, GIF, BMP, TIFF)"
                    )
        else:
            event.ignore()

    def _browse_for_file(self):
        """Open file browser to select an image."""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Image to Upload",
            "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.tiff *.tif);;All Files (*)"
        )

        if file_path:
            self._upload_image(file_path)

    def _is_valid_image(self, file_path):
        """Check if the file is a valid image."""
        valid_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif']
        _, ext = os.path.splitext(file_path.lower())
        return ext in valid_extensions

    def _upload_image(self, file_path):
        """Upload the image to ShotGrid.

        Args:
            file_path: Path to the image file to upload
        """
        # Show type selection dialog
        dialog = UploadTypeDialog(self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return

        selected_type = dialog.get_selected_type()
        if not selected_type:
            return

        # Show progress dialog
        progress = QtWidgets.QProgressDialog(
            "Uploading image to ShotGrid...",
            "Cancel",
            0, 0,
            self
        )
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        try:
            # Map type to ShotGrid version type
            type_mapping = {
                'concept_art': 'Concept Art',
                'storyboard': 'Storyboard',
                'reference': 'Reference',
                'video': 'Video'
            }
            sg_version_type = type_mapping.get(selected_type, 'Concept Art')

            # Get filename for version code
            filename = os.path.basename(file_path)
            version_code = os.path.splitext(filename)[0]

            # Create version in ShotGrid
            version_data = {
                'project': {'type': 'Project', 'id': self.project_id},
                'code': version_code,
                'sg_version_type': sg_version_type,
                'description': f'Uploaded via FF Bidding App'
            }

            logger.info(f"Creating version in ShotGrid: {version_code}")
            version = self.sg_session.sg.create('Version', version_data)

            # Upload the image file
            logger.info(f"Uploading file: {file_path}")
            self.sg_session.sg.upload(
                'Version',
                version['id'],
                file_path,
                field_name='sg_uploaded_movie'
            )

            # Upload as thumbnail too
            self.sg_session.sg.upload_thumbnail(
                'Version',
                version['id'],
                file_path
            )

            # Get the version data (thumbnail might not be ready yet)
            version = self.sg_session.sg.find_one(
                'Version',
                [['id', 'is', version['id']]],
                ['code', 'image', 'sg_version_type', 'created_at', 'project']
            )

            logger.info(f"Version created: {version.get('code')}, image data: {version.get('image')}")
            print(f"[UPLOAD DEBUG] Version created: {version.get('code')}, image data: {version.get('image')}")

            progress.close()

            # Show success message
            QtWidgets.QMessageBox.information(
                self,
                "Upload Successful",
                f"Image uploaded successfully as '{version_code}'"
            )

            # Emit signal with new version data
            self.imageUploaded.emit(version)

        except Exception as e:
            progress.close()
            logger.error(f"Failed to upload image: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Upload Failed",
                f"Failed to upload image to ShotGrid:\n{str(e)}"
            )


class ThumbnailPoller(QtCore.QObject):
    """Background poller that checks ShotGrid for thumbnail availability and updates widgets."""

    thumbnailReady = QtCore.Signal(int, dict)  # (version_id, updated_version_data)

    def __init__(self, sg_session, viewer_widget, parent=None):
        super().__init__(parent)
        self.sg_session = sg_session
        self.viewer_widget = viewer_widget  # Reference to ImageViewerWidget
        self.pending_versions = {}  # version_id -> attempt_count
        self.poll_timer = QtCore.QTimer(self)
        self.poll_timer.timeout.connect(self._check_pending_thumbnails)
        self.poll_timer.setInterval(2000)  # Check every 2 seconds

    def add_version_to_poll(self, version_id):
        """Add a version to poll for thumbnail availability.

        Args:
            version_id: The version ID to poll
        """
        logger.info(f"Adding version {version_id} to polling queue")
        print(f"[POLLER DEBUG] add_version_to_poll called for version {version_id}")
        self.pending_versions[version_id] = 0

        # Start timer if not already running
        if not self.poll_timer.isActive():
            logger.info("Starting poller timer")
            print("[POLLER DEBUG] Starting poller timer (2 second interval)")
            self.poll_timer.start()

    def _check_pending_thumbnails(self):
        """Check all pending versions for thumbnail availability."""
        print(f"[POLLER DEBUG] _check_pending_thumbnails called, pending_versions={list(self.pending_versions.keys())}")
        if not self.pending_versions:
            logger.debug("No pending versions, stopping poller")
            print("[POLLER DEBUG] No pending versions, stopping poller")
            self.poll_timer.stop()
            return

        logger.info(f"Polling {len(self.pending_versions)} versions for thumbnail availability")
        print(f"[POLLER DEBUG] Polling {len(self.pending_versions)} versions for thumbnail availability")
        versions_to_remove = []

        for version_id, attempt_count in list(self.pending_versions.items()):
            # Max 30 attempts (60 seconds total)
            if attempt_count >= 30:
                logger.warning(f"Giving up on thumbnail for version {version_id} after 30 attempts")
                versions_to_remove.append(version_id)
                continue

            # Query ShotGrid for updated version data
            try:
                version_data = self.sg_session.sg.find_one(
                    'Version',
                    [['id', 'is', version_id]],
                    ['code', 'image', 'sg_version_type', 'created_at', 'project']
                )

                logger.debug(f"Version {version_id} query result: {version_data}")

                if version_data:
                    image_data = version_data.get('image')
                    has_url = False

                    if isinstance(image_data, dict):
                        # Only consider it ready if there's an actual URL, not just link_type
                        has_url = bool(image_data.get('url'))
                    elif isinstance(image_data, str):
                        has_url = bool(image_data)  # Non-empty string URL

                    if has_url:
                        logger.info(f"Thumbnail ready for version {version_id} after {attempt_count + 1} attempts")
                        # Find and update the thumbnail widget
                        thumbnail_widget = self.viewer_widget.find_thumbnail_by_version_id(version_id)
                        if thumbnail_widget:
                            thumbnail_widget.refresh_thumbnail(version_data)
                        # Emit signal for other listeners
                        self.thumbnailReady.emit(version_id, version_data)
                        versions_to_remove.append(version_id)
                    else:
                        logger.debug(f"Attempt {attempt_count + 1}/30: Thumbnail not ready for version {version_id}, image_data={image_data}")
                        self.pending_versions[version_id] = attempt_count + 1

            except Exception as e:
                logger.error(f"Error checking thumbnail for version {version_id}: {e}", exc_info=True)
                self.pending_versions[version_id] = attempt_count + 1

        # Remove completed versions
        for version_id in versions_to_remove:
            self.pending_versions.pop(version_id, None)

        # Stop timer if no more pending versions
        if not self.pending_versions:
            logger.info("All thumbnails processed, stopping poller")
            self.poll_timer.stop()


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

        # Zoom level label
        self.zoom_label = QtWidgets.QLabel("100%")
        self.zoom_label.setStyleSheet("font-weight: bold;")
        toolbar.addWidget(self.zoom_label)

        # Toggle details pane button
        self.toggle_details_btn = QtWidgets.QPushButton("Details ▶")
        self.toggle_details_btn.setToolTip("Show/Hide Details Panel")
        self.toggle_details_btn.clicked.connect(self._toggle_details_pane)
        toolbar.addWidget(self.toggle_details_btn)

        layout.addLayout(toolbar)

        # Container widget for image view (to overlay the sliding panel)
        self.view_container = QtWidgets.QWidget()
        view_container_layout = QtWidgets.QVBoxLayout(self.view_container)
        view_container_layout.setContentsMargins(0, 0, 0, 0)

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

        view_container_layout.addWidget(self.graphics_view)
        layout.addWidget(self.view_container)

        # Create sliding overlay panel for details
        self.details_panel = SlidingOverlayPanel(
            parent=self.view_container,
            panel_width=350,
            animation_duration=250
        )
        self.details_panel.set_title("Image Details")

        # Create details content widget
        details_content = self._create_details_content()
        self.details_panel.set_content(details_content)

        # Connect panel signals to update toggle button
        self.details_panel.panel_shown.connect(self._on_details_shown)
        self.details_panel.panel_hidden.connect(self._on_details_hidden)

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

    def _create_details_content(self):
        """Create the details content for the sliding panel."""
        details_widget = QtWidgets.QWidget()
        details_layout = QtWidgets.QVBoxLayout(details_widget)
        details_layout.setContentsMargins(0, 0, 0, 0)

        # Details text area
        self.details_text = QtWidgets.QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b2b;
                border: none;
                color: #ddd;
            }
        """)
        details_layout.addWidget(self.details_text)

        # Populate with version data
        self._update_details()

        return details_widget

    def _toggle_details_pane(self):
        """Toggle the visibility of the details pane."""
        self.details_panel.toggle()

    def _on_details_shown(self):
        """Handle details panel shown event."""
        self.toggle_details_btn.setText("Details ◀")

    def _on_details_hidden(self):
        """Handle details panel hidden event."""
        self.toggle_details_btn.setText("Details ▶")

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
    deleteRequested = QtCore.Signal(dict)  # Emits version data when delete is requested

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
                logger.debug(f"No image data for version {self.version_data.get('code')}")
                self.thumbnail_label.setText("Processing...")
                return

            # If image_data is a URL string, download it
            if isinstance(image_data, str):
                thumbnail_url = image_data
            elif isinstance(image_data, dict):
                # Get URL from the dict - only use 'url', not 'link_type' which is just metadata
                thumbnail_url = image_data.get('url')
            else:
                self.thumbnail_label.setText("Processing...")
                return

            if not thumbnail_url:
                logger.debug(f"No thumbnail URL for version {self.version_data.get('code')}")
                self.thumbnail_label.setText("Processing...")
                return

            logger.debug(f"Loading thumbnail for {self.version_data.get('code')} from {thumbnail_url[:50]}...")

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
            self.thumbnail_label.setText("Processing...")

    def refresh_thumbnail(self, updated_version_data):
        """Refresh thumbnail with updated version data.

        Args:
            updated_version_data: Updated version data from ShotGrid with image URL
        """
        logger.info(f"Refreshing thumbnail for {self.version_data.get('code')}")
        self.version_data = updated_version_data
        self._load_thumbnail()

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

    def contextMenuEvent(self, event):
        """Handle right-click context menu."""
        menu = QtWidgets.QMenu(self)

        # View action
        view_action = menu.addAction("View Enlarged")
        view_action.triggered.connect(self._open_enlarged_view)

        menu.addSeparator()

        # Delete action
        delete_action = menu.addAction("Delete from ShotGrid")
        delete_action.triggered.connect(self._request_delete)

        menu.exec(event.globalPos())

    def _request_delete(self):
        """Request deletion of this version."""
        self.deleteRequested.emit(self.version_data)

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

        # Thumbnail poller for checking ShotGrid for newly uploaded images
        self.thumbnail_poller = ThumbnailPoller(sg_session, self, self)
        self.thumbnail_poller.thumbnailReady.connect(self._on_thumbnail_ready)

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
        self.folder_pane.image_viewer = self  # Set reference for detail view access
        self.splitter.addWidget(self.folder_pane)

        # Connect folder drop signal to update thumbnail states and deselect
        self.folder_pane.imageDropped.connect(self.update_thumbnail_states)
        self.folder_pane.imageDropped.connect(self._deselect_current_thumbnail)

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

        # Add Image button
        add_image_btn = QtWidgets.QPushButton("Add Image")
        add_image_btn.setToolTip("Browse for an image to upload to ShotGrid")
        add_image_btn.clicked.connect(self._browse_for_image)
        header_layout.addWidget(add_image_btn)

        # Refresh button
        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.setToolTip("Reload all images from ShotGrid")
        refresh_btn.clicked.connect(self._refresh_images)
        header_layout.addWidget(refresh_btn)

        # Separator
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.VLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        header_layout.addWidget(separator)

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

        # Thumbnail scroll area with drop support
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scroll_area.setAcceptDrops(True)

        # Container for thumbnails - also accepts drops
        self.thumbnail_container = QtWidgets.QWidget()
        self.thumbnail_container.setAcceptDrops(True)
        self.thumbnail_layout = QtWidgets.QGridLayout(self.thumbnail_container)
        self.thumbnail_layout.setSpacing(10)
        self.thumbnail_layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)

        # Install event filter to handle drops on container
        self.thumbnail_container.dragEnterEvent = self._container_drag_enter
        self.thumbnail_container.dragLeaveEvent = self._container_drag_leave
        self.thumbnail_container.dropEvent = self._container_drop

        self.scroll_area.setWidget(self.thumbnail_container)
        dock_layout.addWidget(self.scroll_area)

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

            # Account for upload widget at position 0
            start_idx = 1 if self.current_project_id and self.sg_session else 0

            # Rearrange existing widgets in layout
            for idx, thumbnail in enumerate(self.thumbnail_widgets):
                grid_idx = idx + start_idx
                row = grid_idx // columns
                col = grid_idx % columns

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

            # Clear selected thumbnail reference BEFORE deleting widgets
            self.selected_thumbnail = None

            # Clear folder highlights
            if self.folder_pane:
                self.folder_pane.highlight_folders_for_image(None)

            # Disconnect signals before clearing to prevent issues
            for thumbnail in self.thumbnail_widgets:
                try:
                    thumbnail.clicked.disconnect()
                    thumbnail.deleteRequested.disconnect()
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
            thumbnail.deleteRequested.connect(self._on_delete_requested)
            self.thumbnail_layout.addWidget(thumbnail, row, col)
            self.thumbnail_widgets.append(thumbnail)

            # Check if thumbnail needs polling (no image URL available yet)
            # Note: link_type being present (e.g., 'upload') doesn't mean the URL is ready
            # We need to check for the actual 'url' field which contains the accessible thumbnail URL
            image_data = version.get('image')
            has_url = False
            if isinstance(image_data, dict):
                # Only consider it ready if there's an actual URL, not just link_type
                has_url = bool(image_data.get('url'))
            elif isinstance(image_data, str):
                has_url = bool(image_data)  # Non-empty string URL

            logger.info(f"Checking version {version.get('id')} ({version.get('code')}): image_data={image_data}, has_url={has_url}")
            print(f"[POLLING DEBUG] Checking version {version.get('id')} ({version.get('code')}): image_data={image_data}, has_url={has_url}")

            if not has_url:
                # Add to poller to check for thumbnail availability
                logger.info(f"Adding version {version.get('id')} to poller (no thumbnail URL yet)")
                print(f"[POLLING DEBUG] Adding version {version.get('id')} to poller (no thumbnail URL yet)")
                self.thumbnail_poller.add_version_to_poll(version.get('id'))


    def find_thumbnail_by_version_id(self, version_id):
        """Find a thumbnail widget by version ID.

        Args:
            version_id: The version ID to find

        Returns:
            ThumbnailWidget or None if not found
        """
        for thumbnail in self.thumbnail_widgets:
            if thumbnail.version_data.get('id') == version_id:
                return thumbnail
        return None

    def _on_thumbnail_clicked(self, version_data):
        """Handle thumbnail click."""
        logger.info(f"Thumbnail clicked: {version_data.get('code')}")

        # Deselect previous (with safety check for deleted widgets)
        if self.selected_thumbnail:
            try:
                # Check if widget is still in our list (not deleted)
                if self.selected_thumbnail in self.thumbnail_widgets:
                    self.selected_thumbnail.set_selected(False)
            except RuntimeError:
                # Widget was deleted, just clear the reference
                pass
            self.selected_thumbnail = None

        # Select new
        for thumbnail in self.thumbnail_widgets:
            if thumbnail.version_data.get('id') == version_data.get('id'):
                thumbnail.set_selected(True)
                self.selected_thumbnail = thumbnail
                break

        # Highlight folders containing this image
        if self.folder_pane:
            image_id = version_data.get('id')
            self.folder_pane.highlight_folders_for_image(image_id)

    def _deselect_current_thumbnail(self):
        """Deselect the currently selected thumbnail."""
        if self.selected_thumbnail:
            try:
                if self.selected_thumbnail in self.thumbnail_widgets:
                    self.selected_thumbnail.set_selected(False)
            except RuntimeError:
                pass
            self.selected_thumbnail = None

        # Clear folder highlights
        if self.folder_pane:
            self.folder_pane.highlight_folders_for_image(None)

    def _on_delete_requested(self, version_data):
        """Handle delete request from thumbnail context menu.

        Args:
            version_data: The version data to delete
        """
        version_code = version_data.get('code', 'Unknown')
        version_id = version_data.get('id')

        if not version_id:
            logger.error("Cannot delete version: no ID found")
            return

        # Confirm deletion
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete '{version_code}' from ShotGrid?\n\n"
            "This action cannot be undone.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply != QtWidgets.QMessageBox.Yes:
            return

        # Delete from ShotGrid
        try:
            logger.info(f"Deleting version {version_id} ({version_code}) from ShotGrid")

            # Show progress
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)

            # Delete the version from ShotGrid
            self.sg_session.sg.delete('Version', version_id)

            logger.info(f"Successfully deleted version {version_id} from ShotGrid")

            # Remove from local lists
            self.all_versions = [v for v in self.all_versions if v.get('id') != version_id]
            self.filtered_versions = [v for v in self.filtered_versions if v.get('id') != version_id]

            # Clear selection if this was selected
            if self.selected_thumbnail and self.selected_thumbnail.version_data.get('id') == version_id:
                self.selected_thumbnail = None

            # Remove from poller if pending
            if version_id in self.thumbnail_poller.pending_versions:
                self.thumbnail_poller.pending_versions.pop(version_id, None)

            # Rebuild thumbnails
            self._rebuild_thumbnails()

            QtWidgets.QApplication.restoreOverrideCursor()

            QtWidgets.QMessageBox.information(
                self,
                "Deleted",
                f"'{version_code}' has been deleted from ShotGrid."
            )

        except Exception as e:
            QtWidgets.QApplication.restoreOverrideCursor()
            logger.error(f"Failed to delete version {version_id}: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Delete Failed",
                f"Failed to delete '{version_code}' from ShotGrid:\n{str(e)}"
            )

    def _on_thumbnail_ready(self, version_id, updated_version_data):
        """Handle thumbnail becoming ready from the poller.

        Args:
            version_id: The version ID that now has a thumbnail
            updated_version_data: The updated version data with image URL
        """
        logger.info(f"Thumbnail ready for version {version_id}, updating all_versions")

        # Update the version data in all_versions list
        for i, version in enumerate(self.all_versions):
            if version.get('id') == version_id:
                self.all_versions[i] = updated_version_data
                logger.info(f"Updated version data in all_versions for {updated_version_data.get('code')}")
                break

        # Also update in filtered_versions if present
        for i, version in enumerate(self.filtered_versions):
            if version.get('id') == version_id:
                self.filtered_versions[i] = updated_version_data
                logger.info(f"Updated version data in filtered_versions for {updated_version_data.get('code')}")
                break

    def _on_image_uploaded(self, version_data):
        """Handle successful image upload.

        Args:
            version_data: The newly created version data from ShotGrid
        """
        logger.info(f"Image uploaded successfully: {version_data.get('code')}")
        print(f"[UPLOAD DEBUG] _on_image_uploaded called with: {version_data.get('code')}, image={version_data.get('image')}")

        # Add new version to all_versions list
        if version_data not in self.all_versions:
            self.all_versions.append(version_data)
            print(f"[UPLOAD DEBUG] Added to all_versions, now has {len(self.all_versions)} versions")

        # Don't call _apply_filters() here as it immediately rebuilds and starts threads
        # Instead, let _rebuild_after_upload handle everything after checking for thread completion
        # Use a delay before rebuilding to allow pending operations to complete
        print("[UPLOAD DEBUG] Scheduling _rebuild_after_upload in 500ms")
        QtCore.QTimer.singleShot(500, self._rebuild_after_upload)

    def _rebuild_after_upload(self):
        """Rebuild UI after image upload with proper cleanup."""
        print("[UPLOAD DEBUG] _rebuild_after_upload called")
        # Check if there are still active image loading threads
        if hasattr(self, 'folder_pane') and self.folder_pane:
            if hasattr(self.folder_pane, 'shared_image_loader'):
                loader = self.folder_pane.shared_image_loader

                # Check for alive threads (not just active_loads counter)
                alive_threads = [t for t in loader.active_threads if t.is_alive()]

                if alive_threads or loader.active_loads > 0:
                    logger.info(f"Still {len(alive_threads)} threads alive and {loader.active_loads} active loads, waiting...")
                    print(f"[UPLOAD DEBUG] Waiting for threads: {len(alive_threads)} alive, {loader.active_loads} active")
                    # Check again after 300ms
                    QtCore.QTimer.singleShot(300, self._rebuild_after_upload)
                    return

        # Process any pending events multiple times to ensure cleanup
        for _ in range(5):
            QtCore.QCoreApplication.processEvents()
            QtCore.QThread.msleep(30)  # Give threads time to finish

        # Update filtered_versions based on current filter states
        self.filtered_versions = []
        for version in self.all_versions:
            version_type = self._get_version_type(version)
            if self.filter_states.get(version_type, True):
                self.filtered_versions.append(version)

        print(f"[UPLOAD DEBUG] filtered_versions now has {len(self.filtered_versions)} versions, calling _rebuild_thumbnails")
        # Rebuild thumbnails to show the new image
        self._rebuild_thumbnails()

        # Update folder pane
        self.update_folder_pane()

        # Update thumbnail states (for border colors)
        self.update_thumbnail_states()


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

    def _refresh_images(self):
        """Refresh all images by reloading from ShotGrid."""
        if not self.current_project_id:
            logger.info("No project selected, cannot refresh")
            return

        logger.info(f"Refreshing images for project {self.current_project_id}")
        print(f"[REFRESH DEBUG] Refreshing images for project {self.current_project_id}")

        try:
            # Show loading cursor
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)

            # Clear existing data
            self.all_versions = []
            self.filtered_versions = []

            # Reload from ShotGrid
            self.all_versions = self.sg_session.get_all_image_versions_for_project(self.current_project_id)
            logger.info(f"Refreshed: loaded {len(self.all_versions)} image versions")
            print(f"[REFRESH DEBUG] Loaded {len(self.all_versions)} image versions")

            # Apply filters and rebuild thumbnails
            self._apply_filters()

            # Update folder pane
            self.update_folder_pane()

            # Update thumbnail states
            self.update_thumbnail_states()

            QtWidgets.QApplication.restoreOverrideCursor()

        except Exception as e:
            QtWidgets.QApplication.restoreOverrideCursor()
            logger.error(f"Failed to refresh images: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Refresh Failed",
                f"Failed to refresh images from ShotGrid:\n{str(e)}"
            )

    def _browse_for_image(self):
        """Open file browser to select an image to upload."""
        if not self.current_project_id or not self.sg_session:
            QtWidgets.QMessageBox.warning(
                self,
                "No Project Selected",
                "Please select a project before uploading images."
            )
            return

        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Image to Upload",
            "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.tiff *.tif);;All Files (*)"
        )

        if file_path:
            self._upload_image(file_path)

    def _container_drag_enter(self, event):
        """Handle drag enter on the thumbnail container."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            # Highlight the container
            self.thumbnail_container.setStyleSheet("background-color: rgba(74, 159, 255, 30);")
        else:
            event.ignore()

    def _container_drag_leave(self, event):
        """Handle drag leave on the thumbnail container."""
        self.thumbnail_container.setStyleSheet("")

    def _container_drop(self, event):
        """Handle drop on the thumbnail container."""
        self.thumbnail_container.setStyleSheet("")

        if not self.current_project_id or not self.sg_session:
            QtWidgets.QMessageBox.warning(
                self,
                "No Project Selected",
                "Please select a project before uploading images."
            )
            event.ignore()
            return

        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                file_path = urls[0].toLocalFile()
                if self._is_valid_image_file(file_path):
                    event.acceptProposedAction()
                    self._upload_image(file_path)
                else:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Invalid File",
                        "Please drop a valid image file (PNG, JPG, JPEG, GIF, BMP, TIFF)"
                    )
        else:
            event.ignore()

    def _is_valid_image_file(self, file_path):
        """Check if the file is a valid image."""
        valid_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif']
        _, ext = os.path.splitext(file_path.lower())
        return ext in valid_extensions

    def _upload_image(self, file_path):
        """Upload an image to ShotGrid.

        Args:
            file_path: Path to the image file to upload
        """
        # Show type selection dialog
        dialog = UploadTypeDialog(self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return

        selected_type = dialog.get_selected_type()
        if not selected_type:
            return

        # Show progress dialog
        progress = QtWidgets.QProgressDialog(
            "Uploading image to ShotGrid...",
            "Cancel",
            0, 0,
            self
        )
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        try:
            # Map type to ShotGrid version type
            type_mapping = {
                'concept_art': 'Concept Art',
                'storyboard': 'Storyboard',
                'reference': 'Reference',
                'video': 'Video'
            }
            sg_version_type = type_mapping.get(selected_type, 'Concept Art')

            # Get filename for version code
            filename = os.path.basename(file_path)
            version_code = os.path.splitext(filename)[0]

            # Create version in ShotGrid
            version_data = {
                'project': {'type': 'Project', 'id': self.current_project_id},
                'code': version_code,
                'sg_version_type': sg_version_type,
                'description': f'Uploaded via FF Bidding App'
            }

            logger.info(f"Creating version in ShotGrid: {version_code}")
            version = self.sg_session.sg.create('Version', version_data)

            # Upload the image file
            logger.info(f"Uploading file: {file_path}")
            self.sg_session.sg.upload(
                'Version',
                version['id'],
                file_path,
                field_name='sg_uploaded_movie'
            )

            # Upload as thumbnail too
            self.sg_session.sg.upload_thumbnail(
                'Version',
                version['id'],
                file_path
            )

            # Get the version data (thumbnail might not be ready yet)
            version = self.sg_session.sg.find_one(
                'Version',
                [['id', 'is', version['id']]],
                ['code', 'image', 'sg_version_type', 'created_at', 'project']
            )

            logger.info(f"Version created: {version.get('code')}, image data: {version.get('image')}")
            print(f"[UPLOAD DEBUG] Version created: {version.get('code')}, image data: {version.get('image')}")

            progress.close()

            # Show success message
            QtWidgets.QMessageBox.information(
                self,
                "Upload Successful",
                f"Image uploaded successfully as '{version_code}'"
            )

            # Handle the uploaded image
            self._on_image_uploaded(version)

        except Exception as e:
            progress.close()
            logger.error(f"Failed to upload image: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Upload Failed",
                f"Failed to upload image to ShotGrid:\n{str(e)}"
            )

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
