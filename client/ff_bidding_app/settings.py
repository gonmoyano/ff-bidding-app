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
                logger.debug(f"Settings loaded from {self.settings_file}")
            except Exception as e:
                logger.error(f"Failed to load settings: {e}")
                self.settings = {}
        else:
            logger.debug("No settings file found, using defaults")
            self.settings = {}

    def _save(self):
        """Save settings to file."""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2)
            logger.debug(f"Settings saved to {self.settings_file}")
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
        logger.debug(f"Sort template '{name}' saved")

    def delete_sort_template(self, name):
        """Delete a sort template.

        Args:
            name: Template name to delete
        """
        if "sort_templates" in self.settings and name in self.settings["sort_templates"]:
            del self.settings["sort_templates"][name]
            self._save()
            logger.debug(f"Sort template '{name}' deleted")

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
        logger.debug(f"Column mapping '{mapping_key}' saved with {len(mapping)} mappings")

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
        logger.debug(f"Column visibility '{context_key}' saved with {len(visibility)} columns")

    def get_column_order(self, context_key):
        """Get column order settings for a specific context.

        Args:
            context_key: Unique key for the context (e.g., "vfx_breakdown")

        Returns:
            List of field names in display order, or None if not found
        """
        if "column_order" not in self.settings:
            return None
        return self.settings["column_order"].get(context_key)

    def set_column_order(self, context_key, order):
        """Save column order settings for a specific context.

        Args:
            context_key: Unique key for the context (e.g., "vfx_breakdown")
            order: List of field names in display order
        """
        if "column_order" not in self.settings:
            self.settings["column_order"] = {}

        self.settings["column_order"][context_key] = order
        self._save()
        logger.debug(f"Column order '{context_key}' saved with {len(order)} columns")

    def get_column_widths(self, context_key):
        """Get column width settings for a specific context.

        Args:
            context_key: Unique key for the context (e.g., "vfx_breakdown")

        Returns:
            Dictionary mapping field names to widths (int), or None if not found
        """
        if "column_widths" not in self.settings:
            return None
        return self.settings["column_widths"].get(context_key)

    def set_column_widths(self, context_key, widths):
        """Save column width settings for a specific context.

        Args:
            context_key: Unique key for the context (e.g., "vfx_breakdown")
            widths: Dictionary mapping field names to widths (int)
        """
        if "column_widths" not in self.settings:
            self.settings["column_widths"] = {}

        self.settings["column_widths"][context_key] = widths
        self._save()
        logger.debug(f"Column widths '{context_key}' saved with {len(widths)} columns")

    def get_column_dropdowns(self, context_key):
        """Get column dropdown settings for a specific context.

        Args:
            context_key: Unique key for the context (e.g., "vfx_breakdown")

        Returns:
            Dictionary mapping field names to dropdown enabled (bool), or None if not found
        """
        if "column_dropdowns" not in self.settings:
            return None
        return self.settings["column_dropdowns"].get(context_key)

    def set_column_dropdowns(self, context_key, dropdowns):
        """Save column dropdown settings for a specific context.

        Args:
            context_key: Unique key for the context (e.g., "vfx_breakdown")
            dropdowns: Dictionary mapping field names to dropdown enabled (bool)
        """
        if "column_dropdowns" not in self.settings:
            self.settings["column_dropdowns"] = {}

        self.settings["column_dropdowns"][context_key] = dropdowns
        self._save()
        logger.debug(f"Column dropdowns '{context_key}' saved with {len(dropdowns)} columns")

    def get_line_items_price_formula(self):
        """Get the default formula for Line Items Price column.

        Returns:
            String containing the default formula, or None if not set
        """
        return self.settings.get("line_items_price_formula")

    def set_line_items_price_formula(self, formula):
        """Set the default formula for Line Items Price column.

        Args:
            formula: Formula string (e.g., "=('Rate Card'!model.1*model) + ...")
        """
        self.settings["line_items_price_formula"] = formula
        self._save()
        logger.debug(f"Line Items price formula saved")

    def get_default_line_items_price_formula(self):
        """Get the default formula for Line Items Price column, with fallback to hardcoded default.

        Returns:
            String containing the formula
        """
        # Try to get from settings first
        formula = self.get_line_items_price_formula()
        if formula:
            return formula

        # Fallback to hardcoded default
        return "=('Rate Card'!model.1*model) + ('Rate Card'!tex.1*tex) + ('Rate Card'!rig.1*rig) + ('Rate Card'!mm.1*mm) + ('Rate Card'!prep.1*prep) + ('Rate Card'!gen.1*gen) + ('Rate Card'!anim.1*anim) + ('Rate Card'!lookdev.1*lookdev) + ('Rate Card'!lgt.1*lgt) + ('Rate Card'!fx.1*fx) + ('Rate Card'!cmp.1*cmp)"

    def get_dpi_scale(self):
        """Get DPI scale factor for the application.

        Returns:
            float: DPI scale factor (default: 1.0)
        """
        return self.get("dpi_scale", 1.0)

    def set_dpi_scale(self, scale):
        """Set DPI scale factor for the application.

        Args:
            scale: DPI scale factor (e.g., 1.0, 1.25, 1.5, 2.0)
        """
        self.set("dpi_scale", scale)
        logger.debug(f"DPI scale set to {scale}")

    def get_currency(self):
        """Get currency symbol used by the application.

        Returns:
            str: Currency symbol (default: "$")
        """
        return self.get("currency", "$")

    def set_currency(self, currency):
        """Set currency symbol used by the application.

        Args:
            currency: Currency symbol (e.g., "$", "€", "£", "¥")
        """
        self.set("currency", currency)
        logger.debug(f"Currency set to {currency}")
