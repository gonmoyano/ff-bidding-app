# Sliding Overlay Panel Component

A reusable PySide6 component that provides a panel that slides in from the right edge of the parent widget, overlaying the content with smooth animation.

## Features

- ✨ Smooth slide-in/out animation using QPropertyAnimation
- 🎨 Semi-transparent overlay background
- 🔘 Close button and toggle functionality
- ⚙️ Configurable panel width and animation duration
- 📐 Higher z-order for floating appearance
- 🎯 Click-outside-to-close functionality
- 🔄 Automatic parent resize handling

## Components

### 1. `SlidingOverlayPanel`

Basic sliding panel without background overlay.

**Use case**: When you want a simple sliding panel without dimming the background.

### 2. `OverlayBackground`

Semi-transparent background overlay that can be clicked to close the panel.

**Use case**: Used internally by `SlidingOverlayPanelWithBackground` or can be used standalone.

### 3. `SlidingOverlayPanelWithBackground` (Recommended)

Combined sliding panel with semi-transparent background overlay.

**Use case**: Most common use case - provides a complete overlay solution with background dimming.

## Installation

The component is located in:
```
client/ff_bidding_app/sliding_overlay_panel.py
```

Simply import the component in your application:

```python
from sliding_overlay_panel import SlidingOverlayPanelWithBackground
```

## Basic Usage

### Simple Overlay Panel

```python
from PySide6 import QtWidgets
from sliding_overlay_panel import SlidingOverlayPanelWithBackground

class MyApp(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        # Create main layout
        layout = QtWidgets.QVBoxLayout(self)

        # Add toggle button
        toggle_btn = QtWidgets.QPushButton("Toggle Panel")
        toggle_btn.clicked.connect(self._toggle_panel)
        layout.addWidget(toggle_btn)

        # Add main content
        content = QtWidgets.QTextEdit("Main content area")
        layout.addWidget(content)

        # Create overlay panel
        self.overlay = SlidingOverlayPanelWithBackground(
            parent=self,
            panel_width=400,
            animation_duration=300,
            background_opacity=0.3,
            close_on_background_click=True
        )
        self.overlay.set_title("Settings")

        # Add content to panel
        panel_content = QtWidgets.QWidget()
        # ... add widgets to panel_content ...
        self.overlay.set_content(panel_content)

    def _toggle_panel(self):
        self.overlay.toggle()
```

## API Reference

### `SlidingOverlayPanelWithBackground`

#### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `parent` | QWidget | None | Parent widget (required) |
| `panel_width` | int | 400 | Width of the panel in pixels |
| `animation_duration` | int | 300 | Animation duration in milliseconds |
| `background_opacity` | float | 0.3 | Opacity of the background overlay (0.0 to 1.0) |
| `close_on_background_click` | bool | True | Whether to close the panel when background is clicked |

#### Methods

| Method | Description |
|--------|-------------|
| `set_title(title: str)` | Set the panel title displayed in the header |
| `set_content(widget: QWidget)` | Set the content widget for the panel |
| `show_panel()` | Show the panel with slide-in animation |
| `hide_panel()` | Hide the panel with slide-out animation |
| `toggle()` | Toggle the panel visibility |
| `is_panel_visible() -> bool` | Check if the panel is currently visible |

#### Signals

| Signal | Description |
|--------|-------------|
| `panel_shown` | Emitted when the panel is fully shown |
| `panel_hidden` | Emitted when the panel is fully hidden |

## Advanced Usage

### Multiple Overlay Panels

You can create multiple overlay panels in the same application:

```python
class MyApp(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        # Create settings panel
        self.settings_panel = SlidingOverlayPanelWithBackground(
            parent=self, panel_width=350
        )
        self.settings_panel.set_title("Settings")
        self.settings_panel.set_content(self._create_settings_content())

        # Create filters panel
        self.filters_panel = SlidingOverlayPanelWithBackground(
            parent=self, panel_width=300
        )
        self.filters_panel.set_title("Filters")
        self.filters_panel.set_content(self._create_filters_content())

    def show_settings(self):
        # Hide other panels first
        self.filters_panel.hide_panel()
        # Show settings
        self.settings_panel.show_panel()
```

### Connecting to Signals

```python
def __init__(self):
    super().__init__()

    self.overlay = SlidingOverlayPanelWithBackground(parent=self)

    # Connect signals
    self.overlay.panel_shown.connect(self._on_panel_shown)
    self.overlay.panel_hidden.connect(self._on_panel_hidden)

def _on_panel_shown(self):
    print("Panel is now visible")
    self.toggle_btn.setText("Hide Panel ◀")

def _on_panel_hidden(self):
    print("Panel is now hidden")
    self.toggle_btn.setText("Show Panel ▶")
```

### Custom Styling

The panel components use Qt stylesheets. You can customize the appearance:

```python
# Customize panel background
self.overlay.panel.setStyleSheet("""
    SlidingOverlayPanel {
        background-color: #1e1e1e;
        border-left: 3px solid #4a9eff;
    }
""")

# Customize header
self.overlay.panel.title_label.setStyleSheet("""
    QLabel {
        color: #4a9eff;
        font-size: 14px;
        font-weight: bold;
    }
""")
```

### Without Background Overlay

If you don't want the semi-transparent background:

```python
from sliding_overlay_panel import SlidingOverlayPanel

overlay = SlidingOverlayPanel(
    parent=self,
    panel_width=400,
    animation_duration=300
)
```

## Integration Examples

### FF Bidding App - Packages Tab

The component is already integrated in the Packages tab to show/hide the Package Manager panel:

```python
# In packages_tab.py
from sliding_overlay_panel import SlidingOverlayPanelWithBackground

class PackagesTab(QtWidgets.QWidget):
    def _build_ui(self):
        # ... main content setup ...

        # Create overlay panel for Package Manager
        right_pane = self._create_right_pane()

        self.overlay_panel = SlidingOverlayPanelWithBackground(
            parent=self,
            panel_width=450,
            animation_duration=300,
            background_opacity=0.3,
            close_on_background_click=True
        )
        self.overlay_panel.set_title("Package Manager")
        self.overlay_panel.set_content(right_pane)

        # Connect signals
        self.overlay_panel.panel_shown.connect(self._on_panel_shown)
        self.overlay_panel.panel_hidden.connect(self._on_panel_hidden)
```

### Fireframe Prodigy Application

To apply the same pattern to the Fireframe Prodigy:

```python
# In your main application file
class PackageManagerApp(QtWidgets.QMainWindow):
    def _build_ui(self):
        # Create main content area
        main_content = self._create_main_content()
        self.setCentralWidget(main_content)

        # Create overlay panel for settings
        self.settings_overlay = SlidingOverlayPanelWithBackground(
            parent=main_content,
            panel_width=400
        )
        self.settings_overlay.set_title("Settings")
        self.settings_overlay.set_content(self._create_settings_panel())

        # Add toggle button to toolbar
        toggle_action = QtWidgets.QAction("Settings", self)
        toggle_action.triggered.connect(self.settings_overlay.toggle)
        self.toolbar.addAction(toggle_action)
```

### Prodigy Application

Similar pattern for Prodigy:

```python
class ProdigyApp(QtWidgets.QMainWindow):
    def _build_ui(self):
        # Main content
        main_widget = QtWidgets.QWidget()
        self.setCentralWidget(main_widget)

        # Create overlay for tools panel
        self.tools_overlay = SlidingOverlayPanelWithBackground(
            parent=main_widget,
            panel_width=350
        )
        self.tools_overlay.set_title("Tools")
        self.tools_overlay.set_content(self._create_tools_panel())

        # Create overlay for properties panel
        self.properties_overlay = SlidingOverlayPanelWithBackground(
            parent=main_widget,
            panel_width=400
        )
        self.properties_overlay.set_title("Properties")
        self.properties_overlay.set_content(self._create_properties_panel())
```

## Best Practices

1. **Parent Widget**: Always pass the parent widget that you want the panel to overlay
2. **Panel Width**: Choose an appropriate width (300-500px typically works well)
3. **Animation Duration**: 250-350ms provides smooth animation without feeling sluggish
4. **Background Opacity**: 0.2-0.4 provides good visibility balance
5. **Content Layout**: Use proper layouts in your content widgets for responsive design
6. **Signal Connections**: Connect to `panel_shown` and `panel_hidden` signals to update UI state

## Performance Considerations

- The panel uses hardware-accelerated QPropertyAnimation for smooth performance
- Background overlay uses semi-transparent rendering which is GPU-accelerated
- Panel content is only rendered when visible
- Automatic geometry updates on parent resize

## Troubleshooting

### Panel doesn't appear
- Ensure the parent widget is properly set
- Check that `show_panel()` is called
- Verify the panel width doesn't exceed parent width

### Animation is choppy
- Increase animation_duration for smoother animation
- Check if there are heavy operations in the panel content

### Panel doesn't overlay content
- Ensure the parent widget has a proper layout
- Call `raise_()` on the panel to bring it to front
- Check z-order in the widget hierarchy

## Examples

See `sliding_overlay_panel_example.py` for complete working examples:

1. **Simple Example**: Basic overlay panel without background
2. **Example with Background**: Panel with semi-transparent background (most common)
3. **Multi-Panel Example**: Multiple overlay panels in one application

Run the examples:
```bash
python sliding_overlay_panel_example.py
```

## License

This component is part of the FF Bidding App project.

## Credits

Created for the Fireframe Prodigy and FF Bidding App projects.
