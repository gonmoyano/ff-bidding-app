"""Spreadsheet caching system for deferred ShotGrid saves.

This module provides a caching layer that stores spreadsheet changes locally
and commits them to ShotGrid in batches during major events (tab change,
project change, app close). It also provides crash recovery by persisting
the cache to disk.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from PySide6 import QtCore, QtWidgets

logger = logging.getLogger(__name__)


class SpreadsheetCache:
    """Manages local caching of spreadsheet data for deferred ShotGrid saves.

    This class:
    - Tracks dirty spreadsheets that have unsaved changes
    - Persists cache to disk for crash recovery
    - Commits cached changes to ShotGrid in batches with progress feedback
    """

    # Cache file location
    CACHE_FILENAME = "spreadsheet_cache.json"

    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize the spreadsheet cache.

        Args:
            cache_dir: Directory for cache files. Defaults to ~/.ff_bidding_app/
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".ff_bidding_app"

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / self.CACHE_FILENAME

        # In-memory cache: {cache_key: {data_dict, cell_meta_dict, sheet_meta, project_id, bid_id, type, timestamp}}
        self._cache: Dict[str, Dict[str, Any]] = {}

        # Track which spreadsheets are dirty (have unsaved changes)
        self._dirty_keys: set = set()

        # ShotGrid session reference (set by caller)
        self._sg_session = None

        # Load any existing cache from disk (for crash recovery)
        self._load_from_disk()

        logger.info(f"SpreadsheetCache initialized. Cache dir: {self.cache_dir}")
        if self._cache:
            logger.info(f"Recovered {len(self._cache)} cached spreadsheets from disk")

    def set_sg_session(self, sg_session):
        """Set the ShotGrid session for committing changes.

        Args:
            sg_session: ShotGrid session object with save_spreadsheet_data method
        """
        self._sg_session = sg_session

    @staticmethod
    def make_cache_key(project_id: int, bid_id: int, spreadsheet_type: str) -> str:
        """Create a unique cache key for a spreadsheet.

        Args:
            project_id: ShotGrid project ID
            bid_id: ShotGrid bid ID
            spreadsheet_type: Type of spreadsheet (e.g., 'misc', 'total_cost')

        Returns:
            Unique cache key string
        """
        return f"{project_id}_{bid_id}_{spreadsheet_type}"

    def mark_dirty(
        self,
        project_id: int,
        bid_id: int,
        spreadsheet_type: str,
        data_dict: Dict[str, Any],
        cell_meta_dict: Optional[Dict[str, Any]] = None,
        sheet_meta: Optional[Dict[str, Any]] = None
    ):
        """Mark a spreadsheet as dirty with its current data.

        This caches the data locally without saving to ShotGrid.

        Args:
            project_id: ShotGrid project ID
            bid_id: ShotGrid bid ID
            spreadsheet_type: Type of spreadsheet
            data_dict: Spreadsheet cell data
            cell_meta_dict: Cell formatting metadata
            sheet_meta: Sheet-level metadata (column widths, etc.)
        """
        cache_key = self.make_cache_key(project_id, bid_id, spreadsheet_type)

        self._cache[cache_key] = {
            'project_id': project_id,
            'bid_id': bid_id,
            'spreadsheet_type': spreadsheet_type,
            'data_dict': data_dict,
            'cell_meta_dict': cell_meta_dict or {},
            'sheet_meta': sheet_meta or {},
            'timestamp': datetime.now().isoformat()
        }

        self._dirty_keys.add(cache_key)

        # Persist to disk for crash recovery
        self._save_to_disk()

        logger.debug(f"Marked spreadsheet dirty: {cache_key} ({len(data_dict)} cells)")

    def is_dirty(self, project_id: int, bid_id: int, spreadsheet_type: str) -> bool:
        """Check if a spreadsheet has unsaved changes.

        Args:
            project_id: ShotGrid project ID
            bid_id: ShotGrid bid ID
            spreadsheet_type: Type of spreadsheet

        Returns:
            True if the spreadsheet has unsaved changes
        """
        cache_key = self.make_cache_key(project_id, bid_id, spreadsheet_type)
        return cache_key in self._dirty_keys

    def has_dirty_spreadsheets(self) -> bool:
        """Check if there are any unsaved spreadsheets.

        Returns:
            True if any spreadsheets have unsaved changes
        """
        return len(self._dirty_keys) > 0

    def get_dirty_count(self) -> int:
        """Get the number of dirty spreadsheets.

        Returns:
            Number of spreadsheets with unsaved changes
        """
        return len(self._dirty_keys)

    def clear_dirty(self, project_id: int, bid_id: int, spreadsheet_type: str):
        """Mark a spreadsheet as clean (saved).

        Args:
            project_id: ShotGrid project ID
            bid_id: ShotGrid bid ID
            spreadsheet_type: Type of spreadsheet
        """
        cache_key = self.make_cache_key(project_id, bid_id, spreadsheet_type)
        self._dirty_keys.discard(cache_key)

        # Remove from cache
        if cache_key in self._cache:
            del self._cache[cache_key]

        # Update disk cache
        self._save_to_disk()

        logger.debug(f"Cleared dirty flag for: {cache_key}")

    def commit_all(
        self,
        parent_widget: Optional[QtWidgets.QWidget] = None,
        on_complete: Optional[Callable[[], None]] = None
    ) -> bool:
        """Commit all dirty spreadsheets to ShotGrid with progress feedback.

        Args:
            parent_widget: Parent widget for progress dialog
            on_complete: Callback when commit is complete

        Returns:
            True if all commits succeeded, False otherwise
        """
        if not self._dirty_keys:
            logger.info("No dirty spreadsheets to commit")
            if on_complete:
                on_complete()
            return True

        if not self._sg_session:
            logger.error("Cannot commit: No ShotGrid session set")
            return False

        dirty_count = len(self._dirty_keys)
        logger.info(f"Committing {dirty_count} dirty spreadsheets to ShotGrid")

        # Create progress dialog
        progress = QtWidgets.QProgressDialog(
            "Saving spreadsheet changes to ShotGrid...",
            "Cancel",
            0,
            dirty_count,
            parent_widget
        )
        progress.setWindowTitle("Saving Changes")
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.setMinimumDuration(0)  # Show immediately
        progress.setValue(0)

        # Process cached spreadsheets
        success_count = 0
        failed_keys = []

        # Get list of keys to process (copy to avoid modification during iteration)
        keys_to_process = list(self._dirty_keys)

        for i, cache_key in enumerate(keys_to_process):
            if progress.wasCanceled():
                logger.warning("Commit cancelled by user")
                break

            cache_entry = self._cache.get(cache_key)
            if not cache_entry:
                continue

            # Update progress
            spreadsheet_type = cache_entry.get('spreadsheet_type', 'unknown')
            bid_id = cache_entry.get('bid_id', 'unknown')
            progress.setLabelText(f"Saving {spreadsheet_type} spreadsheet for bid {bid_id}...")
            progress.setValue(i)

            # Process events to update UI
            QtWidgets.QApplication.processEvents()

            try:
                spreadsheet_type = cache_entry['spreadsheet_type']

                # Use name-based save for custom spreadsheets (Sheet1, Sheet2, etc.)
                if spreadsheet_type.startswith("Sheet"):
                    self._sg_session.save_spreadsheet_by_name(
                        project_id=cache_entry['project_id'],
                        bid_id=cache_entry['bid_id'],
                        spreadsheet_name=spreadsheet_type,
                        data_dict=cache_entry['data_dict'],
                        cell_meta_dict=cache_entry.get('cell_meta_dict', {}),
                        sheet_meta=cache_entry.get('sheet_meta', {})
                    )
                else:
                    # Use type-based save for built-in spreadsheets (misc, total_cost)
                    self._sg_session.save_spreadsheet_data(
                        project_id=cache_entry['project_id'],
                        bid_id=cache_entry['bid_id'],
                        spreadsheet_type=spreadsheet_type,
                        data_dict=cache_entry['data_dict'],
                        cell_meta_dict=cache_entry.get('cell_meta_dict', {}),
                        sheet_meta=cache_entry.get('sheet_meta', {})
                    )

                # Mark as clean
                self._dirty_keys.discard(cache_key)
                del self._cache[cache_key]
                success_count += 1

                logger.info(f"Committed spreadsheet: {cache_key}")

            except Exception as e:
                logger.error(f"Failed to commit spreadsheet {cache_key}: {e}", exc_info=True)
                failed_keys.append(cache_key)

        # Final progress update
        progress.setValue(dirty_count)
        progress.close()

        # Update disk cache
        self._save_to_disk()

        # Log results
        if failed_keys:
            logger.warning(f"Commit complete: {success_count} succeeded, {len(failed_keys)} failed")
        else:
            logger.info(f"Commit complete: {success_count} spreadsheets saved successfully")

        if on_complete:
            on_complete()

        return len(failed_keys) == 0

    def commit_for_bid(
        self,
        bid_id: int,
        parent_widget: Optional[QtWidgets.QWidget] = None
    ) -> bool:
        """Commit all dirty spreadsheets for a specific bid.

        Args:
            bid_id: ShotGrid bid ID
            parent_widget: Parent widget for progress dialog

        Returns:
            True if all commits succeeded
        """
        # Find keys for this bid
        bid_keys = [
            key for key in self._dirty_keys
            if self._cache.get(key, {}).get('bid_id') == bid_id
        ]

        if not bid_keys:
            return True

        # Temporarily limit dirty keys to just this bid's
        original_dirty = self._dirty_keys.copy()
        self._dirty_keys = set(bid_keys)

        result = self.commit_all(parent_widget)

        # Restore any remaining dirty keys
        self._dirty_keys.update(original_dirty - set(bid_keys))

        return result

    def _serialize_dict_keys(self, data: Dict) -> Dict:
        """Convert tuple keys to strings for JSON serialization.

        Args:
            data: Dictionary that may contain tuple keys

        Returns:
            Dictionary with all keys converted to strings
        """
        if not isinstance(data, dict):
            return data

        result = {}
        for key, value in data.items():
            # Convert tuple keys to string format "(row, col)"
            if isinstance(key, tuple):
                str_key = f"({key[0]},{key[1]})"
            else:
                str_key = str(key)

            # Recursively process nested dicts
            if isinstance(value, dict):
                result[str_key] = self._serialize_dict_keys(value)
            else:
                result[str_key] = value

        return result

    def _deserialize_dict_keys(self, data: Dict, convert_to_tuple: bool = False) -> Dict:
        """Convert string keys back to tuples where applicable.

        Args:
            data: Dictionary with string keys
            convert_to_tuple: Whether to convert "(row,col)" format back to tuples

        Returns:
            Dictionary with tuple keys restored where applicable
        """
        if not isinstance(data, dict):
            return data

        result = {}
        for key, value in data.items():
            # Check if key looks like a tuple "(row, col)" or "(row,col)"
            new_key = key
            if convert_to_tuple and isinstance(key, str) and key.startswith('(') and key.endswith(')'):
                try:
                    # Parse "(row,col)" or "(row, col)" format
                    inner = key[1:-1]
                    parts = [p.strip() for p in inner.split(',')]
                    if len(parts) == 2:
                        new_key = (int(parts[0]), int(parts[1]))
                except (ValueError, IndexError):
                    new_key = key

            # Recursively process nested dicts
            if isinstance(value, dict):
                # Only convert tuple keys in data_dict and cell_meta_dict
                should_convert = convert_to_tuple or key in ('data_dict', 'cell_meta_dict')
                result[new_key] = self._deserialize_dict_keys(value, convert_to_tuple=should_convert)
            else:
                result[new_key] = value

        return result

    def _save_to_disk(self):
        """Persist cache to disk for crash recovery."""
        try:
            # Only save dirty entries
            cache_data = {}
            for key in self._dirty_keys:
                if key in self._cache:
                    entry = self._cache[key].copy()
                    # Serialize tuple keys in data_dict and cell_meta_dict
                    if 'data_dict' in entry:
                        entry['data_dict'] = self._serialize_dict_keys(entry['data_dict'])
                    if 'cell_meta_dict' in entry:
                        entry['cell_meta_dict'] = self._serialize_dict_keys(entry['cell_meta_dict'])
                    cache_data[key] = entry

            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, default=str)

            logger.debug(f"Saved {len(cache_data)} cached spreadsheets to disk")

        except Exception as e:
            logger.error(f"Failed to save cache to disk: {e}", exc_info=True)

    def _load_from_disk(self):
        """Load cache from disk (for crash recovery)."""
        if not self.cache_file.exists():
            return

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # Deserialize tuple keys in data_dict and cell_meta_dict
            for key, entry in cache_data.items():
                if 'data_dict' in entry:
                    entry['data_dict'] = self._deserialize_dict_keys(entry['data_dict'], convert_to_tuple=True)
                if 'cell_meta_dict' in entry:
                    entry['cell_meta_dict'] = self._deserialize_dict_keys(entry['cell_meta_dict'], convert_to_tuple=True)

            self._cache = cache_data
            self._dirty_keys = set(cache_data.keys())

            logger.info(f"Loaded {len(cache_data)} cached spreadsheets from disk")

        except Exception as e:
            logger.error(f"Failed to load cache from disk: {e}", exc_info=True)
            self._cache = {}
            self._dirty_keys = set()

    def clear_cache(self):
        """Clear all cached data (both memory and disk)."""
        self._cache.clear()
        self._dirty_keys.clear()

        if self.cache_file.exists():
            try:
                self.cache_file.unlink()
                logger.info("Cleared spreadsheet cache file")
            except Exception as e:
                logger.error(f"Failed to delete cache file: {e}")

    def recover_on_startup(
        self,
        parent_widget: Optional[QtWidgets.QWidget] = None
    ) -> bool:
        """Check for and recover cached data on application startup.

        If there's cached data from a previous session (e.g., after a crash),
        prompts the user and commits it to ShotGrid.

        Args:
            parent_widget: Parent widget for dialogs

        Returns:
            True if recovery was successful or not needed
        """
        if not self.has_dirty_spreadsheets():
            return True

        dirty_count = self.get_dirty_count()

        # Show recovery dialog
        result = QtWidgets.QMessageBox.question(
            parent_widget,
            "Recover Unsaved Changes",
            f"Found {dirty_count} unsaved spreadsheet change(s) from a previous session.\n\n"
            "Would you like to save them to ShotGrid now?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes
        )

        if result == QtWidgets.QMessageBox.Yes:
            return self.commit_all(parent_widget)
        else:
            # User declined recovery - clear the cache
            self.clear_cache()
            logger.info("User declined recovery - cache cleared")
            return True


# Global cache instance
_spreadsheet_cache: Optional[SpreadsheetCache] = None


def get_spreadsheet_cache() -> SpreadsheetCache:
    """Get or create the global spreadsheet cache instance.

    Returns:
        The global SpreadsheetCache instance
    """
    global _spreadsheet_cache
    if _spreadsheet_cache is None:
        _spreadsheet_cache = SpreadsheetCache()
    return _spreadsheet_cache


def reset_spreadsheet_cache():
    """Reset the global spreadsheet cache instance."""
    global _spreadsheet_cache
    _spreadsheet_cache = None
