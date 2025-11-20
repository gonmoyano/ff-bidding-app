from PySide6 import QtWidgets, QtCore, QtGui
import logging
import urllib.request
from threading import Thread

try:
    from .logger import logger
    from .bid_selector_widget import CollapsibleGroupBox
except (ImportError, ValueError, SystemError):
    logger = logging.getLogger("FFPackageManager")
    from bid_selector_widget import CollapsibleGroupBox


class ImageLoader(QtCore.QObject):
    """Asynchronous image loader using QThread."""

    imageLoaded = QtCore.Signal(str, QtGui.QPixmap)  # (cache_key, pixmap)
    loadFailed = QtCore.Signal(str)  # (cache_key)

    def __init__(self, parent=None, max_concurrent=5):
        super().__init__(parent)
        self.load_queue = []
        self.active_loads = 0
        self.max_concurrent = max_concurrent  # Allow multiple concurrent loads
        self.loading_keys = set()  # Track what's currently loading

    def load_image(self, url, cache_key, width, height):
        """Queue an image for loading.

        Args:
            url: URL to load image from
            cache_key: Unique key for caching
            width: Target width for scaling
            height: Target height for scaling
        """
        # Skip if already loading or queued
        if cache_key in self.loading_keys:
            return

        self.loading_keys.add(cache_key)
        self.load_queue.append((url, cache_key, width, height))
        self._process_queue()

    def _process_queue(self):
        """Process the next items in the queue up to max_concurrent."""
        while self.load_queue and self.active_loads < self.max_concurrent:
            self.active_loads += 1
            url, cache_key, width, height = self.load_queue.pop(0)

            # Load in background thread
            thread = Thread(target=self._load_in_thread, args=(url, cache_key, width, height))
            thread.daemon = True
            thread.start()

    def _load_in_thread(self, url, cache_key, width, height):
        """Load image in background thread."""
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                image_bytes = response.read()
                pixmap = QtGui.QPixmap()
                pixmap.loadFromData(image_bytes)

                if not pixmap.isNull():
                    # Scale to fit
                    scaled_pixmap = pixmap.scaled(
                        width, height,
                        QtCore.Qt.KeepAspectRatio,
                        QtCore.Qt.SmoothTransformation
                    )
                    # Emit signal on main thread
                    QtCore.QMetaObject.invokeMethod(
                        self,
                        "_emit_loaded",
                        QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(str, cache_key),
                        QtCore.Q_ARG(QtGui.QPixmap, scaled_pixmap)
                    )
                else:
                    QtCore.QMetaObject.invokeMethod(
                        self,
                        "_emit_failed",
                        QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(str, cache_key)
                    )
        except Exception as e:
            logger.warning(f"Failed to load image from {url}: {e}")
            QtCore.QMetaObject.invokeMethod(
                self,
                "_emit_failed",
                QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(str, cache_key)
            )

    @QtCore.Slot(str, QtGui.QPixmap)
    def _emit_loaded(self, cache_key, pixmap):
        """Emit loaded signal on main thread."""
        self.imageLoaded.emit(cache_key, pixmap)
        self.active_loads -= 1
        self.loading_keys.discard(cache_key)
        self._process_queue()

    @QtCore.Slot(str)
    def _emit_failed(self, cache_key):
        """Emit failed signal on main thread."""
        self.loadFailed.emit(cache_key)
        self.active_loads -= 1
        self.loading_keys.discard(cache_key)
        self._process_queue()


class FolderWidget(QtWidgets.QWidget):
    """Widget representing a folder that can accept image drops."""

    imageDropped = QtCore.Signal()  # Signal emitted when an image is dropped
    doubleClicked = QtCore.Signal(str, str)  # Signal emitted when folder is double-clicked (folder_name, folder_type)

    def __init__(self, folder_name, folder_type, parent=None, icon_size=64):
        """Initialize folder widget.

        Args:
            folder_name: Name of the folder (asset name or scene code)
            folder_type: Type of folder ('asset' or 'scene')
            parent: Parent widget
            icon_size: Size of the folder icon in pixels
        """
        super().__init__(parent)
        self.folder_name = folder_name
        self.folder_type = folder_type
        self.image_ids = set()  # Set of image version IDs in this folder
        self.icon_size = icon_size

        self.setAcceptDrops(True)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the folder UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignCenter)

        # Folder icon
        self.icon_label = QtWidgets.QLabel()
        self.icon_label.setAlignment(QtCore.Qt.AlignCenter)
        self._update_icon()
        layout.addWidget(self.icon_label)

        # Folder name
        self.name_label = QtWidgets.QLabel(self.folder_name)
        self.name_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        self.name_label.setAlignment(QtCore.Qt.AlignCenter)
        self.name_label.setWordWrap(True)
        layout.addWidget(self.name_label)

        # Image count
        self.count_label = QtWidgets.QLabel("0 images")
        self.count_label.setStyleSheet("color: #888; font-size: 10px;")
        self.count_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.count_label)

        # Style for hover effect
        self.setStyleSheet("""
            FolderWidget {
                background-color: #2b2b2b;
                border: 1px solid #444;
                border-radius: 4px;
            }
            FolderWidget:hover {
                background-color: #353535;
                border: 1px solid #555;
            }
        """)

    def _update_icon(self):
        """Update the folder icon with current size."""
        self.icon_label.setPixmap(self.style().standardIcon(
            QtWidgets.QStyle.SP_DirIcon
        ).pixmap(self.icon_size, self.icon_size))

    def set_icon_size(self, size):
        """Set the icon size.

        Args:
            size: Icon size in pixels
        """
        self.icon_size = size
        self._update_icon()

    def dragEnterEvent(self, event):
        """Handle drag enter event."""
        if event.mimeData().hasFormat("application/x-image-version-id"):
            event.acceptProposedAction()
            # Highlight on drag over
            self.setStyleSheet("""
                FolderWidget {
                    background-color: #3a5f8f;
                    border: 2px solid #4a9eff;
                    border-radius: 4px;
                }
            """)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        """Handle drag leave event."""
        # Remove highlight
        self.setStyleSheet("""
            FolderWidget {
                background-color: #2b2b2b;
                border: 1px solid #444;
                border-radius: 4px;
            }
            FolderWidget:hover {
                background-color: #353535;
                border: 1px solid #555;
            }
        """)

    def dropEvent(self, event):
        """Handle drop event."""
        if event.mimeData().hasFormat("application/x-image-version-id"):
            # Get the dropped image version ID
            image_id_bytes = event.mimeData().data("application/x-image-version-id")
            image_id = int(bytes(image_id_bytes).decode())

            # Add to this folder
            self.image_ids.add(image_id)
            self._update_count()

            event.acceptProposedAction()
            logger.info(f"Dropped image {image_id} into folder {self.folder_name}")

            # Emit signal to notify parent
            self.imageDropped.emit()

            # Remove highlight
            self.dragLeaveEvent(event)
        else:
            event.ignore()

    def _update_count(self):
        """Update the image count label."""
        count = len(self.image_ids)
        self.count_label.setText(f"{count} image{'s' if count != 1 else ''}")

    def add_image(self, image_id):
        """Add an image to this folder."""
        self.image_ids.add(image_id)
        self._update_count()

    def remove_image(self, image_id):
        """Remove an image from this folder."""
        self.image_ids.discard(image_id)
        self._update_count()

    def get_image_ids(self):
        """Get all image IDs in this folder."""
        return self.image_ids.copy()

    def set_image_ids(self, image_ids):
        """Set the image IDs in this folder."""
        self.image_ids = set(image_ids)
        self._update_count()

    def mouseDoubleClickEvent(self, event):
        """Handle double-click to view folder contents."""
        if event.button() == QtCore.Qt.LeftButton:
            self.doubleClicked.emit(self.folder_name, self.folder_type)
        super().mouseDoubleClickEvent(event)


class DroppableGroupContainer(QtWidgets.QWidget):
    """Container widget that accepts image drops for a specific type group."""

    imageDropped = QtCore.Signal(int, str)  # (image_id, target_type)

    def __init__(self, image_type, parent=None):
        super().__init__(parent)
        self.image_type = image_type
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        """Handle drag enter event."""
        if event.mimeData().hasFormat("application/x-image-version-id"):
            event.acceptProposedAction()
            # Highlight on drag over
            self.setStyleSheet("background-color: rgba(74, 159, 255, 50);")
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        """Handle drag leave event."""
        # Remove highlight
        self.setStyleSheet("")

    def dropEvent(self, event):
        """Handle drop event."""
        if event.mimeData().hasFormat("application/x-image-version-id"):
            # Get the dropped image version ID
            image_id_bytes = event.mimeData().data("application/x-image-version-id")
            image_id = int(bytes(image_id_bytes).decode())

            event.acceptProposedAction()
            logger.info(f"Dropped image {image_id} into {self.image_type} group")

            # Emit signal with image ID and target type
            self.imageDropped.emit(image_id, self.image_type)

            # Remove highlight
            self.dragLeaveEvent(event)
        else:
            event.ignore()


class FolderDetailView(QtWidgets.QWidget):
    """Widget for viewing contents of a specific folder grouped by type."""

    backClicked = QtCore.Signal()  # Signal when back button is clicked
    imageRemoved = QtCore.Signal(int, str, str)  # Signal when image removed (image_id, folder_name, folder_type)
    imageEnlarged = QtCore.Signal(dict)  # Signal when image should be enlarged (version_data)
    imageDroppedToGroup = QtCore.Signal(int, str, str, str)  # (image_id, target_type, folder_name, folder_type)

    def __init__(self, parent=None, shared_cache=None, shared_loader=None):
        super().__init__(parent)
        self.folder_name = None
        self.folder_type = None
        self.image_versions = []  # List of image version data
        self.sg_session = None  # ShotGrid session for loading images
        self.thumbnail_size = 170  # Default thumbnail size

        # Image cache for loaded thumbnails (use shared if provided)
        self.image_cache = shared_cache if shared_cache is not None else {}
        self.label_cache = {}  # cache_key -> list of QLabel widgets

        # Async image loader (use shared if provided)
        if shared_loader is not None:
            self.image_loader = shared_loader
        else:
            self.image_loader = ImageLoader(self)

        self.image_loader.imageLoaded.connect(self._on_image_loaded)
        self.image_loader.loadFailed.connect(self._on_image_load_failed)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the detail view UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        # Header with breadcrumb and back button
        header_layout = QtWidgets.QHBoxLayout()

        back_btn = QtWidgets.QPushButton("← Back")
        back_btn.clicked.connect(self.backClicked.emit)
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
                font-weight: bold;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #5eb3ff;
            }
        """)
        header_layout.addWidget(back_btn)

        self.breadcrumb_label = QtWidgets.QLabel()
        self.breadcrumb_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #ddd;")
        header_layout.addWidget(self.breadcrumb_label)

        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Scroll area for grouped thumbnails
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        # Container for groups
        container = QtWidgets.QWidget()
        self.groups_layout = QtWidgets.QVBoxLayout(container)
        self.groups_layout.setContentsMargins(5, 5, 5, 5)
        self.groups_layout.setSpacing(10)

        # Create collapsible groups for each type
        self.type_groups = {}
        for image_type in ['Concept Art', 'Storyboard', 'Reference', 'Video']:
            group = CollapsibleGroupBox(f"{image_type} (0 items)")
            group_container = DroppableGroupContainer(image_type)
            group_container.imageDropped.connect(self._on_image_dropped_to_group)
            group_layout = QtWidgets.QGridLayout(group_container)
            group_layout.setSpacing(10)
            group_layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
            group.addWidget(group_container)
            self.groups_layout.addWidget(group)
            self.type_groups[image_type] = {
                'group': group,
                'layout': group_layout,
                'container': group_container
            }

        self.groups_layout.addStretch()

        scroll_area.setWidget(container)
        layout.addWidget(scroll_area)

    def set_folder(self, folder_name, folder_type, image_ids, all_versions, sg_session=None):
        """Set the folder to display.

        Args:
            folder_name: Name of the folder
            folder_type: Type ('asset' or 'scene')
            image_ids: Set of image version IDs in this folder
            all_versions: All image versions available
            sg_session: ShotGrid session for loading images
        """
        self.folder_name = folder_name
        self.folder_type = folder_type
        self.sg_session = sg_session

        # Update breadcrumb
        type_label = "Asset" if folder_type == "asset" else "Scene"
        self.breadcrumb_label.setText(f"Current folder: {type_label}: {folder_name}")

        # Filter versions to only those in this folder
        self.image_versions = [v for v in all_versions if v.get('id') in image_ids]

        # Group by type and display
        self._populate_groups()

        # Preload images in background for faster display
        self._preload_images()

    def _populate_groups(self):
        """Populate the type groups with thumbnails."""
        # Group images by type
        grouped_images = {
            'Concept Art': [],
            'Storyboard': [],
            'Reference': [],
            'Video': []
        }

        for version in self.image_versions:
            image_type = self._get_version_type(version)
            if image_type in grouped_images:
                grouped_images[image_type].append(version)

        # Populate each group
        for image_type, versions in grouped_images.items():
            group_data = self.type_groups[image_type]
            group = group_data['group']
            layout = group_data['layout']

            # Clear existing widgets
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            # Update title with count
            count = len(versions)
            group.setTitle(f"{image_type} ({count} item{'s' if count != 1 else ''})")

            # Add thumbnails
            # Calculate columns based on thumbnail size
            item_width = self.thumbnail_size + 10  # thumbnail + spacing
            columns = max(1, self.width() // item_width)
            for idx, version in enumerate(versions):
                row = idx // columns
                col = idx % columns

                # Create thumbnail item widget
                item_widget = self._create_thumbnail_item(version)
                layout.addWidget(item_widget, row, col)

    def _create_thumbnail_item(self, version):
        """Create a thumbnail item widget with image loading and controls."""
        # Calculate dimensions based on thumbnail size
        thumb_width = self.thumbnail_size
        thumb_height = int(thumb_width * 0.82)  # Maintain aspect ratio
        container_width = thumb_width + 10
        container_height = thumb_height + 50  # Extra space for label

        container = QtWidgets.QWidget()
        container_layout = QtWidgets.QVBoxLayout(container)
        container_layout.setContentsMargins(5, 5, 5, 5)
        container_layout.setSpacing(5)

        # Image container with overlay for remove icon
        image_container = QtWidgets.QWidget()
        image_container.setFixedSize(thumb_width, thumb_height)

        # Image label with thumbnail
        image_label = QtWidgets.QLabel(image_container)
        image_label.setFixedSize(thumb_width, thumb_height)
        image_label.setAlignment(QtCore.Qt.AlignCenter)
        image_label.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                border: 2px solid #444;
                border-radius: 4px;
            }
        """)

        # Load thumbnail
        self._load_thumbnail_for_label(image_label, version, thumb_width - 4, thumb_height - 4)

        # Make label clickable for enlargement
        image_label.setCursor(QtCore.Qt.PointingHandCursor)
        image_label.mouseDoubleClickEvent = lambda event: self.imageEnlarged.emit(version)

        # Remove icon overlay (circular outline with X in bottom-right corner)
        remove_icon = QtWidgets.QPushButton(image_container)
        remove_icon.setFixedSize(28, 28)
        remove_icon.move(thumb_width - 34, thumb_height - 34)  # Position in bottom-right corner
        remove_icon.setCursor(QtCore.Qt.PointingHandCursor)
        remove_icon.clicked.connect(lambda: self._remove_image(version.get('id')))

        # Circular outline style with X
        remove_icon.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 3px solid rgba(255, 255, 255, 200);
                border-radius: 14px;
                color: rgba(255, 255, 255, 200);
                font-weight: bold;
                font-size: 20px;
                padding: 0px;
            }
            QPushButton:hover {
                border: 3px solid rgba(255, 80, 80, 255);
                color: rgba(255, 80, 80, 255);
                background-color: rgba(255, 255, 255, 30);
            }
        """)
        remove_icon.setText("×")

        container_layout.addWidget(image_container)

        # Version code
        version_code = version.get('code', 'Unknown')
        code_label = QtWidgets.QLabel(version_code)
        code_label.setWordWrap(True)
        code_label.setMaximumWidth(thumb_width)
        code_label.setAlignment(QtCore.Qt.AlignCenter)
        code_label.setStyleSheet("font-size: 11px; color: #ddd;")
        container_layout.addWidget(code_label)

        container.setFixedSize(container_width, container_height)
        return container

    def _load_thumbnail_for_label(self, label, version, width=166, height=136):
        """Load thumbnail image for a label from version data.

        Args:
            label: QLabel to display the image
            version: Version data dictionary
            width: Target width for scaling
            height: Target height for scaling
        """
        try:
            image_data = version.get('image')

            if not image_data:
                label.setText("No Preview")
                label.setStyleSheet(label.styleSheet() + "color: #888;")
                return

            # Get URL for the image
            url = None
            if isinstance(image_data, str):
                url = image_data
            elif isinstance(image_data, dict):
                url = image_data.get('url') or image_data.get('local_path')

            if not url:
                label.setText(version.get('code', 'No Image')[:20])
                label.setStyleSheet(label.styleSheet() + "color: #888; font-size: 10px;")
                return

            # Create cache key from URL and size
            cache_key = f"{url}_{width}x{height}"

            # Check if already cached
            if cache_key in self.image_cache:
                label.setPixmap(self.image_cache[cache_key])
                return

            # Show loading text
            label.setText("Loading...")
            label.setStyleSheet(label.styleSheet() + "color: #888; font-size: 10px;")

            # Register label for this cache key
            if cache_key not in self.label_cache:
                self.label_cache[cache_key] = []
            self.label_cache[cache_key].append(label)

            # Queue for async loading
            self.image_loader.load_image(url, cache_key, width, height)

        except Exception as e:
            logger.error(f"Error loading thumbnail: {e}", exc_info=True)
            label.setText("Error")
            label.setStyleSheet(label.styleSheet() + "color: #cc3333;")

    @QtCore.Slot(str, QtGui.QPixmap)
    def _on_image_loaded(self, cache_key, pixmap):
        """Handle successful image load.

        Args:
            cache_key: Cache key for the image
            pixmap: Loaded pixmap
        """
        # Cache the pixmap
        self.image_cache[cache_key] = pixmap

        # Update all labels waiting for this image
        if cache_key in self.label_cache:
            for label in self.label_cache[cache_key]:
                if label and not label.isHidden():
                    label.setPixmap(pixmap)
                    label.setStyleSheet("")  # Clear loading style
            # Clear label cache for this key
            del self.label_cache[cache_key]

    @QtCore.Slot(str)
    def _on_image_load_failed(self, cache_key):
        """Handle failed image load.

        Args:
            cache_key: Cache key for the image
        """
        # Update all labels waiting for this image
        if cache_key in self.label_cache:
            for label in self.label_cache[cache_key]:
                if label and not label.isHidden():
                    label.setText("Failed")
                    label.setStyleSheet("color: #cc3333; font-size: 10px;")
            # Clear label cache for this key
            del self.label_cache[cache_key]

    def _remove_image(self, image_id):
        """Remove an image from the folder."""
        if image_id and self.folder_name and self.folder_type:
            self.imageRemoved.emit(image_id, self.folder_name, self.folder_type)

    def _on_image_dropped_to_group(self, image_id, target_type):
        """Handle image dropped into a type group.

        Args:
            image_id: ID of the dropped image
            target_type: Type group it was dropped into (e.g., 'Concept Art')
        """
        if self.folder_name and self.folder_type:
            # Emit signal to notify parent (FolderPaneWidget)
            self.imageDroppedToGroup.emit(image_id, target_type, self.folder_name, self.folder_type)

    def set_thumbnail_size(self, size):
        """Set the thumbnail size and refresh the view.

        Args:
            size: New thumbnail size in pixels
        """
        self.thumbnail_size = size
        # Refresh the groups with new size
        self._populate_groups()

    def _preload_images(self):
        """Preload all images in background for faster display."""
        # Calculate dimensions based on current thumbnail size
        thumb_width = self.thumbnail_size
        thumb_height = int(thumb_width * 0.82)

        for version in self.image_versions:
            image_data = version.get('image')
            if not image_data:
                continue

            # Get URL
            url = None
            if isinstance(image_data, str):
                url = image_data
            elif isinstance(image_data, dict):
                url = image_data.get('url') or image_data.get('local_path')

            if not url:
                continue

            # Create cache key
            cache_key = f"{url}_{thumb_width - 4}x{thumb_height - 4}"

            # Skip if already cached
            if cache_key in self.image_cache:
                continue

            # Queue for background loading
            self.image_loader.load_image(url, cache_key, thumb_width - 4, thumb_height - 4)

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
            return 'Concept Art'  # Default


class FolderPaneWidget(QtWidgets.QWidget):
    """Widget displaying folders for Assets and Scenes."""

    imageDropped = QtCore.Signal()  # Signal emitted when an image is dropped to any folder

    def __init__(self, parent=None):
        """Initialize folder pane widget."""
        super().__init__(parent)
        self.asset_folders = {}  # asset_name -> FolderWidget
        self.scene_folders = {}  # scene_code -> FolderWidget

        # Load saved sizes from settings
        from PySide6.QtCore import QSettings
        self.settings = QSettings("FFBiddingApp", "FolderPane")
        self.current_icon_size = self.settings.value("folder_icon_size", 64, type=int)
        self.detail_thumbnail_size = self.settings.value("detail_thumbnail_size", 170, type=int)

        # Shared image cache for all views
        self.shared_image_cache = {}  # cache_key -> QPixmap
        self.shared_image_loader = ImageLoader(self)

        # Reference to image viewer widget (set later)
        self.image_viewer = None

        # Flag to prevent concurrent operations
        self._is_relayouting = False

        # Debounce timer for resize events
        self.resize_timer = QtCore.QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self._relayout_folders_delayed)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the folder pane UI."""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # Icon size slider
        slider_layout = QtWidgets.QHBoxLayout()
        self.slider_label = QtWidgets.QLabel("Icon Size:")
        slider_layout.addWidget(self.slider_label)

        self.icon_size_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.icon_size_slider.setMinimum(32)
        self.icon_size_slider.setMaximum(128)
        self.icon_size_slider.setValue(self.current_icon_size)
        self.icon_size_slider.setTickPosition(QtWidgets.QSlider.NoTicks)  # Remove tick marks
        self.icon_size_slider.setFixedWidth(150)  # Fixed width
        self.icon_size_slider.valueChanged.connect(self._on_size_changed)
        slider_layout.addWidget(self.icon_size_slider)

        self.icon_size_label = QtWidgets.QLabel(str(self.current_icon_size))
        self.icon_size_label.setFixedWidth(30)
        self.icon_size_label.setAlignment(QtCore.Qt.AlignRight)
        slider_layout.addWidget(self.icon_size_label)

        slider_layout.addStretch()  # Push everything to the left

        main_layout.addLayout(slider_layout)

        # Stacked widget for switching between views
        self.view_stack = QtWidgets.QStackedWidget()

        # View 0: Folder grid view
        folder_grid_view = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(folder_grid_view)
        layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area for folders
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        # Container for collapsible groups
        container = QtWidgets.QWidget()
        self.container_layout = QtWidgets.QVBoxLayout(container)
        self.container_layout.setContentsMargins(5, 5, 5, 5)
        self.container_layout.setSpacing(10)

        # Assets group
        self.assets_group = CollapsibleGroupBox("Assets")
        self.assets_container = QtWidgets.QWidget()
        self.assets_layout = QtWidgets.QGridLayout(self.assets_container)
        self.assets_layout.setSpacing(10)
        self.assets_layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        self.assets_group.addWidget(self.assets_container)
        self.container_layout.addWidget(self.assets_group)

        # Scenes group
        self.scenes_group = CollapsibleGroupBox("Scenes")
        self.scenes_container = QtWidgets.QWidget()
        self.scenes_layout = QtWidgets.QGridLayout(self.scenes_container)
        self.scenes_layout.setSpacing(10)
        self.scenes_layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        self.scenes_group.addWidget(self.scenes_container)
        self.container_layout.addWidget(self.scenes_group)

        self.container_layout.addStretch()

        scroll_area.setWidget(container)
        layout.addWidget(scroll_area)

        self.view_stack.addWidget(folder_grid_view)  # Index 0

        # View 1: Folder detail view with shared cache
        self.detail_view = FolderDetailView(
            self,
            shared_cache=self.shared_image_cache,
            shared_loader=self.shared_image_loader
        )
        self.detail_view.backClicked.connect(self._show_folder_grid)
        self.detail_view.imageRemoved.connect(self._handle_image_removed)
        self.detail_view.imageEnlarged.connect(self._handle_image_enlarged)
        self.detail_view.imageDroppedToGroup.connect(self._handle_image_dropped_to_group)
        self.view_stack.addWidget(self.detail_view)  # Index 1

        # Connect view stack index change to update slider
        self.view_stack.currentChanged.connect(self._on_view_changed)

        main_layout.addWidget(self.view_stack)

        # Set minimum width
        self.setMinimumWidth(250)

    def _on_size_changed(self, value):
        """Handle size slider change."""
        current_view = self.view_stack.currentIndex()

        if current_view == 0:
            # Grid view - update folder icon size
            self.current_icon_size = value
            self.icon_size_label.setText(str(value))

            # Save to settings
            self.settings.setValue("folder_icon_size", value)

            # Update all existing folder icons
            for folder in self.asset_folders.values():
                folder.set_icon_size(value)
            for folder in self.scene_folders.values():
                folder.set_icon_size(value)

            # Re-layout folders
            self._relayout_folders()
        else:
            # Detail view - update thumbnail size
            self.detail_thumbnail_size = value
            self.icon_size_label.setText(str(value))

            # Save to settings
            self.settings.setValue("detail_thumbnail_size", value)

            # Refresh detail view with new size
            self.detail_view.set_thumbnail_size(value)

    def _on_view_changed(self, index):
        """Handle view stack index change to update slider."""
        if index == 0:
            # Grid view - show folder icon size
            self.slider_label.setText("Icon Size:")
            self.icon_size_slider.blockSignals(True)
            self.icon_size_slider.setMinimum(32)
            self.icon_size_slider.setMaximum(128)
            self.icon_size_slider.setValue(self.current_icon_size)
            self.icon_size_label.setText(str(self.current_icon_size))
            self.icon_size_slider.blockSignals(False)
        else:
            # Detail view - show thumbnail size
            self.slider_label.setText("Thumb Size:")
            self.icon_size_slider.blockSignals(True)
            self.icon_size_slider.setMinimum(120)
            self.icon_size_slider.setMaximum(250)
            self.icon_size_slider.setValue(self.detail_thumbnail_size)
            self.icon_size_label.setText(str(self.detail_thumbnail_size))
            self.icon_size_slider.blockSignals(False)

    def _relayout_folders(self):
        """Re-layout folders in grid based on current pane width."""
        # Prevent concurrent operations
        if self._is_relayouting:
            return

        # Safety check - don't relayout if being destroyed
        if not self.isVisible():
            return

        try:
            self._is_relayouting = True

            # Safety check for width
            pane_width = self.width()
            if pane_width <= 0:
                pane_width = 250  # Use minimum width as default

            # Calculate columns based on pane width and icon size
            folder_width = self.current_icon_size + 40  # Icon + padding
            columns = max(1, pane_width // folder_width)

            # Re-layout assets
            if self.asset_folders:
                self._layout_folders_in_grid(self.asset_folders, self.assets_layout, columns)

            # Re-layout scenes
            if self.scene_folders:
                self._layout_folders_in_grid(self.scene_folders, self.scenes_layout, columns)

        finally:
            self._is_relayouting = False

    def _relayout_folders_delayed(self):
        """Re-layout folders after resize timer expires."""
        self._relayout_folders()

    def _layout_folders_in_grid(self, folders_dict, grid_layout, columns):
        """Layout folders in a grid.

        Args:
            folders_dict: Dictionary of folder_name -> FolderWidget
            grid_layout: QGridLayout to place folders in
            columns: Number of columns in the grid
        """
        if not folders_dict or columns <= 0:
            return

        try:
            # Get sorted folder names
            folder_names = sorted(folders_dict.keys())

            # Collect widgets to keep
            widgets_to_keep = set()
            for folder_name in folder_names:
                folder = folders_dict.get(folder_name)
                if folder:
                    widgets_to_keep.add(folder)

            # Remove only widgets that are not in our folders_dict
            items_to_remove = []
            for i in range(grid_layout.count()):
                item = grid_layout.itemAt(i)
                if item and item.widget():
                    widget = item.widget()
                    if widget not in widgets_to_keep:
                        items_to_remove.append(widget)

            # Remove unwanted widgets
            for widget in items_to_remove:
                grid_layout.removeWidget(widget)
                widget.setParent(None)

            # Re-add all folders to grid in correct positions
            for idx, folder_name in enumerate(folder_names):
                folder = folders_dict.get(folder_name)
                if folder:
                    # Remove from current position
                    grid_layout.removeWidget(folder)
                    # Add to new position
                    row = idx // columns
                    col = idx % columns
                    grid_layout.addWidget(folder, row, col)
                    # Ensure it's visible
                    folder.show()

        except Exception as e:
            logger.error(f"Error laying out folders in grid: {e}", exc_info=True)

    def resizeEvent(self, event):
        """Handle resize event to re-layout folders."""
        super().resizeEvent(event)
        # Only schedule relayout if we have folders
        if self.asset_folders or self.scene_folders:
            # Use debounced timer to avoid excessive relayout during resize
            self.resize_timer.stop()
            self.resize_timer.start(400)  # Wait 400ms after last resize

    def set_assets(self, asset_names):
        """Set the asset folders.

        Args:
            asset_names: List of unique asset names
        """
        # Clear existing asset folders
        for folder_widget in self.asset_folders.values():
            folder_widget.deleteLater()
        self.asset_folders.clear()

        # Clear existing layout first
        while self.assets_layout.count():
            item = self.assets_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        # Add new asset folders
        for asset_name in sorted(asset_names):
            folder = FolderWidget(asset_name, 'asset', self, icon_size=self.current_icon_size)
            # Connect drop signal to propagate up
            folder.imageDropped.connect(self.imageDropped.emit)
            # Connect double-click to show detail view
            folder.doubleClicked.connect(self._show_folder_detail)
            self.asset_folders[asset_name] = folder

        # Update group title with count
        self.assets_group.setTitle(f"Assets ({len(asset_names)})")

        # Schedule re-layout after a short delay to ensure widget is sized
        QtCore.QTimer.singleShot(50, self._relayout_folders)

    def set_scenes(self, scene_codes):
        """Set the scene folders.

        Args:
            scene_codes: List of unique scene codes
        """
        # Clear existing scene folders
        for folder_widget in self.scene_folders.values():
            folder_widget.deleteLater()
        self.scene_folders.clear()

        # Clear existing layout first
        while self.scenes_layout.count():
            item = self.scenes_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        # Add new scene folders
        for scene_code in sorted(scene_codes):
            folder = FolderWidget(scene_code, 'scene', self, icon_size=self.current_icon_size)
            # Connect drop signal to propagate up
            folder.imageDropped.connect(self.imageDropped.emit)
            # Connect double-click to show detail view
            folder.doubleClicked.connect(self._show_folder_detail)
            self.scene_folders[scene_code] = folder

        # Update group title with count
        self.scenes_group.setTitle(f"Scenes ({len(scene_codes)})")

        # Schedule re-layout after a short delay to ensure widget is sized
        QtCore.QTimer.singleShot(50, self._relayout_folders)

    def get_folder_mappings(self):
        """Get all image-to-folder mappings.

        Returns:
            dict: {
                'assets': {asset_name: [image_id1, image_id2, ...]},
                'scenes': {scene_code: [image_id1, image_id2, ...]}
            }
        """
        mappings = {
            'assets': {},
            'scenes': {}
        }

        for asset_name, folder in self.asset_folders.items():
            image_ids = list(folder.get_image_ids())
            if image_ids:
                mappings['assets'][asset_name] = image_ids

        for scene_code, folder in self.scene_folders.items():
            image_ids = list(folder.get_image_ids())
            if image_ids:
                mappings['scenes'][scene_code] = image_ids

        return mappings

    def load_folder_mappings(self, mappings):
        """Load image-to-folder mappings.

        Args:
            mappings: dict in format {
                'assets': {asset_name: [image_id1, image_id2, ...]},
                'scenes': {scene_code: [image_id1, image_id2, ...]}
            }
        """
        if not mappings:
            return

        # Load asset mappings
        asset_mappings = mappings.get('assets', {})
        for asset_name, image_ids in asset_mappings.items():
            if asset_name in self.asset_folders:
                self.asset_folders[asset_name].set_image_ids(image_ids)

        # Load scene mappings
        scene_mappings = mappings.get('scenes', {})
        for scene_code, image_ids in scene_mappings.items():
            if scene_code in self.scene_folders:
                self.scene_folders[scene_code].set_image_ids(image_ids)

    def _show_folder_detail(self, folder_name, folder_type):
        """Show detail view for a specific folder.

        Args:
            folder_name: Name of the folder
            folder_type: Type of folder ('asset' or 'scene')
        """
        # Get the folder widget
        if folder_type == 'asset':
            folder = self.asset_folders.get(folder_name)
        else:
            folder = self.scene_folders.get(folder_name)

        if not folder:
            logger.error(f"Folder {folder_name} ({folder_type}) not found")
            return

        # Get image IDs in this folder
        image_ids = folder.get_image_ids()
        if not image_ids:
            logger.info(f"Folder {folder_name} is empty")
            # Still show the detail view, just with empty groups
            image_ids = set()

        # Get all versions from image viewer
        if not self.image_viewer:
            logger.error("Image viewer reference not set")
            return

        all_versions = self.image_viewer.all_versions
        sg_session = self.image_viewer.sg_session

        # Set folder detail view
        self.detail_view.set_folder(folder_name, folder_type, image_ids, all_versions, sg_session)

        # Switch to detail view
        self.view_stack.setCurrentIndex(1)

    def _show_folder_grid(self):
        """Return to folder grid view."""
        self.view_stack.setCurrentIndex(0)

    def _handle_image_removed(self, image_id, folder_name, folder_type):
        """Handle image removal from folder.

        Args:
            image_id: ID of the image version to remove
            folder_name: Name of the folder
            folder_type: Type of folder ('asset' or 'scene')
        """
        # Get the folder widget
        if folder_type == 'asset':
            folder = self.asset_folders.get(folder_name)
        else:
            folder = self.scene_folders.get(folder_name)

        if not folder:
            logger.error(f"Folder {folder_name} ({folder_type}) not found")
            return

        # Remove image from folder
        folder.remove_image(image_id)
        logger.info(f"Removed image {image_id} from folder {folder_name}")

        # Update thumbnail states in image viewer
        if self.image_viewer:
            self.image_viewer.update_thumbnail_states()

        # Refresh the detail view to reflect the removal
        if self.image_viewer:
            all_versions = self.image_viewer.all_versions
            sg_session = self.image_viewer.sg_session
            self.detail_view.set_folder(folder_name, folder_type, folder.get_image_ids(), all_versions, sg_session)

    def _handle_image_enlarged(self, version_data):
        """Handle request to enlarge an image.

        Args:
            version_data: Version data dictionary for the image to enlarge
        """
        if not self.image_viewer:
            logger.error("Image viewer reference not set")
            return

        # Use the image viewer's method to show enlarged image
        # ImageViewerDialog is defined in image_viewer_widget module
        from .image_viewer_widget import ImageViewerDialog
        dialog = ImageViewerDialog(version_data, self.image_viewer.sg_session, self)
        dialog.exec()

    def _handle_image_dropped_to_group(self, image_id, target_type, folder_name, folder_type):
        """Handle image dropped into a type group in detail view.

        Args:
            image_id: ID of the dropped image
            target_type: Type group it was dropped into (e.g., 'Concept Art')
            folder_name: Name of the folder
            folder_type: Type of folder ('asset' or 'scene')
        """
        # Get the folder widget
        if folder_type == 'asset':
            folder = self.asset_folders.get(folder_name)
        else:
            folder = self.scene_folders.get(folder_name)

        if not folder:
            logger.error(f"Folder {folder_name} ({folder_type}) not found")
            return

        # Add image to folder
        folder.add_image(image_id)
        logger.info(f"Added image {image_id} to folder {folder_name} via detail view drop")

        # Update thumbnail states in image viewer
        if self.image_viewer:
            self.image_viewer.update_thumbnail_states()

        # Refresh the detail view to show the new image
        if self.image_viewer:
            all_versions = self.image_viewer.all_versions
            sg_session = self.image_viewer.sg_session
            self.detail_view.set_folder(folder_name, folder_type, folder.get_image_ids(), all_versions, sg_session)
