"""Shared test fixtures for spotify-playlist-creator tests."""

import pytest


@pytest.fixture
def mock_spotify_track():
    """Factory for creating mock Spotify track objects.

    Returns a function that creates track dictionaries matching
    the Spotify API response structure.
    """
    def _create(
        name,
        artist,
        album="Test Album",
        popularity=50,
        track_id="abc123"
    ):
        return {
            "id": track_id,
            "name": name,
            "artists": [{"name": artist}],
            "album": {"name": album},
            "popularity": popularity
        }
    return _create


@pytest.fixture
def mock_search_response():
    """Factory for creating mock sp.search() responses.

    Returns a function that wraps a list of tracks in the
    Spotify search response structure.
    """
    def _create(tracks):
        return {"tracks": {"items": tracks}}
    return _create
