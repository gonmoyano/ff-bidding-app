"""Google Drive service for uploading and sharing files."""
import os
import logging
from pathlib import Path

logger = logging.getLogger("FFPackageManager")

# Google API imports
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    logger.warning("Google API libraries not installed. Run: pip install google-auth google-auth-oauthlib google-api-python-client")

# Scopes required for Google Drive file upload, sharing, and activity tracking
SCOPES = [
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/drive.activity.readonly'
]


class GoogleDriveService:
    """Service for interacting with Google Drive API."""

    def __init__(self, credentials_dir=None):
        """Initialize the Google Drive service.

        Args:
            credentials_dir: Directory containing credentials.json and token.json.
                           Defaults to the same directory as this module.
        """
        if credentials_dir is None:
            credentials_dir = Path(__file__).parent
        self.credentials_dir = Path(credentials_dir)
        self.credentials_file = self.credentials_dir / "credentials.json"
        self.token_file = self.credentials_dir / "token.json"
        self._service = None
        self._activity_service = None
        self._creds = None

        # Debug logging
        logger.info(f"GoogleDriveService initialized")
        logger.info(f"  __file__ = {__file__}")
        logger.info(f"  credentials_dir = {self.credentials_dir}")
        logger.info(f"  credentials_file = {self.credentials_file}")
        logger.info(f"  credentials_file exists = {self.credentials_file.exists()}")
        logger.info(f"  token_file = {self.token_file}")
        logger.info(f"  token_file exists = {self.token_file.exists()}")

    @property
    def is_available(self):
        """Check if Google API libraries are available."""
        return GOOGLE_API_AVAILABLE

    @property
    def has_credentials(self):
        """Check if credentials.json exists."""
        exists = self.credentials_file.exists()
        logger.info(f"has_credentials check: {self.credentials_file} exists={exists}")
        return exists

    @property
    def is_authenticated(self):
        """Check if we have valid authentication token."""
        if not self.token_file.exists():
            logger.info(f"is_authenticated: token file does not exist: {self.token_file}")
            return False
        try:
            creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)
            valid = creds and creds.valid
            logger.info(f"is_authenticated: token loaded, valid={valid}")
            return valid
        except Exception as e:
            logger.info(f"is_authenticated: error loading token: {e}")
            return False

    def authenticate(self):
        """Authenticate with Google Drive.

        This will open a browser window for OAuth consent if needed.

        Returns:
            True if authentication successful, False otherwise.
        """
        logger.info(f"authenticate() called")
        logger.info(f"  GOOGLE_API_AVAILABLE = {GOOGLE_API_AVAILABLE}")
        logger.info(f"  credentials_file = {self.credentials_file}")
        logger.info(f"  credentials_file.exists() = {self.credentials_file.exists()}")

        if not GOOGLE_API_AVAILABLE:
            logger.error("Google API libraries not available")
            return False

        if not self.has_credentials:
            logger.error(f"credentials.json not found at {self.credentials_file}")
            # List files in the directory for debugging
            try:
                files = list(self.credentials_dir.iterdir())
                logger.error(f"Files in {self.credentials_dir}: {[f.name for f in files]}")
            except Exception as e:
                logger.error(f"Could not list directory: {e}")
            return False

        try:
            creds = None

            # Load existing token if available
            if self.token_file.exists():
                logger.info(f"Loading existing token from {self.token_file}")
                creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)
                logger.info(f"Token loaded, valid={creds.valid if creds else 'None'}")

            # If no valid credentials, authenticate
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    logger.info("Refreshing expired Google Drive token...")
                    creds.refresh(Request())
                else:
                    logger.info(f"Starting Google Drive OAuth flow with {self.credentials_file}...")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_file), SCOPES
                    )
                    creds = flow.run_local_server(port=0)

                # Save the token for future use
                logger.info(f"Saving token to {self.token_file}")
                with open(self.token_file, 'w') as token:
                    token.write(creds.to_json())
                logger.info(f"Token saved to {self.token_file}")

            self._creds = creds
            self._service = build('drive', 'v3', credentials=creds)
            logger.info("Google Drive authentication successful")
            return True

        except Exception as e:
            logger.error(f"Google Drive authentication failed: {e}")
            return False

    def get_service(self):
        """Get the Google Drive service, authenticating if needed.

        Returns:
            Google Drive service object or None if authentication fails.
        """
        if self._service is None:
            if not self.authenticate():
                return None
        return self._service

    def get_activity_service(self):
        """Get the Drive Activity API service, authenticating if needed.

        Returns:
            Drive Activity service object or None if authentication fails.
        """
        if self._activity_service is None:
            if not self.authenticate():
                return None
            try:
                self._activity_service = build('driveactivity', 'v2', credentials=self._creds)
            except Exception as e:
                logger.error(f"Failed to build Drive Activity service: {e}")
                return None
        return self._activity_service

    def check_file_accessed(self, file_id):
        """Check if a file has been accessed (viewed or downloaded) by anyone.

        Uses the Drive Activity API to check for view/download activity on the file.

        Args:
            file_id: Google Drive file ID.

        Returns:
            dict with:
                'accessed': bool - True if file has been accessed
                'access_time': datetime or None - Time of most recent access
                'access_count': int - Number of access events
            Returns None on error.
        """
        activity_service = self.get_activity_service()
        if not activity_service:
            logger.warning("Drive Activity service not available")
            return None

        try:
            # Query for activity on this specific file
            # We look for any action that indicates the file was accessed
            request_body = {
                'itemName': f'items/{file_id}',
                'pageSize': 100,
                'filter': 'detail.action_detail_case:(DOWNLOAD OR VIEW)'
            }

            response = activity_service.activity().query(body=request_body).execute()
            activities = response.get('activities', [])

            if not activities:
                logger.debug(f"No access activity found for file {file_id}")
                return {
                    'accessed': False,
                    'access_time': None,
                    'access_count': 0
                }

            # Parse the activities to get access info
            access_count = len(activities)
            most_recent_time = None

            for activity in activities:
                # Get timestamp from the activity
                timestamp = activity.get('timestamp')
                if timestamp:
                    from datetime import datetime
                    try:
                        # Parse ISO format timestamp
                        if timestamp.endswith('Z'):
                            timestamp = timestamp[:-1] + '+00:00'
                        activity_time = datetime.fromisoformat(timestamp)
                        if most_recent_time is None or activity_time > most_recent_time:
                            most_recent_time = activity_time
                    except (ValueError, TypeError) as e:
                        logger.debug(f"Could not parse timestamp {timestamp}: {e}")

            logger.info(f"File {file_id} has been accessed {access_count} times, most recent: {most_recent_time}")
            return {
                'accessed': True,
                'access_time': most_recent_time,
                'access_count': access_count
            }

        except Exception as e:
            logger.error(f"Failed to check file access: {e}")
            return None

    def extract_file_id_from_url(self, share_url):
        """Extract the Google Drive file ID from a share URL.

        Args:
            share_url: Google Drive share URL (e.g., https://drive.google.com/file/d/FILE_ID/view)

        Returns:
            str: The file ID, or None if it couldn't be extracted.
        """
        if not share_url:
            return None

        import re

        # Pattern for various Google Drive URL formats
        patterns = [
            r'/file/d/([a-zA-Z0-9_-]+)',  # /file/d/FILE_ID/view
            r'/open\?id=([a-zA-Z0-9_-]+)',  # /open?id=FILE_ID
            r'id=([a-zA-Z0-9_-]+)',  # ?id=FILE_ID
            r'/folders/([a-zA-Z0-9_-]+)',  # /folders/FOLDER_ID
        ]

        for pattern in patterns:
            match = re.search(pattern, share_url)
            if match:
                return match.group(1)

        logger.warning(f"Could not extract file ID from URL: {share_url}")
        return None

    def upload_file(self, file_path, folder_id=None, mime_type=None):
        """Upload a file to Google Drive.

        Args:
            file_path: Path to the file to upload.
            folder_id: Optional Google Drive folder ID to upload to.
            mime_type: Optional MIME type. Auto-detected if not provided.

        Returns:
            dict with 'id', 'name', 'webViewLink' on success, None on failure.
        """
        service = self.get_service()
        if not service:
            return None

        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return None

        try:
            # Auto-detect mime type
            if mime_type is None:
                if file_path.suffix.lower() == '.zip':
                    mime_type = 'application/zip'
                else:
                    mime_type = 'application/octet-stream'

            file_metadata = {'name': file_path.name}
            if folder_id:
                file_metadata['parents'] = [folder_id]

            media = MediaFileUpload(str(file_path), mimetype=mime_type, resumable=True)

            logger.info(f"Uploading {file_path.name} to Google Drive...")
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink'
            ).execute()

            logger.info(f"File uploaded successfully: {file.get('name')} (ID: {file.get('id')})")
            return file

        except Exception as e:
            logger.error(f"Failed to upload file to Google Drive: {e}")
            return None

    def share_file(self, file_id, email=None, role='reader', link_sharing=True):
        """Share a file on Google Drive.

        Args:
            file_id: Google Drive file ID.
            email: Email address to share with (optional).
            role: Permission role ('reader', 'commenter', 'writer').
            link_sharing: If True, enable "anyone with link" sharing.

        Returns:
            dict with 'webViewLink' on success, None on failure.
        """
        service = self.get_service()
        if not service:
            return None

        try:
            # Enable link sharing if requested
            if link_sharing:
                permission = {
                    'type': 'anyone',
                    'role': role
                }
                service.permissions().create(
                    fileId=file_id,
                    body=permission
                ).execute()
                logger.info(f"Enabled link sharing for file {file_id}")

            # Share with specific email if provided
            if email:
                permission = {
                    'type': 'user',
                    'role': role,
                    'emailAddress': email
                }
                service.permissions().create(
                    fileId=file_id,
                    body=permission,
                    sendNotificationEmail=True
                ).execute()
                logger.info(f"Shared file {file_id} with {email}")

            # Get the updated file info with sharing link
            file = service.files().get(
                fileId=file_id,
                fields='webViewLink'
            ).execute()

            return file

        except Exception as e:
            logger.error(f"Failed to share file: {e}")
            return None

    def upload_and_share(self, file_path, email=None, role='reader', link_sharing=True, folder_id=None):
        """Upload a file and share it in one operation.

        Args:
            file_path: Path to the file to upload.
            email: Email address to share with (optional).
            role: Permission role ('reader', 'commenter', 'writer').
            link_sharing: If True, enable "anyone with link" sharing.
            folder_id: Optional Google Drive folder ID to upload to.

        Returns:
            dict with 'id', 'name', 'webViewLink' on success, None on failure.
        """
        # Upload the file
        result = self.upload_file(file_path, folder_id=folder_id)
        if not result:
            return None

        file_id = result.get('id')

        # Share the file
        share_result = self.share_file(file_id, email=email, role=role, link_sharing=link_sharing)
        if share_result:
            result['webViewLink'] = share_result.get('webViewLink')

        return result


# Singleton instance
_gdrive_service = None


def get_gdrive_service():
    """Get the singleton Google Drive service instance."""
    global _gdrive_service
    if _gdrive_service is None:
        _gdrive_service = GoogleDriveService()
    return _gdrive_service
