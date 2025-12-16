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

    def __init__(self, table_model=None, sheet_models=None):
        """Initialize the formula evaluator.

        Args:
            table_model: The table model to access cell data (current sheet)
            sheet_models: Dictionary mapping sheet names to their table models
        """
        self.table_model = table_model
        self.sheet_models = sheet_models or {}  # Map sheet names to models
        self.parser = formulas.Parser() if formulas else None
        self.calculating = set()  # Track cells being calculated to detect circular references

        # Log available sheets for debugging
        if self.sheet_models:
            pass
        else:
            pass

    def _get_sheet_model_case_insensitive(self, sheet_name: str):
        """Get a sheet model by name with case-insensitive matching.

        Args:
            sheet_name: The sheet name to look up (e.g., "misc", "Misc", "MISC")

        Returns:
            Tuple of (actual_sheet_name, model) if found, (None, None) if not found
        """
        # Try exact match first
        if sheet_name in self.sheet_models:
            return sheet_name, self.sheet_models[sheet_name]

        # Try case-insensitive match
        sheet_name_lower = sheet_name.lower()
        for name, model in self.sheet_models.items():
            if name.lower() == sheet_name_lower:
                return name, model

        return None, None

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

    def get_column_index_by_field(self, field_name: str, model=None) -> Optional[int]:
        """Get column index by field/header name.

        Args:
            field_name: The field name (e.g., "comp", "sg_comp_mandays", "cmp")
            model: The model to search (defaults to self.table_model)

        Returns:
            Column index (0-based) or None if not found
        """
        if model is None:
            model = self.table_model

        if not model or not hasattr(model, 'column_fields'):
            return None

        # Try exact match first
        if field_name in model.column_fields:
            return model.column_fields.index(field_name)

        # Try case-insensitive exact match
        field_name_lower = field_name.lower()
        for idx, col_field in enumerate(model.column_fields):
            if col_field.lower() == field_name_lower:
                return idx

        # Try partial match: find first field containing the search term
        # This allows "cmp" to match "sg_cmp_rate" or "sg_cmp_mandays"
        for idx, col_field in enumerate(model.column_fields):
            col_field_lower = col_field.lower()
            # Check if field_name appears in col_field (as a substring)
            if field_name_lower in col_field_lower:
                # Prefer fields where the match is at a word boundary
                # e.g., "cmp" should match "sg_cmp_rate" but not "sg_compute_time"
                if (f"_{field_name_lower}_" in col_field_lower or
                    col_field_lower.startswith(field_name_lower + "_") or
                    col_field_lower.endswith("_" + field_name_lower) or
                    col_field_lower == field_name_lower):
                    return idx

        # Last resort: simple substring match (first occurrence)
        for idx, col_field in enumerate(model.column_fields):
            if field_name_lower in col_field.lower():
                return idx

        return None

    def parse_sheet_reference(self, ref: str) -> Tuple[Optional[str], str]:
        """Parse a reference with optional sheet prefix.

        Args:
            ref: Reference like "'Rate Card'!cmp.1", "Price!cmp", or "cmp.1"

        Returns:
            Tuple of (sheet_name, cell_reference)
            - sheet_name is None if no sheet prefix
            - cell_reference is the part after the ! or the whole ref
        """
        # Pattern: 'Sheet Name'!ref or SheetName!ref
        # Match: optional quoted sheet name or unquoted name, followed by !, then the reference
        match = re.match(r"^'([^']+)'!(.+)$", ref)
        if match:
            return (match.group(1), match.group(2))

        match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_ ]*?)!(.+)$", ref)
        if match:
            return (match.group(1), match.group(2))

        return (None, ref)

    def resolve_header_reference(self, ref: str, current_row: Optional[int] = None, model=None) -> Optional[str]:
        """Resolve a header-based reference to a standard cell reference.

        Args:
            ref: Header-based reference like "comp.1", "sg_comp_mandays.5", or "cmp"
            current_row: Current row index (0-based) for same-row references
            model: The model to use for field lookup (defaults to self.table_model)

        Returns:
            Standard cell reference like "E1", "C5", or None if invalid
        """
        if model is None:
            model = self.table_model

        # Pattern 1: fieldname.row (e.g., comp.1, sg_anim_mandays.10)
        match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*?)\.(\d+)$', ref)
        if match:
            field_name, row_str = match.groups()
            row_num = int(row_str)

            # Get column index for this field
            col_idx = self.get_column_index_by_field(field_name, model=model)
            if col_idx is None:
                return None

            # Convert to standard reference
            col_letter = self.col_index_to_letter(col_idx)
            return f"{col_letter}{row_num}"

        # Pattern 2: fieldname only (e.g., comp, sg_comp_mandays) - same row reference
        match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)$', ref)
        if match and current_row is not None:
            field_name = match.group(1)

            # Get column index for this field
            col_idx = self.get_column_index_by_field(field_name, model=model)
            if col_idx is None:
                return None

            # Convert to standard reference using current row
            col_letter = self.col_index_to_letter(col_idx)
            return f"{col_letter}{current_row + 1}"  # +1 for 1-based Excel row

        return None

    def _get_cell_value_from_model(self, ref: str, model) -> Any:
        """Get the numeric/string value of a cell from a specific model.

        Args:
            ref: Cell reference like "A1", "B2"
            model: The table model to fetch from

        Returns:
            Cell value (number, string, or 0)
        """
        # Parse the cell reference (A1 -> row 0, col 0)
        ref = ref.strip().replace('$', '')
        match = re.match(r'^([A-Z]+)(\d+)$', ref.upper())
        if not match or not model:
            print(f"[CROSS-TAB] _get_cell_value_from_model: Invalid ref '{ref}' or no model")
            return 0

        col_letter, row_num = match.groups()
        col = self.letter_to_col(col_letter)
        row = int(row_num) - 1  # Convert to 0-based

        # Check if the row and column are valid for this model
        if row < 0 or col < 0 or row >= model.rowCount() or col >= model.columnCount():
            print(f"[CROSS-TAB] _get_cell_value_from_model: Out of bounds - ref={ref}, row={row}, col={col}")
            return 0

        # Debug: Log the model's internal data for SpreadsheetModel
        if hasattr(model, '_data'):
            print(f"[CROSS-TAB] _get_cell_value_from_model: ref={ref}, model._data keys={list(model._data.keys())}, value at ({row},{col})={model._data.get((row, col), 'NOT_FOUND')}")

        # Get the raw value from the model
        index = model.index(row, col)
        value = model.data(index, QtCore.Qt.EditRole)
        print(f"[CROSS-TAB] _get_cell_value_from_model: ref={ref}, EditRole value='{value}'")

        # If value is a formula, get the calculated value instead
        if isinstance(value, str) and value.startswith('='):
            # Get the display value which should be calculated
            value = model.data(index, QtCore.Qt.DisplayRole)
            print(f"[CROSS-TAB] _get_cell_value_from_model: Formula detected, DisplayRole value='{value}'")

        # Try to convert to number
        try:
            # Handle percentage
            if isinstance(value, str) and value.endswith('%'):
                return float(value[:-1]) / 100
            # Remove formatting characters (commas, dollar signs, spaces) before conversion
            if isinstance(value, str):
                value = value.replace(',', '').replace('$', '').replace(' ', '').strip()
            return float(value) if value else 0
        except (ValueError, TypeError):
            # Return the string value or 0
            return value if value else 0

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
            # Remove formatting characters (commas, dollar signs, spaces) before conversion
            if isinstance(value, str):
                value = value.replace(',', '').replace('$', '').replace(' ', '').strip()
            return float(value) if value else 0
        except (ValueError, TypeError):
            # Return the string value or 0
            return value if value else 0

    def _get_range_values(self, range_ref: str) -> list:
        """Expand a range reference and get all values.

        Args:
            range_ref: Range reference like "A1:A3" or "A1:B3"

        Returns:
            2D list of values for the range
        """
        import numpy as np

        # Parse the range (e.g., "A1:A3")
        if ':' not in range_ref:
            return [[self.get_cell_value(range_ref)]]

        parts = range_ref.split(':')
        if len(parts) != 2:
            return [[0]]

        start_ref = parts[0].strip().replace('$', '')
        end_ref = parts[1].strip().replace('$', '')

        # Parse start and end coordinates
        start_coords = self.parse_cell_reference(start_ref)
        end_coords = self.parse_cell_reference(end_ref)

        if not start_coords or not end_coords:
            return [[0]]

        start_row, start_col = start_coords
        end_row, end_col = end_coords

        # Ensure start <= end
        if start_row > end_row:
            start_row, end_row = end_row, start_row
        if start_col > end_col:
            start_col, end_col = end_col, start_col

        # Build the 2D array of values
        values = []
        for row in range(start_row, end_row + 1):
            row_values = []
            for col in range(start_col, end_col + 1):
                cell_ref = f"{self.col_index_to_letter(col)}{row + 1}"
                row_values.append(self.get_cell_value(cell_ref))
            values.append(row_values)

        # Convert to numpy array for formulas library
        return np.array(values) if values else [[0]]

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
                # Check if it's a range (contains :)
                if ':' in input_ref:
                    # Expand the range and get all values
                    range_values = self._get_range_values(input_ref)
                    input_values.append(range_values)
                else:
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
                return "#NOT_SUPPORTED!"
            except Exception as e:
                return "#ERROR!"

        except Exception as e:
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
        original_formula = formula
        print(f"[CROSS-TAB] _preprocess_formula: Input formula='{formula}' at row={row}, col={col}")

        # Replace sheet references and header-based references
        # This handles: 'Sheet Name'!cmp.1, Price!cmp, cmp.1, cmp
        def replace_sheet_reference_quoted(match):
            """Replace quoted sheet reference like 'Sheet Name'!field.row or 'Sheet Name'!field"""
            sheet_name = match.group(1)
            cell_ref = match.group(2)
            full_ref = match.group(0)

            # Check if sheet exists (case-insensitive)
            actual_name, target_model = self._get_sheet_model_case_insensitive(sheet_name)
            if target_model is None:
                available_sheets = list(self.sheet_models.keys()) if self.sheet_models else []
                logger.warning(f"Sheet not found: '{sheet_name}' in reference {full_ref}. Available sheets: {available_sheets}")
                return "#REF!"

            # Check if it's already a standard cell reference (A1, B2, etc.)
            # Standard cell references don't need header resolution
            if re.match(r'^[A-Z]+\d+$', cell_ref.upper()):
                standard_ref = cell_ref
            else:
                # Resolve the cell reference (with or without explicit row)
                standard_ref = self.resolve_header_reference(cell_ref, current_row=row, model=target_model)

                if not standard_ref:
                    # Field not found in target sheet
                    logger.warning(f"Could not resolve field reference in sheet '{sheet_name}': {cell_ref}")
                    return "#REF!"

            # Fetch the actual value from the target sheet
            value = self._get_cell_value_from_model(standard_ref, target_model)

            # Return the value as a literal
            if value is None or value == "":
                return "0"
            elif isinstance(value, str):
                # If it's a string, we need to quote it for the formula
                # But if it's a number string, keep it as number
                try:
                    float(value)
                    return str(value)
                except (ValueError, TypeError):
                    # It's a text string, return as 0 or handle as text
                    # For formulas, text in calculations usually becomes 0
                    return "0"
            else:
                return str(value)

        def replace_sheet_reference_unquoted(match):
            """Replace unquoted sheet reference like Sheet!field.row or Sheet!field"""
            sheet_name = match.group(1)
            cell_ref = match.group(2)
            full_ref = match.group(0)

            print(f"[CROSS-TAB] Matched '{full_ref}' -> sheet='{sheet_name}', cell_ref='{cell_ref}'")
            print(f"[CROSS-TAB] Available sheets = {list(self.sheet_models.keys()) if self.sheet_models else []}")

            # Check if sheet exists (case-insensitive)
            actual_name, target_model = self._get_sheet_model_case_insensitive(sheet_name)
            if target_model is None:
                available_sheets = list(self.sheet_models.keys()) if self.sheet_models else []
                print(f"[CROSS-TAB] ERROR: Sheet not found: '{sheet_name}'. Available: {available_sheets}")
                return "#REF!"

            print(f"[CROSS-TAB] Found model for '{actual_name}', model type={type(target_model).__name__}")

            # Check if it's already a standard cell reference (A1, B2, etc.)
            # Standard cell references don't need header resolution
            if re.match(r'^[A-Z]+\d+$', cell_ref.upper()):
                standard_ref = cell_ref
            else:
                # Resolve the cell reference (with or without explicit row)
                standard_ref = self.resolve_header_reference(cell_ref, current_row=row, model=target_model)

                if not standard_ref:
                    # Field not found in target sheet
                    logger.warning(f"Could not resolve field reference in sheet '{sheet_name}': {cell_ref}")
                    return "#REF!"

            # Fetch the actual value from the target sheet
            value = self._get_cell_value_from_model(standard_ref, target_model)
            print(f"[CROSS-TAB] Got value '{value}' (type={type(value).__name__}) from {actual_name}!{standard_ref}")

            # Return the value as a literal
            if value is None or value == "":
                print(f"[CROSS-TAB] Value is None/empty, returning '0'")
                return "0"
            elif isinstance(value, str):
                # If it's a string, we need to quote it for the formula
                # But if it's a number string, keep it as number
                try:
                    float(value)
                    print(f"[CROSS-TAB] Returning numeric string '{value}'")
                    return str(value)
                except (ValueError, TypeError):
                    # It's a text string, return as 0 or handle as text
                    # For formulas, text in calculations usually becomes 0
                    print(f"[CROSS-TAB] Text value, returning '0'")
                    return "0"
            else:
                print(f"[CROSS-TAB] Returning str(value) = '{value}'")
                return str(value)

        def replace_local_reference(match):
            """Replace local reference like field.row or field"""
            full_ref = match.group(0)

            # Check if this looks like a standard Excel reference (e.g., A1, B2, AA10)
            # If so, don't try to resolve it as a header reference
            if re.match(r'^[A-Z]+\d+$', full_ref.upper()):
                return full_ref

            # Resolve the reference
            standard_ref = self.resolve_header_reference(full_ref, current_row=row, model=self.table_model)

            if standard_ref:
                return standard_ref
            else:
                # Not a valid field reference - check if it looks like a field.row pattern
                if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*\.\d+$', full_ref):
                    # This looks like a field reference that couldn't be resolved
                    logger.warning(f"Could not resolve field reference: {full_ref}")
                    return "#REF!"
                # Otherwise keep as-is (might be something else)
                return full_ref

        def replace_field_only(match):
            """Replace field name only (same-row reference)"""
            field_name = match.group(0)

            # Don't replace if it looks like:
            # - Single letter (Excel column like A, B, C, etc.)
            # - Known Excel function name (will be followed by parenthesis, already filtered)
            # - Part of a cell reference (e.g., A in A1)
            if len(field_name) == 1 and field_name.upper() in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                return field_name

            # Check if it's a valid field in the model
            col_idx = self.get_column_index_by_field(field_name, model=self.table_model)
            if col_idx is not None:
                # It's a valid field, resolve it as same-row reference
                standard_ref = self.resolve_header_reference(field_name, current_row=row, model=self.table_model)
                if standard_ref:
                    return standard_ref

            # Not a valid field, keep as-is (might be Excel function, constant, etc.)
            return field_name

        # Process in order of specificity:
        # 1. Sheet references (quoted): 'Sheet Name'!field.row or 'Sheet Name'!field or 'Sheet Name'!A1
        # Updated regex to match both field-based references and standard cell references (A1, B2, etc.)
        formula = re.sub(
            r"'([^']+)'!([a-zA-Z_][a-zA-Z0-9_]*(?:\.\d+)?|[A-Z]+\d+)\b",
            replace_sheet_reference_quoted,
            formula
        )

        # 2. Sheet references (unquoted): Sheet!field.row or Sheet!field or Sheet!A1
        # Updated regex to match both field-based references and standard cell references (A1, B2, etc.)
        formula = re.sub(
            r'\b([a-zA-Z_][a-zA-Z0-9_]+)!([a-zA-Z_][a-zA-Z0-9_]*(?:\.\d+)?|[A-Z]+\d+)\b',
            replace_sheet_reference_unquoted,
            formula
        )

        # 3. Local references with explicit row: field.row
        formula = re.sub(
            r'\b([a-zA-Z_][a-zA-Z0-9_]*)\.(\d+)\b',
            replace_local_reference,
            formula
        )

        # 4. Field name only (same-row), but only if valid field and not followed by (
        # This must be done carefully to avoid matching Excel functions
        formula = re.sub(
            r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b(?!\s*[\(\.])',
            replace_field_only,
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
                return "A1"  # Fallback to A1

        # Replace INDIRECT(...) with the resolved reference
        formula = re.sub(
            r'\bINDIRECT\(\s*([^)]+)\s*\)',
            replace_indirect,
            formula,
            flags=re.IGNORECASE
        )

        if formula != original_formula:
            print(f"[CROSS-TAB] _preprocess_formula: Transformed '{original_formula}' -> '{formula}'")

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

    def _extract_short_field_names(self, field_name: str) -> list:
        """Extract potential short field names from a full field name.

        For example:
            sg_prep_mandays -> ['prep', 'prep_mandays', 'sg_prep_mandays']
            sg_model_mandays -> ['model', 'model_mandays', 'sg_model_mandays']
            _calc_price -> ['calc_price', 'price', '_calc_price']

        Args:
            field_name: Full field name

        Returns:
            List of potential short names including the original
        """
        short_names = [field_name]  # Always include the original

        # Remove sg_ prefix if present
        if field_name.startswith('sg_'):
            without_prefix = field_name[3:]  # Remove 'sg_'
            short_names.append(without_prefix)

            # Remove common suffixes: _mandays, _rate, _hours, etc.
            for suffix in ['_mandays', '_rate', '_hours', '_days', '_weeks']:
                if without_prefix.endswith(suffix):
                    short_names.append(without_prefix[:without_prefix.rfind(suffix)])
                    break

        # Handle underscore-prefixed fields like _calc_price
        if field_name.startswith('_'):
            without_prefix = field_name[1:]  # Remove '_'
            short_names.append(without_prefix)

            # Also try removing calc_ or similar prefixes
            if without_prefix.startswith('calc_'):
                short_names.append(without_prefix[5:])  # Remove 'calc_'

        return list(set(short_names))  # Remove duplicates

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

        # Get the field name for the changed cell
        field_name = None
        if hasattr(self.table_model, 'column_fields') and changed_col < len(self.table_model.column_fields):
            field_name = self.table_model.column_fields[changed_col]

        # Get all potential short names for this field
        short_names = self._extract_short_field_names(field_name) if field_name else []

        # Create patterns to match:
        # 1. Standard cell ref: A1, B2, etc.
        # 2. Explicit row header ref: field.1, field.2, etc. (including short names like prep.1)
        # 3. Same-row header ref: field (without row number)
        # 4. Sheet references: 'Sheet'!field.1, Sheet!field, etc.

        changed_header_ref = f"{field_name}.{changed_row + 1}" if field_name else None
        # Also create header refs for all short names
        changed_header_refs = [f"{name}.{changed_row + 1}" for name in short_names]

        # Scan all cells to find those with formulas referencing the changed cell
        for row in range(self.table_model.rowCount()):
            for col in range(self.table_model.columnCount()):
                index = self.table_model.index(row, col)
                value = self.table_model.data(index, QtCore.Qt.EditRole)

                # Check if it's a formula
                if isinstance(value, str) and value.startswith('='):
                    formula_depends_on_changed = False

                    # Check standard cell reference (A1, B2, etc.)
                    if re.search(r'\b' + changed_ref + r'\b', value, re.IGNORECASE):
                        formula_depends_on_changed = True

                    # Check explicit row header reference (field.1, field.2, etc.)
                    # Check all possible header refs including short names
                    if not formula_depends_on_changed and changed_header_refs:
                        for header_ref in changed_header_refs:
                            if re.search(r'\b' + re.escape(header_ref) + r'\b', value, re.IGNORECASE):
                                formula_depends_on_changed = True
                                break

                    # Check same-row header reference (field without row number)
                    # This is only relevant if the formula is in the same row as the changed cell
                    if not formula_depends_on_changed and field_name and row == changed_row:
                        # Look for the field name (or any of its short versions) used without explicit row number
                        # Pattern: field name not followed by a dot and number
                        for name in short_names:
                            pattern = r'\b' + re.escape(name) + r'\b(?!\s*\.)'
                            if re.search(pattern, value, re.IGNORECASE):
                                formula_depends_on_changed = True
                                break

                    # Check sheet references (e.g., 'Sheet'!field.1, Sheet!field)
                    # This is a simple check - just see if the field name appears in a sheet reference
                    # A more complete implementation would parse all sheet models
                    elif field_name:
                        # Check quoted sheet refs: 'AnySheet'!field.row or 'AnySheet'!field
                        pattern = r"'[^']+'!" + re.escape(field_name) + r'\.?' + str(changed_row + 1) + r'\b'
                        if re.search(pattern, value):
                            formula_depends_on_changed = True
                        # Check unquoted sheet refs: AnySheet!field.row or AnySheet!field
                        pattern = r'\b[a-zA-Z_][a-zA-Z0-9_]+!' + re.escape(field_name) + r'\.?' + str(changed_row + 1) + r'\b'
                        if re.search(pattern, value):
                            formula_depends_on_changed = True

                    if formula_depends_on_changed:
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
