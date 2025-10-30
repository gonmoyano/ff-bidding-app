

# Multi-Entity Reference Widget for ShotGrid

A professional-grade Qt widget for displaying and managing ShotGrid entity references in table cells, featuring a modern pill/tag UI with add/remove capabilities.

## Features

✨ **Visual Design**
- Rounded pill/tag display for each entity reference
- Dark theme matching ShotGrid's UI
- Smooth hover effects and transitions
- Responsive flow layout with automatic wrapping
- Professional styling with proper spacing and contrast

🎯 **Functionality**
- Display multiple entity references in a single cell
- Add new entity references via '+' button
- Remove references with 'X' button on each pill
- Automatic layout adjustment based on cell width
- Signal emission for change tracking
- Get/set entity lists programmatically

🔧 **Integration**
- Works seamlessly with QTableWidget
- Compatible with ShotGrid API data format
- Signal/slot architecture for data updates
- Proper sizing and scrolling support
- Cell widget best practices

## Components

### 1. EntityPillWidget
Individual entity reference displayed as a pill.

**Features:**
- Entity name display
- Remove button (X)
- Hover effects
- Rounded rectangle styling

**Signals:**
- `removeRequested(entity)` - Emitted when X is clicked

### 2. MultiEntityReferenceWidget
Container for multiple entity pills.

**Features:**
- Flow layout for pills
- Add button (+)
- Scroll support
- Entity management

**Signals:**
- `entitiesChanged(entities)` - Emitted when entities are added/removed

**Methods:**
```python
# Set entities
widget.set_entities([
    {"type": "CustomEntity07", "id": 101, "name": "cre_deer"},
    {"type": "CustomEntity07", "id": 102, "name": "cre_fray"}
])

# Get entities
entities = widget.get_entities()

# Add entity
widget.add_entity({"type": "Asset", "id": 123, "name": "prop_table"})
```

### 3. FlowLayout
Custom layout that arranges widgets in a flow, wrapping as needed.

### 4. AddEntityDialog
Simple dialog for adding new entity references.
(In production, replace with ShotGrid's entity picker)

## Installation

1. Copy `multi_entity_reference_widget.py` to your project
2. Import the widget:
```python
from multi_entity_reference_widget import MultiEntityReferenceWidget
```

## Usage

### Basic Usage

```python
from PySide6 import QtWidgets
from multi_entity_reference_widget import MultiEntityReferenceWidget

# Create widget
widget = MultiEntityReferenceWidget(
    entities=[
        {"type": "CustomEntity07", "id": 101, "name": "cre_deer"},
        {"type": "CustomEntity07", "id": 102, "name": "cre_fray"}
    ],
    allow_add=True
)

# Connect to change signal
widget.entitiesChanged.connect(on_entities_changed)

def on_entities_changed(entities):
    print(f"Current entities: {[e['name'] for e in entities]}")
```

### In QTableWidget

```python
# Create table
table = QtWidgets.QTableWidget()
table.setRowCount(5)
table.setColumnCount(3)

# Add widget to cell
row = 0
col = 2
widget = MultiEntityReferenceWidget(entities=breakdown_item["sg_bid_assets"])
widget.entitiesChanged.connect(lambda entities: update_breakdown(row, entities))
table.setCellWidget(row, col, widget)

# Set appropriate row height
table.verticalHeader().setDefaultSectionSize(80)
```

### Complete Example

See `multi_entity_reference_example.py` for a full working example with:
- VFX Breakdown table
- Entity management
- ShotGrid integration
- Save/refresh functionality

Run it:
```bash
python multi_entity_reference_example.py
```

## ShotGrid Integration

### Data Format

The widget expects ShotGrid entity dictionaries:

```python
{
    "type": "CustomEntity07",  # Entity type
    "id": 101,                 # Entity ID
    "name": "cre_deer"         # Display name
}
```

### Reading from ShotGrid

```python
import shotgun_api3

sg = shotgun_api3.Shotgun(url, script_name, api_key)

# Query breakdown with assets
breakdown = sg.find_one(
    "CustomEntity02",
    [["id", "is", breakdown_id]],
    ["sg_bid_assets"]
)

# Get entity references
assets = breakdown.get("sg_bid_assets", [])

# Set in widget
widget.set_entities(assets)
```

### Writing to ShotGrid

```python
# Get current entities from widget
current_entities = widget.get_entities()

# Update ShotGrid
sg.update(
    "CustomEntity02",
    breakdown_id,
    {
        "sg_bid_assets": [
            {"type": e["type"], "id": e["id"]}
            for e in current_entities
        ]
    }
)
```

## Customization

### Styling

Modify colors and styling in the widget classes:

```python
# EntityPillWidget styling
self.setStyleSheet("""
    EntityPillWidget {
        background-color: #3a3a3a;  /* Pill background */
        border: 1px solid #555555;   /* Pill border */
        border-radius: 10px;         /* Roundness */
    }
""")
```

### Replace Add Dialog

For production use, replace `AddEntityDialog` with a real ShotGrid entity picker:

```python
def _on_add_clicked(self):
    """Handle add button click."""
    # Use your ShotGrid entity picker
    from your_sg_tools import ShotGridEntityPicker

    picker = ShotGridEntityPicker(
        entity_type="CustomEntity07",
        parent=self
    )

    if picker.exec_() == QtWidgets.QDialog.Accepted:
        entities = picker.get_selected_entities()
        for entity in entities:
            self.add_entity(entity)
```

### Custom Entity Pill Styling

Subclass `EntityPillWidget` for custom styling:

```python
class CustomEntityPill(EntityPillWidget):
    def _apply_styling(self):
        # Custom styling
        self.setStyleSheet("""
            CustomEntityPill {
                background-color: #4a7c4e;  /* Green for assets */
                border-radius: 12px;
            }
        """)
```

## Best Practices

### Table Cell Usage

1. **Set appropriate row heights**
   ```python
   table.verticalHeader().setDefaultSectionSize(80)
   ```

2. **Handle entity changes**
   ```python
   widget.entitiesChanged.connect(
       lambda entities, row=row: on_row_changed(row, entities)
   )
   ```

3. **Retrieve data before saving**
   ```python
   for row in range(table.rowCount()):
       widget = table.cellWidget(row, assets_column)
       if isinstance(widget, MultiEntityReferenceWidget):
           entities = widget.get_entities()
           # Save to ShotGrid
   ```

### Performance

- For large tables (100+ rows), consider lazy loading
- Only create widgets for visible rows
- Use `QAbstractTableModel` with delegates for better performance

### Error Handling

```python
try:
    widget.set_entities(breakdown["sg_bid_assets"])
except Exception as e:
    logger.error(f"Failed to set entities: {e}")
    widget.set_entities([])  # Fallback to empty
```

## API Reference

### MultiEntityReferenceWidget

**Constructor:**
```python
__init__(entities=None, allow_add=True, parent=None)
```

**Methods:**
- `set_entities(entities: list)` - Set entity list
- `get_entities() -> list` - Get entity list
- `add_entity(entity: dict)` - Add single entity

**Signals:**
- `entitiesChanged(list)` - Emitted when entities change

### EntityPillWidget

**Constructor:**
```python
__init__(entity: dict, parent=None)
```

**Methods:**
- `get_entity() -> dict` - Get entity data

**Signals:**
- `removeRequested(object)` - Emitted on remove click

## Troubleshooting

### Pills not wrapping
- Ensure parent has adequate width
- Check FlowLayout is properly configured
- Verify cell widget sizing

### Entities not updating
- Check signal connections
- Verify entity format matches expected structure
- Ensure entitiesChanged signal is connected

### Styling issues
- Apply dark theme to QApplication
- Check stylesheet specificity
- Verify Qt version compatibility (PySide6)

## License

MIT License - Feel free to use and modify for your projects.

## Credits

Created by Claude Code
Based on Qt Flow Layout example
Designed for ShotGrid/Flow Production Tracking integration

## Support

For issues or questions:
1. Check the example file: `multi_entity_reference_example.py`
2. Review the inline documentation
3. Test with the standalone demo: `python multi_entity_reference_widget.py`

---

**Version:** 1.0.0
**Compatible with:** PySide6, ShotGrid API
**Python:** 3.7+
