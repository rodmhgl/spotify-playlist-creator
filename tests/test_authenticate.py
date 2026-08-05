"""Tests for authenticate() handling of revoked cached tokens."""

from unittest.mock import MagicMock, patch

import pytest
from spotipy.oauth2 import SpotifyOauthError

from spotify_playlist import authenticate


@pytest.fixture
def revoked_auth_manager():
    """SpotifyOAuth mock whose cached token refresh fails as revoked."""
    manager = MagicMock()
    manager.get_cached_token.side_effect = SpotifyOauthError(
        "error: invalid_grant, error_description: Refresh token revoked"
    )
    return manager


class TestAuthenticateRevokedToken:
    """A revoked cached token should warn and fall back to fresh authorization."""

    def test_warns_and_reprompts_on_revoked_token(
        self, revoked_auth_manager, capsys, tmp_path, monkeypatch
    ):
        """SpotifyOauthError from the cache triggers a warning and the OAuth prompt."""
        monkeypatch.setenv("SPOTIFY_CACHE_PATH", str(tmp_path / ".spotify_cache"))
        mock_sp = MagicMock()

        with patch("spotify_playlist.SpotifyOAuth", return_value=revoked_auth_manager), \
             patch("spotify_playlist._get_authorization_code", return_value="fresh_code") as mock_prompt, \
             patch("spotify_playlist.spotipy.Spotify", return_value=mock_sp):
            result = authenticate("client_id", "client_secret")

        mock_prompt.assert_called_once_with(revoked_auth_manager)
        revoked_auth_manager.get_access_token.assert_called_once_with("fresh_code")
        assert result is mock_sp

        captured = capsys.readouterr()
        assert "revoked" in captured.err.lower()

    def test_removes_stale_cache_file_on_revoked_token(
        self, revoked_auth_manager, tmp_path, monkeypatch
    ):
        """The dead cache file is deleted so spotipy doesn't retry the revoked token."""
        cache_file = tmp_path / ".spotify_cache"
        cache_file.write_text('{"refresh_token": "revoked"}')
        monkeypatch.setenv("SPOTIFY_CACHE_PATH", str(cache_file))

        with patch("spotify_playlist.SpotifyOAuth", return_value=revoked_auth_manager), \
             patch("spotify_playlist._get_authorization_code", return_value="fresh_code"), \
             patch("spotify_playlist.spotipy.Spotify", return_value=MagicMock()):
            authenticate("client_id", "client_secret")

        assert not cache_file.exists()

    def test_missing_cache_file_does_not_crash(
        self, revoked_auth_manager, tmp_path, monkeypatch
    ):
        """Revocation handling works even if the cache file is already gone."""
        monkeypatch.setenv("SPOTIFY_CACHE_PATH", str(tmp_path / "nonexistent_cache"))

        with patch("spotify_playlist.SpotifyOAuth", return_value=revoked_auth_manager), \
             patch("spotify_playlist._get_authorization_code", return_value="fresh_code"), \
             patch("spotify_playlist.spotipy.Spotify", return_value=MagicMock()):
            result = authenticate("client_id", "client_secret")

        assert result is not None
