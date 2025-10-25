#!/usr/bin/env python3
"""
Test script for checking CustomEntity02 (Breakdown Item) fields in ShotGrid.

This script connects to ShotGrid and checks if all required fields exist
in CustomEntity02 (Breakdown Item). Uses a static template dictionary based
on project 389 for field datatypes.

This script runs standalone without requiring AYON or any other dependencies
besides shotgun_api3.

Usage:
    # Check fields using entity-level schema (uses default credentials)
    python test_breakdown_fields.py

    # Check fields for a specific project (for reporting purposes)
    python test_breakdown_fields.py --project-code PROJECT_CODE

Default Credentials:
    Uses the same ShotGrid credentials as run_standalone.py
    - URL: https://fireframe.shotgrid.autodesk.com/
    - Script: ff_bidding_app

Environment variables (optional overrides):
    SG_URL: Override ShotGrid site URL
    SG_SCRIPT: Override ShotGrid script name
    SG_KEY: Override ShotGrid API key

Example with custom credentials:
    export SG_URL=https://your-studio.shotgrid.com
    export SG_SCRIPT=your_script_name
    export SG_KEY=your_api_key
    python test_breakdown_fields.py
"""

import sys
import os
import argparse
from pathlib import Path
import importlib.util

# Get the path to shotgrid.py directly (bypass package __init__.py to avoid AYON dependency)
client_dir = Path(__file__).parent / "client"
shotgrid_path = client_dir / "ff_bidding_app" / "shotgrid.py"

print("=" * 80)
print("CustomEntity02 (Breakdown Item) Field Checker - Standalone Mode")
print("=" * 80)
print()

# Import the ShotgridClient directly without loading the package __init__.py
# This avoids the AYON dependency in addon.py
try:
    print("Importing ShotgridClient...")
    spec = importlib.util.spec_from_file_location("shotgrid", shotgrid_path)
    shotgrid_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shotgrid_module)
    ShotgridClient = shotgrid_module.ShotgridClient
    print("✓ ShotgridClient imported successfully")
    print()
except Exception as e:
    print(f"✗ Failed to import ShotgridClient: {e}")
    import traceback
    traceback.print_exc()
    print()
    print("Please ensure you're running from the project directory.")
    print(f"Looking for: {shotgrid_path}")
    sys.exit(1)


def test_breakdown_item_fields(project_code=None, verbose=False):
    """
    Test function to check CustomEntity02 (Breakdown Item) fields.

    Uses the static BREAKDOWN_ITEM_REQUIRED_FIELDS dictionary (based on project 389)
    as the template for comparison.

    Args:
        project_code: Project code (for reporting purposes only - schema is entity-level)
        verbose: If True, print debug information about the schema

    Returns:
        bool: True if all fields exist, False if any are missing
    """
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

    print("Connecting to ShotGrid...")
    print(f"Site: {sg_url}")
    if using_defaults:
        print("(Using default credentials from run_standalone.py)")
    print()

    try:
        client = ShotgridClient(
            site_url=sg_url,
            script_name=sg_script,
            api_key=sg_key
        )
        with client:
            print("✓ Connected successfully!")
            print()

            # Run the field check with formatted output
            result = client.print_breakdown_item_fields_report(
                project_code=project_code,
                verbose=verbose
            )

            print()
            print("=" * 80)
            if len(result["missing_fields"]) == 0:
                print("SUCCESS! All required fields exist.")
            else:
                print(f"WARNING! {len(result['missing_fields'])} field(s) missing.")
            print("=" * 80)
            print()

            # Return success/failure based on missing fields
            return len(result["missing_fields"]) == 0

    except Exception as e:
        print()
        print("=" * 80)
        print(f"ERROR: {e}")
        print("=" * 80)
        print()
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point for the test script."""
    parser = argparse.ArgumentParser(
        description="Check CustomEntity02 (Breakdown Item) fields in ShotGrid",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Default Credentials:
  Uses the same ShotGrid credentials as run_standalone.py
  - URL: https://fireframe.shotgrid.autodesk.com/
  - Script: ff_bidding_app

Environment Variables (optional overrides):
  SG_URL      Override ShotGrid site URL
  SG_SCRIPT   Override ShotGrid script name
  SG_KEY      Override ShotGrid API key

Example with custom credentials:
  export SG_URL=https://your-studio.shotgrid.com
  export SG_SCRIPT=your_script_name
  export SG_KEY=your_api_key
  python test_breakdown_fields.py
        """
    )
    parser.add_argument(
        "--project-code",
        type=str,
        default=None,
        help="Project code (for reporting purposes only - schema is entity-level)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose debug output showing schema details"
    )
    parser.add_argument(
        "--dump-schema",
        action="store_true",
        help="Dump complete schema to schema_dump.json file"
    )

    args = parser.parse_args()

    # If dump-schema is requested, dump it and exit
    if args.dump_schema:
        print("Dumping complete CustomEntity02 schema...")
        print()

        # Use same credential logic
        default_url = "https://fireframe.shotgrid.autodesk.com/"
        default_script = "ff_bidding_app"
        default_key = "tiviqwk^jeZqaon8aeemdnnnk"

        sg_url = os.getenv('SG_URL', default_url)
        sg_script = os.getenv('SG_SCRIPT', default_script)
        sg_key = os.getenv('SG_KEY', default_key)

        try:
            client = ShotgridClient(
                site_url=sg_url,
                script_name=sg_script,
                api_key=sg_key
            )
            with client:
                schema = client.get_entity_schema("CustomEntity02")

                import json
                with open("schema_dump.json", "w") as f:
                    json.dump(schema, f, indent=2, default=str)

                print(f"✓ Schema dumped to schema_dump.json")
                print(f"  Total fields: {len(schema)}")
                print(f"  Field names: {list(schema.keys())[:20]}...")
                print()
                sys.exit(0)
        except Exception as e:
            print(f"✗ Failed to dump schema: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    # Run the test (uses defaults from run_standalone.py if env vars not set)
    success = test_breakdown_item_fields(
        project_code=args.project_code,
        verbose=args.verbose
    )

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
