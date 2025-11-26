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


class DroppableDocumentGroupContainer(QtWidgets.QWidget):
    """Container widget that accepts document drops for a specific type group."""

    documentDropped = QtCore.Signal(int, str)  # (document_id, target_type)

    def __init__(self, document_type, parent=None):
        super().__init__(parent)
        self.document_type = document_type
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

            self.documentDropped.emit(document_id, self.document_type)

            self.dragLeaveEvent(event)
        else:
            event.ignore()


class DocumentFolderDetailView(QtWidgets.QWidget):
    """Widget for viewing contents of a specific folder grouped by type."""

    backClicked = QtCore.Signal()
    documentRemoved = QtCore.Signal(int, str, str)  # (document_id, folder_name, folder_type)
    documentEnlarged = QtCore.Signal(dict)  # (version_data)
    documentDroppedToGroup = QtCore.Signal(int, str, str, str)  # (document_id, target_type, folder_name, folder_type)

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

        # Scroll area for grouped thumbnails
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        container = QtWidgets.QWidget()
        self.groups_layout = QtWidgets.QVBoxLayout(container)
        self.groups_layout.setContentsMargins(5, 5, 5, 5)
        self.groups_layout.setSpacing(10)

        # Create collapsible groups for each document type
        self.type_groups = {}
        for doc_type in ['Script', 'Misc']:
            group = CollapsibleGroupBox(f"{doc_type} (0 items)")
            group_container = DroppableDocumentGroupContainer(doc_type)
            group_container.documentDropped.connect(self._on_document_dropped_to_group)
            group_layout = QtWidgets.QGridLayout(group_container)
            group_layout.setSpacing(10)
            group_layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
            group.addWidget(group_container)
            self.groups_layout.addWidget(group)
            self.type_groups[doc_type] = {
                'group': group,
                'layout': group_layout,
                'container': group_container
            }

        self.groups_layout.addStretch()

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

        self._populate_groups()
        self._preload_images()

    def _populate_groups(self):
        """Populate the type groups with thumbnails."""
        try:
            self.document_loader.imageLoaded.disconnect(self._on_image_loaded)
            self.document_loader.loadFailed.disconnect(self._on_image_load_failed)
        except:
            pass

        self.label_cache.clear()

        grouped_documents = {
            'Script': [],
            'Misc': []
        }

        for version in self.document_versions:
            doc_type = self._get_version_type(version)
            if doc_type in grouped_documents:
                grouped_documents[doc_type].append(version)

        for doc_type, versions in grouped_documents.items():
            group_data = self.type_groups[doc_type]
            group = group_data['group']
            layout = group_data['layout']

            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            count = len(versions)
            group.setTitle(f"{doc_type} ({count} item{'s' if count != 1 else ''})")

            item_width = self.thumbnail_size + 10
            columns = max(1, self.width() // item_width)
            for idx, version in enumerate(versions):
                row = idx // columns
                col = idx % columns

                item_widget = self._create_thumbnail_item(version)
                layout.addWidget(item_widget, row, col)

        try:
            self.document_loader.imageLoaded.connect(self._on_image_loaded)
            self.document_loader.loadFailed.connect(self._on_image_load_failed)
        except:
            pass

    def _create_thumbnail_item(self, version):
        """Create a thumbnail item widget with document preview and controls."""
        thumb_width = self.thumbnail_size
        thumb_height = int(thumb_width * 0.82)
        container_width = thumb_width + 10
        container_height = thumb_height + 50

        container = QtWidgets.QWidget()
        container_layout = QtWidgets.QVBoxLayout(container)
        container_layout.setContentsMargins(5, 5, 5, 5)
        container_layout.setSpacing(5)

        # Document container with overlay for remove icon
        doc_container = QtWidgets.QWidget()
        doc_container.setFixedSize(thumb_width, thumb_height)

        # Document label with thumbnail/icon
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

        # Load thumbnail or show icon
        self._load_thumbnail_for_label(doc_label, version, thumb_width - 4, thumb_height - 4)

        # Make label clickable for enlargement
        doc_label.setCursor(QtCore.Qt.PointingHandCursor)
        doc_label.mouseDoubleClickEvent = lambda event: self.documentEnlarged.emit(version)

        # Remove icon overlay
        remove_icon = QtWidgets.QPushButton(doc_container)
        remove_icon.setFixedSize(28, 28)
        remove_icon.move(thumb_width - 34, thumb_height - 34)
        remove_icon.setCursor(QtCore.Qt.PointingHandCursor)
        remove_icon.clicked.connect(lambda: self._remove_document(version.get('id')))

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
        remove_icon.setText("x")

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

    def _load_thumbnail_for_label(self, label, version, width=166, height=136):
        """Load thumbnail for a label from version data."""
        try:
            # Get file extension
            uploaded_movie = version.get('sg_uploaded_movie')
            filename = ''
            if uploaded_movie:
                if isinstance(uploaded_movie, dict):
                    filename = uploaded_movie.get('name', '')
            ext = os.path.splitext(filename)[1].lower() if filename else ''

            # Check for image thumbnail first
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
                    label.setStyleSheet(label.styleSheet() + "color: #888; font-size: 10px;")

                    if cache_key not in self.label_cache:
                        self.label_cache[cache_key] = []
                    self.label_cache[cache_key].append(label)

                    self.document_loader.load_image(url, cache_key, width, height)
                    return

            # No thumbnail, show document icon
            self._show_document_icon(label, ext, width, height)

        except Exception as e:
            logger.error(f"Error loading thumbnail: {e}", exc_info=True)
            label.setText("Error")
            label.setStyleSheet(label.styleSheet() + "color: #cc3333;")

    def _show_document_icon(self, label, ext, width, height):
        """Show document type icon in label."""
        if ext in ['.pdf']:
            icon_text = "PDF"
            icon_color = "#e74c3c"
        elif ext in ['.doc', '.docx']:
            icon_text = "DOC"
            icon_color = "#3498db"
        elif ext in ['.xls', '.xlsx']:
            icon_text = "XLS"
            icon_color = "#27ae60"
        elif ext in ['.txt', '.md']:
            icon_text = "TXT"
            icon_color = "#95a5a6"
        else:
            icon_text = "DOC"
            icon_color = "#9b59b6"

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
        """Handle successful image load."""
        self.image_cache[cache_key] = pixmap

        if cache_key in self.label_cache:
            for label in self.label_cache[cache_key]:
                try:
                    if label and not label.isHidden():
                        label.setPixmap(pixmap)
                        label.setStyleSheet("")
                except (RuntimeError, AttributeError):
                    pass
            del self.label_cache[cache_key]

    @QtCore.Slot(str)
    def _on_image_load_failed(self, cache_key):
        """Handle failed image load."""
        if cache_key in self.label_cache:
            for label in self.label_cache[cache_key]:
                try:
                    if label and not label.isHidden():
                        label.setText("Failed")
                        label.setStyleSheet("color: #cc3333; font-size: 10px;")
                except RuntimeError:
                    pass
            del self.label_cache[cache_key]

    def _remove_document(self, document_id):
        """Remove a document from the folder."""
        if document_id and self.folder_name and self.folder_type:
            self.documentRemoved.emit(document_id, self.folder_name, self.folder_type)

    def _on_document_dropped_to_group(self, document_id, target_type):
        """Handle document dropped into a type group."""
        if self.folder_name and self.folder_type:
            self.documentDroppedToGroup.emit(document_id, target_type, self.folder_name, self.folder_type)

    def set_thumbnail_size(self, size):
        """Set the thumbnail size and refresh the view."""
        self.thumbnail_size = size
        self._populate_groups()

    def _preload_images(self):
        """Preload all images in background."""
        thumb_width = self.thumbnail_size
        thumb_height = int(thumb_width * 0.82)

        for version in self.document_versions:
            image_data = version.get('image')
            if not image_data:
                continue

            url = None
            if isinstance(image_data, str):
                url = image_data
            elif isinstance(image_data, dict):
                url = image_data.get('url') or image_data.get('local_path')

            if not url:
                continue

            cache_key = f"{url}_{thumb_width - 4}x{thumb_height - 4}"

            if cache_key in self.image_cache:
                continue

            self.document_loader.load_image(url, cache_key, thumb_width - 4, thumb_height - 4)

    def _get_version_type(self, version):
        """Get the type category for a version."""
        sg_version_type = version.get('sg_version_type', '')
        if isinstance(sg_version_type, dict):
            version_type = sg_version_type.get('name', '').lower()
        else:
            version_type = str(sg_version_type).lower()

        if 'script' in version_type:
            return 'Script'
        else:
            return 'Misc'


class DocumentFolderPaneWidget(QtWidgets.QWidget):
    """Widget displaying folders for Assets and Scenes (for documents)."""

    documentDropped = QtCore.Signal(int, str, str)  # (document_id, folder_name, folder_type)
    documentRemoved = QtCore.Signal(int, str, str)  # (document_id, folder_name, folder_type)
    packageSelected = QtCore.Signal(str)  # (package_name or empty string)

    def __init__(self, parent=None):
        """Initialize folder pane widget."""
        super().__init__(parent)
        self.asset_folders = {}
        self.scene_folders = {}

        from PySide6.QtCore import QSettings
        self.settings = QSettings("FFBiddingApp", "DocumentFolderPane")
        self.current_icon_size = self.settings.value("folder_icon_size", 64, type=int)
        self.detail_thumbnail_size = self.settings.value("detail_thumbnail_size", 170, type=int)

        self.shared_image_cache = {}
        self.shared_document_loader = DocumentLoader(self)

        self.document_viewer = None

        self._is_relayouting = False

        self.resize_timer = QtCore.QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self._relayout_folders_delayed)

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

        # View 0: Folder grid view
        folder_grid_view = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(folder_grid_view)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

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

        self.view_stack.addWidget(folder_grid_view)

        # View 1: Folder detail view
        self.detail_view = DocumentFolderDetailView(
            self,
            shared_cache=self.shared_image_cache,
            shared_loader=self.shared_document_loader
        )
        self.detail_view.backClicked.connect(self._show_folder_grid)
        self.detail_view.documentRemoved.connect(self._handle_document_removed)
        self.detail_view.documentEnlarged.connect(self._handle_document_enlarged)
        self.detail_view.documentDroppedToGroup.connect(self._handle_document_dropped_to_group)
        self.view_stack.addWidget(self.detail_view)

        self.view_stack.currentChanged.connect(self._on_view_changed)

        main_layout.addWidget(self.view_stack)

        self.setMinimumWidth(250)

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

            self._relayout_folders()
        else:
            self.detail_thumbnail_size = value
            self.icon_size_label.setText(str(value))
            self.settings.setValue("detail_thumbnail_size", value)
            self.detail_view.set_thumbnail_size(value)

    def _on_view_changed(self, index):
        """Handle view stack index change."""
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

    def _relayout_folders(self):
        """Re-layout folders in grid based on current pane width."""
        if self._is_relayouting:
            return

        if not self.isVisible():
            return

        try:
            self._is_relayouting = True

            pane_width = self.width()
            if pane_width <= 0:
                pane_width = 250

            folder_width = self.current_icon_size + 40
            columns = max(1, pane_width // folder_width)

            if self.asset_folders:
                self._layout_folders_in_grid(self.asset_folders, self.assets_layout, columns)

            if self.scene_folders:
                self._layout_folders_in_grid(self.scene_folders, self.scenes_layout, columns)

        finally:
            self._is_relayouting = False

    def _relayout_folders_delayed(self):
        """Re-layout folders after resize timer expires."""
        self._relayout_folders()

    def _layout_folders_in_grid(self, folders_dict, grid_layout, columns):
        """Layout folders in a grid."""
        if not folders_dict or columns <= 0:
            return

        try:
            folder_names = sorted(folders_dict.keys())

            widgets_to_keep = set()
            for folder_name in folder_names:
                folder = folders_dict.get(folder_name)
                if folder:
                    widgets_to_keep.add(folder)

            items_to_remove = []
            for i in range(grid_layout.count()):
                item = grid_layout.itemAt(i)
                if item and item.widget():
                    widget = item.widget()
                    if widget not in widgets_to_keep:
                        items_to_remove.append(widget)

            for widget in items_to_remove:
                grid_layout.removeWidget(widget)
                widget.setParent(None)

            for idx, folder_name in enumerate(folder_names):
                folder = folders_dict.get(folder_name)
                if folder:
                    grid_layout.removeWidget(folder)
                    row = idx // columns
                    col = idx % columns
                    grid_layout.addWidget(folder, row, col)
                    folder.show()

        except Exception as e:
            logger.error(f"Error laying out folders in grid: {e}", exc_info=True)

    def resizeEvent(self, event):
        """Handle resize event."""
        super().resizeEvent(event)
        if self.asset_folders or self.scene_folders:
            self.resize_timer.stop()
            self.resize_timer.start(400)

    def set_assets(self, asset_names):
        """Set the asset folders."""
        for folder_widget in self.asset_folders.values():
            folder_widget.deleteLater()
        self.asset_folders.clear()

        while self.assets_layout.count():
            item = self.assets_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        for asset_name in sorted(asset_names):
            folder = DocumentFolderWidget(asset_name, 'asset', self, icon_size=self.current_icon_size)
            folder.documentDropped.connect(self.documentDropped.emit)
            folder.doubleClicked.connect(self._show_folder_detail)
            self.asset_folders[asset_name] = folder

        self.assets_group.setTitle(f"Assets ({len(asset_names)})")

        QtCore.QTimer.singleShot(50, self._relayout_folders)

    def set_scenes(self, scene_codes):
        """Set the scene folders."""
        for folder_widget in self.scene_folders.values():
            folder_widget.deleteLater()
        self.scene_folders.clear()

        while self.scenes_layout.count():
            item = self.scenes_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        for scene_code in sorted(scene_codes):
            folder = DocumentFolderWidget(scene_code, 'scene', self, icon_size=self.current_icon_size)
            folder.documentDropped.connect(self.documentDropped.emit)
            folder.doubleClicked.connect(self._show_folder_detail)
            self.scene_folders[scene_code] = folder

        self.scenes_group.setTitle(f"Scenes ({len(scene_codes)})")

        QtCore.QTimer.singleShot(50, self._relayout_folders)

    def get_folder_mappings(self):
        """Get all document-to-folder mappings."""
        mappings = {
            'assets': {},
            'scenes': {}
        }

        for asset_name, folder in self.asset_folders.items():
            document_ids = list(folder.get_document_ids())
            if document_ids:
                mappings['assets'][asset_name] = document_ids

        for scene_code, folder in self.scene_folders.items():
            document_ids = list(folder.get_document_ids())
            if document_ids:
                mappings['scenes'][scene_code] = document_ids

        return mappings

    def highlight_folders_for_document(self, document_id):
        """Highlight all folders that contain the specified document."""
        for folder in self.asset_folders.values():
            if document_id is not None and document_id in folder.document_ids:
                folder.set_contains_selected(True)
            else:
                folder.set_contains_selected(False)

        for folder in self.scene_folders.values():
            if document_id is not None and document_id in folder.document_ids:
                folder.set_contains_selected(True)
            else:
                folder.set_contains_selected(False)

    def _on_package_dropdown_changed(self, package_name):
        """Handle package dropdown selection change."""
        if package_name == "(No Package)":
            self.packageSelected.emit("")
        else:
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
        else:
            index = self.package_dropdown.findText(package_name)
            if index >= 0:
                self.package_dropdown.setCurrentIndex(index)
        self.package_dropdown.blockSignals(False)

    def get_selected_package(self):
        """Get the currently selected package name."""
        text = self.package_dropdown.currentText()
        return None if text == "(No Package)" else text

    def load_folder_mappings(self, mappings):
        """Load document-to-folder mappings."""
        if not mappings:
            return

        asset_mappings = mappings.get('assets', {})
        for asset_name, document_ids in asset_mappings.items():
            if asset_name in self.asset_folders:
                self.asset_folders[asset_name].set_document_ids(document_ids)

        scene_mappings = mappings.get('scenes', {})
        for scene_code, document_ids in scene_mappings.items():
            if scene_code in self.scene_folders:
                self.scene_folders[scene_code].set_document_ids(document_ids)

    def _show_folder_detail(self, folder_name, folder_type):
        """Show detail view for a specific folder."""
        if folder_type == 'asset':
            folder = self.asset_folders.get(folder_name)
        else:
            folder = self.scene_folders.get(folder_name)

        if not folder:
            logger.error(f"Folder {folder_name} ({folder_type}) not found")
            return

        document_ids = folder.get_document_ids()
        if not document_ids:
            document_ids = set()

        if not self.document_viewer:
            logger.error("Document viewer reference not set")
            return

        all_versions = self.document_viewer.all_versions
        sg_session = self.document_viewer.sg_session

        self.detail_view.set_folder(folder_name, folder_type, document_ids, all_versions, sg_session)

        self.view_stack.setCurrentIndex(1)

    def _show_folder_grid(self):
        """Return to folder grid view."""
        self.view_stack.setCurrentIndex(0)

    def _handle_document_removed(self, document_id, folder_name, folder_type):
        """Handle document removal from folder."""
        if folder_type == 'asset':
            folder = self.asset_folders.get(folder_name)
        else:
            folder = self.scene_folders.get(folder_name)

        if not folder:
            logger.error(f"Folder {folder_name} ({folder_type}) not found")
            return

        folder.remove_document(document_id)

        self.documentRemoved.emit(document_id, folder_name, folder_type)

        if self.document_viewer:
            self.document_viewer.update_thumbnail_states()

        if self.document_viewer:
            all_versions = self.document_viewer.all_versions
            sg_session = self.document_viewer.sg_session
            self.detail_view.set_folder(folder_name, folder_type, folder.get_document_ids(), all_versions, sg_session)

    def _handle_document_enlarged(self, version_data):
        """Handle request to enlarge a document."""
        if not self.document_viewer:
            logger.error("Document viewer reference not set")
            return

        from .document_viewer_widget import DocumentViewerDialog
        dialog = DocumentViewerDialog(version_data, self.document_viewer.sg_session, self)
        dialog.exec()

    def _handle_document_dropped_to_group(self, document_id, target_type, folder_name, folder_type):
        """Handle document dropped into a type group in detail view."""
        if folder_type == 'asset':
            folder = self.asset_folders.get(folder_name)
        else:
            folder = self.scene_folders.get(folder_name)

        if not folder:
            logger.error(f"Folder {folder_name} ({folder_type}) not found")
            return

        folder.add_document(document_id)

        if self.document_viewer:
            self.document_viewer.update_thumbnail_states()

        if self.document_viewer:
            all_versions = self.document_viewer.all_versions
            sg_session = self.document_viewer.sg_session
            self.detail_view.set_folder(folder_name, folder_type, folder.get_document_ids(), all_versions, sg_session)
