from PySide6 import QtWidgets, QtCore, QtGui
import logging

try:
    from .logger import logger
    from .bid_selector_widget import CollapsibleGroupBox
except (ImportError, ValueError, SystemError):
    logger = logging.getLogger("FFPackageManager")
    from bid_selector_widget import CollapsibleGroupBox


class FolderWidget(QtWidgets.QWidget):
    """Widget representing a folder that can accept image drops."""

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


class FolderPaneWidget(QtWidgets.QWidget):
    """Widget displaying folders for Assets and Scenes."""

    def __init__(self, parent=None):
        """Initialize folder pane widget."""
        super().__init__(parent)
        self.asset_folders = {}  # asset_name -> FolderWidget
        self.scene_folders = {}  # scene_code -> FolderWidget
        self.current_icon_size = 64  # Default icon size

        # Debounce timer for resize events
        self.resize_timer = QtCore.QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self._relayout_folders_delayed)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the folder pane UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Icon size slider
        slider_layout = QtWidgets.QHBoxLayout()
        slider_layout.addWidget(QtWidgets.QLabel("Icon Size:"))

        self.icon_size_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.icon_size_slider.setMinimum(32)
        self.icon_size_slider.setMaximum(128)
        self.icon_size_slider.setValue(64)
        self.icon_size_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.icon_size_slider.setTickInterval(16)
        self.icon_size_slider.valueChanged.connect(self._on_icon_size_changed)
        slider_layout.addWidget(self.icon_size_slider, 1)

        self.icon_size_label = QtWidgets.QLabel("64")
        self.icon_size_label.setFixedWidth(30)
        self.icon_size_label.setAlignment(QtCore.Qt.AlignRight)
        slider_layout.addWidget(self.icon_size_label)

        layout.addLayout(slider_layout)

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

        # Set minimum width
        self.setMinimumWidth(250)

    def _on_icon_size_changed(self, value):
        """Handle icon size slider change."""
        self.current_icon_size = value
        self.icon_size_label.setText(str(value))

        # Update all existing folder icons
        for folder in self.asset_folders.values():
            folder.set_icon_size(value)
        for folder in self.scene_folders.values():
            folder.set_icon_size(value)

        # Re-layout folders
        self._relayout_folders()

    def _relayout_folders(self):
        """Re-layout folders in grid based on current pane width."""
        # Safety check - don't relayout if being destroyed
        if not self.isVisible():
            return

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
            self.resize_timer.start(200)  # Wait 200ms after last resize

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
