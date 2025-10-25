#!/usr/bin/env python3
"""
Test script for checking CustomEntity02 (Breakdown Item) fields in ShotGrid.

This script connects to ShotGrid and checks if all required fields exist
in CustomEntity02 (Breakdown Item). Uses a static template dictionary based
on project 389 for field datatypes.

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

# Add the client directory to the path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "client"))

from ff_bidding_app.shotgrid import ShotgridClient


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
    print("Connecting to ShotGrid...")
    print(f"Site: {os.getenv('SG_URL', 'Not set')}")
    print()

    try:
        with ShotgridClient() as client:
            print("Connected successfully!")
            print()

            # Run the field check with formatted output
            result = client.print_breakdown_item_fields_report(project_code=project_code)

            # Return success/failure based on missing fields
            return len(result["missing_fields"]) == 0

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point for the test script."""
    parser = argparse.ArgumentParser(
        description="Check CustomEntity02 (Breakdown Item) fields in ShotGrid",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
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
        print("ERROR: Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print()
        print("Please set the following environment variables:")
        print("  export SG_URL=https://your-studio.shotgrid.com")
        print("  export SG_SCRIPT=your_script_name")
        print("  export SG_KEY=your_api_key")
        sys.exit(1)

    # Run the test
    success = test_breakdown_item_fields(project_code=args.project_code)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
