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


class DroppableScriptContainer(QtWidgets.QWidget):
    """Container widget that accepts document drops for the Script section."""

    documentDropped = QtCore.Signal(int)  # (document_id)

    def __init__(self, parent=None):
        super().__init__(parent)
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
            self.documentDropped.emit(document_id)
            self.dragLeaveEvent(event)
        else:
            event.ignore()


class DocumentFolderPaneWidget(QtWidgets.QWidget):
    """Widget displaying Script section for documents (documents shown directly at root level)."""

    documentDropped = QtCore.Signal(int, str, str)  # (document_id, folder_name, folder_type) - kept for compatibility
    documentRemoved = QtCore.Signal(int, str, str)  # (document_id, folder_name, folder_type)
    packageSelected = QtCore.Signal(str)  # (package_name or empty string)

    def __init__(self, parent=None):
        """Initialize folder pane widget."""
        super().__init__(parent)

        # Document IDs in the Script section
        self.script_document_ids = set()

        from PySide6.QtCore import QSettings
        self.settings = QSettings("FFBiddingApp", "DocumentFolderPane")
        self.thumbnail_size = self.settings.value("script_thumbnail_size", 150, type=int)

        self.shared_image_cache = {}
        self.shared_document_loader = DocumentLoader(self)
        self.shared_document_loader.imageLoaded.connect(self._on_image_loaded)
        self.shared_document_loader.loadFailed.connect(self._on_image_load_failed)

        self.document_viewer = None
        self.label_cache = {}

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

        self.slider_label = QtWidgets.QLabel("Thumb Size:")
        toolbar_layout.addWidget(self.slider_label)

        self.size_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.size_slider.setMinimum(100)
        self.size_slider.setMaximum(250)
        self.size_slider.setValue(self.thumbnail_size)
        self.size_slider.setTickPosition(QtWidgets.QSlider.NoTicks)
        self.size_slider.setFixedWidth(150)
        self.size_slider.valueChanged.connect(self._on_size_changed)
        toolbar_layout.addWidget(self.size_slider)

        self.size_label = QtWidgets.QLabel(str(self.thumbnail_size))
        self.size_label.setFixedWidth(30)
        self.size_label.setAlignment(QtCore.Qt.AlignRight)
        toolbar_layout.addWidget(self.size_label)

        toolbar_layout.addStretch()

        main_layout.addLayout(toolbar_layout)

        # Scroll area for Script section
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        container = QtWidgets.QWidget()
        self.container_layout = QtWidgets.QVBoxLayout(container)
        self.container_layout.setContentsMargins(5, 5, 5, 5)
        self.container_layout.setSpacing(10)

        # Script section - documents shown directly at root level
        self.script_group = CollapsibleGroupBox("Script (0 items)")
        self.script_container = DroppableScriptContainer()
        self.script_container.documentDropped.connect(self._on_document_dropped_to_script)
        self.script_layout = QtWidgets.QGridLayout(self.script_container)
        self.script_layout.setSpacing(10)
        self.script_layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        self.script_group.addWidget(self.script_container)
        self.container_layout.addWidget(self.script_group)

        self.container_layout.addStretch()

        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

        self.setMinimumWidth(250)

    def _on_size_changed(self, value):
        """Handle size slider change."""
        self.thumbnail_size = value
        self.size_label.setText(str(value))
        self.settings.setValue("script_thumbnail_size", value)
        self._refresh_script_view()

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

    def _on_document_dropped_to_script(self, document_id):
        """Handle document dropped into Script section."""
        self.script_document_ids.add(document_id)

        # Update the version type in ShotGrid
        if self.document_viewer and self.document_viewer.sg_session:
            try:
                self.document_viewer.sg_session.sg.update(
                    'Version',
                    document_id,
                    {'sg_version_type': 'Script'}
                )
                logger.info(f"Updated document {document_id} type to Script")
            except Exception as e:
                logger.error(f"Failed to update document type: {e}")

        # Refresh the view
        self._refresh_script_view()

        # Notify that document was dropped (compatibility signal)
        self.documentDropped.emit(document_id, "Script", "script")

    def _refresh_script_view(self):
        """Refresh the Script section with current documents."""
        # Clear existing items
        while self.script_layout.count():
            item = self.script_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.label_cache.clear()

        if not self.document_viewer:
            return

        # Get all versions and filter for Script type
        all_versions = getattr(self.document_viewer, 'all_versions', [])
        script_versions = []

        for version in all_versions:
            sg_version_type = version.get('sg_version_type', '')
            if isinstance(sg_version_type, dict):
                version_type = sg_version_type.get('name', '').lower()
            else:
                version_type = str(sg_version_type).lower()

            if 'script' in version_type:
                script_versions.append(version)
                self.script_document_ids.add(version.get('id'))

        # Update group title
        count = len(script_versions)
        self.script_group.setTitle(f"Script ({count} item{'s' if count != 1 else ''})")

        # Calculate columns based on width
        item_width = self.thumbnail_size + 10
        columns = max(1, self.width() // item_width) if self.width() > 0 else 2

        # Create thumbnail items
        for idx, version in enumerate(script_versions):
            row = idx // columns
            col = idx % columns
            item_widget = self._create_thumbnail_item(version)
            self.script_layout.addWidget(item_widget, row, col)

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
        doc_label.mouseDoubleClickEvent = lambda event: self._enlarge_document(version)

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

                    if cache_key in self.shared_image_cache:
                        label.setPixmap(self.shared_image_cache[cache_key])
                        return

                    label.setText("Loading...")
                    label.setStyleSheet(label.styleSheet() + "color: #888; font-size: 10px;")

                    if cache_key not in self.label_cache:
                        self.label_cache[cache_key] = []
                    self.label_cache[cache_key].append(label)

                    self.shared_document_loader.load_image(url, cache_key, width, height)
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
        self.shared_image_cache[cache_key] = pixmap

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
        """Remove a document from the Script section."""
        if document_id:
            self.script_document_ids.discard(document_id)
            self.documentRemoved.emit(document_id, "Script", "script")
            self._refresh_script_view()

    def _enlarge_document(self, version_data):
        """Open document in viewer dialog."""
        if not self.document_viewer:
            logger.error("Document viewer reference not set")
            return

        try:
            from .document_viewer_widget import DocumentViewerDialog
        except ImportError:
            from document_viewer_widget import DocumentViewerDialog

        dialog = DocumentViewerDialog(version_data, self.document_viewer.sg_session, self)
        dialog.exec()

    def highlight_folders_for_document(self, document_id):
        """Compatibility method - no-op since we don't have folders anymore."""
        pass

    # Compatibility methods for the old folder-based API
    def set_assets(self, asset_names):
        """Compatibility method - triggers Script section refresh."""
        self._refresh_script_view()

    def set_scenes(self, scene_codes):
        """Compatibility method - triggers Script section refresh."""
        self._refresh_script_view()

    def get_folder_mappings(self):
        """Get document mappings - returns Script section documents."""
        return {
            'script': list(self.script_document_ids)
        }

    def load_folder_mappings(self, mappings):
        """Load document mappings - loads Script section documents."""
        if not mappings:
            return

        script_docs = mappings.get('script', [])
        self.script_document_ids = set(script_docs)
        self._refresh_script_view()

    def resizeEvent(self, event):
        """Handle resize event."""
        super().resizeEvent(event)
        # Trigger refresh to recalculate columns
        QtCore.QTimer.singleShot(100, self._refresh_script_view)
