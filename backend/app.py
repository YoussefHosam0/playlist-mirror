from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
import requests
from urllib.parse import quote
import os
import ssl
import certifi
from dotenv import load_dotenv

load_dotenv()

os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

app = Flask(__name__)
app.secret_key = os.urandom(24)
CORS(app, origins=["http://localhost:3000", "https://playlist-mirror-frontend.onrender.com"], supports_credentials=True)

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

ANGHAMI_BASE = "https://coussa.anghami.com"
ANGHAMI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Origin": "https://play.anghami.com",
    "Referer": "https://play.anghami.com/"
}

def get_spotify_client():
    return spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET
    ))

def get_spotify_oauth():
    return SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope="playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private",
        cache_path="/tmp/.spotify_cache"
    )

def get_spotify_authed_client(token):
    return spotipy.Spotify(auth=token)

@app.route("/spotify/login")
def spotify_login():
    auth_url = get_spotify_oauth().get_authorize_url()
    return jsonify({"auth_url": auth_url})

@app.route("/callback")
def spotify_callback():
    code = request.args.get("code")
    oauth = get_spotify_oauth()
    token_info = oauth.get_access_token(code)
    access_token = token_info["access_token"]
    return redirect(f"https://playlist-mirror-frontend.onrender.com?spotify_token={access_token}")

# ── Thing 1: Song Search ──────────────────────────────────────────

@app.route("/search", methods=["GET"])
def search_song():
    song = request.args.get("song", "")
    artist = request.args.get("artist", "")
    query = f"{song} {artist}".strip()
    if not query:
        return jsonify({"error": "No query provided"}), 400

    sp = get_spotify_client()
    results = sp.search(q=query, type="track", limit=5)
    tracks = results["tracks"]["items"]
    if not tracks and artist:
        results = sp.search(q=song, type="track", limit=5)
        tracks = results["tracks"]["items"]
    if not tracks:
        return jsonify({"error": "No results found"}), 404

    top = tracks[0]
    track_name = top["name"]
    artist_name = top["artists"][0]["name"]
    album_art = top["album"]["images"][0]["url"] if top["album"]["images"] else None
    spotify_url = top["external_urls"]["spotify"]
    anghami_search_url = f"https://play.anghami.com/search/{quote(f'{track_name} {artist_name}', safe='')}"

    return jsonify({
        "track_name": track_name,
        "artist_name": artist_name,
        "album_art": album_art,
        "spotify_url": spotify_url,
        "anghami_url": anghami_search_url
    })

# ── Anghami API helpers ───────────────────────────────────────────

def anghami_search(query, sid):
    url = f"{ANGHAMI_BASE}/rest/v2/GETSearchResults.view"
    params = {
        "query": query,
        "page": 0,
        "filter_type": "top",
        "simple_results": "true",
        "output": "jsonhp",
        "web2": "true",
        "lang": "en",
        "language": "en",
        "sid": sid
    }
    r = requests.get(url, params=params, headers=ANGHAMI_HEADERS, timeout=10)
    return r.json()

def anghami_get_playlist(playlist_id, sid):
    url = f"{ANGHAMI_BASE}/gateway.php"
    params = {
        "type": "GETplaylistdata",
        "playlistid": playlist_id,
        "buffered": 1,
        "output": "jsonhp",
        "web2": "true",
        "lang": "en",
        "language": "en",
        "sid": sid
    }
    r = requests.get(url, params=params, headers=ANGHAMI_HEADERS, timeout=10)
    return r.json()

def anghami_add_song(playlist_id, song_id, sid):
    url = f"{ANGHAMI_BASE}/gateway.php"
    params = {
        "type": "PUTplaylist",
        "playlistid": playlist_id,
        "action": "append",
        "songID": song_id,
        "output": "jsonhp",
        "web2": "true",
        "lang": "en",
        "language": "en",
        "sid": sid
    }
    r = requests.get(url, params=params, headers=ANGHAMI_HEADERS, timeout=10)
    return r.json()

def extract_playlist_id(url):
    try:
        return url.rstrip("/").split("/")[-1].split("?")[0]
    except:
        return None

# ── Thing 2: Playlist Mirror ──────────────────────────────────────

@app.route("/playlist/spotify", methods=["GET"])
def get_spotify_playlist():
    playlist_url = request.args.get("url", "")
    token = request.args.get("token", "")
    if not playlist_url:
        return jsonify({"error": "No URL provided"}), 400
    try:
        playlist_id = playlist_url.split("playlist/")[1].split("?")[0]
    except:
        return jsonify({"error": "Invalid Spotify playlist URL"}), 400

    sp = get_spotify_authed_client(token) if token else get_spotify_client()
    results = sp.playlist_tracks(playlist_id)
    tracks = []
    while results:
        for item in results["items"]:
            track = item.get("track")
            if track:
                tracks.append({
                    "name": track["name"],
                    "artist": track["artists"][0]["name"],
                    "spotify_url": track["external_urls"]["spotify"],
                    "spotify_id": track["id"]
                })
        results = sp.next(results) if results["next"] else None
    return jsonify({"tracks": tracks, "count": len(tracks)})

@app.route("/playlist/anghami", methods=["GET"])
def get_anghami_playlist():
    playlist_url = request.args.get("url", "")
    sid = request.args.get("sid", "")
    if not playlist_url or not sid:
        return jsonify({"error": "URL and sid required"}), 400

    playlist_id = extract_playlist_id(playlist_url)
    if not playlist_id:
        return jsonify({"error": "Invalid Anghami playlist URL"}), 400

    data = anghami_get_playlist(playlist_id, sid)
    songs = data.get("songs", [])
    tracks = []
    for s in songs:
        tracks.append({
            "name": s.get("title", ""),
            "artist": s.get("artist", ""),
            "anghami_id": str(s.get("id", ""))
        })
    return jsonify({"tracks": tracks, "count": len(tracks), "playlist_id": playlist_id})

@app.route("/sync", methods=["POST"])
def sync_playlists():
    data = request.json
    spotify_url = data.get("spotify_url", "")
    anghami_url = data.get("anghami_url", "")
    sid = data.get("sid", "")
    token = data.get("spotify_token", "")
    direction = data.get("direction", "both")

    if not sid:
        return jsonify({"error": "Anghami session ID (sid) required"}), 400

    normalize = lambda s: s.lower().strip()
    results = {"added_to_spotify": [], "added_to_anghami": [], "errors": []}

    try:
        sp = get_spotify_authed_client(token) if token else get_spotify_client()

        spotify_id = spotify_url.split("playlist/")[1].split("?")[0]
        sp_results = sp.playlist_tracks(spotify_id)
        spotify_tracks = []
        while sp_results:
            for item in sp_results["items"]:
                track = item.get("track")
                if track:
                    spotify_tracks.append({
                        "name": track["name"],
                        "artist": track["artists"][0]["name"],
                        "spotify_id": track["id"]
                    })
            sp_results = sp.next(sp_results) if sp_results["next"] else None

        anghami_id = extract_playlist_id(anghami_url)
        anghami_data = anghami_get_playlist(anghami_id, sid)
        anghami_tracks = []
        for s in anghami_data.get("songs", []):
            anghami_tracks.append({
                "name": s.get("title", ""),
                "artist": s.get("artist", ""),
                "anghami_id": str(s.get("id", ""))
            })

        if direction in ["both", "to_anghami"]:
            for st in spotify_tracks:
                match = any(normalize(st["name"]) in normalize(at["name"]) or normalize(at["name"]) in normalize(st["name"]) for at in anghami_tracks)
                if not match:
                    query = f"{st['name']} {st['artist']}"
                    search_data = anghami_search(query, sid)
                    found_songs = search_data.get("sections", [{}])[0].get("data", [])
                    if found_songs:
                        song_id = found_songs[0].get("id")
                        if song_id:
                            anghami_add_song(anghami_id, song_id, sid)
                            results["added_to_anghami"].append(f"{st['name']} - {st['artist']}")

        if direction in ["both", "to_spotify"]:
            sp_playlist_id = spotify_url.split("playlist/")[1].split("?")[0]
            for at in anghami_tracks:
                match = any(normalize(at["name"]) in normalize(st["name"]) or normalize(st["name"]) in normalize(at["name"]) for st in spotify_tracks)
                if not match:
                    query = f"{at['name']} {at['artist']}"
                    sp_search = sp.search(q=query, type="track", limit=1)
                    sp_found = sp_search["tracks"]["items"]
                    if sp_found:
                        track_uri = sp_found[0]["uri"]
                        sp.playlist_add_items(sp_playlist_id, [track_uri])
                        results["added_to_spotify"].append(f"{at['name']} - {at['artist']}")

    except Exception as e:
        results["errors"].append(str(e))

    return jsonify(results)

@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)