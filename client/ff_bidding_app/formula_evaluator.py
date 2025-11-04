"""
Formula Evaluator
Evaluates Google Sheets-style formulas for calculated fields in tables.
"""

import re
from typing import Any, Dict, List, Optional
from PySide6 import QtWidgets

try:
    from .logger import logger
except ImportError:
    import logging
    logger = logging.getLogger("FFPackageManager")


class FormulaEvaluator:
    """Evaluates formulas similar to Google Sheets."""

    def __init__(self, table_model=None):
        """Initialize the formula evaluator.

        Args:
            table_model: The table model to access cell data
        """
        self.table_model = table_model
        self.functions = {
            'SUM': self._func_sum,
            'AVERAGE': self._func_average,
            'AVG': self._func_average,
            'COUNT': self._func_count,
            'MIN': self._func_min,
            'MAX': self._func_max,
            'IF': self._func_if,
        }

    def evaluate(self, formula: str, current_row: int = None) -> Any:
        """Evaluate a formula and return the result.

        Args:
            formula: The formula string (e.g., "=SUM(A1:A10)")
            current_row: The current row index for relative references

        Returns:
            The calculated value or error message
        """
        if not formula:
            return ""

        # Remove leading/trailing whitespace
        formula = formula.strip()

        # Check if it's a formula
        if not formula.startswith('='):
            # Not a formula, return as-is
            return formula

        # Remove the = sign
        formula = formula[1:].strip()

        try:
            result = self._evaluate_expression(formula, current_row)
            return result
        except Exception as e:
            logger.error(f"Error evaluating formula '{formula}': {e}", exc_info=True)
            return f"#ERROR: {str(e)}"

    def _evaluate_expression(self, expr: str, current_row: int = None) -> Any:
        """Evaluate an expression (without the = sign)."""
        # Handle function calls
        func_match = re.match(r'([A-Z]+)\((.*)\)$', expr, re.IGNORECASE)
        if func_match:
            func_name = func_match.group(1).upper()
            args_str = func_match.group(2)

            if func_name in self.functions:
                return self.functions[func_name](args_str, current_row)
            else:
                return f"#ERROR: Unknown function {func_name}"

        # Handle cell references
        if self._is_cell_reference(expr):
            return self._get_cell_value(expr, current_row)

        # Handle range references (convert to list)
        if ':' in expr:
            values = self._get_range_values(expr, current_row)
            return values

        # Handle arithmetic expressions
        try:
            # Simple arithmetic evaluation (be careful with eval!)
            # Replace cell references with their values
            evaluated_expr = self._replace_cell_references(expr, current_row)
            result = eval(evaluated_expr, {"__builtins__": {}}, {})
            return result
        except:
            # If eval fails, try to parse as a number
            try:
                return float(expr)
            except:
                return expr

    def _is_cell_reference(self, ref: str) -> bool:
        """Check if a string is a valid cell reference (e.g., A1, $B$2)."""
        pattern = r'^\$?[A-Z]+\$?\d+$'
        return bool(re.match(pattern, ref, re.IGNORECASE))

    def _parse_cell_reference(self, ref: str) -> tuple:
        """Parse a cell reference into column and row indices.

        Args:
            ref: Cell reference like "A1", "$B$2", "C10"

        Returns:
            Tuple of (column_index, row_index) or (None, None) if invalid
        """
        # Remove $ signs for absolute references
        ref = ref.replace('$', '')

        # Extract column letters and row number
        match = re.match(r'([A-Z]+)(\d+)', ref, re.IGNORECASE)
        if not match:
            return None, None

        col_letters = match.group(1).upper()
        row_num = int(match.group(2))

        # Convert column letters to index (A=0, B=1, ..., Z=25, AA=26, etc.)
        col_index = 0
        for i, letter in enumerate(reversed(col_letters)):
            col_index += (ord(letter) - ord('A') + 1) * (26 ** i)
        col_index -= 1  # Make it 0-based

        # Row is 1-based in formulas, 0-based in code
        row_index = row_num - 1

        return col_index, row_index

    def _get_cell_value(self, ref: str, current_row: int = None) -> Any:
        """Get the value of a cell reference."""
        if not self.table_model:
            return 0

        col_index, row_index = self._parse_cell_reference(ref)
        if col_index is None or row_index is None:
            return 0

        # Get value from the model
        try:
            index = self.table_model.index(row_index, col_index)
            value = self.table_model.data(index, QtWidgets.Qt.DisplayRole)

            # Try to convert to number
            try:
                return float(value) if value else 0
            except (ValueError, TypeError):
                return value if value else ""
        except:
            return 0

    def _get_range_values(self, range_ref: str, current_row: int = None) -> List[float]:
        """Get values from a range reference (e.g., A1:A10)."""
        if ':' not in range_ref:
            return []

        start_ref, end_ref = range_ref.split(':', 1)
        start_col, start_row = self._parse_cell_reference(start_ref.strip())
        end_col, end_row = self._parse_cell_reference(end_ref.strip())

        if None in (start_col, start_row, end_col, end_row):
            return []

        values = []
        for row in range(start_row, end_row + 1):
            for col in range(start_col, end_col + 1):
                val = self._get_cell_value(f"{self._col_index_to_letter(col)}{row + 1}", current_row)
                try:
                    values.append(float(val))
                except (ValueError, TypeError):
                    pass  # Skip non-numeric values

        return values

    def _col_index_to_letter(self, index: int) -> str:
        """Convert column index to letter(s) (0 -> A, 25 -> Z, 26 -> AA, etc.)."""
        result = ""
        index += 1  # Make it 1-based
        while index > 0:
            index -= 1
            result = chr(ord('A') + (index % 26)) + result
            index //= 26
        return result

    def _replace_cell_references(self, expr: str, current_row: int = None) -> str:
        """Replace cell references in an expression with their values."""
        # Find all cell references
        pattern = r'\$?[A-Z]+\$?\d+'

        def replacer(match):
            ref = match.group(0)
            value = self._get_cell_value(ref, current_row)
            return str(value)

        return re.sub(pattern, replacer, expr, flags=re.IGNORECASE)

    # Formula functions

    def _func_sum(self, args_str: str, current_row: int = None) -> float:
        """SUM function."""
        values = self._parse_function_args(args_str, current_row)
        numeric_values = []
        for val in values:
            if isinstance(val, list):
                numeric_values.extend(val)
            else:
                try:
                    numeric_values.append(float(val))
                except (ValueError, TypeError):
                    pass
        return sum(numeric_values)

    def _func_average(self, args_str: str, current_row: int = None) -> float:
        """AVERAGE function."""
        values = self._parse_function_args(args_str, current_row)
        numeric_values = []
        for val in values:
            if isinstance(val, list):
                numeric_values.extend(val)
            else:
                try:
                    numeric_values.append(float(val))
                except (ValueError, TypeError):
                    pass

        if not numeric_values:
            return 0
        return sum(numeric_values) / len(numeric_values)

    def _func_count(self, args_str: str, current_row: int = None) -> int:
        """COUNT function."""
        values = self._parse_function_args(args_str, current_row)
        count = 0
        for val in values:
            if isinstance(val, list):
                count += len(val)
            else:
                count += 1
        return count

    def _func_min(self, args_str: str, current_row: int = None) -> float:
        """MIN function."""
        values = self._parse_function_args(args_str, current_row)
        numeric_values = []
        for val in values:
            if isinstance(val, list):
                numeric_values.extend(val)
            else:
                try:
                    numeric_values.append(float(val))
                except (ValueError, TypeError):
                    pass

        return min(numeric_values) if numeric_values else 0

    def _func_max(self, args_str: str, current_row: int = None) -> float:
        """MAX function."""
        values = self._parse_function_args(args_str, current_row)
        numeric_values = []
        for val in values:
            if isinstance(val, list):
                numeric_values.extend(val)
            else:
                try:
                    numeric_values.append(float(val))
                except (ValueError, TypeError):
                    pass

        return max(numeric_values) if numeric_values else 0

    def _func_if(self, args_str: str, current_row: int = None) -> Any:
        """IF function: IF(condition, value_if_true, value_if_false)."""
        # Split by comma, but respect nested functions
        args = self._split_args(args_str)

        if len(args) < 2:
            return "#ERROR: IF requires at least 2 arguments"

        condition = args[0].strip()
        value_if_true = args[1].strip() if len(args) > 1 else ""
        value_if_false = args[2].strip() if len(args) > 2 else ""

        # Evaluate condition
        try:
            cond_result = self._evaluate_expression(condition, current_row)
            if cond_result:
                return self._evaluate_expression(value_if_true, current_row)
            else:
                return self._evaluate_expression(value_if_false, current_row)
        except:
            return "#ERROR: Invalid IF condition"

    def _parse_function_args(self, args_str: str, current_row: int = None) -> List[Any]:
        """Parse function arguments."""
        args = self._split_args(args_str)
        values = []

        for arg in args:
            arg = arg.strip()
            if ':' in arg:
                # Range reference
                range_vals = self._get_range_values(arg, current_row)
                values.append(range_vals)
            elif self._is_cell_reference(arg):
                # Cell reference
                values.append(self._get_cell_value(arg, current_row))
            else:
                # Try to evaluate as expression
                try:
                    val = self._evaluate_expression(arg, current_row)
                    values.append(val)
                except:
                    values.append(arg)

        return values

    def _split_args(self, args_str: str) -> List[str]:
        """Split function arguments by comma, respecting nested parentheses."""
        args = []
        current_arg = ""
        paren_depth = 0

        for char in args_str:
            if char == ',' and paren_depth == 0:
                args.append(current_arg)
                current_arg = ""
            else:
                if char == '(':
                    paren_depth += 1
                elif char == ')':
                    paren_depth -= 1
                current_arg += char

        if current_arg:
            args.append(current_arg)

        return args
