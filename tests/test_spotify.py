"""Unit tests for Spotify integration."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from launchsampler.models import AudioSample, SpotifyConfig, SpotifySample
from launchsampler.services import SpotifyAuthError, SpotifyService


class TestSpotifySample:
    """Test SpotifySample model."""

    @pytest.mark.unit
    def test_create_with_valid_uri(self):
        """Test creating SpotifySample with valid Spotify URI."""
        sample = SpotifySample(
            name="Test Track",
            spotify_uri="spotify:track:4iV5W9uYEdYUVa79Axb7Rh",
        )
        assert sample.name == "Test Track"
        assert sample.spotify_uri == "spotify:track:4iV5W9uYEdYUVa79Axb7Rh"
        assert sample.type == "spotify"

    @pytest.mark.unit
    def test_track_id_property(self):
        """Test track_id property extraction."""
        sample = SpotifySample(
            name="Test Track",
            spotify_uri="spotify:track:4iV5W9uYEdYUVa79Axb7Rh",
        )
        assert sample.track_id == "4iV5W9uYEdYUVa79Axb7Rh"

    @pytest.mark.unit
    def test_from_spotify_link(self):
        """Test creating SpotifySample from Spotify share link."""
        link = "https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh"
        sample = SpotifySample.from_link(link, name="My Track")

        assert sample.name == "My Track"
        assert sample.spotify_uri == "spotify:track:4iV5W9uYEdYUVa79Axb7Rh"

    @pytest.mark.unit
    def test_from_spotify_link_with_query_params(self):
        """Test creating SpotifySample from Spotify link with query params."""
        link = "https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh?si=abc123def"
        sample = SpotifySample(name="Track", spotify_uri=link)

        assert sample.spotify_uri == "spotify:track:4iV5W9uYEdYUVa79Axb7Rh"

    @pytest.mark.unit
    def test_from_link_auto_name(self):
        """Test creating SpotifySample from link generates default name."""
        link = "https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh"
        sample = SpotifySample.from_link(link)

        assert sample.name.startswith("Track ")
        assert "4iV5W9uY" in sample.name

    @pytest.mark.unit
    def test_invalid_uri_raises_error(self):
        """Test that invalid Spotify URI raises validation error."""
        with pytest.raises(ValueError, match="Invalid Spotify URI"):
            SpotifySample(name="Bad", spotify_uri="not-a-valid-uri")

    @pytest.mark.unit
    def test_invalid_track_id_length_raises_error(self):
        """Test that wrong track ID length raises validation error."""
        with pytest.raises(ValueError, match="Invalid Spotify URI"):
            SpotifySample(name="Bad", spotify_uri="spotify:track:tooshort")

    @pytest.mark.unit
    def test_serialization_roundtrip(self):
        """Test SpotifySample can be serialized and deserialized."""
        sample = SpotifySample(
            name="Test Track",
            spotify_uri="spotify:track:4iV5W9uYEdYUVa79Axb7Rh",
        )

        # Serialize to JSON
        json_data = sample.model_dump()
        assert json_data["type"] == "spotify"
        assert json_data["name"] == "Test Track"
        assert json_data["spotify_uri"] == "spotify:track:4iV5W9uYEdYUVa79Axb7Rh"

        # Deserialize from JSON
        restored = SpotifySample.model_validate(json_data)
        assert restored.name == sample.name
        assert restored.spotify_uri == sample.spotify_uri


class TestAudioSampleBackwardCompatibility:
    """Test AudioSample maintains backward compatibility."""

    @pytest.mark.unit
    def test_audio_sample_has_type_field(self, sample_audio_file):
        """Test AudioSample has type='audio' discriminator."""
        sample = AudioSample.from_file(sample_audio_file)
        assert sample.type == "audio"

    @pytest.mark.unit
    def test_audio_sample_serialization(self, sample_audio_file):
        """Test AudioSample serialization includes type field."""
        sample = AudioSample.from_file(sample_audio_file)
        json_data = sample.model_dump()

        assert json_data["type"] == "audio"
        assert "name" in json_data
        assert "path" in json_data


class TestSpotifyConfig:
    """Test SpotifyConfig model."""

    @pytest.mark.unit
    def test_default_config(self):
        """Test creating default SpotifyConfig."""
        config = SpotifyConfig()
        assert config.client_id is None
        assert config.redirect_uri == "http://localhost:8888/callback"
        assert config.access_token is None
        assert config.refresh_token is None
        assert config.is_configured is False
        assert config.is_authenticated is False

    @pytest.mark.unit
    def test_configured_check(self):
        """Test is_configured property."""
        config = SpotifyConfig(client_id="test_client_id")
        assert config.is_configured is True
        assert config.is_authenticated is False

    @pytest.mark.unit
    def test_authenticated_check(self):
        """Test is_authenticated property."""
        config = SpotifyConfig(
            client_id="test_client_id",
            access_token="test_token",
        )
        assert config.is_configured is True
        assert config.is_authenticated is True


class TestSpotifyService:
    """Test SpotifyService using Spotipy."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock Spotify config."""
        return SpotifyConfig(
            client_id="test_client_id",
            redirect_uri="http://localhost:8888/callback",
        )

    @pytest.fixture
    def temp_cache_path(self, temp_dir):
        """Create a temporary cache path."""
        return temp_dir / ".spotify_cache"

    @pytest.fixture
    def service_with_mocked_auth(self, mock_config, temp_cache_path):
        """Create SpotifyService with mocked auth manager."""
        with patch("launchsampler.services.spotify_service.SpotifyPKCE") as mock_pkce:
            # Mock the auth manager
            mock_auth = MagicMock()
            mock_auth.get_cached_token.return_value = {
                "access_token": "test_token",
                "refresh_token": "test_refresh",
                "expires_at": 9999999999,
            }
            mock_pkce.return_value = mock_auth

            service = SpotifyService(mock_config, cache_path=temp_cache_path)
            service._auth_manager = mock_auth

            # Mock the Spotify client
            mock_sp = MagicMock()
            service._sp = mock_sp

            yield service

            service.close()

    @pytest.mark.unit
    def test_service_creation_unconfigured(self):
        """Test creating unconfigured SpotifyService."""
        config = SpotifyConfig()
        service = SpotifyService(config)
        assert service.is_configured is False
        assert service.is_authenticated is False
        service.close()

    @pytest.mark.unit
    def test_service_creation_configured(self, mock_config, temp_cache_path):
        """Test creating configured SpotifyService."""
        with patch("launchsampler.services.spotify_service.SpotifyPKCE") as mock_pkce:
            mock_auth = MagicMock()
            mock_auth.get_cached_token.return_value = None  # Not authenticated yet
            mock_pkce.return_value = mock_auth

            service = SpotifyService(mock_config, cache_path=temp_cache_path)
            assert service.is_configured is True
            assert service.is_authenticated is False
            service.close()

    @pytest.mark.unit
    def test_authenticate_requires_client_id(self, temp_cache_path):
        """Test authenticate raises error without client_id."""
        config = SpotifyConfig()
        service = SpotifyService(config, cache_path=temp_cache_path)

        with pytest.raises(SpotifyAuthError, match="client_id not configured"):
            service.authenticate()

        service.close()

    @pytest.mark.unit
    def test_is_authenticated_with_cached_token(self, mock_config, temp_cache_path):
        """Test is_authenticated returns True when token is cached."""
        with patch("launchsampler.services.spotify_service.SpotifyPKCE") as mock_pkce:
            mock_auth = MagicMock()
            mock_auth.get_cached_token.return_value = {"access_token": "test_token"}
            mock_pkce.return_value = mock_auth

            service = SpotifyService(mock_config, cache_path=temp_cache_path)
            assert service.is_authenticated is True
            service.close()

    @pytest.mark.unit
    def test_toggle_playback_starts_when_stopped(self, service_with_mocked_auth):
        """Test toggle_playback starts track when nothing playing."""
        service = service_with_mocked_auth
        service._sp.current_playback.return_value = None

        result = service.toggle_playback("spotify:track:test123test123test12")

        service._sp.start_playback.assert_called_once_with(
            uris=["spotify:track:test123test123test12"], device_id=None
        )
        assert result is True

    @pytest.mark.unit
    def test_toggle_playback_stops_when_same_track_playing(self, service_with_mocked_auth):
        """Test toggle_playback stops (with seek to 0) when same track is playing."""
        service = service_with_mocked_auth
        service._sp.current_playback.return_value = {
            "item": {"uri": "spotify:track:test123test123test12"},
            "is_playing": True,
        }

        result = service.toggle_playback("spotify:track:test123test123test12")

        # stop() calls pause_playback and seek_track(0)
        service._sp.pause_playback.assert_called_once()
        service._sp.seek_track.assert_called_once_with(0)
        assert result is False

    @pytest.mark.unit
    def test_toggle_playback_starts_fresh_when_same_track_paused(self, service_with_mocked_auth):
        """Test toggle_playback starts from beginning when same track is paused."""
        service = service_with_mocked_auth
        service._sp.current_playback.return_value = {
            "item": {"uri": "spotify:track:test123test123test12"},
            "is_playing": False,
        }

        result = service.toggle_playback("spotify:track:test123test123test12")

        # Should start fresh from beginning, not resume
        service._sp.start_playback.assert_called_once_with(
            uris=["spotify:track:test123test123test12"], device_id=None
        )
        assert result is True

    @pytest.mark.unit
    def test_toggle_playback_switches_track(self, service_with_mocked_auth):
        """Test toggle_playback starts new track when different track playing."""
        service = service_with_mocked_auth
        service._sp.current_playback.return_value = {
            "item": {"uri": "spotify:track:differenttrack12345"},
            "is_playing": True,
        }

        result = service.toggle_playback("spotify:track:test123test123test12")

        service._sp.start_playback.assert_called_once_with(
            uris=["spotify:track:test123test123test12"], device_id=None
        )
        assert result is True

    @pytest.mark.unit
    def test_is_track_playing_true(self, service_with_mocked_auth):
        """Test is_track_playing returns True when track is playing."""
        service = service_with_mocked_auth
        service._sp.current_playback.return_value = {
            "item": {"uri": "spotify:track:test123test123test12"},
            "is_playing": True,
        }

        result = service.is_track_playing("spotify:track:test123test123test12")
        assert result is True

    @pytest.mark.unit
    def test_is_track_playing_false_different_track(self, service_with_mocked_auth):
        """Test is_track_playing returns False when different track playing."""
        service = service_with_mocked_auth
        service._sp.current_playback.return_value = {
            "item": {"uri": "spotify:track:differenttrack12345"},
            "is_playing": True,
        }

        result = service.is_track_playing("spotify:track:test123test123test12")
        assert result is False

    @pytest.mark.unit
    def test_is_track_playing_false_when_paused(self, service_with_mocked_auth):
        """Test is_track_playing returns False when track is paused."""
        service = service_with_mocked_auth
        service._sp.current_playback.return_value = {
            "item": {"uri": "spotify:track:test123test123test12"},
            "is_playing": False,
        }

        result = service.is_track_playing("spotify:track:test123test123test12")
        assert result is False

    @pytest.mark.unit
    def test_is_track_playing_false_when_no_state(self, service_with_mocked_auth):
        """Test is_track_playing returns False when nothing playing."""
        service = service_with_mocked_auth
        service._sp.current_playback.return_value = None

        result = service.is_track_playing("spotify:track:test123test123test12")
        assert result is False

    @pytest.mark.unit
    def test_play_track(self, service_with_mocked_auth):
        """Test play_track calls Spotipy correctly."""
        service = service_with_mocked_auth

        service.play_track("spotify:track:test123test123test12")

        service._sp.start_playback.assert_called_once_with(
            uris=["spotify:track:test123test123test12"], device_id=None
        )

    @pytest.mark.unit
    def test_play_track_with_device_id(self, service_with_mocked_auth):
        """Test play_track with specific device."""
        service = service_with_mocked_auth

        service.play_track("spotify:track:test123test123test12", device_id="device123")

        service._sp.start_playback.assert_called_once_with(
            uris=["spotify:track:test123test123test12"], device_id="device123"
        )

    @pytest.mark.unit
    def test_pause(self, service_with_mocked_auth):
        """Test pause calls Spotipy correctly."""
        service = service_with_mocked_auth

        service.pause()

        service._sp.pause_playback.assert_called_once()

    @pytest.mark.unit
    def test_stop(self, service_with_mocked_auth):
        """Test stop pauses and seeks to beginning."""
        service = service_with_mocked_auth

        service.stop()

        service._sp.pause_playback.assert_called_once()
        service._sp.seek_track.assert_called_once_with(0)

    @pytest.mark.unit
    def test_resume(self, service_with_mocked_auth):
        """Test resume calls Spotipy correctly."""
        service = service_with_mocked_auth

        service.resume()

        service._sp.start_playback.assert_called_once()

    @pytest.mark.unit
    def test_get_available_devices(self, service_with_mocked_auth):
        """Test get_available_devices returns device list."""
        service = service_with_mocked_auth
        service._sp.devices.return_value = {
            "devices": [
                {"id": "device1", "name": "My Speaker", "type": "Speaker", "is_active": True},
                {"id": "device2", "name": "Phone", "type": "Smartphone", "is_active": False},
            ]
        }

        devices = service.get_available_devices()

        assert len(devices) == 2
        assert devices[0]["name"] == "My Speaker"
        assert devices[1]["name"] == "Phone"

    @pytest.mark.unit
    def test_context_manager(self, mock_config, temp_cache_path):
        """Test SpotifyService as context manager."""
        with patch("launchsampler.services.spotify_service.SpotifyPKCE"):
            with SpotifyService(mock_config, cache_path=temp_cache_path) as service:
                assert service.is_configured is True
            # Service should be closed after exiting context
