# Testing CustomEntity02 (Breakdown Item) Fields

This guide explains how to use the utility function to check if all required fields exist in CustomEntity02 (Breakdown Item) for your ShotGrid instance.

**Note:** These scripts run **standalone** without requiring AYON or any other dependencies besides `shotgun_api3`. They can be run directly from the command line.

## What It Does

The utility checks for the following fields in CustomEntity02 and compares them against a static template dictionary (based on project 389):

| Field Name | Datatype |
|------------|----------|
| `code` | text |
| `sg_complexity` | list |
| `sg_interior_exterior` | list |
| `sg_number_of_shots` | number |
| `sg_on_set_vfx_needs` | text |
| `sg_page_eights` | number |
| `sg_previs` | checkbox |
| `sg_script_excerpt` | text |
| `sg_set` | text |
| `sg_sim` | checkbox |
| `sg_sorting_priority` | number |
| `sg_team_notes` | text |
| `sg_time_of_day` | list |
| `sg_unit` | text |
| `sg_vfx_assumptions` | text |
| `sg_vfx_breakdown_scene` | text |
| `sg_vfx_questions` | text |
| `sg_vfx_supervisor_notes` | text |
| `sg_vfx_type` | list |

The utility uses a **static dictionary** (`BREAKDOWN_ITEM_REQUIRED_FIELDS`) based on project 389's schema. This dictionary is defined in the `ShotgridClient` class and can be easily updated if needed.

## Prerequisites

1. **Python 3.6+** installed
2. **shotgun_api3** package installed:
   ```bash
   pip install shotgun_api3
   ```

3. **ShotGrid API credentials** - You need:
   - Site URL
   - Script name
   - API key

4. **No AYON required** - These scripts run standalone without AYON or any addon framework

## Setup

Set up your ShotGrid credentials as environment variables:

```bash
export SG_URL=https://your-studio.shotgrid.com
export SG_SCRIPT=your_script_name
export SG_KEY=your_api_key
```

Or on Windows (Command Prompt):
```cmd
set SG_URL=https://your-studio.shotgrid.com
set SG_SCRIPT=your_script_name
set SG_KEY=your_api_key
```

Or on Windows (PowerShell):
```powershell
$env:SG_URL="https://your-studio.shotgrid.com"
$env:SG_SCRIPT="your_script_name"
$env:SG_KEY="your_api_key"
```

## Running the Test

### Option 1: Using the Test Script (Recommended)

The easiest way is to use the provided test script:

```bash
cd /home/user/ff-bidding-app
python test_breakdown_fields.py
```

This will check the entity-level schema for CustomEntity02 and display a detailed report.

**Example Output:**
```
================================================================================
CustomEntity02 (Breakdown Item) Field Checker - Standalone Mode
================================================================================

Importing ShotgridClient...
✓ ShotgridClient imported successfully

Connecting to ShotGrid...
Site: https://your-studio.shotgrid.com

✓ Connected successfully!

================================================================================
CustomEntity02 (Breakdown Item) Field Check Report
Project: entity-level
Template: Based on project 389 (static dictionary)
================================================================================
[... field report ...]

================================================================================
SUCCESS! All required fields exist.
================================================================================
```

#### Command-line Options

```bash
# Basic check (entity-level)
python test_breakdown_fields.py

# Check with a project code label (for reporting purposes)
python test_breakdown_fields.py --project-code YOUR_PROJECT_CODE
```

Note: The project code is only used for labeling in the report. The schema check is done at the entity level since ShotGrid schemas are shared across all projects.

### Option 2: Using Python Interactively

You can also use the function directly in a Python script or interactive session:

```python
from client.ff_bidding_app.shotgrid import ShotgridClient

# Create and connect to ShotGrid
with ShotgridClient() as client:
    # Option 1: Get the raw data
    result = client.check_breakdown_item_fields()
    print(f"Missing fields: {result['missing_fields']}")
    print(f"Existing fields: {result['existing_fields']}")

    # Access the static template dictionary
    print(f"Template fields: {client.BREAKDOWN_ITEM_REQUIRED_FIELDS}")

    # Option 2: Print a formatted report
    client.print_breakdown_item_fields_report()

    # Option 3: Check with a project code label
    client.print_breakdown_item_fields_report(project_code="YOUR_PROJECT")
```

### Option 3: Quick One-liner

```bash
python -c "from client.ff_bidding_app.shotgrid import ShotgridClient; ShotgridClient().print_breakdown_item_fields_report()"
```

### Option 4: View the Static Template Dictionary

You can view the template dictionary without connecting to ShotGrid:

```python
from client.ff_bidding_app.shotgrid import ShotgridClient

# View the static template (no connection required)
print(ShotgridClient.BREAKDOWN_ITEM_REQUIRED_FIELDS)
```

## Understanding the Output

The test will output a detailed report with three sections:

### 1. Required Fields (from template - project 389)
Shows all fields with their expected datatypes from the static template dictionary:
```
Required Fields (from template - project 389):
--------------------------------------------------------------------------------
  code                                     -> text
  sg_complexity                            -> list
  sg_interior_exterior                     -> list
  sg_number_of_shots                       -> number
  ...
```

### 2. Existing Fields in current schema
Lists fields that exist in your ShotGrid instance:
```
Existing Fields in current schema:
--------------------------------------------------------------------------------
  code                                     -> text
  sg_complexity                            -> list
  sg_vfx_breakdown_scene                   -> text
  ...
```

### 3. Missing Fields in current schema
Shows fields that are missing (these need to be created in ShotGrid):
```
Missing Fields in current schema:
--------------------------------------------------------------------------------
  sg_page_eights                           (expected type: number)
  sg_unit                                  (expected type: text)
  ...
```

### 4. Summary
```
Summary: 17 exist, 2 missing
```

## Exit Codes

When using the test script, it returns:
- `0` - All fields exist (success)
- `1` - Some fields are missing or an error occurred (failure)

This is useful for CI/CD pipelines or automated checks.

## Troubleshooting

### Error: "shotgun_api3 not installed"
Install the ShotGrid Python API:
```bash
pip install shotgun_api3
```

### Error: "Missing credentials"
Make sure you've set the environment variables:
```bash
echo $SG_URL
echo $SG_SCRIPT
echo $SG_KEY
```

If any are empty, set them following the setup instructions above.

### Error: "Permission denied"
Make sure the test script is executable:
```bash
chmod +x test_breakdown_fields.py
```

## Integration with Your Code

You can integrate this check into your application:

```python
from client.ff_bidding_app.shotgrid import ShotgridClient

def validate_project_schema(project_code):
    """Validate that a project has all required CustomEntity02 fields."""
    client = ShotgridClient()
    client.connect()

    result = client.check_breakdown_item_fields(project_code)

    if result['missing_fields']:
        print(f"WARNING: Project {project_code} is missing {len(result['missing_fields'])} fields:")
        for field in result['missing_fields']:
            print(f"  - {field}")
        return False

    print(f"Project {project_code} has all required fields.")
    return True
```

## Updating the Template Dictionary

If you need to update the static template dictionary with actual datatypes from your ShotGrid instance:

1. **Option 1: Manual Update**
   - Edit `client/ff_bidding_app/shotgrid.py`
   - Find the `BREAKDOWN_ITEM_REQUIRED_FIELDS` dictionary (around line 39)
   - Update the field names and datatypes as needed

2. **Option 2: Generate from ShotGrid**
   - Use the helper script to get actual datatypes:
   ```bash
   python get_field_types_from_389.py > field_types.txt
   ```
   - The script runs standalone (no AYON required) and outputs status to stderr, dictionary to stdout
   - Copy the output dictionary from `field_types.txt` to replace `BREAKDOWN_ITEM_REQUIRED_FIELDS` in `shotgrid.py`

   **Example:**
   ```bash
   # Run the helper script
   python get_field_types_from_389.py > field_types.txt

   # View the generated dictionary
   cat field_types.txt

   # Copy the dictionary and paste it into shotgrid.py
   ```

## Notes

- **Entity-level Schema**: In ShotGrid, custom entity schemas are entity-level (shared across all projects), not project-specific. The function checks the entity schema, which is consistent across your entire ShotGrid site.

- **Static Dictionary**: The `BREAKDOWN_ITEM_REQUIRED_FIELDS` dictionary is based on project 389's schema. This provides a stable reference point for field validation without requiring dynamic queries.

- **Field Creation**: If fields are missing, you'll need to create them in ShotGrid's site preferences under the CustomEntity02 (Breakdown Item) configuration.

- **Datatype Reference**: Common ShotGrid datatypes include:
  - `text`: Short text field
  - `number`: Numeric field
  - `list`: Dropdown/multi-select list
  - `checkbox`: Boolean checkbox
  - `entity`: Link to another entity
  - `multi_entity`: Link to multiple entities
  - `date`: Date field
  - `date_time`: Date and time field

## Support

For issues or questions, please refer to the main project documentation or contact your ShotGrid administrator.
