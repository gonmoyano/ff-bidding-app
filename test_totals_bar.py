"""
Test script for TableWithTotalsBar wrapper component.
Demonstrates the frozen totals bar with a simple QTableWidget example.
"""

import sys
import random
from PySide6 import QtWidgets
from client.ff_bidding_app.table_with_totals_bar import TableWithTotalsBar


def create_sample_table():
    """Create a sample table with test data."""
    # Create table
    table = QtWidgets.QTableWidget(30, 12)
    table.setHorizontalHeaderLabels([
        "Shot", "model", "tex", "rig", "mm", "prep",
        "gen", "anim", "lookdev", "lgt", "fx", "cmp"
    ])

    # Add test data
    for row in range(30):
        # Shot name
        table.setItem(row, 0, QtWidgets.QTableWidgetItem(f"Shot_{row+1:03d}"))

        # Random costs for each department
        for col in range(1, 12):
            value = random.randint(100, 5000)
            table.setItem(row, col, QtWidgets.QTableWidgetItem(str(value)))

    # Auto-size columns
    table.resizeColumnsToContents()

    return table


def main():
    """Main test function."""
    app = QtWidgets.QApplication(sys.argv)

    # Create main window
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("TableWithTotalsBar Test")
    window.resize(1200, 600)

    # Create sample table
    print("Creating sample table...")
    sample_table = create_sample_table()

    # Wrap it with totals bar
    print("Wrapping table with totals bar...")
    table_with_totals = TableWithTotalsBar(sample_table)

    # Calculate totals
    print("Calculating totals...")
    table_with_totals.calculate_totals(skip_first_col=True)

    # Set as central widget
    window.setCentralWidget(table_with_totals)

    # Show window
    print("Showing window...")
    window.show()

    print("\nTest Instructions:")
    print("1. Scroll the table horizontally - totals bar should scroll too")
    print("2. Scroll vertically - totals bar should stay at bottom")
    print("3. Resize columns - totals should stay aligned")
    print("4. Check that 'TOTAL' appears in first column")
    print("5. Check that numeric totals appear in other columns")
    print("\nPress Ctrl+C in terminal to exit\n")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
