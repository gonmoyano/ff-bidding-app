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
            except Exception as e:
                logger.error(f"Failed to load settings: {e}")
                self.settings = {}
        else:
            self.settings = {}

    def _save(self):
        """Save settings to file."""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2)
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

    def delete_sort_template(self, name):
        """Delete a sort template.

        Args:
            name: Template name to delete
        """
        if "sort_templates" in self.settings and name in self.settings["sort_templates"]:
            del self.settings["sort_templates"][name]
            self._save()

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
        return "=('Rate Card'!model.1*model) + ('Rate Card'!tex.1*tex) + ('Rate Card'!rig.1*rig) + ('Rate Card'!mm.1*mm) + ('Rate Card'!prep.1*prep) + ('Rate Card'!gen.1*gen) + ('Rate Card'!anim.1*anim) + ('Rate Card'!lookdev.1*lookdev) + ('Rate Card'!lgt.1*lgt) + ('Rate Card'!fx.1*fx) + ('Rate Card'!cmp.1*cmp) + ('Rate Card'!io.1*io)"

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

    def get_bid_currency(self, bid_id):
        """Get currency symbol for a specific bid.

        Args:
            bid_id: ID of the bid

        Returns:
            str: Currency symbol (falls back to global setting if not set)
        """
        bid_currencies = self.get("bid_currencies", {})
        bid_key = str(bid_id)
        if bid_key in bid_currencies:
            return bid_currencies[bid_key].get("symbol", self.get_currency())
        return self.get_currency()

    def set_bid_currency(self, bid_id, currency):
        """Set currency symbol for a specific bid.

        Args:
            bid_id: ID of the bid
            currency: Currency symbol (e.g., "$", "€", "£", "¥")
        """
        bid_currencies = self.get("bid_currencies", {})
        bid_key = str(bid_id)
        if bid_key not in bid_currencies:
            bid_currencies[bid_key] = {}
        bid_currencies[bid_key]["symbol"] = currency
        self.set("bid_currencies", bid_currencies)

    def get_bid_currency_position(self, bid_id):
        """Get currency symbol position for a specific bid.

        Args:
            bid_id: ID of the bid

        Returns:
            str: "prepend" or "append" (default: "prepend")
        """
        bid_currencies = self.get("bid_currencies", {})
        bid_key = str(bid_id)
        if bid_key in bid_currencies:
            return bid_currencies[bid_key].get("position", "prepend")
        return "prepend"

    def set_bid_currency_position(self, bid_id, position):
        """Set currency symbol position for a specific bid.

        Args:
            bid_id: ID of the bid
            position: "prepend" or "append"
        """
        bid_currencies = self.get("bid_currencies", {})
        bid_key = str(bid_id)
        if bid_key not in bid_currencies:
            bid_currencies[bid_key] = {}
        bid_currencies[bid_key]["position"] = position
        self.set("bid_currencies", bid_currencies)

    def get_thumbnail_cache_path(self):
        """Get the thumbnail cache folder path.

        Returns:
            Path: Path to thumbnail cache folder
        """
        default_cache = Path.home() / ".ff_bidding_app" / "thumbnail_cache"
        cache_path = self.get("thumbnail_cache_path")
        if cache_path:
            return Path(cache_path)
        return default_cache

    def set_thumbnail_cache_path(self, path):
        """Set the thumbnail cache folder path.

        Args:
            path: Path to cache folder (string or Path object)
        """
        self.set("thumbnail_cache_path", str(path))

    def get_thumbnail_cache_max_age_days(self):
        """Get the maximum age of cached thumbnails in days.

        Returns:
            int: Max age in days (default: 7)
        """
        return self.get("thumbnail_cache_max_age_days", 7)

    def set_thumbnail_cache_max_age_days(self, days):
        """Set the maximum age of cached thumbnails in days.

        Args:
            days: Max age in days
        """
        self.set("thumbnail_cache_max_age_days", days)

    def get_last_selected_rfq_id(self):
        """Get the last selected RFQ ID.

        Returns:
            int: Last selected RFQ ID, or None if not set
        """
        return self.get("last_selected_rfq_id")

    def set_last_selected_rfq_id(self, rfq_id):
        """Set the last selected RFQ ID.

        Args:
            rfq_id: RFQ ID to save
        """
        self.set("last_selected_rfq_id", rfq_id)

    def get_last_selected_package_for_rfq(self, rfq_id):
        """Get the last selected package ID for a specific RFQ.

        Args:
            rfq_id: RFQ ID

        Returns:
            int: Last selected package ID for this RFQ, or None if not set
        """
        if "last_selected_packages" not in self.settings:
            return None
        return self.settings["last_selected_packages"].get(str(rfq_id))

    def set_last_selected_package_for_rfq(self, rfq_id, package_id):
        """Set the last selected package ID for a specific RFQ.

        Args:
            rfq_id: RFQ ID
            package_id: Package ID to save (or None to clear)
        """
        if "last_selected_packages" not in self.settings:
            self.settings["last_selected_packages"] = {}

        if package_id is None:
            # Remove the entry if package_id is None
            if str(rfq_id) in self.settings["last_selected_packages"]:
                del self.settings["last_selected_packages"][str(rfq_id)]
        else:
            self.settings["last_selected_packages"][str(rfq_id)] = package_id

        self._save()
