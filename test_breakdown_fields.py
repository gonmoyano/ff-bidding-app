#!/usr/bin/env python3
"""
Test script for checking CustomEntity02 (Breakdown Item) fields in ShotGrid.

This script connects to ShotGrid and checks if all required fields exist
in CustomEntity02 (Breakdown Item). Uses a static template dictionary based
on project 389 for field datatypes.

This script runs standalone without requiring AYON or any other dependencies
besides shotgun_api3.

Usage:
    # Check fields using entity-level schema
    python test_breakdown_fields.py

    # Check fields for a specific project (for reporting purposes)
    python test_breakdown_fields.py --project-code PROJECT_CODE

Environment variables required:
    SG_URL: ShotGrid site URL (e.g., https://your-studio.shotgrid.com)
    SG_SCRIPT: ShotGrid script name
    SG_KEY: ShotGrid API key

Example:
    export SG_URL=https://your-studio.shotgrid.com
    export SG_SCRIPT=your_script_name
    export SG_KEY=your_api_key
    python test_breakdown_fields.py
"""

import sys
import os
import argparse
from pathlib import Path

# Add the client directory to the path so we can import the module
# This allows running standalone without AYON
client_dir = Path(__file__).parent / "client"
sys.path.insert(0, str(client_dir))

print("=" * 80)
print("CustomEntity02 (Breakdown Item) Field Checker - Standalone Mode")
print("=" * 80)
print()

# Import the ShotgridClient
try:
    print("Importing ShotgridClient...")
    from ff_bidding_app.shotgrid import ShotgridClient
    print("✓ ShotgridClient imported successfully")
    print()
except ImportError as e:
    print(f"✗ Failed to import ShotgridClient: {e}")
    import traceback
    traceback.print_exc()
    print()
    print("Please ensure you're running from the project directory.")
    sys.exit(1)


def test_breakdown_item_fields(project_code=None):
    """
    Test function to check CustomEntity02 (Breakdown Item) fields.

    Uses the static BREAKDOWN_ITEM_REQUIRED_FIELDS dictionary (based on project 389)
    as the template for comparison.

    Args:
        project_code: Project code (for reporting purposes only - schema is entity-level)

    Returns:
        bool: True if all fields exist, False if any are missing
    """
    sg_url = os.getenv('SG_URL', '')
    print("Connecting to ShotGrid...")
    print(f"Site: {sg_url or 'Not set'}")
    print()

    try:
        with ShotgridClient() as client:
            print("✓ Connected successfully!")
            print()

            # Run the field check with formatted output
            result = client.print_breakdown_item_fields_report(project_code=project_code)

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
Environment Variables:
  SG_URL      ShotGrid site URL (e.g., https://your-studio.shotgrid.com)
  SG_SCRIPT   ShotGrid script name
  SG_KEY      ShotGrid API key

Example:
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

    args = parser.parse_args()

    # Check environment variables
    required_env_vars = ["SG_URL", "SG_SCRIPT", "SG_KEY"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    if missing_vars:
        print("=" * 80)
        print("ERROR: Missing required environment variables")
        print("=" * 80)
        print()
        for var in missing_vars:
            print(f"  ✗ {var}")
        print()
        print("Please set the following environment variables:")
        print()
        print("  export SG_URL=https://your-studio.shotgrid.com")
        print("  export SG_SCRIPT=your_script_name")
        print("  export SG_KEY=your_api_key")
        print()
        print("Or on Windows (Command Prompt):")
        print()
        print("  set SG_URL=https://your-studio.shotgrid.com")
        print("  set SG_SCRIPT=your_script_name")
        print("  set SG_KEY=your_api_key")
        print()
        sys.exit(1)

    # Run the test
    success = test_breakdown_item_fields(project_code=args.project_code)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
