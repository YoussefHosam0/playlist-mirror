import React, { useState } from "react";
import axios from "axios";
import "./App.css";

const API = "http://localhost:5000";

function SongSearch() {
  const [song, setSong] = useState("");
  const [artist, setArtist] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const search = async () => {
    if (!song.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await axios.get(`${API}/search`, { params: { song, artist } });
      setResult(res.data);
    } catch (e) {
      setError(e.response?.data?.error || "Something went wrong");
    }
    setLoading(false);
  };

  return (
    <div className="card">
      <h2>Song Search</h2>
      <p className="subtitle">Find a song on Spotify and Anghami</p>
      <input placeholder="Song name" value={song} onChange={(e) => setSong(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()} dir="auto" />
      <input placeholder="Artist name (optional)" value={artist} onChange={(e) => setArtist(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()} dir="auto" />
      <button onClick={search} disabled={loading}>{loading ? "Searching..." : "Search"}</button>
      {error && <p className="error">{error}</p>}
      {result && (
        <div className="result">
          {result.album_art && <img src={result.album_art} alt="Album art" className="album-art" />}
          <div className="result-info">
            <p className="track-name">{result.track_name}</p>
            <p className="artist-name">{result.artist_name}</p>
            <div className="links">
              <a href={result.spotify_url} target="_blank" rel="noreferrer" className="btn spotify">Open on Spotify</a>
              <a href={result.anghami_url} target="_blank" rel="noreferrer" className="btn anghami">Search on Anghami</a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function TrackRow({ track, platform }) {
  const url = platform === "spotify"
    ? `https://open.spotify.com/search/${encodeURIComponent(track.name + " " + track.artist)}`
    : `https://play.anghami.com/search/${encodeURIComponent(track.name + " " + track.artist)}`;
  const label = platform === "spotify" ? "Find on Spotify" : "Find on Anghami";
  const cls = platform === "spotify" ? "btn spotify small" : "btn anghami small";
  return (
    <li className="track-row">
      <span dir="auto" className="track-title">{track.name}</span>
      <span dir="auto" className="artist-tag">{track.artist}</span>
      <a href={url} target="_blank" rel="noreferrer" className={cls}>{label}</a>
    </li>
  );
}

function PlaylistMirror() {
  const [spotifyUrl, setSpotifyUrl] = useState("");
  const [anghamiUrl, setAnghamiUrl] = useState("");
  const [spotifyTracks, setSpotifyTracks] = useState([]);
  const [anghamiTracks, setAnghamiTracks] = useState([]);
  const [missing, setMissing] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [synced, setSynced] = useState(false);

  const normalize = (str) => str.toLowerCase().replace(/[^a-z0-9\u0600-\u06FF\s]/g, "").trim();

  const sync = async () => {
    if (!spotifyUrl.trim() && !anghamiUrl.trim()) return;
    setLoading(true);
    setError("");
    setMissing(null);
    setSynced(false);
    try {
      let sTracks = [];
      let aTracks = [];
      if (spotifyUrl.trim()) {
        const res = await axios.get(`${API}/playlist/spotify`, { params: { url: spotifyUrl } });
        sTracks = res.data.tracks;
        setSpotifyTracks(sTracks);
      }
      if (anghamiUrl.trim()) {
        const res = await axios.get(`${API}/playlist/anghami`, { params: { url: anghamiUrl } });
        aTracks = res.data.tracks;
        setAnghamiTracks(aTracks);
      }
      const missingInSpotify = aTracks.filter((at) => !sTracks.some((st) => normalize(st.name).includes(normalize(at.name)) || normalize(at.name).includes(normalize(st.name))));
      const missingInAnghami = sTracks.filter((st) => !aTracks.some((at) => normalize(st.name).includes(normalize(at.name)) || normalize(at.name).includes(normalize(st.name))));
      setMissing({ missingInSpotify, missingInAnghami });
      setSynced(true);
    } catch (e) {
      setError(e.response?.data?.error || "Something went wrong");
    }
    setLoading(false);
  };

  return (
    <div className="card">
      <h2>Playlist Mirror</h2>
      <p className="subtitle">Compare and sync playlists between Spotify and Anghami</p>
      <input placeholder="Spotify playlist URL" value={spotifyUrl} onChange={(e) => setSpotifyUrl(e.target.value)} />
      <input placeholder="Anghami playlist URL" value={anghamiUrl} onChange={(e) => setAnghamiUrl(e.target.value)} />
      <button onClick={sync} disabled={loading}>{loading ? "Syncing..." : "Sync Playlists"}</button>
      {error && <p className="error">{error}</p>}
      {synced && missing && (
        <div className="sync-results">
          <div className="sync-summary">
            <span>Spotify: <strong>{spotifyTracks.length} tracks</strong></span>
            <span>Anghami: <strong>{anghamiTracks.length} tracks</strong></span>
          </div>
          {missing.missingInSpotify.length > 0 && (
            <div className="missing-section">
              <h3>In Anghami but missing from Spotify ({missing.missingInSpotify.length})</h3>
              <ul>{missing.missingInSpotify.map((t, i) => <TrackRow key={i} track={t} platform="spotify" />)}</ul>
            </div>
          )}
          {missing.missingInAnghami.length > 0 && (
            <div className="missing-section">
              <h3>In Spotify but missing from Anghami ({missing.missingInAnghami.length})</h3>
              <ul>{missing.missingInAnghami.map((t, i) => <TrackRow key={i} track={t} platform="anghami" />)}</ul>
            </div>
          )}
          {missing.missingInSpotify.length === 0 && missing.missingInAnghami.length === 0 && (
            <p className="all-good">Playlists are fully in sync!</p>
          )}
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState("search");
  return (
    <div className="app">
      <header>
        <h1>Playlist Mirror</h1>
        <p>Search songs and sync playlists between Spotify and Anghami</p>
        <div className="tabs">
          <button className={tab === "search" ? "active" : ""} onClick={() => setTab("search")}>Song Search</button>
          <button className={tab === "mirror" ? "active" : ""} onClick={() => setTab("mirror")}>Playlist Mirror</button>
        </div>
      </header>
      <main>{tab === "search" ? <SongSearch /> : <PlaylistMirror />}</main>
    </div>
  );
}
