"""
Formula Evaluator
Evaluates Google Sheets/Excel-style formulas for calculated fields in tables.
Uses the 'formulas' library for full Excel formula compatibility.
"""

import re
from typing import Any, Dict, Optional, Set, Tuple
from PySide6 import QtCore

try:
    import formulas
except ImportError:
    formulas = None

try:
    from .logger import logger
except ImportError:
    import logging
    logger = logging.getLogger("FFPackageManager")


class FormulaEvaluator:
    """Evaluates formulas using Excel-compatible formulas library."""

    def __init__(self, table_model=None):
        """Initialize the formula evaluator.

        Args:
            table_model: The table model to access cell data
        """
        self.table_model = table_model
        self.parser = formulas.Parser() if formulas else None
        self.calculating = set()  # Track cells being calculated to detect circular references

    @staticmethod
    def col_index_to_letter(col):
        """Convert column index to letter (0->A, 1->B, ..., 25->Z, 26->AA)"""
        result = ""
        while col >= 0:
            result = chr(65 + (col % 26)) + result
            col = col // 26 - 1
        return result

    @staticmethod
    def letter_to_col(letter):
        """Convert column letter to index (A->0, B->1, ..., Z->25, AA->26)"""
        col = 0
        for char in letter:
            col = col * 26 + (ord(char) - 65 + 1)
        return col - 1

    def parse_cell_reference(self, ref: str) -> Optional[Tuple[int, int]]:
        """Parse cell reference like 'A1' into (row, col).

        Args:
            ref: Cell reference like "A1", "$B$2", "C10"

        Returns:
            Tuple of (row, col) or None if invalid
        """
        # Remove $ signs for absolute references
        ref = ref.strip().replace('$', '')

        match = re.match(r'^([A-Z]+)(\d+)$', ref.upper())
        if match:
            col_letter, row_num = match.groups()
            col = self.letter_to_col(col_letter)
            row = int(row_num) - 1  # Convert to 0-based

            if self.table_model:
                if 0 <= row < self.table_model.rowCount() and 0 <= col < self.table_model.columnCount():
                    return (row, col)
        return None

    def get_cell_reference(self, row: int, col: int) -> str:
        """Get cell reference string like 'A1' from row/col indices."""
        return f"{self.col_index_to_letter(col)}{row + 1}"

    def get_column_index_by_field(self, field_name: str) -> Optional[int]:
        """Get column index by field/header name.

        Args:
            field_name: The field name (e.g., "comp", "sg_comp_mandays")

        Returns:
            Column index (0-based) or None if not found
        """
        if not self.table_model or not hasattr(self.table_model, 'column_fields'):
            return None

        # Try exact match first
        if field_name in self.table_model.column_fields:
            return self.table_model.column_fields.index(field_name)

        # Try case-insensitive match
        field_name_lower = field_name.lower()
        for idx, col_field in enumerate(self.table_model.column_fields):
            if col_field.lower() == field_name_lower:
                return idx

        return None

    def resolve_header_reference(self, ref: str) -> Optional[str]:
        """Resolve a header-based reference to a standard cell reference.

        Args:
            ref: Header-based reference like "comp.1", "sg_comp_mandays.5"

        Returns:
            Standard cell reference like "E1", "C5", or None if invalid
        """
        # Pattern: fieldname.row (e.g., comp.1, sg_anim_mandays.10)
        match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*?)\.(\d+)$', ref)
        if not match:
            return None

        field_name, row_str = match.groups()
        row_num = int(row_str)

        # Get column index for this field
        col_idx = self.get_column_index_by_field(field_name)
        if col_idx is None:
            return None

        # Convert to standard reference
        col_letter = self.col_index_to_letter(col_idx)
        return f"{col_letter}{row_num}"

    def get_cell_value(self, ref: str) -> Any:
        """Get the numeric/string value of a cell for formula calculation.

        Args:
            ref: Cell reference like "A1", "B2"

        Returns:
            Cell value (number, string, or 0)
        """
        coords = self.parse_cell_reference(ref)
        if not coords or not self.table_model:
            return 0

        row, col = coords

        # Get the raw value from the model
        index = self.table_model.index(row, col)
        value = self.table_model.data(index, QtCore.Qt.EditRole)

        # If value is a formula, get the calculated value instead
        if isinstance(value, str) and value.startswith('='):
            # Get the display value which should be calculated
            value = self.table_model.data(index, QtCore.Qt.DisplayRole)

        # Try to convert to number
        try:
            # Handle percentage
            if isinstance(value, str) and value.endswith('%'):
                return float(value[:-1]) / 100
            return float(value) if value else 0
        except (ValueError, TypeError):
            # Return the string value or 0
            return value if value else 0

    def evaluate(self, formula: str, row: int = None, col: int = None) -> Any:
        """Evaluate a formula and return the result.

        Args:
            formula: The formula string (e.g., "=SUM(A1:A10)")
            row: The row index of the cell being calculated (for circular ref detection)
            col: The column index of the cell being calculated

        Returns:
            The calculated value or error message
        """
        if not formula:
            return ""

        formula = formula.strip()

        # Check if it's a formula
        if not formula.startswith('='):
            # Not a formula, return as-is
            return formula

        # Check for formulas library availability
        if not formulas or not self.parser:
            return "#ERROR: formulas library not available"

        # Pre-process formula to handle ROW(), COLUMN(), and INDIRECT()
        if row is not None and col is not None:
            formula = self._preprocess_formula(formula, row, col)

        # Check for circular reference
        if row is not None and col is not None:
            cell_ref = self.get_cell_reference(row, col)
            if cell_ref in self.calculating:
                return "#CIRCULAR!"
            self.calculating.add(cell_ref)

        try:
            # Parse and compile the formula
            parsed = self.parser.ast(formula)

            if not parsed or len(parsed) <= 1:
                return "#PARSE_ERROR!"

            compiled_formula = parsed[1].compile()

            # Get input cell references
            inputs = list(compiled_formula.inputs)

            # Get values for each input
            input_values = []
            for input_ref in inputs:
                input_values.append(self.get_cell_value(input_ref))

            # Execute the formula
            try:
                result = compiled_formula(*input_values)

                # Handle array results
                if hasattr(result, 'tolist'):
                    result = result.tolist()
                if isinstance(result, list):
                    result = result[0] if result else 0

                # Format the result
                if isinstance(result, float):
                    if abs(result - round(result)) < 1e-10:
                        result = int(round(result))
                    else:
                        result = round(result, 10)

                return result

            except NotImplementedError:
                logger.debug(f"Formula contains unsupported function: '{formula}'")
                return "#NOT_SUPPORTED!"
            except Exception as e:
                logger.debug(f"Error executing formula '{formula}': {e}")
                return "#ERROR!"

        except Exception as e:
            logger.debug(f"Error parsing formula '{formula}': {e}")
            return "#PARSE_ERROR!"
        finally:
            # Remove from calculating set
            if row is not None and col is not None:
                cell_ref = self.get_cell_reference(row, col)
                self.calculating.discard(cell_ref)

    def _preprocess_formula(self, formula: str, row: int, col: int) -> str:
        """Pre-process formula to replace ROW(), COLUMN(), and resolve INDIRECT().

        Args:
            formula: The original formula
            row: Current row index (0-based)
            col: Current column index (0-based)

        Returns:
            Processed formula with ROW(), COLUMN(), INDIRECT(), and header refs replaced
        """
        # Replace header-based references (e.g., comp.1, sg_anim_mandays.5)
        # Pattern: fieldname.rownum
        def replace_header_ref(match):
            header_ref = match.group(0)
            standard_ref = self.resolve_header_reference(header_ref)
            if standard_ref:
                return standard_ref
            else:
                # If field not found, keep as-is (will likely cause parse error)
                logger.debug(f"Could not resolve header reference: {header_ref}")
                return header_ref

        # Match fieldname.number pattern (e.g., comp.1, sg_comp_mandays.10)
        formula = re.sub(
            r'\b([a-zA-Z_][a-zA-Z0-9_]*?)\.(\d+)\b',
            replace_header_ref,
            formula
        )

        # Replace ROW() with the actual row number (1-based for Excel)
        formula = re.sub(r'\bROW\(\s*\)', str(row + 1), formula, flags=re.IGNORECASE)

        # Replace COLUMN() with the actual column number (1-based for Excel)
        formula = re.sub(r'\bCOLUMN\(\s*\)', str(col + 1), formula, flags=re.IGNORECASE)

        # Handle INDIRECT() - resolve the indirect reference
        # Match INDIRECT("...") or INDIRECT('...')
        def replace_indirect(match):
            try:
                # Get the argument to INDIRECT
                arg = match.group(1)

                # Evaluate the argument (could be a string concatenation like "A"&ROW())
                # First, replace any ROW() or COLUMN() in the argument
                arg = re.sub(r'\bROW\(\s*\)', str(row + 1), arg, flags=re.IGNORECASE)
                arg = re.sub(r'\bCOLUMN\(\s*\)', str(col + 1), arg, flags=re.IGNORECASE)

                # Evaluate the string expression
                # Remove quotes and evaluate string concatenation
                # Handle patterns like "A"&5 or "A"&ROW()
                evaluated_ref = self._evaluate_indirect_argument(arg)

                # Return the evaluated cell reference
                return evaluated_ref
            except Exception as e:
                logger.debug(f"Error resolving INDIRECT: {e}")
                return "A1"  # Fallback to A1

        # Replace INDIRECT(...) with the resolved reference
        formula = re.sub(
            r'\bINDIRECT\(\s*([^)]+)\s*\)',
            replace_indirect,
            formula,
            flags=re.IGNORECASE
        )

        return formula

    def _evaluate_indirect_argument(self, arg: str) -> str:
        """Evaluate the argument to INDIRECT() to get a cell reference.

        Args:
            arg: The argument expression (e.g., "A"&5, "B2", etc.)

        Returns:
            The evaluated cell reference as a string
        """
        # Remove outer quotes if present
        arg = arg.strip()

        # Handle simple quoted strings
        if (arg.startswith('"') and arg.endswith('"')) or (arg.startswith("'") and arg.endswith("'")):
            return arg[1:-1]

        # Handle string concatenation with &
        if '&' in arg:
            # Split by & and evaluate each part
            parts = arg.split('&')
            result = ""
            for part in parts:
                part = part.strip()
                # Remove quotes
                if (part.startswith('"') and part.endswith('"')) or (part.startswith("'") and part.endswith("'")):
                    result += part[1:-1]
                else:
                    # It's a number or expression
                    try:
                        result += str(int(part))
                    except:
                        result += part
            return result

        # Return as-is
        return arg

    def find_dependent_cells(self, changed_row: int, changed_col: int) -> Set[Tuple[int, int]]:
        """Find all cells that depend on the changed cell.

        Args:
            changed_row: Row index of the changed cell
            changed_col: Column index of the changed cell

        Returns:
            Set of (row, col) tuples that depend on the changed cell
        """
        if not self.table_model:
            return set()

        changed_ref = self.get_cell_reference(changed_row, changed_col)
        dependents = set()

        # Also get the header-based reference for the changed cell
        changed_header_ref = None
        if hasattr(self.table_model, 'column_fields') and changed_col < len(self.table_model.column_fields):
            field_name = self.table_model.column_fields[changed_col]
            changed_header_ref = f"{field_name}.{changed_row + 1}"

        # Scan all cells to find those with formulas referencing the changed cell
        for row in range(self.table_model.rowCount()):
            for col in range(self.table_model.columnCount()):
                index = self.table_model.index(row, col)
                value = self.table_model.data(index, QtCore.Qt.EditRole)

                # Check if it's a formula
                if isinstance(value, str) and value.startswith('='):
                    # Check if this formula references the changed cell (standard or header-based)
                    if re.search(r'\b' + changed_ref + r'\b', value, re.IGNORECASE):
                        dependents.add((row, col))
                    elif changed_header_ref and re.search(r'\b' + re.escape(changed_header_ref) + r'\b', value, re.IGNORECASE):
                        dependents.add((row, col))

        return dependents

    def recalculate_dependents(self, changed_row: int, changed_col: int):
        """Recalculate all cells that depend on the changed cell.

        Args:
            changed_row: Row index of the changed cell
            changed_col: Column index of the changed cell
        """
        dependents = self.find_dependent_cells(changed_row, changed_col)

        for dep_row, dep_col in dependents:
            index = self.table_model.index(dep_row, dep_col)
            formula = self.table_model.data(index, QtCore.Qt.EditRole)

            if isinstance(formula, str) and formula.startswith('='):
                # Trigger recalculation by emitting dataChanged
                self.table_model.dataChanged.emit(index, index, [QtCore.Qt.DisplayRole])
