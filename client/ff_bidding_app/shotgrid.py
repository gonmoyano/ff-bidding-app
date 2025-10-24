"""Simplified Shotgrid client for FF Package Manager."""
import logging
import os

try:
    from shotgun_api3 import Shotgun
    from shotgun_api3 import Fault  # at top with other imports
except ImportError:
    Shotgun = None
    print("Warning: shotgun_api3 not installed. Using simulated data.")


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

    def get_beats_for_vfx_breakdown(self, vfx_breakdown_id, fields=None, order=None):
        """
        Return all Beats (CustomEntity02) whose sg_parent references the given VFX Breakdown (CustomEntity01).
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

    def get_bids(self, project_id, fields=None, order=None):
        """
        Get Bids (CustomEntity06) for a project.

        Args:
            project_id: Project ID
            fields: List of fields to return
            order: List of order dicts

        Returns:
            List of Bid dictionaries
        """
        if fields is None:
            fields = ["id", "code", "sg_bid_type", "sg_vfx_breakdown", "created_at", "updated_at"]
        if order is None:
            order = [{"field_name": "created_at", "direction": "desc"}]

        filters = [["project", "is", {"type": "Project", "id": int(project_id)}]]
        return self.sg.find("CustomEntity06", filters, fields, order=order)

    def create_bid(self, project_id, code, bid_type="Early Bid", vfx_breakdown=None):
        """
        Create a new Bid (CustomEntity06).

        Args:
            project_id: Project ID
            code: Bid name/code
            bid_type: Bid type (default: "Early Bid")
            vfx_breakdown: VFX Breakdown entity dict (optional)

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
            raise

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