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

# Keywords that indicate non-original versions (karaoke, covers, etc.)
KARAOKE_KEYWORDS = {
    "karaoke", "instrumental", "backing track", "cover",
    "tribute", "in the style of", "made famous by",
    "originally performed", "sing along", "minus one"
}
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth


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


def authenticate(client_id, client_secret):
    """Authenticate with Spotify and return client."""
    try:
        auth_manager = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri="http://127.0.0.1:8888/callback",
            scope="playlist-modify-public playlist-modify-private",
            cache_path=".spotify_cache",
            open_browser=False
        )

        # Check if we have a cached token
        token_info = auth_manager.get_cached_token()
        if not token_info:
            auth_url = auth_manager.get_authorize_url()
            print(f"\nOpen this URL in your browser to authorize:\n{auth_url}\n")
            response_url = input("Paste the redirect URL here: ").strip()

            code = auth_manager.parse_response_code(response_url)
            auth_manager.get_access_token(code)

        sp = spotipy.Spotify(auth_manager=auth_manager)
        sp.current_user()
        return sp
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

    Returns (score, track_name, artist_name) tuple.
    """
    track_name = track["name"]
    artist_name = track["artists"][0]["name"]
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
    for keyword in KARAOKE_KEYWORDS:
        if keyword in combined_text:
            score -= 50
            break

    return max(0, score), track_name, artist_name


def search_track(sp, title, artist):
    """
    Search for a track on Spotify using two-pass strategy with scoring.

    Fetches multiple results from each search and scores them to find
    the best match, filtering out karaoke/cover versions.

    Returns (track_id, score, matched_title, matched_artist) if found,
    (None, 0, None, None) otherwise.
    """
    candidates = []

    # First pass: field-specific search
    query = f'track:{title} artist:{artist}'
    results = sp.search(q=query, type="track", limit=10)
    candidates.extend(results["tracks"]["items"])

    # Second pass: fallback search (may find different results)
    fallback_query = f'{title} {artist}'
    results = sp.search(q=fallback_query, type="track", limit=10)
    for track in results["tracks"]["items"]:
        if track["id"] not in [c["id"] for c in candidates]:
            candidates.append(track)

    if not candidates:
        return None, 0, None, None

    # Score all candidates and pick the best
    best_score = -1
    best_track = None
    best_name = None
    best_artist = None

    for track in candidates:
        score, track_name, artist_name = score_track_match(track, title, artist)
        if score > best_score:
            best_score = score
            best_track = track
            best_name = track_name
            best_artist = artist_name

    return best_track["id"], best_score, best_name, best_artist


def create_playlist(sp, track_ids, name, public, description):
    """
    Create a Spotify playlist and add tracks.

    Returns the playlist URL.
    """
    user_id = sp.current_user()["id"]

    playlist = sp.user_playlist_create(
        user=user_id,
        name=name,
        public=public,
        description=description
    )

    playlist_id = playlist["id"]

    for i in range(0, len(track_ids), 100):
        batch = track_ids[i:i + 100]
        sp.playlist_add_items(playlist_id, batch)

    return playlist["external_urls"]["spotify"]


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
        print(f'Created playlist: "{args.name}"')
        print(f"URL: {url}")
    else:
        print("No tracks found. Playlist not created.")

    if not_found:
        print(f"\nNot found ({len(not_found)} tracks):")
        for title, artist in not_found:
            print(f'  - "{title}" by {artist}')


if __name__ == "__main__":
    main()
