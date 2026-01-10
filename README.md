# Spotify Playlist Creator

Create Spotify playlists from TSV files containing song titles and artists.

## Prerequisites

You need Python 3.9 or later and a Spotify Developer account. The app requires two OAuth scopes: `playlist-modify-public` and `playlist-modify-private`.

## Installation

```bash
pip install -r requirements.txt
```

## Spotify API Setup

Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) and create a new app. Set the redirect URI to `http://127.0.0.1:8888/callback` in your app settings.

Copy the Client ID and Client Secret from your app. Set them as environment variables or create a `.env` file in the project directory:

```
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
```

On first run, the tool will prompt you to authorize via browser. After authorization, the token is cached to `.spotify_cache` for subsequent runs.

## Usage

```bash
python spotify_playlist.py <input_file> --name "<playlist_name>" [options]
```

Options:
- `-n, --name` (required) — Playlist name
- `-p, --public` — Make playlist public (default: private)
- `-d, --description` — Custom description
- `--dry-run` — Search without creating the playlist
- `-v, --verbose` — Show per-track search results

The input file should be tab-separated with a header row:

```
Title	Artist
Earth Angel	The Penguins
Stand by Me	Ben E. King
Bohemian Rhapsody	Queen
```

Additional columns after Artist are ignored.

## Behavior Notes

**Track matching**: The search uses a scoring system to filter out karaoke and cover versions. Tracks containing keywords like "karaoke", "instrumental", "cover", or "tribute" are heavily penalized.

**Missing tracks**: When a track is not found, the tool skips it and continues. All unfound tracks are listed at the end. The exit code is 0 even if some tracks were not found. Exit code 1 is reserved for configuration errors (missing credentials, bad input file, auth failure).

**Duplicates**: Not deduplicated. If your input contains the same song twice, it appears twice in the playlist.

## Example

Given `tracks.tsv`:

```
Title	Artist
Hotel California	Eagles
Imagine	John Lennon
Stairway to Heaven	Led Zeppelin
```

Run:

```bash
python spotify_playlist.py tracks.tsv -n "Classic Rock" -v
```

Output:

```
Searching for 3 tracks...
[1/3] Found: "Hotel California - 2013 Remaster" by Eagles (score: 78)
[2/3] Found: "Imagine - Remastered 2010" by John Lennon (score: 80)
[3/3] Found: "Stairway to Heaven - Remaster" by Led Zeppelin (score: 79)
Found: 3/3 tracks
Created playlist: "Classic Rock"
URL: https://open.spotify.com/playlist/xxxxx
```
