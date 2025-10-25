#!/usr/bin/env python3
"""
Helper script to get field datatypes from ShotGrid for CustomEntity02.

This script queries your ShotGrid instance and generates a Python dictionary
with the current field datatypes that can be used to update the static
BREAKDOWN_ITEM_REQUIRED_FIELDS dictionary in shotgrid.py.

This script runs standalone without requiring AYON or any other dependencies
besides shotgun_api3.

Usage:
    python get_field_types_from_389.py

    # Save to file
    python get_field_types_from_389.py > field_types.txt

Default Credentials:
    Uses the same ShotGrid credentials as run_standalone.py
    - URL: https://fireframe.shotgrid.autodesk.com/
    - Script: ff_bidding_app

Environment variables (optional overrides):
    SG_URL: Override ShotGrid site URL
    SG_SCRIPT: Override ShotGrid script name
    SG_KEY: Override ShotGrid API key
"""

import sys
import os
from pathlib import Path
import importlib.util

# Get the path to shotgrid.py directly (bypass package __init__.py to avoid AYON dependency)
client_dir = Path(__file__).parent / "client"
shotgrid_path = client_dir / "ff_bidding_app" / "shotgrid.py"

print("=" * 80, file=sys.stderr)
print("CustomEntity02 Field Type Extractor - Standalone Mode", file=sys.stderr)
print("=" * 80, file=sys.stderr)
print(file=sys.stderr)

# Import the ShotgridClient directly without loading the package __init__.py
# This avoids the AYON dependency in addon.py
try:
    print("Importing ShotgridClient...", file=sys.stderr)
    spec = importlib.util.spec_from_file_location("shotgrid", shotgrid_path)
    shotgrid_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shotgrid_module)
    ShotgridClient = shotgrid_module.ShotgridClient
    print("✓ ShotgridClient imported successfully", file=sys.stderr)
    print(file=sys.stderr)
except Exception as e:
    print(f"✗ Failed to import ShotgridClient: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)
    print(file=sys.stderr)
    print("Please ensure you're running from the project directory.", file=sys.stderr)
    print(f"Looking for: {shotgrid_path}", file=sys.stderr)
    sys.exit(1)

# Fields to check
fields = [
    "sg_vfx_breakdown_scene",
    "sg_interior_exterior",
    "sg_set",
    "sg_time_of_day",
    "code",
    "sg_previs",
    "sg_sim",
    "sg_script_excerpt",
    "sg_vfx_type",
    "sg_number_of_shots",
    "sg_complexity",
    "sg_vfx_assumptions",
    "sg_vfx_questions",
    "sg_team_notes",
    "sg_vfx_supervisor_notes",
    "sg_on_set_vfx_needs",
    "sg_page_eights",
    "sg_unit",
    "sg_sorting_priority",
]

# Default credentials from run_standalone.py
# Can be overridden with environment variables
default_url = "https://fireframe.shotgrid.autodesk.com/"
default_script = "ff_bidding_app"
default_key = "tiviqwk^jeZqaon8aeemdnnnk"

sg_url = os.getenv('SG_URL', default_url)
sg_script = os.getenv('SG_SCRIPT', default_script)
sg_key = os.getenv('SG_KEY', default_key)

using_defaults = (
    os.getenv('SG_URL') is None and
    os.getenv('SG_SCRIPT') is None and
    os.getenv('SG_KEY') is None
)

print(f"Connecting to ShotGrid: {sg_url}", file=sys.stderr)
if using_defaults:
    print("(Using default credentials from run_standalone.py)", file=sys.stderr)
print(file=sys.stderr)

try:
    client = ShotgridClient(
        site_url=sg_url,
        script_name=sg_script,
        api_key=sg_key
    )
    with client:
        print("✓ Connected successfully!", file=sys.stderr)
        print(file=sys.stderr)
        print("Fetching CustomEntity02 schema...", file=sys.stderr)

        schema = client.get_entity_schema("CustomEntity02")

        print("✓ Schema retrieved", file=sys.stderr)
        print(file=sys.stderr)
        print("=" * 80, file=sys.stderr)
        print("Generating dictionary (output to stdout)...", file=sys.stderr)
        print("=" * 80, file=sys.stderr)
        print(file=sys.stderr)

        # Output to stdout (can be redirected to a file)
        print("# Field datatypes from CustomEntity02")
        print("# Copy this dictionary to replace BREAKDOWN_ITEM_REQUIRED_FIELDS in shotgrid.py")
        print("BREAKDOWN_ITEM_REQUIRED_FIELDS = {")

        for field_name in fields:
            if field_name in schema:
                field_info = schema[field_name]
                datatype = field_info.get("data_type", {})

                # Handle case where data_type might be a dict with 'value' key or just a string
                if isinstance(datatype, dict):
                    datatype = datatype.get("value", str(datatype))

                field_label = field_info.get("name", {})
                if isinstance(field_label, dict):
                    field_label = field_label.get("value", field_name)

                print(f'    "{field_name}": "{datatype}",  # {field_label}')
            else:
                print(f'    "{field_name}": "MISSING",  # NOT FOUND IN SCHEMA')

        print("}")

        print(file=sys.stderr)
        print("=" * 80, file=sys.stderr)
        print("SUCCESS! Dictionary generated above.", file=sys.stderr)
        print("=" * 80, file=sys.stderr)

except Exception as e:
    print(file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    print(f"ERROR: {e}", file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    print(file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)
