"""Tests for search_track() function and related helpers."""

from unittest.mock import MagicMock

import pytest
import spotipy

from spotify_playlist import search_track, _execute_search, _find_best_match


class TestSearchTrackTwoPassStrategy:
    """Test the two-pass search strategy."""

    def test_both_searches_executed(self, mock_spotify_track, mock_search_response):
        """Both search queries are executed."""
        track1 = mock_spotify_track(
            name="Bohemian Rhapsody",
            artist="Queen",
            track_id="track1",
            popularity=80
        )
        track2 = mock_spotify_track(
            name="Bohemian Rhapsody - Remastered",
            artist="Queen",
            track_id="track2",
            popularity=70
        )

        mock_sp = MagicMock()
        # First query returns track1, second returns track2
        mock_sp.search.side_effect = [
            mock_search_response([track1]),
            mock_search_response([track2])
        ]

        result = search_track(mock_sp, "Bohemian Rhapsody", "Queen")

        assert mock_sp.search.call_count == 2
        # First call uses field specifiers
        first_query = mock_sp.search.call_args_list[0][1]["q"]
        assert "track:" in first_query and "artist:" in first_query
        # Second call is plain text
        second_query = mock_sp.search.call_args_list[1][1]["q"]
        assert "track:" not in second_query

    def test_best_match_selected(self, mock_spotify_track, mock_search_response):
        """Best scored track is returned from all candidates."""
        low_score_track = mock_spotify_track(
            name="Bohemian Rhapsody",
            artist="Some Cover Band",
            track_id="low",
            popularity=20
        )
        high_score_track = mock_spotify_track(
            name="Bohemian Rhapsody",
            artist="Queen",
            track_id="high",
            popularity=90
        )

        mock_sp = MagicMock()
        mock_sp.search.side_effect = [
            mock_search_response([low_score_track]),
            mock_search_response([high_score_track])
        ]

        track_id, score, title, artist = search_track(mock_sp, "Bohemian Rhapsody", "Queen")

        assert track_id == "high"
        assert artist == "Queen"


class TestSearchTrackDuplicateFiltering:
    """Test duplicate track filtering."""

    def test_duplicate_tracks_filtered(self, mock_spotify_track, mock_search_response):
        """Same track ID appearing in both searches is only scored once."""
        track = mock_spotify_track(
            name="Bohemian Rhapsody",
            artist="Queen",
            track_id="same_id",
            popularity=80
        )

        mock_sp = MagicMock()
        mock_sp.search.side_effect = [
            mock_search_response([track]),
            mock_search_response([track])
        ]

        track_id, score, title, artist = search_track(mock_sp, "Bohemian Rhapsody", "Queen")

        assert track_id == "same_id"
        assert title == "Bohemian Rhapsody"


class TestSearchTrackNoResults:
    """Test handling when no results are found."""

    def test_no_results_from_either_search(self, mock_search_response):
        """Returns None tuple when neither search finds results."""
        mock_sp = MagicMock()
        mock_sp.search.side_effect = [
            mock_search_response([]),
            mock_search_response([])
        ]

        track_id, score, title, artist = search_track(mock_sp, "Nonexistent Song", "Unknown Artist")

        assert track_id is None
        assert score == 0
        assert title is None
        assert artist is None

    def test_all_results_below_threshold(self, mock_spotify_track, mock_search_response):
        """Returns None when all candidates score <= 0 (e.g., karaoke tracks)."""
        karaoke_track = mock_spotify_track(
            name="Test Song (Karaoke Version)",
            artist="Karaoke Band",
            track_id="karaoke",
            popularity=50
        )

        mock_sp = MagicMock()
        mock_sp.search.side_effect = [
            mock_search_response([karaoke_track]),
            mock_search_response([])
        ]

        track_id, score, title, artist = search_track(mock_sp, "Test Song", "Original Artist")

        assert track_id is None


class TestSearchTrackErrorHandling:
    """Test error handling during search."""

    def test_first_search_fails_continues_to_second(
        self, mock_spotify_track, mock_search_response, capsys
    ):
        """When first search fails, second search still executes."""
        track = mock_spotify_track(
            name="Test Song",
            artist="Test Artist",
            track_id="found",
            popularity=80
        )

        mock_sp = MagicMock()
        # First search raises exception, second succeeds
        mock_sp.search.side_effect = [
            spotipy.SpotifyException(http_status=500, code=-1, msg="Server error"),
            mock_search_response([track])
        ]

        track_id, score, title, artist = search_track(mock_sp, "Test Song", "Test Artist")

        # Should find track from second search
        assert track_id == "found"

        # Error should be logged
        captured = capsys.readouterr()
        assert "Spotify API error" in captured.err


class TestExecuteSearch:
    """Test the _execute_search helper function."""

    def test_returns_track_items(self, mock_spotify_track, mock_search_response):
        """Returns items array from search response."""
        track = mock_spotify_track(name="Test", artist="Artist", track_id="123")
        mock_sp = MagicMock()
        mock_sp.search.return_value = mock_search_response([track])

        result = _execute_search(mock_sp, "test query", "Test")

        assert len(result) == 1
        assert result[0]["id"] == "123"

    def test_returns_empty_list_on_error(self, capsys):
        """Returns empty list when Spotify API raises exception."""
        mock_sp = MagicMock()
        mock_sp.search.side_effect = spotipy.SpotifyException(
            http_status=429, code=-1, msg="Rate limited"
        )

        result = _execute_search(mock_sp, "test query", "Test")

        assert result == []


class TestFindBestMatch:
    """Test the _find_best_match helper function."""

    def test_returns_highest_scored_track(self, mock_spotify_track):
        """Returns track with highest score."""
        low = mock_spotify_track(name="Wrong Song", artist="Wrong Artist", track_id="low", popularity=90)
        high = mock_spotify_track(name="Right Song", artist="Right Artist", track_id="high", popularity=80)

        result = _find_best_match([low, high], "Right Song", "Right Artist")

        assert result[0] == "high"

    def test_returns_none_for_empty_candidates(self):
        """Returns None tuple for empty candidate list."""
        result = _find_best_match([], "Song", "Artist")

        assert result == (None, 0, None, None)

    def test_returns_none_when_all_scores_zero_or_below(self, mock_spotify_track):
        """Returns None when all candidates have score <= 0."""
        karaoke = mock_spotify_track(
            name="Song (Karaoke)",
            artist="Karaoke Kings",
            track_id="karaoke",
            popularity=50
        )

        result = _find_best_match([karaoke], "Song", "Original Artist")

        assert result == (None, 0, None, None)
