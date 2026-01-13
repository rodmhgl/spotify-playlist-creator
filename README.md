# Spotify Playlist Creator

Create Spotify playlists from TSV files containing song titles and artists.

## Quick Start

```bash
pip install -r requirements.txt
python spotify_playlist.py tracks.tsv -n "My Playlist"
```

## Setup

**Requirements:** Python 3.9+, Spotify Developer account

1. Create an app at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Set redirect URI to `http://127.0.0.1:8888/callback` in app settings
3. Create `.env` file with your credentials:

```
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
```

On first run, authorize via browser. Token is cached to `.spotify_cache` for subsequent runs.

## Usage

```bash
python spotify_playlist.py <input_file> --name "<playlist_name>" [options]
```

| Option | Description |
|--------|-------------|
| `-n, --name` | Playlist name (required) |
| `-p, --public` | Make playlist public (default: private) |
| `-d, --description` | Custom description |
| `--dry-run` | Search without creating playlist |
| `-v, --verbose` | Show per-track search results |

## Input Format

Tab-separated file with header row. Additional columns are ignored.

```
Title	Artist
Hotel California	Eagles
Imagine	John Lennon
Stairway to Heaven	Led Zeppelin
```

## Example

```bash
python spotify_playlist.py tracks.tsv -n "Classic Rock" -v
```

```
Searching for 3 tracks...
[1/3] Found: "Hotel California - 2013 Remaster" by Eagles (score: 78)
[2/3] Found: "Imagine - Remastered 2010" by John Lennon (score: 80)
[3/3] Found: "Stairway to Heaven - Remaster" by Led Zeppelin (score: 79)
Found: 3/3 tracks
Created playlist: "Classic Rock"
URL: https://open.spotify.com/playlist/xxxxx
```

## Behavior

- **Track matching:** Uses scoring to filter karaoke/cover versions. Keywords like "karaoke", "instrumental", "cover" are penalized.
- **Missing tracks:** Skipped and listed at end. Exit code 0 even if some not found.
- **Duplicates:** Not deduplicated. Same song twice in input = twice in playlist.

## Environment Variables

| Variable | Required | Default |
|----------|----------|---------|
| `SPOTIFY_CLIENT_ID` | Yes | — |
| `SPOTIFY_CLIENT_SECRET` | Yes | — |
| `SPOTIFY_REDIRECT_URI` | No | `http://127.0.0.1:8888/callback` |
| `SPOTIFY_CACHE_PATH` | No | `.spotify_cache` |
