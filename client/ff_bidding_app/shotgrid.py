"""Simplified Shotgrid client for FF Package Manager."""
import logging
import os

try:
    from shotgun_api3 import Shotgun
    from shotgun_api3 import Fault  # at top with other imports
except ImportError:
    Shotgun = None
    print("Warning: shotgun_api3 not installed. Using simulated data.")

logger = logging.getLogger(__name__)


class ShotgridClient:
    """
    Simple Shotgrid API wrapper.

    Usage:
        # Via environment variables
        client = ShotgridClient()

        # Via parameters
        client = ShotgridClient(
            site_url="https://studio.shotgrid.com",
            script_name="my_script",
            api_key="abc123"
        )

        # Get projects
        projects = client.get_projects()

        # Get project entities
        assets = client.get_assets(project_id=123)
        shots = client.get_shots(project_id=123)
        rfqs = client.get_rfqs(project_id=123)
    """

    def __init__(self, site_url=None, script_name=None, api_key=None):
        """
        Initialize Shotgrid client.

        Args:
            site_url: SG URL (or use SG_URL env var)
            script_name: Script name (or use SG_SCRIPT env var)
            api_key: API key (or use SG_KEY env var)
        """
        self.site_url = site_url or os.getenv("SG_URL", "")
        self.script_name = script_name or os.getenv("SG_SCRIPT", "")
        self.api_key = api_key or os.getenv("SG_KEY", "")
        self._sg = None
        self._field_schema_cache = {}
        self._entity_schema_cache = {}

    def connect(self):
        """Connect to Shotgrid."""
        if Shotgun is None:
            raise RuntimeError(
                "shotgun_api3 not installed. "
                "Install with: pip install shotgun_api3"
            )

        if not all([self.site_url, self.script_name, self.api_key]):
            raise ValueError(
                "Missing credentials. Provide site_url, script_name, api_key "
                "or set SG_URL, SG_SCRIPT, SG_KEY environment variables."
            )

        if self._sg is None:
            self._sg = Shotgun(
                base_url=self.site_url,
                script_name=self.script_name,
                api_key=self.api_key
            )

        return self._sg

    @property
    def sg(self):
        """Get or create Shotgrid connection."""
        return self.connect()

    def get_projects(self, fields=None, status=None):
        """
        Get all projects.

        Args:
            fields: List of fields to return. Defaults to id, code, name, sg_status
            status: Filter by status (e.g., "Active", "Bidding"). None = all projects

        Returns:
            List of project dictionaries
        """
        if fields is None:
            fields = ["id", "code", "name", "sg_status"]

        # Build filters
        filters = []
        if status:
            filters.append(["sg_status", "is", status])

        return self.sg.find(
            "Project",
            filters,
            fields,
            order=[{"field_name": "name", "direction": "asc"}]
        )

    def get_bid_projects(self, fields=None):
        """
        Get all projects with status "Bidding".

        Args:
            fields: List of fields to return. Defaults to id, code, name, sg_status

        Returns:
            List of project dictionaries
        """
        return self.get_projects(fields=fields, status="Bidding")

    def get_assets(self, project_id, fields=None):
        """
        Get assets for a project.

        Args:
            project_id: Project ID
            fields: List of fields to return

        Returns:
            List of asset dictionaries
        """
        if fields is None:
            fields = ["id", "code", "sg_asset_type", "description"]

        return self.sg.find(
            "Asset",
            [["project", "is", {"type": "Project", "id": project_id}]],
            fields,
            order=[{"field_name": "code", "direction": "asc"}]
        )

    def get_shots(self, project_id, fields=None):
        """
        Get shots for a project.

        Args:
            project_id: Project ID
            fields: List of fields to return

        Returns:
            List of shot dictionaries
        """
        if fields is None:
            fields = ["id", "code", "sg_status_list", "sg_cut_in", "sg_cut_out"]

        return self.sg.find(
            "Shot",
            [["project", "is", {"type": "Project", "id": project_id}]],
            fields,
            order=[{"field_name": "code", "direction": "asc"}]
        )

    def get_sequences(self, project_id, fields=None):
        """
        Get sequences for a project.

        Args:
            project_id: Project ID
            fields: List of fields to return

        Returns:
            List of sequence dictionaries
        """
        if fields is None:
            fields = ["id", "code", "description"]

        return self.sg.find(
            "Sequence",
            [["project", "is", {"type": "Project", "id": project_id}]],
            fields,
            order=[{"field_name": "code", "direction": "asc"}]
        )

    def get_tasks(self, entity_type, entity_id, fields=None):
        """
        Get tasks for an entity.

        Args:
            entity_type: Type of entity (Shot, Asset, etc.)
            entity_id: Entity ID
            fields: List of fields to return

        Returns:
            List of task dictionaries
        """
        if fields is None:
            fields = ["id", "content", "sg_status_list", "task_assignees"]

        return self.sg.find(
            "Task",
            [[f"entity.{entity_type}.id", "is", entity_id]],
            fields,
            order=[{"field_name": "content", "direction": "asc"}]
        )

    def get_versions(self, entity_type, entity_id, fields=None):
        """
        Get versions for an entity.

        Args:
            entity_type: Type of entity (Shot, Asset, etc.)
            entity_id: Entity ID
            fields: List of fields to return

        Returns:
            List of version dictionaries
        """
        if fields is None:
            fields = ["id", "code", "sg_status_list", "created_at"]

        return self.sg.find(
            "Version",
            [[f"entity.{entity_type}.id", "is", entity_id]],
            fields,
            order=[{"field_name": "created_at", "direction": "desc"}]
        )

    def get_rfqs(self, project_id, fields=None):
        """
        Get RFQs (CustomEntity04) for a project, including the linked VFX Breakdown.
        """
        if fields is None:
            fields = [
                "id",
                "code",
                "sg_status_list",
                "created_at",
                "sg_vfx_breakdown",  # include the link so UI stays in sync on reload
                "sg_vendors",  # vendors assigned to this RFQ
            ]

        return self.sg.find(
            "CustomEntity04",
            [["project", "is", {"type": "Project", "id": int(project_id)}]],
            fields,
            order=[{"field_name": "created_at", "direction": "desc"}],
        )

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------

    def get_field_schema(self, entity_type, field_name):
        """Read schema information for a specific field and cache the result."""

        cache_key = (entity_type, field_name)
        if cache_key not in self._field_schema_cache:
            schema = self.sg.schema_field_read(entity_type, field_name)
            self._field_schema_cache[cache_key] = schema.get(field_name, {})
        return self._field_schema_cache[cache_key]

    def get_entity_schema(self, entity_type):
        """Read and cache the schema for an entity type."""

        if entity_type not in self._entity_schema_cache:
            self._entity_schema_cache[entity_type] = self.sg.schema_read(entity_type)
        return self._entity_schema_cache[entity_type]

    def get_bidding_scenes_for_vfx_breakdown(self, vfx_breakdown_id, fields=None, order=None):
        """
        Return all Bidding Scenes (CustomEntity02) whose sg_parent references the given VFX Breakdown (CustomEntity01).
        """
        if fields is None:
            fields = [
                "id", "code", "sg_beat_id", "sg_vfx_breakdown_scene", "sg_page",
                "sg_script_excerpt", "description", "sg_vfx_type", "sg_complexity",
                "sg_category", "sg_vfx_description", "sg_numer_of_shots", "sg_number_of_shots"
            ]
        if order is None:
            order = [
                {"field_name": "sg_page", "direction": "asc"},
                {"field_name": "code", "direction": "asc"},
            ]

        filters = [
            ["sg_parent", "is", {"type": "CustomEntity01", "id": int(vfx_breakdown_id)}],
        ]
        return self.sg.find("CustomEntity02", filters, fields, order=order)

    def get_vfx_breakdown_entity_type(self):
        """
        Return the SG entity type used for VFX Breakdowns.
        1) Try schema on RFQ field 'sg_vfx_breakdown'
        2) Fallback to explicit override (env var or default)
        """
        # 1) Schema-based
        try:
            field_schema = self.get_field_schema("CustomEntity04", "sg_vfx_breakdown")
            props = field_schema.get("properties", {}) or {}
            valid_types = props.get("valid_types", []) or []
            if valid_types:
                # SG returns {'entity_type': 'CustomEntityXX', 'name': '...'} (older) or {'type': 'CustomEntityXX'} (newer)
                ent = valid_types[0].get("entity_type") or valid_types[0].get("type")
                if ent:
                    return ent
        except Exception as e:
            logging.getLogger(__name__).warning(f"Schema read failed for sg_vfx_breakdown: {e}")

        # 2) Fallback (env or known default)
        return os.getenv("FF_VFX_BREAKDOWN_ENTITY", "CustomEntity01")

    def get_vfx_breakdowns(self, project_id, fields=None, order=None):
        """
        Return all VFX Breakdowns (CustomEntity01) for a project.
        """
        entity = "CustomEntity01"
        if fields is None:
            fields = ["id", "code", "name", "description", "created_at", "updated_at"]
        if order is None:
            order = [{"field_name": "created_at", "direction": "desc"}]

        filters = [["project", "is", {"type": "Project", "id": int(project_id)}]]
        return self.sg.find(entity, filters, fields, order=order)

    def get_bids(self, project_id, fields=None, order=None, rfq_id=None):
        """
        Get Bids (CustomEntity06) for a project, optionally filtered by RFQ.

        Args:
            project_id: Project ID
            fields: List of fields to return
            order: List of order dicts
            rfq_id: RFQ ID to filter by (optional). If provided, only returns
                    bids linked to this RFQ via sg_parent_rfq field.

        Returns:
            List of Bid dictionaries
        """
        if fields is None:
            fields = ["id", "code", "sg_bid_type", "sg_vfx_breakdown", "sg_bid_assets", "sg_price_list", "created_at", "updated_at"]
        if order is None:
            order = [{"field_name": "created_at", "direction": "desc"}]

        filters = [["project", "is", {"type": "Project", "id": int(project_id)}]]

        # Filter by RFQ if provided
        if rfq_id is not None:
            filters.append(["sg_parent_rfq", "is", {"type": "CustomEntity04", "id": int(rfq_id)}])

        return self.sg.find("CustomEntity06", filters, fields, order=order)

    def create_bid(self, project_id, code, bid_type="Early Bid", vfx_breakdown=None, parent_rfq_id=None):
        """
        Create a new Bid (CustomEntity06).

        Args:
            project_id: Project ID
            code: Bid name/code
            bid_type: Bid type (default: "Early Bid")
            vfx_breakdown: VFX Breakdown entity dict (optional)
            parent_rfq_id: Parent RFQ ID to link the bid to (optional)

        Returns:
            Created Bid entity dictionary
        """
        data = {
            "code": code,
            "project": {"type": "Project", "id": int(project_id)},
            "sg_bid_type": bid_type
        }

        if vfx_breakdown:
            data["sg_vfx_breakdown"] = vfx_breakdown

        if parent_rfq_id is not None:
            data["sg_parent_rfq"] = {"type": "CustomEntity04", "id": int(parent_rfq_id)}

        result = self.sg.create("CustomEntity06", data)
        return result

    def update_bid(self, bid_id, data):
        """
        Update a Bid (CustomEntity06).

        Args:
            bid_id: Bid ID
            data: Dictionary of fields to update

        Returns:
            Updated Bid entity dictionary
        """
        result = self.sg.update("CustomEntity06", int(bid_id), data)
        return result

    def delete_bid(self, bid_id):
        """
        Delete a Bid (CustomEntity06).

        Args:
            bid_id: Bid ID

        Returns:
            bool: True if successful
        """
        result = self.sg.delete("CustomEntity06", int(bid_id))
        return result

    def create_rfq(self, project_id, code):
        """
        Create a new RFQ (CustomEntity04).

        Args:
            project_id: Project ID
            code: RFQ name/code

        Returns:
            Created RFQ entity dictionary
        """
        data = {
            "code": code,
            "project": {"type": "Project", "id": int(project_id)}
        }

        result = self.sg.create("CustomEntity04", data)
        return result

    def update_rfq(self, rfq_id, data):
        """
        Update an RFQ (CustomEntity04).

        Args:
            rfq_id: RFQ ID
            data: Dictionary of field values to update

        Returns:
            Updated RFQ entity dictionary
        """
        result = self.sg.update("CustomEntity04", int(rfq_id), data)
        return result

    def delete_rfq(self, rfq_id):
        """
        Delete an RFQ (CustomEntity04).

        Args:
            rfq_id: RFQ ID

        Returns:
            Result of the delete operation
        """
        result = self.sg.delete("CustomEntity04", int(rfq_id))
        return result

    def delete_vfx_breakdown(self, breakdown_id):
        """
        Delete a VFX Breakdown (CustomEntity01).

        Args:
            breakdown_id: VFX Breakdown ID

        Returns:
            Result of the delete operation
        """
        result = self.sg.delete("CustomEntity01", int(breakdown_id))
        return result

    def delete_bidding_scene(self, scene_id):
        """
        Delete a Bidding Scene (CustomEntity02).

        Args:
            scene_id: Bidding Scene ID

        Returns:
            Result of the delete operation
        """
        result = self.sg.delete("CustomEntity02", int(scene_id))
        return result

    def delete_bid_assets(self, bid_assets_id):
        """
        Delete Bid Assets (CustomEntity08).

        Args:
            bid_assets_id: Bid Assets ID

        Returns:
            Result of the delete operation
        """
        result = self.sg.delete("CustomEntity08", int(bid_assets_id))
        return result

    def delete_asset(self, asset_id):
        """
        Delete an Asset (CustomEntity07).

        Args:
            asset_id: Asset ID

        Returns:
            Result of the delete operation
        """
        result = self.sg.delete("CustomEntity07", int(asset_id))
        return result

    def delete_rfq_and_related(self, rfq_id):
        """
        Delete an RFQ and all related elements (Bids, VFX Breakdowns, Bidding Scenes, Bid Assets).

        Args:
            rfq_id: RFQ ID

        Returns:
            dict: Summary of deleted items
        """
        log = logging.getLogger(__name__)
        deleted_summary = {
            "rfq": 0,
            "bids": 0,
            "vfx_breakdowns": 0,
            "bidding_scenes": 0,
            "bid_assets": 0,
            "assets": 0
        }

        try:
            # First, get the RFQ with all its linked data
            rfq = self.sg.find_one(
                "CustomEntity04",
                [["id", "is", int(rfq_id)]],
                ["id", "code", "sg_early_bid", "sg_turnover_bid", "sg_vfx_breakdown"]
            )

            if not rfq:
                log.warning(f"RFQ {rfq_id} not found")
                return deleted_summary

            # Collect all bids linked to this RFQ
            bids_to_delete = []
            if rfq.get("sg_early_bid"):
                bid = rfq["sg_early_bid"]
                if isinstance(bid, dict) and bid.get("id"):
                    bids_to_delete.append(bid["id"])
                elif isinstance(bid, list):
                    bids_to_delete.extend([b["id"] for b in bid if isinstance(b, dict) and b.get("id")])

            if rfq.get("sg_turnover_bid"):
                bid = rfq["sg_turnover_bid"]
                if isinstance(bid, dict) and bid.get("id"):
                    bids_to_delete.append(bid["id"])
                elif isinstance(bid, list):
                    bids_to_delete.extend([b["id"] for b in bid if isinstance(b, dict) and b.get("id")])

            # Collect all VFX breakdowns linked to this RFQ
            vfx_breakdowns_to_delete = []
            if rfq.get("sg_vfx_breakdown"):
                breakdown = rfq["sg_vfx_breakdown"]
                if isinstance(breakdown, dict) and breakdown.get("id"):
                    vfx_breakdowns_to_delete.append(breakdown["id"])
                elif isinstance(breakdown, list):
                    vfx_breakdowns_to_delete.extend([b["id"] for b in breakdown if isinstance(b, dict) and b.get("id")])

            # For each bid, get its linked VFX breakdown and bid assets
            for bid_id in bids_to_delete:
                try:
                    bid_data = self.sg.find_one(
                        "CustomEntity06",
                        [["id", "is", int(bid_id)]],
                        ["id", "sg_vfx_breakdown", "sg_bid_assets"]
                    )

                    if bid_data:
                        # Add VFX breakdown from bid (if not already in list)
                        if bid_data.get("sg_vfx_breakdown"):
                            breakdown = bid_data["sg_vfx_breakdown"]
                            if isinstance(breakdown, dict) and breakdown.get("id"):
                                if breakdown["id"] not in vfx_breakdowns_to_delete:
                                    vfx_breakdowns_to_delete.append(breakdown["id"])
                            elif isinstance(breakdown, list):
                                for b in breakdown:
                                    if isinstance(b, dict) and b.get("id") and b["id"] not in vfx_breakdowns_to_delete:
                                        vfx_breakdowns_to_delete.append(b["id"])

                        # Delete bid assets linked to this bid
                        if bid_data.get("sg_bid_assets"):
                            bid_assets = bid_data["sg_bid_assets"]
                            if isinstance(bid_assets, dict) and bid_assets.get("id"):
                                try:
                                    self.delete_bid_assets(bid_assets["id"])
                                    deleted_summary["bid_assets"] += 1
                                    log.info(f"Deleted Bid Assets {bid_assets['id']}")
                                except Exception as e:
                                    log.error(f"Failed to delete Bid Assets {bid_assets['id']}: {e}")
                            elif isinstance(bid_assets, list):
                                for ba in bid_assets:
                                    if isinstance(ba, dict) and ba.get("id"):
                                        try:
                                            self.delete_bid_assets(ba["id"])
                                            deleted_summary["bid_assets"] += 1
                                            log.info(f"Deleted Bid Assets {ba['id']}")
                                        except Exception as e:
                                            log.error(f"Failed to delete Bid Assets {ba['id']}: {e}")

                    # Delete the bid
                    self.delete_bid(bid_id)
                    deleted_summary["bids"] += 1
                    log.info(f"Deleted Bid {bid_id}")

                except Exception as e:
                    log.error(f"Failed to delete Bid {bid_id}: {e}")

            # For each VFX breakdown, delete all linked bidding scenes
            for breakdown_id in vfx_breakdowns_to_delete:
                try:
                    # Get all bidding scenes linked to this breakdown
                    bidding_scenes = self.get_bidding_scenes_for_vfx_breakdown(
                        breakdown_id,
                        fields=["id"]
                    )

                    # Delete all bidding scenes
                    for scene in bidding_scenes:
                        try:
                            self.delete_bidding_scene(scene["id"])
                            deleted_summary["bidding_scenes"] += 1
                            log.info(f"Deleted Bidding Scene {scene['id']}")
                        except Exception as e:
                            log.error(f"Failed to delete Bidding Scene {scene['id']}: {e}")

                    # Delete the VFX breakdown
                    self.delete_vfx_breakdown(breakdown_id)
                    deleted_summary["vfx_breakdowns"] += 1
                    log.info(f"Deleted VFX Breakdown {breakdown_id}")

                except Exception as e:
                    log.error(f"Failed to delete VFX Breakdown {breakdown_id}: {e}")

            # Finally, delete the RFQ
            self.delete_rfq(rfq_id)
            deleted_summary["rfq"] = 1
            log.info(f"Deleted RFQ {rfq_id}")

        except Exception as e:
            log.error(f"Error in delete_rfq_and_related: {e}", exc_info=True)
            raise

        return deleted_summary

    def update_rfq_bid(self, rfq_id, bid):
        """
        Update the Bid linked to an RFQ.

        Args:
            rfq_id: RFQ ID
            bid: Bid entity dict (e.g., {"type": "CustomEntity06", "id": 123})

        Returns:
            Updated RFQ entity dictionary
        """
        # Normalize link
        if isinstance(bid, int):
            bid_link = {"type": "CustomEntity06", "id": int(bid)}
        elif isinstance(bid, dict) and "id" in bid:
            bid_link = {"type": bid.get("type", "CustomEntity06"), "id": int(bid["id"])}
        else:
            raise ValueError("Invalid bid argument; expected id or SG link dict.")

        data = {"sg_bid": bid_link}
        result = self.sg.update("CustomEntity04", int(rfq_id), data)
        return result

    def update_bid_vfx_breakdown(self, bid_id, breakdown):
        """
        Set sg_vfx_breakdown on Bid (CustomEntity06) to the given breakdown link.

        Args:
            bid_id: Bid ID
            breakdown: VFX Breakdown entity dict or ID

        Returns:
            Updated Bid entity dictionary
        """
        # Normalize link
        if isinstance(breakdown, int):
            br_link = {"type": "CustomEntity01", "id": int(breakdown)}
        elif isinstance(breakdown, dict) and "id" in breakdown:
            br_link = {"type": breakdown.get("type", "CustomEntity01"), "id": int(breakdown["id"])}
        else:
            raise ValueError("Invalid breakdown argument; expected id or SG link dict.")

        data = {"sg_vfx_breakdown": br_link}
        result = self.sg.update("CustomEntity06", int(bid_id), data)
        return result

    def update_rfq_vfx_breakdown(self, rfq_id, breakdown):
        """
        Set sg_vfx_breakdown on RFQ (CustomEntity04) to the given breakdown link.
        Robust to single-entity vs multi-entity:
          - try as multi (list) first
          - if API says 'expected Hash', retry as single (dict)
        """
        # Normalize link
        if isinstance(breakdown, int):
            br_link = {"type": "CustomEntity01", "id": int(breakdown)}
        elif isinstance(breakdown, dict) and "id" in breakdown:
            br_link = {"type": breakdown.get("type", "CustomEntity01"), "id": int(breakdown["id"])}
        else:
            raise ValueError("Invalid breakdown argument; expected id or SG link dict.")

        # Import Fault safely (works even if shotgun_api3 wasn't imported globally)
        try:
            from shotgun_api3 import Fault as SGFault
        except Exception:  # pragma: no cover
            SGFault = Exception

        log = logging.getLogger(__name__)
        payload_multi = {"sg_vfx_breakdown": [br_link]}
        payload_single = {"sg_vfx_breakdown": br_link}

        log.info(f"Updating RFQ {rfq_id} sg_vfx_breakdown -> TRY multi {payload_multi}")
        try:
            return self.sg.update("CustomEntity04", int(rfq_id), payload_multi)
        except SGFault as e:
            msg = str(e)
            log.warning(f"Multi update failed: {msg}")
            if "expected Hash" in msg:
                log.info(f"Retrying RFQ {rfq_id} sg_vfx_breakdown -> single {payload_single}")
                return self.sg.update("CustomEntity04", int(rfq_id), payload_single)
            if "doesn't exist" in msg:
                # Field sg_vfx_breakdown is not configured on RFQ entity - skip silently
                log.warning(
                    f"Field sg_vfx_breakdown does not exist on RFQ (CustomEntity04). "
                    "Skipping VFX Breakdown link on RFQ. The VFX Breakdown was still created "
                    "and is linked to the Bid if one was created."
                )
                return None
            raise

    def create_vfx_breakdown(self, project_id, code):
        """
        Create a new VFX Breakdown (CustomEntity01).

        Args:
            project_id: Project ID
            code: VFX Breakdown name/code

        Returns:
            Created VFX Breakdown entity dictionary
        """
        data = {
            "code": code,
            "project": {"type": "Project", "id": int(project_id)}
        }

        result = self.sg.create("CustomEntity01", data)
        return result

    def create_bidding_scene(self, project_id, vfx_breakdown_id, code="New Bidding Scene"):
        """
        Create a new Bidding Scene (CustomEntity02) linked to a VFX Breakdown.

        Args:
            project_id: Project ID
            vfx_breakdown_id: Parent VFX Breakdown ID
            code: Bidding Scene name/code (default: "New Bidding Scene")

        Returns:
            Created Bidding Scene entity dictionary
        """
        data = {
            "code": code,
            "project": {"type": "Project", "id": int(project_id)},
            "sg_parent": {"type": "CustomEntity01", "id": int(vfx_breakdown_id)}
        }

        result = self.sg.create("CustomEntity02", data)
        return result

    def create_bid_assets(self, project_id, code):
        """
        Create a new Bid Assets (CustomEntity08).

        Args:
            project_id: Project ID
            code: Bid Assets name/code

        Returns:
            Created Bid Assets entity dictionary
        """
        data = {
            "code": code,
            "project": {"type": "Project", "id": int(project_id)}
        }

        result = self.sg.create("CustomEntity08", data)
        return result

    def create_asset_item(self, project_id, bid_assets_id, code="New Asset"):
        """
        Create a new Asset Item (CustomEntity07) linked to Bid Assets.

        Args:
            project_id: Project ID
            bid_assets_id: Parent Bid Assets ID
            code: Asset item name/code (default: "New Asset")

        Returns:
            Created Asset Item entity dictionary
        """
        data = {
            "code": code,
            "project": {"type": "Project", "id": int(project_id)},
            "sg_bid_assets": {"type": "CustomEntity08", "id": int(bid_assets_id)}
        }

        result = self.sg.create("CustomEntity07", data)
        return result

    def update_bid_bid_assets(self, bid_id, bid_assets):
        """
        Set sg_bid_assets on Bid (CustomEntity06) to the given Bid Assets link.

        Args:
            bid_id: Bid ID
            bid_assets: Bid Assets entity dict or ID

        Returns:
            Updated Bid entity dictionary
        """
        # Normalize link
        if isinstance(bid_assets, int):
            ba_link = {"type": "CustomEntity08", "id": int(bid_assets)}
        elif isinstance(bid_assets, dict) and "id" in bid_assets:
            ba_link = {"type": bid_assets.get("type", "CustomEntity08"), "id": int(bid_assets["id"])}
        else:
            raise ValueError("Invalid bid_assets argument; expected id or SG link dict.")

        data = {"sg_bid_assets": ba_link}
        result = self.sg.update("CustomEntity06", int(bid_id), data)
        return result

    def update_rfq_early_bid(self, rfq_id, bid):
        """
        Set sg_bid on RFQ (CustomEntity04) to the given Bid link.
        This is an alias for update_rfq_bid for clarity when setting the current bid.

        Args:
            rfq_id: RFQ ID
            bid: Bid entity dict or ID

        Returns:
            Updated RFQ entity dictionary
        """
        return self.update_rfq_bid(rfq_id, bid)

    def get_entity_fields_with_labels(self, entity_type):
        """Return a tuple of (field_names, display_labels) for an entity type."""

        schema = self.get_entity_schema(entity_type)
        field_names = []
        display_labels = {}

        for field, metadata in schema.items():
            field_names.append(field)
            display_labels[field] = metadata.get("name") or metadata.get("properties", {}).get("display_name", field)

        return field_names, display_labels

    def get_entity_by_id(self, entity_type, entity_id, fields=None):
        """Retrieve a single entity by id."""

        filters = [["id", "is", entity_id]]
        return self.sg.find_one(entity_type, filters, fields)

    def get_rfq_versions(self, rfq_id, fields=None):
        """
        Get all versions linked to an RFQ through the sg_versions field.

        Args:
            rfq_id: RFQ (CustomEntity04) ID
            fields: List of fields to return. Defaults to common version fields

        Returns:
            List of version dictionaries linked to the RFQ
        """
        # First, get the RFQ with its sg_versions field
        rfq = self.sg.find_one(
            "CustomEntity04",
            [["id", "is", rfq_id]],
            ["sg_versions"]
        )

        if not rfq or not rfq.get("sg_versions"):
            return []

        # Extract version IDs from the sg_versions field
        version_ids = [v["id"] for v in rfq["sg_versions"]]

        if not version_ids:
            return []

        # Now query those specific versions with desired fields
        if fields is None:
            fields = [
                "id",
                "code",
                "entity",  # The entity this version is linked to (Shot, Asset, etc.)
                "sg_status_list",
                "created_at",
                "updated_at",
                "user",  # Who created it
                "description",
                "sg_task",  # Associated task
                "sg_path_to_movie",  # Movie path if available
                "sg_path_to_frames",  # Frame path if available
                "sg_uploaded_movie",  # Uploaded movie file
                "sg_path_to_geometry",  # Geometry path if available
            ]

        return self.sg.find(
            "Version",
            [["id", "in", version_ids]],
            fields,
            order=[
                {"field_name": "entity", "direction": "asc"},  # Group by entity
                {"field_name": "created_at", "direction": "desc"}  # Newest first within entity
            ]
        )

    def get_version_published_files(self, version_id, fields=None):
        """
        Get all published files linked to a version.

        Args:
            version_id: Version ID
            fields: List of fields to return

        Returns:
            List of published file dictionaries
        """
        if fields is None:
            fields = [
                "id",
                "code",
                "path",  # File path
                "path_cache",  # Cached path
                "published_file_type",  # Type (e.g., Maya Scene, Alembic Cache, etc.)
                "version_number",
                "created_at",
            ]

        return self.sg.find(
            "PublishedFile",
            [["version", "is", {"type": "Version", "id": version_id}]],
            fields,
            order=[{"field_name": "created_at", "direction": "desc"}]
        )

    def get_version_media_url(self, version_id):
        """
        Get the streaming media URL for a version (for playback in browser/RV).

        Args:
            version_id: Version ID

        Returns:
            Dictionary with media URLs or None if no media available
        """
        version = self.sg.find_one(
            "Version",
            [["id", "is", version_id]],
            ["sg_uploaded_movie", "sg_uploaded_movie_webm", "sg_uploaded_movie_mp4"]
        )

        if not version:
            return None

        return {
            "uploaded_movie": version.get("sg_uploaded_movie"),
            "webm": version.get("sg_uploaded_movie_webm"),
            "mp4": version.get("sg_uploaded_movie_mp4"),
        }

    def get_version_uploaded_movie(self, version_id):
        """
        Get the uploaded movie information for a version.

        Args:
            version_id: Version ID

        Returns:
            Dictionary with uploaded movie info including URL and local path, or None
        """
        version = self.sg.find_one(
            "Version",
            [["id", "is", version_id]],
            ["sg_uploaded_movie", "sg_uploaded_movie_webm", "sg_uploaded_movie_mp4",
             "sg_uploaded_movie_frame_rate", "code", "sg_version_type"]
        )

        #logging.info("Version data: %s", version)

        if not version:
            return None

        uploaded_movie = version.get("sg_uploaded_movie")

        if not uploaded_movie:
            return None

        return {
            "code": version.get("code"),
            "name": uploaded_movie.get("name"),
            "url": uploaded_movie.get("url"),
            "local_path": uploaded_movie.get("local_path"),
            "link_type": uploaded_movie.get("link_type"),
            "content_type": uploaded_movie.get("content_type"),
            "webm": version.get("sg_uploaded_movie_webm"),
            "mp4": version.get("sg_uploaded_movie_mp4"),
            "frame_rate": version.get("sg_uploaded_movie_frame_rate"),
            "version_type": version.get("sg_version_type"),
        }

    def download_version_attachment(self, version_id, field_name, download_path):
        """
        Download an attachment field from a version (e.g., uploaded movie).

        Args:
            version_id: Version ID
            field_name: Field name (e.g., "sg_uploaded_movie")
            download_path: Directory path or full file path to save the file.
                          If a directory is provided, the original filename will be used.

        Returns:
            Path to downloaded file or None if failed
        """
        import os

        try:
            # Get the version with the attachment field
            version = self.sg.find_one(
                "Version",
                [["id", "is", version_id]],
                [field_name]
            )

            if not version or not version.get(field_name):
                print(f"No attachment found in field {field_name}")
                return None

            attachment = version[field_name]

            # If download_path is a directory, append the filename
            if os.path.isdir(download_path):
                filename = attachment.get('name', f'version_{version_id}_{field_name}')
                download_path = os.path.join(download_path, filename)

            # Download using the attachment dictionary
            downloaded_path = self.sg.download_attachment(
                attachment,
                download_path
            )
            return downloaded_path
        except Exception as e:
            print(f"Failed to download attachment: {e}")
            import traceback
            traceback.print_exc()
            return None

    def download_version_movie(self, version_id, download_path):
        """
        Download the uploaded movie from a version.

        Args:
            version_id: Version ID
            download_path: Directory path or full file path to save the movie.
                          If a directory is provided, the original filename will be used.

        Returns:
            Path to downloaded file or None if failed
        """
        return self.download_version_attachment(version_id, "sg_uploaded_movie", download_path)

    def download_version_movie_mp4(self, version_id, download_path):
        """
        Download the MP4 transcoded version of the uploaded movie.

        Args:
            version_id: Version ID
            download_path: Directory path or full file path to save the movie.
                          If a directory is provided, the original filename will be used.

        Returns:
            Path to downloaded file or None if failed
        """
        return self.download_version_attachment(version_id, "sg_uploaded_movie_mp4", download_path)

    def download_thumbnail(self, entity_type, entity_id, download_path=None):
        """
        Download a thumbnail image for an entity.

        Args:
            entity_type: Type of entity (e.g., "Version", "Asset")
            entity_id: ID of the entity
            download_path: Optional path to save the thumbnail. If None, returns image data.

        Returns:
            Path to downloaded file if download_path provided, otherwise bytes of image data
        """
        try:
            # Get the thumbnail URL from the entity
            entity = self.sg.find_one(
                entity_type,
                [["id", "is", entity_id]],
                ["image"]
            )

            if not entity or not entity.get("image"):
                return None

            # Download the thumbnail
            thumbnail_url = entity["image"]

            if download_path:
                # Download to file
                downloaded_path = self.sg.download_attachment(thumbnail_url, download_path)
                return downloaded_path
            else:
                # Return image data as bytes
                import requests
                response = requests.get(thumbnail_url)
                if response.status_code == 200:
                    return response.content
                return None

        except Exception as e:
            logger.error(f"Failed to download thumbnail: {e}")
            return None

    # ------------------------------------------------------------------
    # Package Management (CustomEntity12)
    # ------------------------------------------------------------------

    def create_package(self, package_name, project_id, description=None):
        """
        Create a new Package (CustomEntity12) entity in ShotGrid.

        Note: Package does not directly link to RFQ. The relationship is one-way
        via the RFQ's sg_packages field.

        Args:
            package_name: Name/code of the package
            project_id: ID of the project
            description: Optional description

        Returns:
            Created package entity dictionary
        """
        package_data = {
            "code": package_name,
            "project": {"type": "Project", "id": int(project_id)},
        }

        if description:
            package_data["description"] = description

        package = self.sg.create("CustomEntity12", package_data)

        return package

    def get_packages_for_rfq(self, rfq_id, fields=None):
        """
        Get all Packages (CustomEntity12) linked to an RFQ via its sg_packages field.

        Args:
            rfq_id: ID of the RFQ
            fields: List of fields to return

        Returns:
            List of package dictionaries
        """
        if fields is None:
            fields = ["id", "code", "description", "created_at"]

        # Get the RFQ with its sg_packages field
        rfq = self.sg.find_one(
            "CustomEntity04",
            [["id", "is", int(rfq_id)]],
            ["sg_packages"]
        )

        if not rfq or not rfq.get("sg_packages"):
            return []

        # Extract package IDs
        package_ids = [pkg["id"] for pkg in rfq["sg_packages"]]

        if not package_ids:
            return []

        # Query for those packages
        return self.sg.find(
            "CustomEntity12",
            [["id", "in", package_ids]],
            fields,
            order=[{"field_name": "created_at", "direction": "desc"}]
        )

    def link_package_to_rfq(self, package_id, rfq_id):
        """
        Link a Package to an RFQ's sg_packages field (multi-entity field).

        Args:
            package_id: ID of the package to link
            rfq_id: ID of the RFQ

        Returns:
            Updated RFQ entity
        """
        # Get current packages linked to the RFQ
        rfq = self.sg.find_one(
            "CustomEntity04",
            [["id", "is", int(rfq_id)]],
            ["sg_packages"]
        )

        if not rfq:
            logger.error(f"RFQ {rfq_id} not found")
            return None

        # Get existing packages (or empty list if None)
        existing_packages = rfq.get("sg_packages") or []

        # Check if package is already linked
        package_link = {"type": "CustomEntity12", "id": int(package_id)}
        if any(p.get("id") == int(package_id) for p in existing_packages):
            return rfq

        # Add the new package to the list
        updated_packages = existing_packages + [package_link]

        # Update the RFQ
        result = self.sg.update(
            "CustomEntity04",
            int(rfq_id),
            {"sg_packages": updated_packages}
        )

        return result

    def update_package(self, package_id, package_name=None, description=None, status=None, manifest=None):
        """
        Update a Package (CustomEntity12) entity in ShotGrid.

        Args:
            package_id: ID of the package to update
            package_name: New name/code for the package (optional)
            description: New description (optional)
            status: New status for sg_status_list field (optional)
            manifest: Manifest data for sg_manifest field (optional, uploaded as JSON file)

        Returns:
            Updated package entity dictionary
        """
        import json
        import tempfile
        import os
        import logging
        logger = logging.getLogger("FFPackageManager")

        update_data = {}

        if package_name:
            update_data["code"] = package_name
        if description is not None:
            update_data["description"] = description
        if status is not None:
            update_data["sg_status_list"] = status

        # First update non-manifest fields
        package = None
        if update_data:
            package = self.sg.update("CustomEntity12", int(package_id), update_data)

        # Upload manifest as a file attachment
        if manifest is not None:
            temp_file = None
            try:
                # Write manifest to a temporary JSON file
                manifest_str = json.dumps(manifest, indent=2) if isinstance(manifest, dict) else str(manifest)
                temp_file = tempfile.NamedTemporaryFile(
                    mode='w',
                    suffix='.json',
                    prefix='manifest_',
                    delete=False
                )
                temp_file.write(manifest_str)
                temp_file.close()

                # Upload the file to sg_manifest field
                self.sg.upload(
                    "CustomEntity12",
                    int(package_id),
                    temp_file.name,
                    field_name="sg_manifest",
                    display_name="manifest.json"
                )
                logger.info(f"Uploaded manifest to package {package_id}")
            except Exception as e:
                logger.warning(f"Could not upload manifest to sg_manifest field: {e}")
            finally:
                # Clean up temp file
                if temp_file and os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)

        return package

    def get_package_by_name(self, package_name, project_id=None, fields=None):
        """
        Find a Package (CustomEntity12) by its name/code.

        Args:
            package_name: Name/code of the package to find
            project_id: Optional project ID to filter by
            fields: List of fields to return

        Returns:
            Package entity dictionary or None if not found
        """
        if fields is None:
            fields = ["id", "code", "description", "sg_status_list", "sg_manifest", "project"]

        filters = [["code", "is", package_name]]
        if project_id:
            filters.append(["project", "is", {"type": "Project", "id": int(project_id)}])

        return self.sg.find_one("CustomEntity12", filters, fields)

    def delete_package(self, package_id):
        """
        Delete a Package (CustomEntity12) entity from ShotGrid.

        Args:
            package_id: ID of the package to delete

        Returns:
            True if successful, False otherwise
        """
        result = self.sg.delete("CustomEntity12", int(package_id))

        return result

    def unlink_package_from_rfq(self, package_id, rfq_id):
        """
        Unlink a Package from an RFQ's sg_packages field.

        Args:
            package_id: ID of the package to unlink
            rfq_id: ID of the RFQ

        Returns:
            Updated RFQ entity or None if failed
        """
        # Get current packages linked to the RFQ
        rfq = self.sg.find_one(
            "CustomEntity04",
            [["id", "is", int(rfq_id)]],
            ["sg_packages"]
        )

        if not rfq:
            logger.error(f"RFQ {rfq_id} not found")
            return None

        # Get existing packages
        existing_packages = rfq.get("sg_packages") or []

        # Remove the package from the list
        updated_packages = [
            pkg for pkg in existing_packages
            if pkg.get("id") != int(package_id)
        ]

        # Only update if something changed
        if len(updated_packages) == len(existing_packages):
            return rfq

        # Update the RFQ
        result = self.sg.update(
            "CustomEntity04",
            int(rfq_id),
            {"sg_packages": updated_packages}
        )

        return result

    # ------------------------------------------------------------------
    # PackageItem Management (CustomEntity13)
    # ------------------------------------------------------------------

    def create_package_item(self, package_id, project_id, version_id=None):
        """
        Create a new PackageItem (CustomEntity13) entity in ShotGrid.

        Args:
            package_id: ID of the Package to link to
            project_id: ID of the project
            version_id: Optional ID of the version to link

        Returns:
            Created PackageItem entity dictionary
        """
        package_item_data = {
            "project": {"type": "Project", "id": int(project_id)},
        }

        # If version_id is provided, link it to the sg_versions field
        if version_id:
            package_item_data["sg_versions"] = [{"type": "Version", "id": int(version_id)}]

        package_item = self.sg.create("CustomEntity13", package_item_data)

        # Link the PackageItem to the Package's sg_packageitems field
        self._link_package_item_to_package(package_item["id"], package_id)

        return package_item

    def _link_package_item_to_package(self, package_item_id, package_id):
        """
        Link a PackageItem to a Package's sg_packageitems field (multi-entity field).

        Args:
            package_item_id: ID of the PackageItem to link
            package_id: ID of the Package

        Returns:
            Updated Package entity or None if failed
        """
        # Get current PackageItems linked to the Package
        package = self.sg.find_one(
            "CustomEntity12",
            [["id", "is", int(package_id)]],
            ["sg_packageitems"]
        )

        if not package:
            logger.error(f"Package {package_id} not found")
            return None

        # Get existing PackageItems (or empty list if None)
        existing_items = package.get("sg_packageitems") or []

        # Check if PackageItem is already linked
        if any(item.get("id") == int(package_item_id) for item in existing_items):
            return package

        # Add the new PackageItem to the list
        package_item_link = {"type": "CustomEntity13", "id": int(package_item_id)}
        updated_items = existing_items + [package_item_link]

        # Update the Package
        result = self.sg.update(
            "CustomEntity12",
            int(package_id),
            {"sg_packageitems": updated_items}
        )

        return result

    def get_package_items(self, package_id, fields=None):
        """
        Get all PackageItems linked to a Package via its sg_packageitems field.

        Args:
            package_id: ID of the package
            fields: List of fields to return for PackageItems

        Returns:
            List of PackageItem dictionaries
        """
        if fields is None:
            fields = ["id", "sg_versions"]

        # Get the Package with its sg_packageitems field
        package = self.sg.find_one(
            "CustomEntity12",
            [["id", "is", int(package_id)]],
            ["sg_packageitems"]
        )

        if not package or not package.get("sg_packageitems"):
            return []

        # Extract PackageItem IDs
        package_item_ids = [item["id"] for item in package["sg_packageitems"]]

        if not package_item_ids:
            return []

        # Query for those PackageItems
        return self.sg.find(
            "CustomEntity13",
            [["id", "in", package_item_ids]],
            fields
        )

    def find_package_item_for_version(self, package_id, version_id):
        """
        Find the PackageItem that contains a specific version.

        Args:
            package_id: ID of the Package
            version_id: ID of the Version to find

        Returns:
            PackageItem entity dictionary or None if not found
        """
        package_items = self.get_package_items(package_id, fields=["id", "sg_versions"])

        for item in package_items:
            versions = item.get("sg_versions") or []
            for version in versions:
                if version.get("id") == int(version_id):
                    return item

        return None

    def delete_package_item(self, package_item_id):
        """
        Delete a PackageItem (CustomEntity13) entity from ShotGrid.

        Args:
            package_item_id: ID of the PackageItem to delete

        Returns:
            True if successful, False otherwise
        """
        result = self.sg.delete("CustomEntity13", int(package_item_id))
        return result

    def update_package_item_folders(self, package_item_id, folder_name):
        """
        Update the sg_package_folders field on a PackageItem.

        If the folder is not already in the list, it will be appended.
        Multiple folders are separated by ";".

        Args:
            package_item_id: ID of the PackageItem to update
            folder_name: Folder name to add (e.g., "Asset_Name" or "Scene_001")

        Returns:
            Updated PackageItem entity or None if failed
        """
        # Get the current sg_package_folders value
        package_item = self.sg.find_one(
            "CustomEntity13",
            [["id", "is", int(package_item_id)]],
            ["sg_package_folders"]
        )

        if not package_item:
            logger.error(f"PackageItem {package_item_id} not found")
            return None

        # Get existing folders or empty string
        existing_folders = package_item.get("sg_package_folders") or ""

        # Parse existing folders into a list
        folder_list = [f.strip() for f in existing_folders.split(";") if f.strip()]

        # Add the new folder if not already present
        if folder_name not in folder_list:
            folder_list.append(folder_name)
            new_folders = ";".join(folder_list)

            # Update the PackageItem
            result = self.sg.update(
                "CustomEntity13",
                int(package_item_id),
                {"sg_package_folders": new_folders}
            )
            return result
        else:
            return package_item

    def remove_folder_from_package_item(self, package_item_id, folder_name):
        """
        Remove a folder from the sg_package_folders field on a PackageItem.

        Args:
            package_item_id: ID of the PackageItem to update
            folder_name: Folder name to remove

        Returns:
            Updated PackageItem entity or None if failed
        """
        # Get the current sg_package_folders value
        package_item = self.sg.find_one(
            "CustomEntity13",
            [["id", "is", int(package_item_id)]],
            ["sg_package_folders"]
        )

        if not package_item:
            logger.error(f"PackageItem {package_item_id} not found")
            return None

        # Get existing folders
        existing_folders = package_item.get("sg_package_folders") or ""
        folder_list = [f.strip() for f in existing_folders.split(";") if f.strip()]

        # Remove the folder if present
        if folder_name in folder_list:
            folder_list.remove(folder_name)
            new_folders = ";".join(folder_list)

            # Update the PackageItem
            result = self.sg.update(
                "CustomEntity13",
                int(package_item_id),
                {"sg_package_folders": new_folders}
            )
            return result

        return package_item

    def get_package_versions_with_folders(self, package_id, fields=None):
        """
        Get all versions linked to a Package via its PackageItems,
        including the folder information from each PackageItem.

        Args:
            package_id: ID of the package
            fields: List of fields to return for versions

        Returns:
            List of version dictionaries, each with an additional
            '_package_folders' key containing the folder names
        """
        if fields is None:
            fields = [
                "id", "code", "entity", "sg_status_list", "created_at", "updated_at",
                "user", "description", "sg_task", "sg_path_to_movie", "sg_path_to_frames",
                "sg_uploaded_movie", "sg_path_to_geometry", "sg_version_type"
            ]

        # Get all PackageItems for this Package with folder info
        package_items = self.get_package_items(
            package_id,
            fields=["id", "sg_versions", "sg_package_folders"]
        )

        if not package_items:
            return []

        # Build a mapping of version_id -> folder names
        version_to_folders = {}
        version_ids = []

        for item in package_items:
            folders = item.get("sg_package_folders") or ""
            versions = item.get("sg_versions") or []

            for version in versions:
                version_id = version.get("id")
                if version_id:
                    if version_id not in version_ids:
                        version_ids.append(version_id)
                    # Store folders for this version
                    version_to_folders[version_id] = folders

        if not version_ids:
            return []

        # Query for those versions
        versions = self.sg.find(
            "Version",
            [["id", "in", version_ids]],
            fields,
            order=[
                {"field_name": "entity", "direction": "asc"},
                {"field_name": "created_at", "direction": "desc"}
            ]
        )

        # Add folder info to each version
        for version in versions:
            version_id = version.get("id")
            version["_package_folders"] = version_to_folders.get(version_id, "")

        return versions

    def link_version_to_package_with_folder(self, version_id, package_id, folder_name):
        """
        Link a Version to a Package and set its folder assignment.

        Args:
            version_id: ID of the version to link
            package_id: ID of the package
            folder_name: Name of the folder the version was dropped to

        Returns:
            PackageItem entity with the version linked and folder set
        """
        logger.warning(f"DEBUG link_version_to_package_with_folder: version={version_id}, package={package_id}, folder={folder_name}")

        # First, link the version (creates PackageItem if needed)
        package_item = self.link_version_to_package(version_id, package_id)
        logger.warning(f"DEBUG link_version_to_package returned: {package_item}")

        if package_item:
            # Update the folder assignment
            logger.warning(f"DEBUG Updating folder assignment for PackageItem {package_item['id']} to {folder_name}")
            self.update_package_item_folders(package_item["id"], folder_name)
            logger.warning(f"DEBUG Folder assignment updated successfully")
        else:
            logger.warning(f"DEBUG No package_item returned, cannot set folder assignment")

        return package_item

    def remove_folder_reference_from_package(self, version_id, package_id, folder_path):
        """
        Remove a folder reference from a version's PackageItem.

        If the sg_package_folders field becomes empty after removal,
        the PackageItem will be deleted entirely.

        Args:
            version_id: ID of the version
            package_id: ID of the package
            folder_path: Folder path to remove (e.g., '/assets/CRE/Concept Art')

        Returns:
            True if successful, False otherwise
        """
        # Find the PackageItem for this version
        package_item = self.find_package_item_for_version(package_id, version_id)

        if not package_item:
            logger.warning(f"No PackageItem found for version {version_id} in package {package_id}")
            return False

        package_item_id = package_item["id"]

        # Get current folders
        package_item_full = self.sg.find_one(
            "CustomEntity13",
            [["id", "is", int(package_item_id)]],
            ["sg_package_folders"]
        )

        if not package_item_full:
            logger.error(f"PackageItem {package_item_id} not found")
            return False

        existing_folders = package_item_full.get("sg_package_folders") or ""
        folder_list = [f.strip() for f in existing_folders.split(";") if f.strip()]

        # Remove the folder path if present
        if folder_path in folder_list:
            folder_list.remove(folder_path)
            new_folders = ";".join(folder_list)

            if new_folders:
                # Still has folders, just update
                self.sg.update(
                    "CustomEntity13",
                    int(package_item_id),
                    {"sg_package_folders": new_folders}
                )
                return True
            else:
                # No more folders, delete the PackageItem
                self.delete_package_item(package_item_id)
                return True
        else:
            return False

    # ------------------------------------------------------------------
    # Version Management
    # ------------------------------------------------------------------

    def get_package_versions(self, package_id, fields=None):
        """
        Get all versions linked to a Package via its PackageItems.

        The versions are accessed through the Package's sg_packageitems field,
        and each PackageItem has a sg_versions field linking to Versions.

        Args:
            package_id: ID of the package
            fields: List of fields to return for versions

        Returns:
            List of version dictionaries
        """
        if fields is None:
            fields = [
                "id", "code", "entity", "sg_status_list", "created_at", "updated_at",
                "user", "description", "sg_task", "sg_path_to_movie", "sg_path_to_frames",
                "sg_uploaded_movie", "sg_path_to_geometry", "sg_version_type"
            ]

        # Get all PackageItems for this Package
        package_items = self.get_package_items(package_id, fields=["id", "sg_versions"])

        if not package_items:
            return []

        # Collect all version IDs from all PackageItems
        version_ids = []
        for item in package_items:
            versions = item.get("sg_versions") or []
            for version in versions:
                if version.get("id") and version["id"] not in version_ids:
                    version_ids.append(version["id"])

        if not version_ids:
            return []

        # Query for those versions
        return self.sg.find(
            "Version",
            [["id", "in", version_ids]],
            fields,
            order=[
                {"field_name": "entity", "direction": "asc"},  # Group by entity
                {"field_name": "created_at", "direction": "desc"}  # Newest first within entity
            ]
        )

    def get_versions_by_parent_package(self, package_id, fields=None):
        """
        Get versions where sg_parent_packages contains this package.
        Used for Script, Concept Art, and Storyboard versions.

        Args:
            package_id: ID of the Package entity
            fields: List of fields to return for versions

        Returns:
            List of version dictionaries
        """
        if fields is None:
            fields = [
                "id", "code", "entity", "sg_status_list", "created_at", "updated_at",
                "user", "description", "sg_task", "sg_path_to_movie", "sg_path_to_frames",
                "sg_uploaded_movie", "sg_path_to_geometry", "sg_version_type"
            ]

        # Query versions where sg_parent_packages contains this package
        versions = self.sg.find(
            "Version",
            [["sg_parent_packages", "in", {"type": "CustomEntity12", "id": int(package_id)}]],
            fields,
            order=[
                {"field_name": "entity", "direction": "asc"},  # Group by entity
                {"field_name": "created_at", "direction": "desc"}  # Newest first within entity
            ]
        )

        return versions

    def create_version(self, version_code, project_id, description=None, sg_version_type=None):
        """
        Create a new Version entity in ShotGrid.

        Args:
            version_code: Code/name for the version
            project_id: ID of the project
            description: Optional description
            sg_version_type: Optional version type (e.g., "Bid Tracker")

        Returns:
            Created version entity dictionary
        """
        version_data = {
            "code": version_code,
            "project": {"type": "Project", "id": int(project_id)},
        }

        if description:
            version_data["description"] = description

        if sg_version_type:
            version_data["sg_version_type"] = sg_version_type

        version = self.sg.create("Version", version_data)

        return version

    def upload_file_to_version(self, version_id, file_path, field_name="sg_uploaded_movie"):
        """
        Upload a file to a Version entity.

        Args:
            version_id: ID of the version
            file_path: Path to the file to upload
            field_name: Field to upload to (default: sg_uploaded_movie)

        Returns:
            True if successful, False otherwise
        """
        result = self.sg.upload(
            "Version",
            int(version_id),
            file_path,
            field_name=field_name
        )
        return result

    def link_version_to_package(self, version_id, package_id):
        """
        Link a Version to a Package by creating a PackageItem (CustomEntity13).

        The PackageItem is linked to the Package's sg_packageitems field,
        and the Version is linked to the PackageItem's sg_versions field.

        Args:
            version_id: ID of the version to link
            package_id: ID of the package

        Returns:
            Created PackageItem entity or existing package if already linked
        """
        # Check if version is already linked via an existing PackageItem
        existing_item = self.find_package_item_for_version(package_id, version_id)
        if existing_item:
            return existing_item

        # Get the Package to find its project
        package = self.sg.find_one(
            "CustomEntity12",
            [["id", "is", int(package_id)]],
            ["project"]
        )

        if not package:
            logger.error(f"Package {package_id} not found")
            return None

        project_id = package.get("project", {}).get("id")
        if not project_id:
            logger.error(f"Package {package_id} has no project")
            return None

        # Create a new PackageItem with the version linked
        package_item = self.create_package_item(
            package_id=package_id,
            project_id=project_id,
            version_id=version_id
        )

        return package_item

    def unlink_version_from_package(self, version_id, package_id):
        """
        Unlink a Version from a Package by deleting its PackageItem.

        Finds the PackageItem that contains the version and deletes it,
        which automatically removes the version from the package.

        Args:
            version_id: ID of the version to unlink
            package_id: ID of the package

        Returns:
            True if successful, False if version was not linked
        """
        # Find the PackageItem that contains this version
        package_item = self.find_package_item_for_version(package_id, version_id)

        if not package_item:
            return False

        # Delete the PackageItem
        result = self.delete_package_item(package_item["id"])

        return result

    def find_bid_tracker_versions_in_package(self, package_id):
        """
        Find all Bid Tracker versions in a package.

        Args:
            package_id: ID of the package

        Returns:
            List of version entities with sg_version_type matching "Bid Tracker"
        """
        versions = self.get_package_versions(package_id, fields=["id", "code", "sg_version_type"])

        bid_tracker_versions = []
        for version in versions:
            sg_version_type = version.get("sg_version_type")
            if sg_version_type:
                # Handle both string and dict formats
                if isinstance(sg_version_type, dict):
                    version_type = sg_version_type.get("name", "").lower()
                else:
                    version_type = str(sg_version_type).lower()

                if "bid" in version_type or "tracker" in version_type:
                    bid_tracker_versions.append(version)

        return bid_tracker_versions

    def get_all_bid_tracker_versions_for_project(self, project_id, rfq_code=None):
        """
        Get all Bid Tracker versions for a project, optionally filtered by RFQ code.

        Args:
            project_id: ID of the project
            rfq_code: Optional RFQ code to filter by (searches in version code)

        Returns:
            List of version entities with sg_version_type matching "Bid Tracker"
        """
        filters = [
            ["project", "is", {"type": "Project", "id": int(project_id)}],
            ["sg_version_type", "is", "Bid Tracker"]
        ]

        # If rfq_code provided, filter by code containing the lowercase rfq_code
        if rfq_code:
            rfq_code_lower = rfq_code.lower().replace(" ", "")
            filters.append(["code", "contains", rfq_code_lower])

        versions = self.sg.find(
            "Version",
            filters,
            fields=["id", "code", "sg_version_type", "description", "created_at", "sg_status_list"],
            order=[{"field_name": "created_at", "direction": "desc"}]
        )

        return versions

    def get_all_image_versions_for_project(self, project_id):
        """
        Get all image versions for a project (Concept Art, Storyboard, Reference, etc.).

        Args:
            project_id: ID of the project

        Returns:
            List of version entities with image-related sg_version_type
        """
        # Query all versions for the project
        versions = self.sg.find(
            "Version",
            [["project", "is", {"type": "Project", "id": int(project_id)}]],
            fields=[
                "id", "code", "entity", "sg_status_list", "created_at", "updated_at",
                "user", "description", "sg_task", "sg_path_to_movie", "sg_path_to_frames",
                "sg_uploaded_movie", "sg_path_to_geometry", "sg_version_type", "image"
            ],
            order=[{"field_name": "created_at", "direction": "desc"}]
        )

        # Filter for image-related versions
        image_versions = []
        for version in versions:
            sg_version_type = version.get('sg_version_type')
            if sg_version_type:
                # Handle both string and dict formats
                if isinstance(sg_version_type, dict):
                    version_type = sg_version_type.get('name', '').lower()
                else:
                    version_type = str(sg_version_type).lower()

                # Check for image-related keywords
                if any(keyword in version_type for keyword in [
                    'concept', 'art', 'storyboard', 'reference', 'image', 'ref', 'video', 'movie'
                ]):
                    image_versions.append(version)

        logger.info(f"Found {len(image_versions)} image versions in project {project_id}")
        return image_versions

    # ------------------------------------------------------------------
    # Vendor Management (CustomEntity05)
    # ------------------------------------------------------------------

    def get_vendors(self, project_id, fields=None, order=None):
        """
        Get Vendors (CustomEntity05) for a project.

        Args:
            project_id: Project ID
            fields: List of fields to return
            order: List of order dicts

        Returns:
            List of Vendor dictionaries
        """
        if fields is None:
            fields = ["id", "code", "sg_vendor_category", "sg_status_list", "description", "sg_members", "created_at", "updated_at"]
        if order is None:
            order = [{"field_name": "code", "direction": "asc"}]

        filters = [["project", "is", {"type": "Project", "id": int(project_id)}]]
        return self.sg.find("CustomEntity05", filters, fields, order=order)

    def get_vendors_by_ids(self, vendor_ids, fields=None):
        """
        Get Vendors (CustomEntity05) by their IDs.

        Args:
            vendor_ids: List of vendor IDs
            fields: List of fields to return

        Returns:
            List of Vendor dictionaries
        """
        if not vendor_ids:
            return []

        if fields is None:
            fields = ["id", "code", "sg_vendor_category", "sg_status_list", "description", "sg_members", "created_at", "updated_at"]

        filters = [["id", "in", [int(vid) for vid in vendor_ids]]]
        return self.sg.find("CustomEntity05", filters, fields, order=[{"field_name": "code", "direction": "asc"}])

    def get_vendor_categories(self, project_id):
        """
        Get unique vendor categories for a project.

        Args:
            project_id: Project ID

        Returns:
            List of unique category names
        """
        vendors = self.get_vendors(project_id, fields=["id", "sg_vendor_category"])
        categories = set()
        for vendor in vendors:
            category = vendor.get("sg_vendor_category")
            if category:
                categories.add(category)
        return sorted(list(categories))

    def get_client_users(self, user_ids, fields=None):
        """
        Get ClientUser entities by their IDs.

        Args:
            user_ids: List of ClientUser IDs
            fields: List of fields to return

        Returns:
            List of ClientUser dictionaries
        """
        if not user_ids:
            return []

        if fields is None:
            fields = ["id", "name", "email"]

        filters = [["id", "in", user_ids]]
        return self.sg.find("ClientUser", filters, fields)

    def get_all_client_users(self, fields=None, include_inactive=False):
        """
        Get all ClientUser entities.

        Args:
            fields: List of fields to return
            include_inactive: If True, include inactive users

        Returns:
            List of ClientUser dictionaries
        """
        if fields is None:
            fields = ["id", "name", "email", "sg_status_list", "sg_packages_recipient"]

        # Filter for active client users only unless include_inactive is True
        if include_inactive:
            filters = []
        else:
            filters = [["sg_status_list", "is", "act"]]
        return self.sg.find("ClientUser", filters, fields, order=[{"field_name": "name", "direction": "asc"}])

    def create_client_user(self, name, email, status="act", packages_recipient=False):
        """
        Create a new ClientUser.

        Args:
            name: User's name
            email: User's email address
            status: Status ('act' for active, 'dis' for inactive)
            packages_recipient: Whether this user is a packages recipient

        Returns:
            Created ClientUser entity dictionary
        """
        data = {
            "name": name,
            "email": email,
            "sg_status_list": status,
            "sg_packages_recipient": packages_recipient,
        }
        return self.sg.create("ClientUser", data)

    def update_client_user(self, user_id, data):
        """
        Update a ClientUser.

        Args:
            user_id: ClientUser ID
            data: Dictionary of fields to update

        Returns:
            Updated ClientUser entity dictionary
        """
        return self.sg.update("ClientUser", int(user_id), data)

    def delete_client_user(self, user_id):
        """
        Delete a ClientUser.

        Args:
            user_id: ClientUser ID

        Returns:
            bool: True if successful
        """
        return self.sg.delete("ClientUser", int(user_id))

    def create_vendor(self, project_id, code, vendor_category=None, description=None):
        """
        Create a new Vendor (CustomEntity05).

        Args:
            project_id: Project ID
            code: Vendor name/code
            vendor_category: Vendor category (optional)
            description: Description (optional)

        Returns:
            Created Vendor entity dictionary
        """
        data = {
            "code": code,
            "project": {"type": "Project", "id": int(project_id)},
        }

        if vendor_category:
            data["sg_vendor_category"] = vendor_category
        if description:
            data["description"] = description

        result = self.sg.create("CustomEntity05", data)
        return result

    def update_vendor(self, vendor_id, data):
        """
        Update a Vendor (CustomEntity05).

        Args:
            vendor_id: Vendor ID
            data: Dictionary of fields to update

        Returns:
            Updated Vendor entity dictionary
        """
        result = self.sg.update("CustomEntity05", int(vendor_id), data)
        return result

    def delete_vendor(self, vendor_id):
        """
        Delete a Vendor (CustomEntity05).

        Args:
            vendor_id: Vendor ID

        Returns:
            bool: True if successful
        """
        result = self.sg.delete("CustomEntity05", int(vendor_id))
        return result

    def get_all_document_versions_for_project(self, project_id):
        """
        Get all document versions for a project (Script, Misc, etc.).

        Args:
            project_id: ID of the project

        Returns:
            List of version entities with document-related sg_version_type
        """
        # Query all versions for the project
        versions = self.sg.find(
            "Version",
            [["project", "is", {"type": "Project", "id": int(project_id)}]],
            fields=[
                "id", "code", "entity", "sg_status_list", "created_at", "updated_at",
                "user", "description", "sg_task", "sg_path_to_movie", "sg_path_to_frames",
                "sg_uploaded_movie", "sg_path_to_geometry", "sg_version_type", "image"
            ],
            order=[{"field_name": "created_at", "direction": "desc"}]
        )

        # Filter for document-related versions
        document_versions = []
        for version in versions:
            sg_version_type = version.get('sg_version_type')
            if sg_version_type:
                # Handle both string and dict formats
                if isinstance(sg_version_type, dict):
                    version_type = sg_version_type.get('name', '').lower()
                else:
                    version_type = str(sg_version_type).lower()

                # Check for document-related keywords
                if any(keyword in version_type for keyword in [
                    'script', 'misc', 'document', 'doc', 'pdf', 'excel', 'xls'
                ]):
                    document_versions.append(version)

        logger.info(f"Found {len(document_versions)} document versions in project {project_id}")
        return document_versions

    def get_latest_version_number(self, package_id, version_prefix):
        """
        Get the latest version number for a given prefix in a package.

        Args:
            package_id: ID of the package
            version_prefix: Prefix to search for (e.g., "bidtracker_myproject")

        Returns:
            Next available version number (int)
        """
        # Get versions from package
        versions = self.get_package_versions(package_id, fields=["code"])

        # Extract version numbers from matching codes
        version_numbers = []
        for version in versions:
            code = version.get("code", "")
            if code.startswith(version_prefix):
                # Extract version number from end (e.g., "bidtracker_myproject_v001" -> 1)
                parts = code.split("_v")
                if len(parts) == 2:
                    try:
                        version_num = int(parts[1])
                        version_numbers.append(version_num)
                    except ValueError:
                        continue

        # Return next version number
        if version_numbers:
            return max(version_numbers) + 1
        else:
            return 1

    # ------------------------------------------------------------------
    # PackageTracking Management (CustomEntity14)
    # ------------------------------------------------------------------

    def create_package_tracking(self, project_id, package_name, share_link, vendor, rfq, status="dlvr"):
        """
        Create a new PackageTracking (CustomEntity14) entity in ShotGrid.

        Args:
            project_id: ID of the project
            package_name: Name/code for the tracking record
            share_link: Google Drive share link (sg_share_link) - string URL
            vendor: Vendor entity dict or ID (sg_recipient)
            rfq: RFQ entity dict or ID (sg_rfq)
            status: Status code (default: "dlvr" for Delivered). Valid: 'dlvr', 'dwnld'

        Returns:
            Created PackageTracking entity dictionary
        """
        # Normalize vendor link
        if isinstance(vendor, int):
            vendor_link = {"type": "CustomEntity05", "id": int(vendor)}
        elif isinstance(vendor, dict) and "id" in vendor:
            vendor_link = {"type": vendor.get("type", "CustomEntity05"), "id": int(vendor["id"])}
        else:
            raise ValueError("Invalid vendor argument; expected id or SG link dict.")

        # Normalize RFQ link
        if isinstance(rfq, int):
            rfq_link = {"type": "CustomEntity04", "id": int(rfq)}
        elif isinstance(rfq, dict) and "id" in rfq:
            rfq_link = {"type": rfq.get("type", "CustomEntity04"), "id": int(rfq["id"])}
        else:
            raise ValueError("Invalid rfq argument; expected id or SG link dict.")

        # Format share_link as a URL field (ShotGrid expects a dict for URL fields)
        share_link_data = None
        if share_link:
            share_link_data = {
                "url": share_link,
                "name": f"{package_name} - Google Drive"
            }

        data = {
            "code": package_name,
            "project": {"type": "Project", "id": int(project_id)},
            "sg_recipient": vendor_link,
            "sg_rfq": rfq_link,
            "sg_status_list": status,
        }

        # Only add share_link if it exists
        if share_link_data:
            data["sg_share_link"] = share_link_data

        result = self.sg.create("CustomEntity14", data)
        logger.info(f"Created PackageTracking: {result.get('id')} for vendor {vendor_link['id']}, RFQ {rfq_link['id']}")
        return result

    def get_package_tracking_for_rfq(self, rfq_id, fields=None):
        """
        Get all PackageTracking (CustomEntity14) records for a specific RFQ.

        Args:
            rfq_id: ID of the RFQ to filter by
            fields: List of fields to return

        Returns:
            List of PackageTracking dictionaries
        """
        if fields is None:
            fields = [
                "id", "code", "sg_share_link", "sg_recipient", "sg_rfq",
                "sg_status_list", "created_at", "updated_at"
            ]

        filters = [["sg_rfq", "is", {"type": "CustomEntity04", "id": int(rfq_id)}]]

        return self.sg.find(
            "CustomEntity14",
            filters,
            fields,
            order=[{"field_name": "created_at", "direction": "desc"}]
        )

    def get_package_tracking_for_vendor_and_rfq(self, vendor_id, rfq_id, fields=None):
        """
        Get PackageTracking (CustomEntity14) records filtered by vendor and RFQ.

        Args:
            vendor_id: ID of the vendor (CustomEntity05)
            rfq_id: ID of the RFQ (CustomEntity04)
            fields: List of fields to return

        Returns:
            List of PackageTracking dictionaries
        """
        if fields is None:
            fields = [
                "id", "code", "sg_share_link", "sg_recipient", "sg_rfq",
                "sg_status_list", "created_at", "updated_at"
            ]

        filters = [
            ["sg_recipient", "is", {"type": "CustomEntity05", "id": int(vendor_id)}],
            ["sg_rfq", "is", {"type": "CustomEntity04", "id": int(rfq_id)}]
        ]

        return self.sg.find(
            "CustomEntity14",
            filters,
            fields,
            order=[{"field_name": "created_at", "direction": "desc"}]
        )

    def check_package_already_shared(self, package_name, vendor_id, rfq_id):
        """
        Check if a package has already been shared with a vendor for an RFQ.

        Args:
            package_name: Name/code of the package
            vendor_id: ID of the vendor (CustomEntity05)
            rfq_id: ID of the RFQ (CustomEntity04)

        Returns:
            dict or None: The existing PackageTracking record if found, None otherwise
        """
        filters = [
            ["code", "is", package_name],
            ["sg_recipient", "is", {"type": "CustomEntity05", "id": int(vendor_id)}],
            ["sg_rfq", "is", {"type": "CustomEntity04", "id": int(rfq_id)}]
        ]

        results = self.sg.find(
            "CustomEntity14",
            filters,
            ["id", "code", "sg_share_link", "sg_recipient", "sg_status_list", "created_at"],
            limit=1
        )

        return results[0] if results else None

    def update_package_tracking(self, tracking_id, data):
        """
        Update a PackageTracking (CustomEntity14) entity.

        Args:
            tracking_id: PackageTracking ID
            data: Dictionary of fields to update

        Returns:
            Updated PackageTracking entity dictionary
        """
        result = self.sg.update("CustomEntity14", int(tracking_id), data)
        return result

    def delete_package_tracking(self, tracking_id):
        """
        Delete a PackageTracking (CustomEntity14) entity.

        Args:
            tracking_id: PackageTracking ID

        Returns:
            bool: True if successful
        """
        result = self.sg.delete("CustomEntity14", int(tracking_id))
        return result

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self._sg = None


# Example usage
if __name__ == "__main__":
    # Set environment variables first:
    # export SG_URL=https://your-studio.shotgrid.com
    # export SG_SCRIPT=your_script_name
    # export SG_KEY=your_api_key

    with ShotgridClient() as client:
        print("Connected to:", client.site_url)

        # Get bidding projects
        projects = client.get_bid_projects()
        print(f"\nFound {len(projects)} bidding projects:")
        for proj in projects[:3]:
            print(f"  - {proj['code']}: {proj['name']}")

        # Get RFQs and assets from first project
        if projects:
            project_id = projects[0]["id"]
            project_code = projects[0]["code"]

            # Get RFQs
            rfqs = client.get_rfqs(project_id)
            print(f"\nFound {len(rfqs)} RFQs in {project_code}:")
            for rfq in rfqs[:5]:
                print(f"  - {rfq.get('code', 'N/A')} (Status: {rfq.get('sg_status_list', 'N/A')})")

            # Get versions for first RFQ
            if rfqs:
                rfq_id = rfqs[0]["id"]
                versions = client.get_rfq_versions(rfq_id)
                print(f"\nFound {len(versions)} versions for RFQ {rfqs[0].get('code', 'N/A')}:")
                for version in versions[:5]:
                    entity = version.get('entity', {})
                    entity_name = entity.get('name', 'Unknown') if entity else 'Unknown'
                    print(f"  - {version['code']} ({entity_name}) - Status: {version.get('sg_status_list', 'N/A')}")

            # Get assets
            assets = client.get_assets(project_id)
            print(f"\nFound {len(assets)} assets in {project_code}")