"""Spotify integration service for controlling playback using Spotipy."""

import logging
from pathlib import Path
from typing import Any

import spotipy
from spotipy.oauth2 import SpotifyPKCE

from launchsampler.models import SpotifyConfig

logger = logging.getLogger(__name__)

# OAuth scopes required for playback control
SPOTIFY_SCOPES = " ".join([
    "user-modify-playback-state",  # Play/pause/seek
    "user-read-playback-state",  # Get current playback state
    "user-read-currently-playing",  # Get currently playing track
])


class SpotifyAuthError(Exception):
    """Error during Spotify authentication."""

    pass


class SpotifyPlaybackError(Exception):
    """Error during Spotify playback control."""

    pass


class SpotifyService:
    """
    Service for controlling Spotify playback using Spotipy.

    Uses Spotify Web API with OAuth 2.0 PKCE flow for authentication.
    Supports play/pause toggle for individual tracks.

    The PKCE flow is recommended for desktop applications as it doesn't
    require storing a client secret.

    Usage:
        service = SpotifyService(config.spotify)
        if not service.is_authenticated:
            service.authenticate()  # Opens browser for OAuth

        # Play a track
        service.play_track("spotify:track:4iV5W9uYEdYUVa79Axb7Rh")

        # Toggle playback (pause if playing, play if paused)
        service.toggle_playback("spotify:track:4iV5W9uYEdYUVa79Axb7Rh")
    """

    def __init__(self, config: SpotifyConfig, cache_path: Path | None = None):
        """
        Initialize Spotify service.

        Args:
            config: Spotify configuration with client credentials
            cache_path: Optional path for token cache file. If None, uses
                       ~/.launchsampler/.spotify_cache
        """
        self._config = config
        self._sp: spotipy.Spotify | None = None
        self._auth_manager: SpotifyPKCE | None = None

        # Set up cache path for token storage
        if cache_path is None:
            cache_path = Path.home() / ".launchsampler" / ".spotify_cache"
        self._cache_path = cache_path

        # Initialize if configured
        if self.is_configured:
            self._init_auth_manager()

    def _init_auth_manager(self) -> None:
        """Initialize the Spotipy PKCE auth manager."""
        if not self._config.client_id:
            return

        # Ensure cache directory exists
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)

        self._auth_manager = SpotifyPKCE(
            client_id=self._config.client_id,
            redirect_uri=self._config.redirect_uri,
            scope=SPOTIFY_SCOPES,
            cache_path=str(self._cache_path),
            open_browser=True,
        )

    def close(self) -> None:
        """Clean up resources."""
        self._sp = None
        self._auth_manager = None

    @property
    def is_configured(self) -> bool:
        """Check if Spotify client ID is configured."""
        return self._config.is_configured

    @property
    def is_authenticated(self) -> bool:
        """Check if we have valid authentication tokens."""
        if not self.is_configured or not self._auth_manager:
            return False

        # Check if we have a cached token
        token_info = self._auth_manager.get_cached_token()
        if not token_info:
            return False

        # Spotipy handles token refresh automatically when making API calls
        return True

    def authenticate(self) -> bool:
        """
        Start OAuth 2.0 PKCE authentication flow.

        Opens browser for user to authorize the application.
        Spotipy handles the callback server automatically.

        Returns:
            True if authentication successful

        Raises:
            SpotifyAuthError: If authentication fails
        """
        if not self.is_configured:
            raise SpotifyAuthError("Spotify client_id not configured")

        if not self._auth_manager:
            self._init_auth_manager()

        if not self._auth_manager:
            raise SpotifyAuthError("Failed to initialize auth manager")

        try:
            # This will open a browser and wait for the callback
            # Spotipy handles the local server automatically
            logger.info("Opening browser for Spotify authentication...")
            token_info = self._auth_manager.get_access_token()

            if token_info:
                # Create the Spotify client
                self._sp = spotipy.Spotify(auth_manager=self._auth_manager)
                logger.info("Spotify authentication successful")
                return True
            else:
                raise SpotifyAuthError("Failed to obtain access token")

        except Exception as e:
            logger.error(f"Spotify authentication failed: {e}")
            raise SpotifyAuthError(f"Authentication failed: {e}") from e

    def _ensure_client(self) -> spotipy.Spotify:
        """Ensure we have an authenticated Spotify client."""
        if self._sp:
            return self._sp

        if not self._auth_manager:
            raise SpotifyAuthError("Not configured - set client_id first")

        # Try to use cached token
        token_info = self._auth_manager.get_cached_token()
        if not token_info:
            raise SpotifyAuthError("Not authenticated - call authenticate() first")

        self._sp = spotipy.Spotify(auth_manager=self._auth_manager)
        return self._sp

    def get_playback_state(self) -> dict | None:
        """
        Get current playback state.

        Returns:
            Playback state dict or None if nothing is playing
        """
        sp = self._ensure_client()

        try:
            state = sp.current_playback()
            return state
        except spotipy.SpotifyException as e:
            if e.http_status == 204:
                return None  # No active device
            raise SpotifyPlaybackError(f"Failed to get playback state: {e}") from e

    def play_track(self, spotify_uri: str, device_id: str | None = None) -> None:
        """
        Start playing a specific track.

        Args:
            spotify_uri: Spotify URI (e.g., spotify:track:4iV5W9uYEdYUVa79Axb7Rh)
            device_id: Optional device ID to play on

        Raises:
            SpotifyPlaybackError: If playback fails
        """
        sp = self._ensure_client()

        try:
            sp.start_playback(uris=[spotify_uri], device_id=device_id)
            logger.info(f"Started playing: {spotify_uri}")
        except spotipy.SpotifyException as e:
            raise SpotifyPlaybackError(f"Failed to play track: {e}") from e

    def pause(self) -> None:
        """Pause current playback."""
        sp = self._ensure_client()

        try:
            sp.pause_playback()
            logger.info("Playback paused")
        except spotipy.SpotifyException as e:
            # 403 can mean already paused or no active device
            if e.http_status == 403:
                logger.debug("Playback already paused or no active device")
                return
            raise SpotifyPlaybackError(f"Failed to pause: {e}") from e

    def stop(self) -> None:
        """Stop playback and reset to beginning (pause + seek to 0)."""
        sp = self._ensure_client()

        try:
            sp.pause_playback()
            # Seek to beginning so next play starts fresh
            sp.seek_track(0)
            logger.info("Playback stopped (reset to beginning)")
        except spotipy.SpotifyException as e:
            # 403 can mean already paused or no active device
            if e.http_status == 403:
                logger.debug("Playback already stopped or no active device")
                return
            raise SpotifyPlaybackError(f"Failed to stop: {e}") from e

    def resume(self) -> None:
        """Resume current playback."""
        sp = self._ensure_client()

        try:
            sp.start_playback()
            logger.info("Playback resumed")
        except spotipy.SpotifyException as e:
            raise SpotifyPlaybackError(f"Failed to resume: {e}") from e

    def toggle_playback(self, spotify_uri: str) -> bool:
        """
        Toggle playback for a track.

        If the track is currently playing, stop it (resets to beginning).
        If not playing, start playing from the beginning.

        Args:
            spotify_uri: Spotify URI of the track

        Returns:
            True if now playing, False if stopped

        Raises:
            SpotifyPlaybackError: If playback control fails
        """
        state = self.get_playback_state()

        if state:
            current_uri = state.get("item", {}).get("uri") if state.get("item") else None
            is_playing = state.get("is_playing", False)

            if current_uri == spotify_uri and is_playing:
                # Same track playing - stop it (resets to beginning)
                self.stop()
                return False

        # Not playing or different track - always start from beginning
        self.play_track(spotify_uri)
        return True

    def is_track_playing(self, spotify_uri: str) -> bool:
        """
        Check if a specific track is currently playing.

        Args:
            spotify_uri: Spotify URI of the track

        Returns:
            True if the track is currently playing
        """
        state = self.get_playback_state()

        if not state:
            return False

        current_uri = state.get("item", {}).get("uri") if state.get("item") else None
        is_playing = state.get("is_playing", False)

        return current_uri == spotify_uri and is_playing

    def get_available_devices(self) -> list[dict]:
        """
        Get list of available Spotify playback devices.

        Returns:
            List of device dictionaries with id, name, type, is_active fields
        """
        sp = self._ensure_client()

        try:
            devices = sp.devices()
            return devices.get("devices", [])
        except spotipy.SpotifyException as e:
            raise SpotifyPlaybackError(f"Failed to get devices: {e}") from e

    def __enter__(self) -> "SpotifyService":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()
