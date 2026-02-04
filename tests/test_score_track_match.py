"""Tests for score_track_match() function."""

import pytest

from spotify_playlist import score_track_match, KARAOKE_KEYWORDS


class TestScoreTrackMatchScoring:
    """Test the scoring logic in score_track_match()."""

    def test_exact_match_high_popularity(self, mock_spotify_track):
        """Exact match with max popularity scores 80 points (40 artist + 30 title + 10 popularity)."""
        track = mock_spotify_track(
            name="Bohemian Rhapsody",
            artist="Queen",
            popularity=100
        )

        score, name, artist = score_track_match(track, "Bohemian Rhapsody", "Queen")

        assert score == pytest.approx(80.0, abs=0.1)
        assert name == "Bohemian Rhapsody"
        assert artist == "Queen"

    def test_partial_artist_match(self, mock_spotify_track):
        """Partial artist name match reduces artist score component."""
        track = mock_spotify_track(
            name="Imagine",
            artist="John Lennon",
            popularity=50
        )

        score_full, _, _ = score_track_match(track, "Imagine", "John Lennon")
        score_partial, _, _ = score_track_match(track, "Imagine", "Lennon")

        # Partial match should score lower than full match
        assert score_partial < score_full

    def test_zero_popularity(self, mock_spotify_track):
        """Track with zero popularity scores 70 points (40 artist + 30 title + 0 popularity)."""
        track = mock_spotify_track(
            name="Test Song",
            artist="Test Artist",
            popularity=0
        )

        score, _, _ = score_track_match(track, "Test Song", "Test Artist")

        assert score == pytest.approx(70.0, abs=0.1)

    def test_case_insensitive_matching(self, mock_spotify_track):
        """Matching is case-insensitive for both title and artist."""
        track = mock_spotify_track(
            name="BOHEMIAN RHAPSODY",
            artist="QUEEN",
            popularity=50
        )

        score, _, _ = score_track_match(track, "bohemian rhapsody", "queen")

        assert score >= 70


class TestScoreTrackMatchKaraokePenalty:
    """Test karaoke keyword detection and penalty."""

    def test_karaoke_in_title(self, mock_spotify_track):
        """Karaoke keyword in title applies -50 penalty."""
        track = mock_spotify_track(
            name="Bohemian Rhapsody (Karaoke Version)",
            artist="Queen",
            popularity=50
        )

        score, _, _ = score_track_match(track, "Bohemian Rhapsody", "Queen")

        # Score should be significantly reduced (possibly negative)
        assert score < 30

    def test_karaoke_in_artist(self, mock_spotify_track):
        """Karaoke keyword in artist name applies -50 penalty."""
        track = mock_spotify_track(
            name="Bohemian Rhapsody",
            artist="Karaoke Kings",
            popularity=50
        )

        score, _, _ = score_track_match(track, "Bohemian Rhapsody", "Queen")

        assert score < 30

    def test_karaoke_in_album(self, mock_spotify_track):
        """Karaoke keyword in album name applies -50 penalty."""
        track = mock_spotify_track(
            name="Bohemian Rhapsody",
            artist="Queen",
            album="Karaoke Hits Vol 1",
            popularity=50
        )

        score, _, _ = score_track_match(track, "Bohemian Rhapsody", "Queen")

        assert score < 30

    def test_cover_keyword_detected(self, mock_spotify_track):
        """'cover' keyword also triggers penalty."""
        track = mock_spotify_track(
            name="Bohemian Rhapsody (Cover)",
            artist="Some Band",
            popularity=50
        )

        score, _, _ = score_track_match(track, "Bohemian Rhapsody", "Queen")

        assert score < 30

    def test_all_karaoke_keywords_are_checked(self):
        """Verify KARAOKE_KEYWORDS constant contains expected keywords."""
        expected_keywords = {
            "karaoke", "instrumental", "backing track", "cover",
            "tribute", "in the style of", "made famous by",
            "originally performed", "sing along", "minus one"
        }
        assert KARAOKE_KEYWORDS == expected_keywords


class TestScoreTrackMatchEdgeCases:
    """Test edge cases and defensive handling."""

    def test_missing_artists_array(self):
        """Handles track with missing artists array gracefully."""
        track = {
            "id": "abc123",
            "name": "Test Song",
            "artists": None,
            "album": {"name": "Test Album"},
            "popularity": 50
        }

        score, name, artist = score_track_match(track, "Test Song", "Test Artist")

        assert artist == ""
        assert name == "Test Song"
        assert score < 40

    def test_empty_artists_array(self):
        """Handles track with empty artists array gracefully."""
        track = {
            "id": "abc123",
            "name": "Test Song",
            "artists": [],
            "album": {"name": "Test Album"},
            "popularity": 50
        }

        score, name, artist = score_track_match(track, "Test Song", "Test Artist")

        assert artist == ""
        assert score < 40

    def test_missing_album(self):
        """Handles track with missing album field gracefully."""
        track = {
            "id": "abc123",
            "name": "Test Song",
            "artists": [{"name": "Test Artist"}],
            "popularity": 50
        }

        score, name, artist = score_track_match(track, "Test Song", "Test Artist")

        assert score >= 70

    def test_missing_popularity(self):
        """Handles track with missing popularity field, defaults to 0."""
        track = {
            "id": "abc123",
            "name": "Test Song",
            "artists": [{"name": "Test Artist"}],
            "album": {"name": "Test Album"}
        }

        score, name, artist = score_track_match(track, "Test Song", "Test Artist")

        assert score == pytest.approx(70.0, abs=0.1)
