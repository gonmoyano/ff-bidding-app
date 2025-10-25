# Testing CustomEntity02 (Breakdown Item) Fields

This guide explains how to use the utility function to check if all required fields exist in CustomEntity02 (Breakdown Item) for your ShotGrid project.

## What It Does

The utility checks for the following fields in CustomEntity02:
- `sg_vfx_breakdown_scene`
- `sg_interior_exterior`
- `sg_set`
- `sg_time_of_day`
- `code`
- `sg_previs`
- `sg_sim`
- `sg_script_excerpt`
- `sg_vfx_type`
- `sg_number_of_shots`
- `sg_complexity`
- `sg_vfx_assumptions`
- `sg_vfx_questions`
- `sg_team_notes`
- `sg_vfx_supervisor_notes`
- `sg_on_set_vfx_needs`
- `sg_page_eights`
- `sg_unit`
- `sg_sorting_priority`

The utility uses **project 389** as the template for field datatypes and reports which fields are missing in your target project.

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

#### Command-line Options

```bash
# Check for a specific project
python test_breakdown_fields.py --project-code YOUR_PROJECT_CODE

# Use a different template project (default is 389)
python test_breakdown_fields.py --template-project 389

# Combine options
python test_breakdown_fields.py --project-code YOUR_PROJECT_CODE --template-project 389
```

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

    # Option 2: Print a formatted report
    client.print_breakdown_item_fields_report()

    # Option 3: Check for a specific project
    client.print_breakdown_item_fields_report(project_code="YOUR_PROJECT")
```

### Option 3: Quick One-liner

```bash
python -c "from client.ff_bidding_app.shotgrid import ShotgridClient; ShotgridClient().print_breakdown_item_fields_report()"
```

## Understanding the Output

The test will output a detailed report with three sections:

### 1. Template Fields
Shows all fields with their expected datatypes from project 389:
```
Template Fields (from project 389):
--------------------------------------------------------------------------------
  code                                     -> text
  sg_complexity                            -> list
  sg_interior_exterior                     -> text
  ...
```

### 2. Existing Fields
Lists fields that exist in your target project:
```
Existing Fields in target project:
--------------------------------------------------------------------------------
  code                                     -> text
  sg_vfx_breakdown_scene                   -> text
  ...
```

### 3. Missing Fields
Shows fields that are missing (these need to be created in ShotGrid):
```
Missing Fields in target project:
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

## Notes

- **Entity-level vs Project-level**: In ShotGrid, custom entity schemas are typically entity-level (shared across all projects), not project-specific. The function checks the entity schema, which should be consistent across your ShotGrid site.

- **Template Project 389**: This project is used as a reference to get the expected field datatypes. If your site uses a different project as the template, specify it using the `--template-project` argument.

- **Field Creation**: If fields are missing, you'll need to create them in ShotGrid's site preferences under the CustomEntity02 configuration.

## Support

For issues or questions, please refer to the main project documentation or contact your ShotGrid administrator.
