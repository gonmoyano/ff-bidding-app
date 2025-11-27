from PySide6 import QtWidgets, QtCore, QtGui
import logging
import urllib.request
from threading import Thread
import os

try:
    from .logger import logger
    from .bid_selector_widget import CollapsibleGroupBox
except (ImportError, ValueError, SystemError):
    logger = logging.getLogger("FFPackageManager")
    from bid_selector_widget import CollapsibleGroupBox


def create_trash_icon(size=24, color=QtGui.QColor(255, 255, 255, 200)):
    """Create a trash can outline icon from Material Design Icons.

    Args:
        size: Icon size in pixels
        color: Icon color (QColor)

    Returns:
        QIcon with the trash can outline
    """
    # Material Design Icons trash-can-outline path (24x24 viewBox)
    svg_path = "M9 3v1H4v2h1v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V6h1V4h-5V3H9zM7 6h10v13H7V6zm2 2v9h2V8H9zm4 0v9h2V8h-2z"

    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(QtCore.Qt.transparent)

    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)

    # Scale to fit the icon size
    scale = size / 24.0
    painter.scale(scale, scale)

    # Parse and draw the path
    path = QtGui.QPainterPath()
    path.setFillRule(QtCore.Qt.WindingFill)

    # Parse SVG path commands
    i = 0
    commands = svg_path.replace(',', ' ').split()
    current_x, current_y = 0, 0
    start_x, start_y = 0, 0

    while i < len(commands):
        cmd = commands[i]
        if cmd == 'M':
            current_x, current_y = float(commands[i+1]), float(commands[i+2])
            start_x, start_y = current_x, current_y
            path.moveTo(current_x, current_y)
            i += 3
        elif cmd == 'm':
            current_x += float(commands[i+1])
            current_y += float(commands[i+2])
            start_x, start_y = current_x, current_y
            path.moveTo(current_x, current_y)
            i += 3
        elif cmd == 'v':
            current_y += float(commands[i+1])
            path.lineTo(current_x, current_y)
            i += 2
        elif cmd == 'V':
            current_y = float(commands[i+1])
            path.lineTo(current_x, current_y)
            i += 2
        elif cmd == 'h':
            current_x += float(commands[i+1])
            path.lineTo(current_x, current_y)
            i += 2
        elif cmd == 'H':
            current_x = float(commands[i+1])
            path.lineTo(current_x, current_y)
            i += 2
        elif cmd == 'L':
            current_x, current_y = float(commands[i+1]), float(commands[i+2])
            path.lineTo(current_x, current_y)
            i += 3
        elif cmd == 'l':
            current_x += float(commands[i+1])
            current_y += float(commands[i+2])
            path.lineTo(current_x, current_y)
            i += 3
        elif cmd == 'a':
            # Simplified arc - just move to endpoint for now
            rx, ry = float(commands[i+1]), float(commands[i+2])
            rotation = float(commands[i+3])
            large_arc = int(commands[i+4])
            sweep = int(commands[i+5])
            dx, dy = float(commands[i+6]), float(commands[i+7])
            current_x += dx
            current_y += dy
            path.lineTo(current_x, current_y)
            i += 8
        elif cmd == 'z' or cmd == 'Z':
            path.closeSubpath()
            current_x, current_y = start_x, start_y
            i += 1
        else:
            # Try to parse as number (continuation of previous command)
            try:
                float(cmd)
                i += 1
            except ValueError:
                i += 1

    painter.fillPath(path, color)
    painter.end()

    return QtGui.QIcon(pixmap)


class DocumentLoader(QtCore.QObject):
    """Asynchronous document/thumbnail loader using QThread."""

    imageLoaded = QtCore.Signal(str, QtGui.QPixmap)  # (cache_key, pixmap)
    loadFailed = QtCore.Signal(str)  # (cache_key)

    def __init__(self, parent=None, max_concurrent=5):
        super().__init__(parent)
        self.load_queue = []
        self.active_loads = 0
        self.max_concurrent = max_concurrent
        self.loading_keys = set()
        self.active_threads = []

    def clear_queue(self):
        """Clear the loading queue and reset loading keys."""
        self.load_queue.clear()

    def load_image(self, url, cache_key, width, height):
        """Queue an image for loading."""
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

            thread = Thread(target=self._load_in_thread, args=(url, cache_key, width, height))
            thread.daemon = True
            thread.start()

            self.active_threads.append(thread)
            self.active_threads = [t for t in self.active_threads if t.is_alive()]

    def _load_in_thread(self, url, cache_key, width, height):
        """Load image in background thread."""
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                image_bytes = response.read()
                pixmap = QtGui.QPixmap()
                pixmap.loadFromData(image_bytes)

                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(
                        width, height,
                        QtCore.Qt.KeepAspectRatio,
                        QtCore.Qt.SmoothTransformation
                    )
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


class DroppableSectionContainer(QtWidgets.QWidget):
    """Container widget that accepts document drops for a section (Script or Documents)."""

    documentDropped = QtCore.Signal(int, str)  # (document_id, section_name)

    def __init__(self, section_name, parent=None):
        super().__init__(parent)
        self.section_name = section_name
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        """Handle drag enter event."""
        if event.mimeData().hasFormat("application/x-document-version-id"):
            event.acceptProposedAction()
            self.setStyleSheet("background-color: rgba(74, 159, 255, 50);")
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        """Handle drag leave event."""
        self.setStyleSheet("")

    def dropEvent(self, event):
        """Handle drop event."""
        if event.mimeData().hasFormat("application/x-document-version-id"):
            document_id_bytes = event.mimeData().data("application/x-document-version-id")
            document_id = int(bytes(document_id_bytes).decode())

            event.acceptProposedAction()
            self.documentDropped.emit(document_id, self.section_name)
            self.dragLeaveEvent(event)
        else:
            event.ignore()


class DocumentFolderWidget(QtWidgets.QWidget):
    """Widget representing a folder that can accept document drops."""

    documentDropped = QtCore.Signal(int, str, str)  # (document_id, folder_name, folder_type)
    doubleClicked = QtCore.Signal(str, str)  # (folder_name, folder_type)

    def __init__(self, folder_name, folder_type, parent=None, icon_size=64):
        """Initialize folder widget."""
        super().__init__(parent)
        self.folder_name = folder_name
        self.folder_type = folder_type
        self.document_ids = set()
        self.icon_size = icon_size
        self._contains_selected = False
        self._is_drag_over = False

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

        # Document count
        self.count_label = QtWidgets.QLabel("0 documents")
        self.count_label.setStyleSheet("color: #888; font-size: 10px;")
        self.count_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.count_label)

        self._update_style()

    def _update_style(self):
        """Update the folder styling based on current state."""
        if self._is_drag_over:
            self.setStyleSheet("""
                DocumentFolderWidget {
                    background-color: #3a5f8f;
                    border: 2px solid #4a9eff;
                    border-radius: 4px;
                }
            """)
        elif self._contains_selected:
            self.setStyleSheet("""
                DocumentFolderWidget {
                    background-color: #2b3a4a;
                    border: 2px solid #4a9eff;
                    border-radius: 4px;
                }
                DocumentFolderWidget:hover {
                    background-color: #354555;
                    border: 2px solid #5aafff;
                }
            """)
        else:
            self.setStyleSheet("""
                DocumentFolderWidget {
                    background-color: #2b2b2b;
                    border: 1px solid #444;
                    border-radius: 4px;
                }
                DocumentFolderWidget:hover {
                    background-color: #353535;
                    border: 1px solid #555;
                }
            """)

    def set_contains_selected(self, contains_selected):
        """Set whether this folder contains the currently selected document."""
        if self._contains_selected != contains_selected:
            self._contains_selected = contains_selected
            self._update_style()
            self._update_icon()

    def _update_icon(self):
        """Update the folder icon with current size and selection state."""
        self.icon_label.setPixmap(self.style().standardIcon(
            QtWidgets.QStyle.SP_DirIcon
        ).pixmap(self.icon_size, self.icon_size))

        if self._contains_selected:
            self.icon_label.setStyleSheet("""
                QLabel {
                    border: 3px solid #4a9eff;
                    border-radius: 4px;
                    padding: 2px;
                }
            """)
        else:
            self.icon_label.setStyleSheet("""
                QLabel {
                    border: 3px solid #2b2b2b;
                    border-radius: 4px;
                    padding: 2px;
                }
            """)

    def set_icon_size(self, size):
        """Set the icon size."""
        self.icon_size = size
        self._update_icon()

    def dragEnterEvent(self, event):
        """Handle drag enter event."""
        if event.mimeData().hasFormat("application/x-document-version-id"):
            event.acceptProposedAction()
            self._is_drag_over = True
            self._update_style()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        """Handle drag leave event."""
        self._is_drag_over = False
        self._update_style()

    def dropEvent(self, event):
        """Handle drop event."""
        if event.mimeData().hasFormat("application/x-document-version-id"):
            document_id_bytes = event.mimeData().data("application/x-document-version-id")
            document_id = int(bytes(document_id_bytes).decode())

            self.document_ids.add(document_id)
            self._update_count()

            event.acceptProposedAction()
            self.documentDropped.emit(document_id, self.folder_name, self.folder_type)
            self.dragLeaveEvent(event)
        else:
            event.ignore()

    def _update_count(self):
        """Update the document count label."""
        count = len(self.document_ids)
        self.count_label.setText(f"{count} document{'s' if count != 1 else ''}")

    def add_document(self, document_id):
        """Add a document to this folder."""
        self.document_ids.add(document_id)
        self._update_count()

    def remove_document(self, document_id):
        """Remove a document from this folder."""
        self.document_ids.discard(document_id)
        self._update_count()

    def get_document_ids(self):
        """Get all document IDs in this folder."""
        return self.document_ids.copy()

    def set_document_ids(self, document_ids):
        """Set the document IDs in this folder."""
        self.document_ids = set(document_ids)
        self._update_count()

    def mouseDoubleClickEvent(self, event):
        """Handle double-click to view folder contents."""
        if event.button() == QtCore.Qt.LeftButton:
            self.doubleClicked.emit(self.folder_name, self.folder_type)
        super().mouseDoubleClickEvent(event)


class DocumentFolderDetailView(QtWidgets.QWidget):
    """Widget for viewing contents of a specific folder grouped by type."""

    backClicked = QtCore.Signal()
    documentRemoved = QtCore.Signal(int, str, str)  # (document_id, folder_name, folder_type)
    documentEnlarged = QtCore.Signal(dict)  # (version_data)

    def __init__(self, parent=None, shared_cache=None, shared_loader=None):
        super().__init__(parent)
        self.folder_name = None
        self.folder_type = None
        self.document_versions = []
        self.sg_session = None
        self.thumbnail_size = 170

        self.image_cache = shared_cache if shared_cache is not None else {}
        self.label_cache = {}

        if shared_loader is not None:
            self.document_loader = shared_loader
        else:
            self.document_loader = DocumentLoader(self)

        self.document_loader.imageLoaded.connect(self._on_image_loaded)
        self.document_loader.loadFailed.connect(self._on_image_load_failed)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the detail view UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        # Header
        header_layout = QtWidgets.QHBoxLayout()

        back_btn = QtWidgets.QPushButton("< Back")
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

        # Scroll area for thumbnails
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        container = QtWidgets.QWidget()
        self.thumbnails_layout = QtWidgets.QGridLayout(container)
        self.thumbnails_layout.setSpacing(10)
        self.thumbnails_layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)

        scroll_area.setWidget(container)
        layout.addWidget(scroll_area)

    def set_folder(self, folder_name, folder_type, document_ids, all_versions, sg_session=None):
        """Set the folder to display."""
        self.folder_name = folder_name
        self.folder_type = folder_type
        self.sg_session = sg_session

        type_label = "Asset" if folder_type == "asset" else "Scene"
        self.breadcrumb_label.setText(f"Current folder: {type_label}: {folder_name}")

        self.document_versions = [v for v in all_versions if v.get('id') in document_ids]

        self._populate_thumbnails()

    def _populate_thumbnails(self):
        """Populate the thumbnails grid."""
        # Clear existing
        while self.thumbnails_layout.count():
            item = self.thumbnails_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.label_cache.clear()

        # Calculate columns
        item_width = self.thumbnail_size + 10
        columns = max(1, self.width() // item_width) if self.width() > 0 else 2

        for idx, version in enumerate(self.document_versions):
            row = idx // columns
            col = idx % columns
            item_widget = self._create_thumbnail_item(version)
            self.thumbnails_layout.addWidget(item_widget, row, col)

    def _create_thumbnail_item(self, version):
        """Create a thumbnail item widget."""
        thumb_width = self.thumbnail_size
        thumb_height = int(thumb_width * 0.82)
        container_width = thumb_width + 10
        container_height = thumb_height + 50

        container = QtWidgets.QWidget()
        container_layout = QtWidgets.QVBoxLayout(container)
        container_layout.setContentsMargins(5, 5, 5, 5)
        container_layout.setSpacing(5)

        # Document container
        doc_container = QtWidgets.QWidget()
        doc_container.setFixedSize(thumb_width, thumb_height)

        # Document label
        doc_label = QtWidgets.QLabel(doc_container)
        doc_label.setFixedSize(thumb_width, thumb_height)
        doc_label.setAlignment(QtCore.Qt.AlignCenter)
        doc_label.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                border: 2px solid #444;
                border-radius: 4px;
            }
        """)

        self._load_thumbnail_for_label(doc_label, version, thumb_width - 4, thumb_height - 4)
        doc_label.setCursor(QtCore.Qt.PointingHandCursor)
        doc_label.mouseDoubleClickEvent = lambda event: self.documentEnlarged.emit(version)

        # Remove icon with trash can
        remove_icon = QtWidgets.QPushButton(doc_container)
        remove_icon.setFixedSize(28, 28)
        remove_icon.move(thumb_width - 34, thumb_height - 34)
        remove_icon.setCursor(QtCore.Qt.PointingHandCursor)
        remove_icon.clicked.connect(lambda: self._remove_document(version.get('id')))

        # Set trash can icon
        remove_icon.setIcon(create_trash_icon(20, QtGui.QColor(255, 255, 255, 200)))
        remove_icon.setIconSize(QtCore.QSize(20, 20))

        # Style for the button
        remove_icon.setStyleSheet("""
            QPushButton {
                background-color: rgba(40, 40, 40, 180);
                border: 2px solid rgba(255, 255, 255, 200);
                border-radius: 14px;
                padding: 2px;
            }
            QPushButton:hover {
                border: 2px solid rgba(255, 80, 80, 255);
                background-color: rgba(60, 40, 40, 200);
            }
        """)

        container_layout.addWidget(doc_container)

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

    def _load_thumbnail_for_label(self, label, version, width, height):
        """Load thumbnail for a label."""
        try:
            uploaded_movie = version.get('sg_uploaded_movie')
            filename = ''
            if uploaded_movie and isinstance(uploaded_movie, dict):
                filename = uploaded_movie.get('name', '')
            ext = os.path.splitext(filename)[1].lower() if filename else ''

            image_data = version.get('image')
            if image_data:
                url = None
                if isinstance(image_data, str):
                    url = image_data
                elif isinstance(image_data, dict):
                    url = image_data.get('url') or image_data.get('local_path')

                if url:
                    cache_key = f"{url}_{width}x{height}"
                    if cache_key in self.image_cache:
                        label.setPixmap(self.image_cache[cache_key])
                        return

                    label.setText("Loading...")
                    if cache_key not in self.label_cache:
                        self.label_cache[cache_key] = []
                    self.label_cache[cache_key].append(label)
                    self.document_loader.load_image(url, cache_key, width, height)
                    return

            self._show_document_icon(label, ext)
        except Exception as e:
            logger.error(f"Error loading thumbnail: {e}")
            label.setText("Error")

    def _show_document_icon(self, label, ext):
        """Show document type icon."""
        if ext in ['.pdf']:
            icon_text, icon_color = "PDF", "#e74c3c"
        elif ext in ['.doc', '.docx']:
            icon_text, icon_color = "DOC", "#3498db"
        elif ext in ['.xls', '.xlsx']:
            icon_text, icon_color = "XLS", "#27ae60"
        elif ext in ['.txt', '.md']:
            icon_text, icon_color = "TXT", "#95a5a6"
        else:
            icon_text, icon_color = "DOC", "#9b59b6"

        label.setText(icon_text)
        label.setStyleSheet(f"""
            QLabel {{
                background-color: {icon_color};
                color: white;
                font-size: 24px;
                font-weight: bold;
                border: 2px solid #444;
                border-radius: 4px;
            }}
        """)

    @QtCore.Slot(str, QtGui.QPixmap)
    def _on_image_loaded(self, cache_key, pixmap):
        """Handle image loaded."""
        self.image_cache[cache_key] = pixmap
        if cache_key in self.label_cache:
            for label in self.label_cache[cache_key]:
                try:
                    if label and not label.isHidden():
                        label.setPixmap(pixmap)
                except (RuntimeError, AttributeError):
                    pass
            del self.label_cache[cache_key]

    @QtCore.Slot(str)
    def _on_image_load_failed(self, cache_key):
        """Handle image load failed."""
        if cache_key in self.label_cache:
            for label in self.label_cache[cache_key]:
                try:
                    if label and not label.isHidden():
                        label.setText("Failed")
                except RuntimeError:
                    pass
            del self.label_cache[cache_key]

    def _remove_document(self, document_id):
        """Remove document from folder."""
        if document_id and self.folder_name and self.folder_type:
            self.documentRemoved.emit(document_id, self.folder_name, self.folder_type)

    def set_thumbnail_size(self, size):
        """Set thumbnail size."""
        self.thumbnail_size = size
        self._populate_thumbnails()


class DocumentFolderPaneWidget(QtWidgets.QWidget):
    """Widget displaying Script/Documents sections and Asset/Scene folders for documents."""

    documentDropped = QtCore.Signal(int, str, str)  # (document_id, folder_name, folder_type)
    documentRemoved = QtCore.Signal(int, str, str)  # (document_id, folder_name, folder_type)
    packageSelected = QtCore.Signal(str)  # (package_name or empty string)

    def __init__(self, parent=None):
        """Initialize folder pane widget."""
        super().__init__(parent)

        # Document IDs in each section (only populated via drag and drop)
        self.script_document_ids = set()
        self.documents_document_ids = set()

        # Folder widgets
        self.asset_folders = {}
        self.scene_folders = {}

        from PySide6.QtCore import QSettings
        self.settings = QSettings("FFBiddingApp", "DocumentFolderPane")
        self.current_icon_size = self.settings.value("folder_icon_size", 64, type=int)
        self.section_thumbnail_size = self.settings.value("section_thumbnail_size", 120, type=int)
        self.detail_thumbnail_size = self.settings.value("detail_thumbnail_size", 170, type=int)

        self.shared_image_cache = {}
        self.shared_document_loader = DocumentLoader(self)
        self.shared_document_loader.imageLoaded.connect(self._on_image_loaded)
        self.shared_document_loader.loadFailed.connect(self._on_image_load_failed)

        self.document_viewer = None
        self.label_cache = {}

        self._is_relayouting = False
        self.resize_timer = QtCore.QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self._relayout_all)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the folder pane UI."""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # Toolbar
        toolbar_layout = QtWidgets.QHBoxLayout()

        toolbar_layout.addWidget(QtWidgets.QLabel("Package:"))
        self.package_dropdown = QtWidgets.QComboBox()
        self.package_dropdown.setMinimumWidth(150)
        self.package_dropdown.addItem("(No Package)")
        self.package_dropdown.currentTextChanged.connect(self._on_package_dropdown_changed)
        toolbar_layout.addWidget(self.package_dropdown)

        toolbar_layout.addSpacing(20)

        self.slider_label = QtWidgets.QLabel("Icon Size:")
        toolbar_layout.addWidget(self.slider_label)

        self.icon_size_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.icon_size_slider.setMinimum(32)
        self.icon_size_slider.setMaximum(128)
        self.icon_size_slider.setValue(self.current_icon_size)
        self.icon_size_slider.setTickPosition(QtWidgets.QSlider.NoTicks)
        self.icon_size_slider.setFixedWidth(150)
        self.icon_size_slider.valueChanged.connect(self._on_size_changed)
        toolbar_layout.addWidget(self.icon_size_slider)

        self.icon_size_label = QtWidgets.QLabel(str(self.current_icon_size))
        self.icon_size_label.setFixedWidth(30)
        self.icon_size_label.setAlignment(QtCore.Qt.AlignRight)
        toolbar_layout.addWidget(self.icon_size_label)

        toolbar_layout.addStretch()

        main_layout.addLayout(toolbar_layout)

        # Stacked widget for views
        self.view_stack = QtWidgets.QStackedWidget()

        # View 0: Main grid view
        main_view = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(main_view)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        container = QtWidgets.QWidget()
        self.container_layout = QtWidgets.QVBoxLayout(container)
        self.container_layout.setContentsMargins(5, 5, 5, 5)
        self.container_layout.setSpacing(10)

        # Script section
        self.script_group = CollapsibleGroupBox("Script (0 items)")
        self.script_container = DroppableSectionContainer("Script")
        self.script_container.documentDropped.connect(self._on_document_dropped_to_section)
        self.script_layout = QtWidgets.QGridLayout(self.script_container)
        self.script_layout.setSpacing(10)
        self.script_layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        self.script_group.addWidget(self.script_container)
        self.container_layout.addWidget(self.script_group)

        # Documents section
        self.documents_group = CollapsibleGroupBox("Documents (0 items)")
        self.documents_container = DroppableSectionContainer("Documents")
        self.documents_container.documentDropped.connect(self._on_document_dropped_to_section)
        self.documents_layout = QtWidgets.QGridLayout(self.documents_container)
        self.documents_layout.setSpacing(10)
        self.documents_layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        self.documents_group.addWidget(self.documents_container)
        self.container_layout.addWidget(self.documents_group)

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

        self.view_stack.addWidget(main_view)

        # View 1: Folder detail view
        self.detail_view = DocumentFolderDetailView(
            self,
            shared_cache=self.shared_image_cache,
            shared_loader=self.shared_document_loader
        )
        self.detail_view.backClicked.connect(self._show_main_view)
        self.detail_view.documentRemoved.connect(self._handle_document_removed)
        self.detail_view.documentEnlarged.connect(self._handle_document_enlarged)
        self.view_stack.addWidget(self.detail_view)

        self.view_stack.currentChanged.connect(self._on_view_changed)

        main_layout.addWidget(self.view_stack)

        # Create "No Package Selected" overlay
        self._create_no_package_overlay()

        self.setMinimumWidth(250)

    def _create_no_package_overlay(self):
        """Create the 'No Package Selected' overlay widget."""
        self.no_package_overlay = QtWidgets.QFrame(self)
        self.no_package_overlay.setObjectName("noPackageOverlay")
        self.no_package_overlay.setStyleSheet("""
            QFrame#noPackageOverlay {
                background-color: rgba(40, 40, 40, 220);
                border-radius: 4px;
            }
        """)

        overlay_layout = QtWidgets.QVBoxLayout(self.no_package_overlay)
        overlay_layout.setAlignment(QtCore.Qt.AlignCenter)

        # Icon
        icon_label = QtWidgets.QLabel()
        icon_label.setPixmap(
            self.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxQuestion).pixmap(64, 64)
        )
        icon_label.setAlignment(QtCore.Qt.AlignCenter)
        overlay_layout.addWidget(icon_label)

        # Message
        message_label = QtWidgets.QLabel("No Package Selected")
        message_label.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        message_label.setAlignment(QtCore.Qt.AlignCenter)
        overlay_layout.addWidget(message_label)

        # Sub-message
        sub_message = QtWidgets.QLabel("Select a package from the dropdown above\nto view and manage folder contents.")
        sub_message.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 12px;
            }
        """)
        sub_message.setAlignment(QtCore.Qt.AlignCenter)
        overlay_layout.addWidget(sub_message)

        # Initially shown (no package selected by default)
        self.no_package_overlay.show()
        # Defer initial geometry update until layout is complete
        QtCore.QTimer.singleShot(0, self._update_overlay_geometry)

    def _update_overlay_geometry(self):
        """Update the overlay position to cover the view_stack area (below toolbar)."""
        if hasattr(self, 'no_package_overlay') and hasattr(self, 'view_stack'):
            # Get the view_stack geometry relative to this widget
            stack_geometry = self.view_stack.geometry()
            self.no_package_overlay.setGeometry(stack_geometry)
            self.no_package_overlay.raise_()

    def _show_no_package_overlay(self):
        """Show the 'No Package Selected' overlay."""
        if hasattr(self, 'no_package_overlay'):
            self._update_overlay_geometry()
            self.no_package_overlay.show()
            self.no_package_overlay.raise_()

    def _hide_no_package_overlay(self):
        """Hide the 'No Package Selected' overlay."""
        if hasattr(self, 'no_package_overlay'):
            self.no_package_overlay.hide()

    def resizeEvent(self, event):
        """Handle resize to update overlay position."""
        super().resizeEvent(event)
        # Update overlay geometry when pane resizes
        if hasattr(self, 'no_package_overlay') and self.no_package_overlay.isVisible():
            self._update_overlay_geometry()

    def showEvent(self, event):
        """Handle show event to update overlay position."""
        super().showEvent(event)
        # Update overlay geometry when pane is shown
        QtCore.QTimer.singleShot(0, self._update_overlay_geometry)

    def _on_size_changed(self, value):
        """Handle size slider change."""
        current_view = self.view_stack.currentIndex()

        if current_view == 0:
            self.current_icon_size = value
            self.icon_size_label.setText(str(value))
            self.settings.setValue("folder_icon_size", value)

            for folder in self.asset_folders.values():
                folder.set_icon_size(value)
            for folder in self.scene_folders.values():
                folder.set_icon_size(value)

            self._relayout_all()
        else:
            self.detail_thumbnail_size = value
            self.icon_size_label.setText(str(value))
            self.settings.setValue("detail_thumbnail_size", value)
            self.detail_view.set_thumbnail_size(value)

    def _on_view_changed(self, index):
        """Handle view stack change."""
        if index == 0:
            self.slider_label.setText("Icon Size:")
            self.icon_size_slider.blockSignals(True)
            self.icon_size_slider.setMinimum(32)
            self.icon_size_slider.setMaximum(128)
            self.icon_size_slider.setValue(self.current_icon_size)
            self.icon_size_label.setText(str(self.current_icon_size))
            self.icon_size_slider.blockSignals(False)
        else:
            self.slider_label.setText("Thumb Size:")
            self.icon_size_slider.blockSignals(True)
            self.icon_size_slider.setMinimum(120)
            self.icon_size_slider.setMaximum(250)
            self.icon_size_slider.setValue(self.detail_thumbnail_size)
            self.icon_size_label.setText(str(self.detail_thumbnail_size))
            self.icon_size_slider.blockSignals(False)

    def _on_package_dropdown_changed(self, package_name):
        """Handle package dropdown selection change."""
        if package_name == "(No Package)":
            self._show_no_package_overlay()
            self.packageSelected.emit("")
        else:
            self._hide_no_package_overlay()
            self.packageSelected.emit(package_name)

    def set_packages(self, package_names):
        """Set the list of packages in the dropdown."""
        self.package_dropdown.blockSignals(True)
        while self.package_dropdown.count() > 1:
            self.package_dropdown.removeItem(1)
        for name in package_names:
            self.package_dropdown.addItem(name)
        self.package_dropdown.blockSignals(False)

    def set_selected_package(self, package_name):
        """Programmatically select a package in the dropdown."""
        self.package_dropdown.blockSignals(True)
        if not package_name:
            self.package_dropdown.setCurrentText("(No Package)")
            self._show_no_package_overlay()
        else:
            index = self.package_dropdown.findText(package_name)
            if index >= 0:
                self.package_dropdown.setCurrentIndex(index)
            self._hide_no_package_overlay()
        self.package_dropdown.blockSignals(False)

    def get_selected_package(self):
        """Get the currently selected package name."""
        text = self.package_dropdown.currentText()
        return None if text == "(No Package)" else text

    def _on_document_dropped_to_section(self, document_id, section_name):
        """Handle document dropped into Script or Documents section."""
        # Add to the appropriate section
        if section_name == "Script":
            self.script_document_ids.add(document_id)
            sg_version_type = "Script"
        else:
            self.documents_document_ids.add(document_id)
            sg_version_type = "Document"

        # Update version type in ShotGrid
        if self.document_viewer and self.document_viewer.sg_session:
            try:
                self.document_viewer.sg_session.sg.update(
                    'Version',
                    document_id,
                    {'sg_version_type': sg_version_type}
                )
                logger.info(f"Updated document {document_id} type to {sg_version_type}")
            except Exception as e:
                logger.error(f"Failed to update document type: {e}")

        # Link to selected package
        selected_package = self.get_selected_package()
        if selected_package and self.document_viewer:
            self._link_document_to_package(document_id, section_name)

        # Refresh the sections
        self._refresh_sections()

        # Emit signal
        self.documentDropped.emit(document_id, section_name, "section")

    def _link_document_to_package(self, document_id, section_name):
        """Link a document to the currently selected package."""
        selected_package = self.get_selected_package()
        logger.warning(f"DEBUG _link_document_to_package called: doc={document_id}, section={section_name}, selected_package={selected_package}")

        if not selected_package or not self.document_viewer:
            logger.warning(f"DEBUG Skipping link: selected_package={selected_package}, document_viewer={self.document_viewer}")
            return

        try:
            packages_tab = getattr(self.document_viewer, 'packages_tab', None)
            if not packages_tab:
                logger.warning("DEBUG No packages_tab found on document_viewer")
                return

            # Get package ID from packages dict
            sg_package_id = None
            packages = getattr(packages_tab, 'packages', {})
            logger.warning(f"DEBUG packages dict has {len(packages)} packages: {list(packages.keys())}")

            for pkg_name, pkg_data in packages.items():
                if pkg_name == selected_package:
                    sg_package_id = pkg_data.get('sg_package_id')
                    logger.warning(f"DEBUG Found package '{pkg_name}' with sg_package_id={sg_package_id}")
                    break

            if not sg_package_id:
                logger.warning(f"DEBUG Could not find package ID for '{selected_package}' in packages: {list(packages.keys())}")
                return

            folder_path = f"/{section_name}"

            logger.warning(f"DEBUG Calling link_version_to_package_with_folder: version={document_id}, package={sg_package_id}, folder={folder_path}")
            self.document_viewer.sg_session.link_version_to_package_with_folder(
                version_id=document_id,
                package_id=sg_package_id,
                folder_name=folder_path
            )

            logger.warning(f"DEBUG Successfully linked document {document_id} to package {selected_package} in {folder_path}")

            # Refresh package data tree
            if hasattr(packages_tab, 'package_data_tree') and packages_tab.package_data_tree:
                logger.warning(f"DEBUG Refreshing package_data_tree for package {sg_package_id}")
                packages_tab.package_data_tree.load_package_versions(sg_package_id)
            else:
                logger.warning(f"DEBUG No package_data_tree: hasattr={hasattr(packages_tab, 'package_data_tree')}")

        except Exception as e:
            logger.error(f"Failed to link document to package: {e}", exc_info=True)

    def _refresh_sections(self):
        """Refresh Script and Documents sections."""
        # Clear and rebuild Script section
        while self.script_layout.count():
            item = self.script_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Clear and rebuild Documents section
        while self.documents_layout.count():
            item = self.documents_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.label_cache.clear()

        if not self.document_viewer:
            return

        all_versions = getattr(self.document_viewer, 'all_versions', [])

        # Find versions for each section
        script_versions = [v for v in all_versions if v.get('id') in self.script_document_ids]
        documents_versions = [v for v in all_versions if v.get('id') in self.documents_document_ids]

        # Update group titles
        self.script_group.setTitle(f"Script ({len(script_versions)} item{'s' if len(script_versions) != 1 else ''})")
        self.documents_group.setTitle(f"Documents ({len(documents_versions)} item{'s' if len(documents_versions) != 1 else ''})")

        # Calculate columns
        thumb_size = self.section_thumbnail_size
        item_width = thumb_size + 10
        columns = max(1, self.width() // item_width) if self.width() > 0 else 2

        # Populate Script section
        for idx, version in enumerate(script_versions):
            row, col = idx // columns, idx % columns
            item = self._create_section_thumbnail(version, "Script")
            self.script_layout.addWidget(item, row, col)

        # Populate Documents section
        for idx, version in enumerate(documents_versions):
            row, col = idx // columns, idx % columns
            item = self._create_section_thumbnail(version, "Documents")
            self.documents_layout.addWidget(item, row, col)

    def _create_section_thumbnail(self, version, section_name):
        """Create a thumbnail for Script or Documents section."""
        thumb_size = self.section_thumbnail_size
        thumb_height = int(thumb_size * 0.82)

        container = QtWidgets.QWidget()
        container_layout = QtWidgets.QVBoxLayout(container)
        container_layout.setContentsMargins(5, 5, 5, 5)
        container_layout.setSpacing(5)

        doc_container = QtWidgets.QWidget()
        doc_container.setFixedSize(thumb_size, thumb_height)

        doc_label = QtWidgets.QLabel(doc_container)
        doc_label.setFixedSize(thumb_size, thumb_height)
        doc_label.setAlignment(QtCore.Qt.AlignCenter)
        doc_label.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                border: 2px solid #444;
                border-radius: 4px;
            }
        """)

        self._load_thumbnail_for_label(doc_label, version, thumb_size - 4, thumb_height - 4)
        doc_label.setCursor(QtCore.Qt.PointingHandCursor)
        doc_label.mouseDoubleClickEvent = lambda event: self._enlarge_document(version)

        # Remove button with trash can icon
        remove_btn = QtWidgets.QPushButton(doc_container)
        remove_btn.setFixedSize(24, 24)
        remove_btn.move(thumb_size - 28, thumb_height - 28)
        remove_btn.setCursor(QtCore.Qt.PointingHandCursor)
        remove_btn.clicked.connect(lambda: self._remove_from_section(version.get('id'), section_name))

        # Set trash can icon
        remove_btn.setIcon(create_trash_icon(16, QtGui.QColor(255, 255, 255, 180)))
        remove_btn.setIconSize(QtCore.QSize(16, 16))

        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(40, 40, 40, 180);
                border: 2px solid rgba(255, 255, 255, 180);
                border-radius: 12px;
                padding: 2px;
            }
            QPushButton:hover {
                border: 2px solid rgba(255, 80, 80, 255);
                background-color: rgba(60, 40, 40, 200);
            }
        """)

        container_layout.addWidget(doc_container)

        code_label = QtWidgets.QLabel(version.get('code', 'Unknown'))
        code_label.setWordWrap(True)
        code_label.setMaximumWidth(thumb_size)
        code_label.setAlignment(QtCore.Qt.AlignCenter)
        code_label.setStyleSheet("font-size: 10px; color: #ddd;")
        container_layout.addWidget(code_label)

        container.setFixedSize(thumb_size + 10, thumb_height + 40)
        return container

    def _remove_from_section(self, document_id, section_name):
        """Remove document from Script or Documents section."""
        if section_name == "Script":
            self.script_document_ids.discard(document_id)
        else:
            self.documents_document_ids.discard(document_id)

        self._refresh_sections()
        self.documentRemoved.emit(document_id, section_name, "section")

    def _load_thumbnail_for_label(self, label, version, width, height):
        """Load thumbnail for a label."""
        try:
            uploaded_movie = version.get('sg_uploaded_movie')
            filename = ''
            if uploaded_movie and isinstance(uploaded_movie, dict):
                filename = uploaded_movie.get('name', '')
            ext = os.path.splitext(filename)[1].lower() if filename else ''

            image_data = version.get('image')
            if image_data:
                url = None
                if isinstance(image_data, str):
                    url = image_data
                elif isinstance(image_data, dict):
                    url = image_data.get('url') or image_data.get('local_path')

                if url:
                    cache_key = f"{url}_{width}x{height}"
                    if cache_key in self.shared_image_cache:
                        label.setPixmap(self.shared_image_cache[cache_key])
                        return

                    label.setText("...")
                    if cache_key not in self.label_cache:
                        self.label_cache[cache_key] = []
                    self.label_cache[cache_key].append(label)
                    self.shared_document_loader.load_image(url, cache_key, width, height)
                    return

            self._show_document_icon(label, ext)
        except Exception as e:
            logger.error(f"Error loading thumbnail: {e}")

    def _show_document_icon(self, label, ext):
        """Show document type icon."""
        if ext in ['.pdf']:
            icon_text, icon_color = "PDF", "#e74c3c"
        elif ext in ['.doc', '.docx']:
            icon_text, icon_color = "DOC", "#3498db"
        elif ext in ['.xls', '.xlsx']:
            icon_text, icon_color = "XLS", "#27ae60"
        else:
            icon_text, icon_color = "DOC", "#9b59b6"

        label.setText(icon_text)
        label.setStyleSheet(f"""
            QLabel {{
                background-color: {icon_color};
                color: white;
                font-size: 20px;
                font-weight: bold;
                border: 2px solid #444;
                border-radius: 4px;
            }}
        """)

    @QtCore.Slot(str, QtGui.QPixmap)
    def _on_image_loaded(self, cache_key, pixmap):
        """Handle image loaded."""
        self.shared_image_cache[cache_key] = pixmap
        if cache_key in self.label_cache:
            for label in self.label_cache[cache_key]:
                try:
                    if label and not label.isHidden():
                        label.setPixmap(pixmap)
                except (RuntimeError, AttributeError):
                    pass
            del self.label_cache[cache_key]

    @QtCore.Slot(str)
    def _on_image_load_failed(self, cache_key):
        """Handle image load failed."""
        if cache_key in self.label_cache:
            del self.label_cache[cache_key]

    def _enlarge_document(self, version_data):
        """Open document in viewer dialog."""
        if not self.document_viewer:
            return

        try:
            from .document_viewer_widget import DocumentViewerDialog
        except ImportError:
            from document_viewer_widget import DocumentViewerDialog

        dialog = DocumentViewerDialog(version_data, self.document_viewer.sg_session, self)
        dialog.exec()

    # Asset and Scene folder methods
    def set_assets(self, asset_names):
        """Set the asset folders."""
        for folder in self.asset_folders.values():
            folder.deleteLater()
        self.asset_folders.clear()

        while self.assets_layout.count():
            item = self.assets_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        for asset_name in sorted(asset_names):
            folder = DocumentFolderWidget(asset_name, 'asset', self, icon_size=self.current_icon_size)
            folder.documentDropped.connect(self._on_folder_document_dropped)
            folder.doubleClicked.connect(self._show_folder_detail)
            self.asset_folders[asset_name] = folder

        self.assets_group.setTitle(f"Assets ({len(asset_names)})")
        QtCore.QTimer.singleShot(50, self._relayout_all)

    def set_scenes(self, scene_codes):
        """Set the scene folders."""
        for folder in self.scene_folders.values():
            folder.deleteLater()
        self.scene_folders.clear()

        while self.scenes_layout.count():
            item = self.scenes_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        for scene_code in sorted(scene_codes):
            folder = DocumentFolderWidget(scene_code, 'scene', self, icon_size=self.current_icon_size)
            folder.documentDropped.connect(self._on_folder_document_dropped)
            folder.doubleClicked.connect(self._show_folder_detail)
            self.scene_folders[scene_code] = folder

        self.scenes_group.setTitle(f"Scenes ({len(scene_codes)})")
        QtCore.QTimer.singleShot(50, self._relayout_all)

    def _on_folder_document_dropped(self, document_id, folder_name, folder_type):
        """Handle document dropped into a folder."""
        # Emit signal - linking is handled by document_viewer_widget.update_thumbnail_states
        # which creates the correct path with document category (e.g., /scenes/ARR/Script)
        self.documentDropped.emit(document_id, folder_name, folder_type)

    def _link_folder_document_to_package(self, document_id, folder_name, folder_type):
        """Link a document from a folder to the selected package."""
        selected_package = self.get_selected_package()
        logger.warning(f"DEBUG _link_folder_document_to_package called: doc={document_id}, folder={folder_name}, type={folder_type}, selected_package={selected_package}")

        if not selected_package or not self.document_viewer:
            logger.warning(f"DEBUG Skipping folder link: selected_package={selected_package}, document_viewer={self.document_viewer}")
            return

        try:
            packages_tab = getattr(self.document_viewer, 'packages_tab', None)
            if not packages_tab:
                logger.warning("DEBUG No packages_tab found on document_viewer for folder link")
                return

            # Get package ID from packages dict
            sg_package_id = None
            packages = getattr(packages_tab, 'packages', {})
            logger.warning(f"DEBUG packages dict has {len(packages)} packages for folder link")

            for pkg_name, pkg_data in packages.items():
                if pkg_name == selected_package:
                    sg_package_id = pkg_data.get('sg_package_id')
                    break

            if not sg_package_id:
                logger.warning(f"DEBUG Could not find package ID for '{selected_package}' for folder link")
                return

            folder_type_plural = 'assets' if folder_type == 'asset' else 'scenes'
            folder_path = f"/{folder_type_plural}/{folder_name}"

            logger.warning(f"DEBUG Calling link_version_to_package_with_folder for folder: version={document_id}, package={sg_package_id}, folder={folder_path}")
            self.document_viewer.sg_session.link_version_to_package_with_folder(
                version_id=document_id,
                package_id=sg_package_id,
                folder_name=folder_path
            )

            logger.warning(f"DEBUG Successfully linked document {document_id} to package {selected_package} in {folder_path}")

            if hasattr(packages_tab, 'package_data_tree') and packages_tab.package_data_tree:
                packages_tab.package_data_tree.load_package_versions(sg_package_id)

        except Exception as e:
            logger.error(f"Failed to link document to package: {e}", exc_info=True)

    def _relayout_all(self):
        """Relayout all sections and folders."""
        if self._is_relayouting:
            return

        try:
            self._is_relayouting = True

            pane_width = self.width()
            if pane_width <= 0:
                pane_width = 250

            folder_width = self.current_icon_size + 40
            columns = max(1, pane_width // folder_width)

            if self.asset_folders:
                self._layout_in_grid(self.asset_folders, self.assets_layout, columns)

            if self.scene_folders:
                self._layout_in_grid(self.scene_folders, self.scenes_layout, columns)

            self._refresh_sections()

        finally:
            self._is_relayouting = False

    def _layout_in_grid(self, folders_dict, grid_layout, columns):
        """Layout folders in a grid."""
        if not folders_dict or columns <= 0:
            return

        folder_names = sorted(folders_dict.keys())

        for idx, folder_name in enumerate(folder_names):
            folder = folders_dict.get(folder_name)
            if folder:
                grid_layout.removeWidget(folder)
                row = idx // columns
                col = idx % columns
                grid_layout.addWidget(folder, row, col)
                folder.show()

    def resizeEvent(self, event):
        """Handle resize event."""
        super().resizeEvent(event)
        self.resize_timer.stop()
        self.resize_timer.start(200)

    def _show_folder_detail(self, folder_name, folder_type):
        """Show detail view for a folder."""
        if folder_type == 'asset':
            folder = self.asset_folders.get(folder_name)
        else:
            folder = self.scene_folders.get(folder_name)

        if not folder or not self.document_viewer:
            return

        document_ids = folder.get_document_ids()
        all_versions = getattr(self.document_viewer, 'all_versions', [])
        sg_session = self.document_viewer.sg_session

        self.detail_view.set_folder(folder_name, folder_type, document_ids, all_versions, sg_session)
        self.view_stack.setCurrentIndex(1)

    def _show_main_view(self):
        """Return to main view."""
        self.view_stack.setCurrentIndex(0)

    def _handle_document_removed(self, document_id, folder_name, folder_type):
        """Handle document removal from folder."""
        if folder_type == 'asset':
            folder = self.asset_folders.get(folder_name)
        else:
            folder = self.scene_folders.get(folder_name)

        if folder:
            folder.remove_document(document_id)

        self.documentRemoved.emit(document_id, folder_name, folder_type)

        # Refresh detail view
        if folder and self.document_viewer:
            all_versions = getattr(self.document_viewer, 'all_versions', [])
            sg_session = self.document_viewer.sg_session
            self.detail_view.set_folder(folder_name, folder_type, folder.get_document_ids(), all_versions, sg_session)

    def _handle_document_enlarged(self, version_data):
        """Handle document enlargement."""
        self._enlarge_document(version_data)

    def highlight_folders_for_document(self, document_id):
        """Highlight folders containing the document."""
        for folder in self.asset_folders.values():
            folder.set_contains_selected(document_id is not None and document_id in folder.document_ids)

        for folder in self.scene_folders.values():
            folder.set_contains_selected(document_id is not None and document_id in folder.document_ids)

    def get_folder_mappings(self):
        """Get all document-to-folder mappings."""
        mappings = {
            'script': list(self.script_document_ids),
            'documents': list(self.documents_document_ids),
            'assets': {},
            'scenes': {}
        }

        for asset_name, folder in self.asset_folders.items():
            doc_ids = list(folder.get_document_ids())
            if doc_ids:
                mappings['assets'][asset_name] = doc_ids

        for scene_code, folder in self.scene_folders.items():
            doc_ids = list(folder.get_document_ids())
            if doc_ids:
                mappings['scenes'][scene_code] = doc_ids

        return mappings

    def load_folder_mappings(self, mappings):
        """Load document-to-folder mappings."""
        if not mappings:
            return

        self.script_document_ids = set(mappings.get('script', []))
        self.documents_document_ids = set(mappings.get('documents', []))

        for asset_name, doc_ids in mappings.get('assets', {}).items():
            if asset_name in self.asset_folders:
                self.asset_folders[asset_name].set_document_ids(doc_ids)

        for scene_code, doc_ids in mappings.get('scenes', {}).items():
            if scene_code in self.scene_folders:
                self.scene_folders[scene_code].set_document_ids(doc_ids)

        self._refresh_sections()
