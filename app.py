from flask import Flask, request, jsonify, redirect, session
from flask_cors import CORS
import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
from urllib.parse import quote

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)
CORS(app, supports_credentials=True)

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

def get_spotify_client():
    return spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET
    ))

# ── Thing 1: Song Search ──────────────────────────────────────────

@app.route("/search", methods=["GET"])
def search_song():
    song = request.args.get("song", "")
    artist = request.args.get("artist", "")
    query = f"{song} {artist}".strip()

    if not query:
        return jsonify({"error": "No query provided"}), 400

    sp = get_spotify_client()

    # Try exact query first, then fallback to song only
    results = sp.search(q=query, type="track", limit=5)
    tracks = results["tracks"]["items"]

    if not tracks and artist:
        results = sp.search(q=song, type="track", limit=5)
        tracks = results["tracks"]["items"]

    if not tracks:
        return jsonify({"error": "No results found"}), 404

    top = tracks[0]
    spotify_url = top["external_urls"]["spotify"]
    track_name = top["name"]
    artist_name = top["artists"][0]["name"]
    album_art = top["album"]["images"][0]["url"] if top["album"]["images"] else None

    # Properly encode Arabic and English for Anghami URL
    anghami_query = quote(f"{track_name} {artist_name}", safe="")
    anghami_search_url = f"https://play.anghami.com/search/{anghami_query}"

    return jsonify({
        "track_name": track_name,
        "artist_name": artist_name,
        "album_art": album_art,
        "spotify_url": spotify_url,
        "anghami_url": anghami_search_url
    })

# ── Thing 2: Playlist Mirror ──────────────────────────────────────

@app.route("/playlist/spotify", methods=["GET"])
def get_spotify_playlist():
    playlist_url = request.args.get("url", "")
    if not playlist_url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        playlist_id = playlist_url.split("playlist/")[1].split("?")[0]
    except:
        return jsonify({"error": "Invalid Spotify playlist URL"}), 400

    sp = get_spotify_client()
    results = sp.playlist_tracks(playlist_id)
    tracks = []

    while results:
        for item in results["items"]:
            track = item.get("track")
            if track:
                tracks.append({
                    "name": track["name"],
                    "artist": track["artists"][0]["name"],
                    "spotify_url": track["external_urls"]["spotify"]
                })
        results = sp.next(results) if results["next"] else None

    return jsonify({"tracks": tracks, "count": len(tracks)})

@app.route("/playlist/anghami", methods=["GET"])
def get_anghami_playlist():
    playlist_url = request.args.get("url", "")
    if not playlist_url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Charset": "utf-8",
            "Accept-Language": "ar,en;q=0.9"
        }
        response = requests.get(playlist_url, headers=headers, timeout=10)
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")

        tracks = []
        for item in soup.select("[class*='song']"):
            title = item.select_one("[class*='title']")
            artist = item.select_one("[class*='artist']")
            if title and artist:
                tracks.append({
                    "name": title.get_text(strip=True),
                    "artist": artist.get_text(strip=True)
                })

        return jsonify({"tracks": tracks, "count": len(tracks)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)