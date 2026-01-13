#!/usr/bin/env python3
"""
Spotify Playlist Creator - Create Spotify playlists from TSV files.
"""

import argparse
import csv
import os
import sys
from difflib import SequenceMatcher

import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

# Keywords that indicate non-original versions (karaoke, covers, etc.)
KARAOKE_KEYWORDS = {
    "karaoke", "instrumental", "backing track", "cover",
    "tribute", "in the style of", "made famous by",
    "originally performed", "sing along", "minus one"
}


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Create a Spotify playlist from a TSV file of songs."
    )
    parser.add_argument("input_file", help="Path to TSV file with Title and Artist columns")
    parser.add_argument(
        "-n", "--name",
        required=True,
        help="Name for the new Spotify playlist"
    )
    parser.add_argument(
        "-p", "--public",
        action="store_true",
        help="Make the playlist public (default: private)"
    )
    parser.add_argument(
        "-d", "--description",
        default="Created by Spotify Playlist Creator",
        help="Playlist description"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Search for tracks and report results without creating a playlist"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed progress during execution"
    )
    return parser.parse_args()


def validate_env():
    """Validate required environment variables are set."""
    load_dotenv()

    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

    missing = []
    if not client_id:
        missing.append("SPOTIFY_CLIENT_ID")
    if not client_secret:
        missing.append("SPOTIFY_CLIENT_SECRET")

    if missing:
        print(f"Error: Missing required environment variable(s): {', '.join(missing)}", file=sys.stderr)
        print("Get credentials at https://developer.spotify.com/dashboard", file=sys.stderr)
        sys.exit(1)

    return client_id, client_secret


def parse_tsv(filepath):
    """
    Parse TSV file and extract track information.

    Returns list of (title, artist) tuples.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            rows = list(reader)
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    if len(rows) <= 1:
        print("Error: Input file is empty or contains only a header row", file=sys.stderr)
        sys.exit(1)

    tracks = []
    for line_num, row in enumerate(rows[1:], start=2):
        if len(row) < 2:
            print(f"Error: Invalid row at line {line_num}: expected at least 2 columns (Title, Artist)", file=sys.stderr)
            sys.exit(1)

        title = row[0].strip()
        artist = row[1].strip()

        if not title or not artist:
            print(f"Error: Empty title or artist at line {line_num}", file=sys.stderr)
            sys.exit(1)

        tracks.append((title, artist))

    return tracks


def _get_authorization_code(auth_manager):
    """
    Prompt user for OAuth authorization and return the authorization code.
    Exits with error if authorization fails.
    """
    auth_url = auth_manager.get_authorize_url()
    print(f"\nOpen this URL in your browser to authorize:\n{auth_url}\n")
    response_url = input("Paste the redirect URL here: ").strip()

    if not response_url:
        print(
            "Error: No redirect URL provided. "
            "After approving access, copy the full URL from your browser.",
            file=sys.stderr
        )
        sys.exit(1)

    try:
        code = auth_manager.parse_response_code(response_url)
        if not code:
            raise ValueError("No code in response")
        return code
    except Exception:
        print(
            "Error: Could not extract authorization code from URL. "
            "Paste the full URL from your browser's address bar.",
            file=sys.stderr
        )
        sys.exit(1)


def _handle_spotify_auth_error(error):
    """Print appropriate error message for Spotify authentication errors and exit."""
    error_messages = {
        401: "Invalid or expired credentials. Check your client ID/secret.",
        403: "Insufficient permissions. Ensure app has required scopes.",
    }
    message = error_messages.get(error.http_status, f"Spotify API error ({error.http_status}): {error.msg}")
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def authenticate(client_id, client_secret):
    """Authenticate with Spotify and return client."""
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
    cache_path = os.getenv("SPOTIFY_CACHE_PATH", ".spotify_cache")

    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope="playlist-modify-public playlist-modify-private",
        cache_path=cache_path,
        open_browser=False
    )

    if not auth_manager.get_cached_token():
        code = _get_authorization_code(auth_manager)
        auth_manager.get_access_token(code)

    try:
        sp = spotipy.Spotify(auth_manager=auth_manager)
        sp.current_user()
        return sp
    except spotipy.SpotifyException as e:
        _handle_spotify_auth_error(e)
    except Exception as e:
        print(f"Error: Spotify authentication failed: {e}", file=sys.stderr)
        sys.exit(1)


def score_track_match(track, expected_title, expected_artist):
    """
    Score how well a Spotify track matches the expected title and artist.

    Scoring breakdown:
    - Artist similarity: 0-40 points (fuzzy match)
    - Title similarity: 0-30 points (fuzzy match)
    - Popularity bonus: 0-10 points (scaled from Spotify's 0-100)
    - Karaoke keyword penalty: -50 points if detected

    Scores can be negative (karaoke tracks). Tracks with score <= 0 are excluded.

    Returns (score, track_name, artist_name) tuple.
    """
    track_name = track["name"]
    artists = track.get("artists") or []
    artist_name = artists[0].get("name", "") if artists else ""
    album_name = track.get("album", {}).get("name", "")
    popularity = track.get("popularity", 0)

    score = 0.0

    # Artist similarity (0-40 points)
    artist_ratio = SequenceMatcher(
        None, expected_artist.lower(), artist_name.lower()
    ).ratio()
    score += artist_ratio * 40

    # Title similarity (0-30 points)
    title_ratio = SequenceMatcher(
        None, expected_title.lower(), track_name.lower()
    ).ratio()
    score += title_ratio * 30

    # Popularity bonus (0-10 points)
    score += popularity / 10

    # Karaoke keyword penalty (-50 points)
    combined_text = f"{track_name} {artist_name} {album_name}".lower()
    if any(keyword in combined_text for keyword in KARAOKE_KEYWORDS):
        score -= 50

    return score, track_name, artist_name


def _execute_search(sp, query, title):
    """Execute a Spotify search and return track results, handling errors gracefully."""
    try:
        results = sp.search(q=query, type="track", limit=10)
        return results["tracks"]["items"]
    except spotipy.SpotifyException as e:
        print(f"Spotify API error searching for '{title}': {e.msg}", file=sys.stderr)
    except Exception as e:
        print(f"Error searching for '{title}': {e}", file=sys.stderr)
    return []


def _find_best_match(candidates, title, artist):
    """
    Score all candidate tracks and return the best match above threshold.

    Returns (track_id, score, matched_title, matched_artist) or (None, 0, None, None).
    """
    best_score = 0
    best_match = None

    for track in candidates:
        score, track_name, artist_name = score_track_match(track, title, artist)
        if score > best_score:
            best_score = score
            best_match = (track["id"], score, track_name, artist_name)

    return best_match if best_match else (None, 0, None, None)


def search_track(sp, title, artist):
    """
    Search for a track on Spotify using two-pass strategy with scoring.

    Fetches multiple results from each search and scores them to find
    the best match, filtering out karaoke/cover versions.

    Returns (track_id, score, matched_title, matched_artist) if found,
    (None, 0, None, None) otherwise.
    """
    candidates = []
    seen_ids = set()

    queries = [
        f'track:{title} artist:{artist}',
        f'{title} {artist}',
    ]

    for query in queries:
        for track in _execute_search(sp, query, title):
            if track["id"] not in seen_ids:
                candidates.append(track)
                seen_ids.add(track["id"])

    if not candidates:
        return None, 0, None, None

    return _find_best_match(candidates, title, artist)


def _add_tracks_in_batches(sp, playlist_id, track_ids):
    """Add tracks to playlist in batches of 100, reporting any failures."""
    tracks_added = 0
    batch_size = 100

    for i in range(0, len(track_ids), batch_size):
        batch = track_ids[i:i + batch_size]
        try:
            sp.playlist_add_items(playlist_id, batch)
            tracks_added += len(batch)
        except spotipy.SpotifyException as e:
            batch_num = i // batch_size + 1
            print(f"Error adding tracks (batch {batch_num}): {e.msg}", file=sys.stderr)
            print(f"Added {tracks_added}/{len(track_ids)} tracks before failure.", file=sys.stderr)
            break

    return tracks_added


def create_playlist(sp, track_ids, name, public, description):
    """
    Create a Spotify playlist and add tracks.

    Returns the playlist URL, or None if creation failed.
    """
    try:
        user_id = sp.current_user()["id"]
        playlist = sp.user_playlist_create(
            user=user_id,
            name=name,
            public=public,
            description=description
        )

        _add_tracks_in_batches(sp, playlist["id"], track_ids)
        return playlist["external_urls"]["spotify"]

    except spotipy.SpotifyException as e:
        error_messages = {
            403: "Permission denied. Check playlist creation permissions.",
        }
        message = error_messages.get(e.http_status, f"Spotify API error: {e.msg}")
        print(f"Error: {message}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error creating playlist: {e}", file=sys.stderr)
        return None


def main():
    args = parse_args()
    client_id, client_secret = validate_env()
    tracks = parse_tsv(args.input_file)

    print(f"Searching for {len(tracks)} tracks...")

    sp = authenticate(client_id, client_secret)

    found_ids = []
    not_found = []
    total = len(tracks)

    for idx, (title, artist) in enumerate(tracks, start=1):
        track_id, score, matched_title, matched_artist = search_track(sp, title, artist)
        if track_id:
            found_ids.append(track_id)
            if args.verbose:
                print(f'[{idx}/{total}] Found: "{matched_title}" by {matched_artist} (score: {score:.0f})')
        else:
            not_found.append((title, artist))
            if args.verbose:
                print(f'[{idx}/{total}] NOT FOUND: "{title}" by {artist}')

    print(f"Found: {len(found_ids)}/{len(tracks)} tracks")

    if args.dry_run:
        print("Dry run complete. No playlist created.")
        print(f'Would have added {len(found_ids)} tracks to playlist "{args.name}"')
    elif found_ids:
        url = create_playlist(sp, found_ids, args.name, args.public, args.description)
        if url:
            print(f'Created playlist: "{args.name}"')
            print(f"URL: {url}")
        else:
            print("Failed to create playlist.", file=sys.stderr)
    else:
        print("No tracks found. Playlist not created.")

    if not_found:
        print(f"\nNot found ({len(not_found)} tracks):")
        for title, artist in not_found:
            print(f'  - "{title}" by {artist}')


if __name__ == "__main__":
    main()
