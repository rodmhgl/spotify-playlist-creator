"""Tests for parse_tsv() function."""

import pytest

from spotify_playlist import parse_tsv


class TestParseTsvErrors:
    """Test error handling in parse_tsv()."""

    def test_file_not_found(self):
        """parse_tsv exits with code 1 when file does not exist."""
        with pytest.raises(SystemExit) as exc_info:
            parse_tsv("/nonexistent/path/to/file.tsv")
        assert exc_info.value.code == 1

    def test_empty_file(self, tmp_path):
        """parse_tsv exits with code 1 for empty file."""
        tsv_file = tmp_path / "empty.tsv"
        tsv_file.write_text("")

        with pytest.raises(SystemExit) as exc_info:
            parse_tsv(str(tsv_file))
        assert exc_info.value.code == 1

    def test_header_only(self, tmp_path):
        """parse_tsv exits with code 1 when file contains only header row."""
        tsv_file = tmp_path / "header_only.tsv"
        tsv_file.write_text("Title\tArtist\n")

        with pytest.raises(SystemExit) as exc_info:
            parse_tsv(str(tsv_file))
        assert exc_info.value.code == 1

    def test_insufficient_columns(self, tmp_path):
        """parse_tsv exits with code 1 when row has fewer than 2 columns."""
        tsv_file = tmp_path / "bad_columns.tsv"
        tsv_file.write_text("Title\tArtist\nOnly One Column\n")

        with pytest.raises(SystemExit) as exc_info:
            parse_tsv(str(tsv_file))
        assert exc_info.value.code == 1

    def test_empty_title(self, tmp_path):
        """parse_tsv exits with code 1 when title is empty."""
        tsv_file = tmp_path / "empty_title.tsv"
        tsv_file.write_text("Title\tArtist\n\tQueen\n")

        with pytest.raises(SystemExit) as exc_info:
            parse_tsv(str(tsv_file))
        assert exc_info.value.code == 1

    def test_empty_artist(self, tmp_path):
        """parse_tsv exits with code 1 when artist is empty."""
        tsv_file = tmp_path / "empty_artist.tsv"
        tsv_file.write_text("Title\tArtist\nBohemian Rhapsody\t\n")

        with pytest.raises(SystemExit) as exc_info:
            parse_tsv(str(tsv_file))
        assert exc_info.value.code == 1

    def test_whitespace_only_fields(self, tmp_path):
        """parse_tsv exits with code 1 when fields contain only whitespace."""
        tsv_file = tmp_path / "whitespace.tsv"
        tsv_file.write_text("Title\tArtist\n   \tQueen\n")

        with pytest.raises(SystemExit) as exc_info:
            parse_tsv(str(tsv_file))
        assert exc_info.value.code == 1


class TestParseTsvSuccess:
    """Test successful parsing scenarios."""

    def test_valid_tsv(self, tmp_path):
        """parse_tsv returns list of (title, artist) tuples for valid input."""
        tsv_file = tmp_path / "valid.tsv"
        tsv_file.write_text(
            "Title\tArtist\n"
            "Bohemian Rhapsody\tQueen\n"
            "Hotel California\tEagles\n"
        )

        result = parse_tsv(str(tsv_file))

        assert result == [
            ("Bohemian Rhapsody", "Queen"),
            ("Hotel California", "Eagles"),
        ]

    def test_extra_columns_ignored(self, tmp_path):
        """parse_tsv ignores columns beyond Title and Artist."""
        tsv_file = tmp_path / "extra_cols.tsv"
        tsv_file.write_text(
            "Title\tArtist\tAlbum\tYear\n"
            "Imagine\tJohn Lennon\tImagine\t1971\n"
        )

        result = parse_tsv(str(tsv_file))

        assert result == [("Imagine", "John Lennon")]

    def test_whitespace_trimmed(self, tmp_path):
        """parse_tsv strips leading/trailing whitespace from title and artist."""
        tsv_file = tmp_path / "whitespace.tsv"
        tsv_file.write_text(
            "Title\tArtist\n"
            "  Thriller  \t  Michael Jackson  \n"
        )

        result = parse_tsv(str(tsv_file))

        assert result == [("Thriller", "Michael Jackson")]

    def test_multiple_tracks(self, tmp_path):
        """parse_tsv handles multiple tracks correctly."""
        tsv_file = tmp_path / "multiple.tsv"
        tsv_file.write_text(
            "Title\tArtist\n"
            "Track 1\tArtist A\n"
            "Track 2\tArtist B\n"
            "Track 3\tArtist C\n"
        )

        result = parse_tsv(str(tsv_file))

        assert result == [
            ("Track 1", "Artist A"),
            ("Track 2", "Artist B"),
            ("Track 3", "Artist C"),
        ]
