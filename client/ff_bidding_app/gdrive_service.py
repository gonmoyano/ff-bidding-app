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

# Scopes required for Google Drive file upload and sharing
SCOPES = ['https://www.googleapis.com/auth/drive.file']


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
        self._creds = None

    @property
    def is_available(self):
        """Check if Google API libraries are available."""
        return GOOGLE_API_AVAILABLE

    @property
    def has_credentials(self):
        """Check if credentials.json exists."""
        return self.credentials_file.exists()

    @property
    def is_authenticated(self):
        """Check if we have valid authentication token."""
        if not self.token_file.exists():
            return False
        try:
            creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)
            return creds and creds.valid
        except Exception:
            return False

    def authenticate(self):
        """Authenticate with Google Drive.

        This will open a browser window for OAuth consent if needed.

        Returns:
            True if authentication successful, False otherwise.
        """
        if not GOOGLE_API_AVAILABLE:
            logger.error("Google API libraries not available")
            return False

        if not self.has_credentials:
            logger.error(f"credentials.json not found at {self.credentials_file}")
            return False

        try:
            creds = None

            # Load existing token if available
            if self.token_file.exists():
                creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)

            # If no valid credentials, authenticate
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    logger.info("Refreshing expired Google Drive token...")
                    creds.refresh(Request())
                else:
                    logger.info("Starting Google Drive OAuth flow...")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_file), SCOPES
                    )
                    creds = flow.run_local_server(port=0)

                # Save the token for future use
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
