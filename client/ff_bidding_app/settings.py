"""Application settings manager for persistent storage."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class AppSettings:
    """Manages application settings with persistent JSON storage."""

    def __init__(self, settings_file=None):
        """Initialize settings manager.

        Args:
            settings_file: Path to settings file. If None, uses default location.
        """
        if settings_file is None:
            # Use user's home directory for settings
            settings_dir = Path.home() / ".ff_bidding_app"
            settings_dir.mkdir(exist_ok=True)
            settings_file = settings_dir / "settings.json"

        self.settings_file = Path(settings_file)
        self.settings = {}
        self._load()

    def _load(self):
        """Load settings from file."""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
                logger.info(f"Settings loaded from {self.settings_file}")
            except Exception as e:
                logger.error(f"Failed to load settings: {e}")
                self.settings = {}
        else:
            logger.info("No settings file found, using defaults")
            self.settings = {}

    def _save(self):
        """Save settings to file."""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2)
            logger.info(f"Settings saved to {self.settings_file}")
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    def get_sort_templates(self):
        """Get saved sort templates.

        Returns:
            Dictionary of {template_name: [(col_idx, direction), ...]}
        """
        return self.settings.get("sort_templates", {})

    def set_sort_templates(self, templates):
        """Save sort templates.

        Args:
            templates: Dictionary of {template_name: [(col_idx, direction), ...]}
        """
        self.settings["sort_templates"] = templates
        self._save()

    def save_sort_template(self, name, config):
        """Save a single sort template.

        Args:
            name: Template name
            config: List of (col_idx, direction) tuples
        """
        if "sort_templates" not in self.settings:
            self.settings["sort_templates"] = {}

        self.settings["sort_templates"][name] = config
        self._save()
        logger.info(f"Sort template '{name}' saved")

    def delete_sort_template(self, name):
        """Delete a sort template.

        Args:
            name: Template name to delete
        """
        if "sort_templates" in self.settings and name in self.settings["sort_templates"]:
            del self.settings["sort_templates"][name]
            self._save()
            logger.info(f"Sort template '{name}' deleted")

    def get_column_mappings(self):
        """Get saved column mappings for import dialogs.

        Returns:
            Dictionary of {mapping_key: {sg_field: excel_column}}
        """
        return self.settings.get("column_mappings", {})

    def set_column_mapping(self, mapping_key, mapping):
        """Save a column mapping.

        Args:
            mapping_key: Unique key for this mapping (e.g., "vfx_breakdown")
            mapping: Dictionary mapping SG fields to Excel columns
        """
        if "column_mappings" not in self.settings:
            self.settings["column_mappings"] = {}

        self.settings["column_mappings"][mapping_key] = mapping
        self._save()
        logger.info(f"Column mapping '{mapping_key}' saved with {len(mapping)} mappings")

    def get_column_mapping(self, mapping_key):
        """Get a specific column mapping.

        Args:
            mapping_key: Unique key for the mapping

        Returns:
            Dictionary mapping SG fields to Excel columns, or None if not found
        """
        mappings = self.get_column_mappings()
        return mappings.get(mapping_key)

    def get(self, key, default=None):
        """Get a setting value.

        Args:
            key: Setting key
            default: Default value if key not found

        Returns:
            Setting value or default
        """
        return self.settings.get(key, default)

    def set(self, key, value):
        """Set a setting value.

        Args:
            key: Setting key
            value: Setting value
        """
        self.settings[key] = value
        self._save()

    def get_column_visibility(self, context_key):
        """Get column visibility settings for a specific context.

        Args:
            context_key: Unique key for the context (e.g., "vfx_breakdown")

        Returns:
            Dictionary mapping field names to visibility (bool), or None if not found
        """
        if "column_visibility" not in self.settings:
            return None
        return self.settings["column_visibility"].get(context_key)

    def set_column_visibility(self, context_key, visibility):
        """Save column visibility settings for a specific context.

        Args:
            context_key: Unique key for the context (e.g., "vfx_breakdown")
            visibility: Dictionary mapping field names to visibility (bool)
        """
        if "column_visibility" not in self.settings:
            self.settings["column_visibility"] = {}

        self.settings["column_visibility"][context_key] = visibility
        self._save()
        logger.info(f"Column visibility '{context_key}' saved with {len(visibility)} columns")
