"""Thumbnail caching system for faster image loading."""

import hashlib
import logging
import os
import time
from pathlib import Path
from datetime import datetime, timedelta

import requests

logger = logging.getLogger(__name__)


class ThumbnailCache:
    """Manages local caching of thumbnail images."""

    def __init__(self, cache_path, max_age_days=7):
        """Initialize the thumbnail cache.

        Args:
            cache_path: Path to cache folder
            max_age_days: Maximum age of cached files in days
        """
        self.cache_path = Path(cache_path)
        self.max_age_days = max_age_days
        self._ensure_cache_dir()

    def _ensure_cache_dir(self):
        """Ensure cache directory exists."""
        self.cache_path.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, version_id, url=None):
        """Generate a cache key for a version.

        Args:
            version_id: ShotGrid version ID
            url: Optional URL to include in hash for cache busting

        Returns:
            str: Cache filename
        """
        # Use version ID as primary key, with optional URL hash
        if url:
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            return f"thumb_{version_id}_{url_hash}.png"
        return f"thumb_{version_id}.png"

    def get_cache_path(self, version_id, url=None):
        """Get the full path for a cached thumbnail.

        Args:
            version_id: ShotGrid version ID
            url: Optional URL for cache key

        Returns:
            Path: Full path to cached file
        """
        return self.cache_path / self._get_cache_key(version_id, url)

    def is_cached(self, version_id, url=None):
        """Check if a valid cached thumbnail exists.

        Args:
            version_id: ShotGrid version ID
            url: Optional URL for cache key

        Returns:
            bool: True if valid cache exists
        """
        cache_file = self.get_cache_path(version_id, url)
        if not cache_file.exists():
            return False

        # Check age
        file_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
        if file_age > timedelta(days=self.max_age_days):
            return False

        return True

    def get_cached_data(self, version_id, url=None):
        """Get cached thumbnail data if available.

        Args:
            version_id: ShotGrid version ID
            url: Optional URL for cache key

        Returns:
            bytes or None: Cached image data, or None if not cached
        """
        if not self.is_cached(version_id, url):
            return None

        cache_file = self.get_cache_path(version_id, url)
        try:
            with open(cache_file, 'rb') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read cached thumbnail: {e}")
            return None

    def cache_thumbnail(self, version_id, image_data, url=None):
        """Save thumbnail data to cache.

        Args:
            version_id: ShotGrid version ID
            image_data: Image bytes to cache
            url: Optional URL for cache key
        """
        self._ensure_cache_dir()
        cache_file = self.get_cache_path(version_id, url)
        try:
            with open(cache_file, 'wb') as f:
                f.write(image_data)
        except Exception as e:
            logger.error(f"Failed to cache thumbnail: {e}")

    def download_and_cache(self, version_id, url, timeout=10):
        """Download thumbnail from URL and cache it.

        Args:
            version_id: ShotGrid version ID
            url: URL to download from
            timeout: Request timeout in seconds

        Returns:
            bytes or None: Image data, or None if download failed
        """
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                image_data = response.content
                self.cache_thumbnail(version_id, image_data, url)
                return image_data
            else:
                logger.error(f"Failed to download thumbnail: HTTP {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Failed to download thumbnail: {e}")
            return None

    def invalidate(self, version_id):
        """Invalidate cached thumbnails for a version.

        Args:
            version_id: ShotGrid version ID
        """
        # Find and delete all cached files for this version
        pattern = f"thumb_{version_id}*.png"
        for cache_file in self.cache_path.glob(pattern):
            try:
                cache_file.unlink()
            except Exception as e:
                logger.error(f"Failed to invalidate cache: {e}")

    def clear_all(self):
        """Clear all cached thumbnails."""
        if not self.cache_path.exists():
            return

        for cache_file in self.cache_path.glob("thumb_*.png"):
            try:
                cache_file.unlink()
            except Exception as e:
                logger.error(f"Failed to delete cache file: {e}")

        logger.info("Cleared all cached thumbnails")

    def cleanup_expired(self):
        """Remove expired cache files."""
        if not self.cache_path.exists():
            return

        now = datetime.now()
        expired_count = 0

        for cache_file in self.cache_path.glob("thumb_*.png"):
            try:
                file_age = now - datetime.fromtimestamp(cache_file.stat().st_mtime)
                if file_age > timedelta(days=self.max_age_days):
                    cache_file.unlink()
                    expired_count += 1
            except Exception as e:
                logger.error(f"Failed to check/remove cache file: {e}")

        if expired_count:
            logger.info(f"Removed {expired_count} expired cache files")

    def get_stats(self):
        """Get cache statistics.

        Returns:
            dict: Statistics about the cache
        """
        if not self.cache_path.exists():
            return {"file_count": 0, "total_size": 0}

        files = list(self.cache_path.glob("thumb_*.png"))
        total_size = sum(f.stat().st_size for f in files if f.exists())

        return {
            "file_count": len(files),
            "total_size": total_size,
            "cache_path": str(self.cache_path)
        }
