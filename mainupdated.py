from flask import Flask, render_template, request, redirect, url_for, session, flash
import requests
import os
import random
import base64
import json
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

API_KEY = os.getenv('LAST_FM_ID')
CLIENT_ID = os.getenv("SPOT_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOT_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:3000/callback"
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
SCOPE = "user-read-private user-read-email playlist-modify-private playlist-modify-public user-read-recently-played ugc-image-upload"

BASE_URL = 'http://ws.audioscrobbler.com/2.0/'

MOOD_TAG_MAP = {
    'chill': ['chill', 'ambient', 'lo-fi'],
    'sad': ['sad', 'slow', 'acoustic'],
    'happy': ['happy', 'feelgood', 'dance'],
    'angry': ['angry', 'workout', 'fast'],
}

GENRE_TAGS = ['pop', 'rock', 'hip-hop', 'electronic', 'jazz', 'metal', 'lo-fi', 'folk', 'edm', 'classical']
REGIONS = ['global', 'united states', 'united kingdom', 'germany', 'france', 'japan', 'canada', 'australia']

@app.route('/login')
def login():
    if 'token' in session:
        return redirect(url_for('index'))
    auth_query_parameters = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
    }
    auth_url = f"{AUTH_URL}?{'&'.join([f'{key}={value}' for key, value in auth_query_parameters.items()])}"
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get("code")
    if not code:
        return "Authorization failed!", 400
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    response = requests.post(TOKEN_URL, data=token_data)
    token_info = response.json()
    if "access_token" not in token_info:
        return "Failed to retrieve access token!", 400
    session["token"] = token_info["access_token"]
    headers = {'Authorization': f'Bearer {session["token"]}'}
    user_response = requests.get("https://api.spotify.com/v1/me", headers=headers)
    user_info = user_response.json()
    session['user_name'] = user_info.get('display_name', 'User')
    return redirect(url_for("index"))

@app.route('/')
def index():
    if 'token' not in session:
        return redirect(url_for('welcome'))
    user_name = session.get('user_name', 'Guest')
    moods = list(MOOD_TAG_MAP.keys())
    return render_template('index.html', moods=moods, user_name=user_name)

@app.route('/logout')
def logout():
    session.clear()
    flash("You've been logged out.", "info")
    return redirect(url_for('welcome'))

@app.route('/welcome')
def welcome():
    return render_template('welcome.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/customize', methods=['GET'])
def customize():
    mood = request.args.get('mood')
    if mood not in MOOD_TAG_MAP:
        return "Invalid mood."
    return render_template('customize.html', tags=MOOD_TAG_MAP[mood], mood=mood, genres=GENRE_TAGS, regions=REGIONS)

@app.route('/recent')
def recent():
    if 'token' not in session:
        return redirect(url_for('login'))
    return render_template('recent.html', tracks=get_recent_tracks(session['token']))

def api_call(params):
    response = requests.get(BASE_URL, params=params)
    return response.json() if response.status_code == 200 else {}

def get_recent_tracks(token, limit=6):
    url = "https://api.spotify.com/v1/me/player/recently-played"
    headers = {'Authorization': f'Bearer {token}'}
    params = {'limit': limit}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        return []
    return [{
        'name': item['track']['name'],
        'artist': ', '.join([a['name'] for a in item['track']['artists']]),
        'spotify_url': item['track']['external_urls']['spotify'],
        'image': item['track']['album']['images'][0]['url'] if item['track']['album']['images'] else None
    } for item in response.json().get("items", [])]

def get_artist_top_tags(artist):
    data = api_call({"method": "artist.getTopTags", "artist": artist, "api_key": API_KEY, "format": "json"})
    return [tag['name'].lower() for tag in data.get('toptags', {}).get('tag', [])]

def get_similar_artists(artist, limit=5):
    data = api_call({"method": "artist.getSimilar", "artist": artist, "api_key": API_KEY, "format": "json", "limit": 50})
    all_similar = [a['name'] for a in data.get('similarartists', {}).get('artist', [])]
    random.shuffle(all_similar)
    return all_similar[:limit]

def get_top_tracks_for_artist(artist, limit=5):
    data = api_call({"method": "artist.getTopTracks", "artist": artist, "api_key": API_KEY, "format": "json", "limit": limit})
    return [{
        'name': track['name'],
        'artist': artist,
        'url': track.get('url', ''),
        'image': track['image'][-1]['#text'] if track.get('image') and track['image'][-1]['#text'] else 'https://via.placeholder.com/150'
    } for track in data.get('toptracks', {}).get('track', [])]

def fetch_spotify_album_art(artist_name, track_name, token):
    url = "https://api.spotify.com/v1/search"
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    params = {'q': f"track:{track_name} artist:{artist_name}", 'type': 'track', 'limit': 1}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        results = response.json().get('tracks', {}).get('items', [])
        if results:
            track = results[0]
            image = track['album']['images'][0]['url'] if track['album']['images'] else None
            return image, track['external_urls']['spotify']
    return None, None

@app.route('/generate', methods=['POST'])
def generate():
    if 'token' not in session:
        return redirect(url_for('login'))
    mood_tags = request.form.getlist('tags')
    genre = request.form.get('genre')
    specific_artist = request.form.get('artist')
    playlist_name = request.form.get('playlist_name')
    all_tracks = {}
    added_artists = set()
    if specific_artist:
        mood_tags += get_artist_top_tags(specific_artist)
        added_artists.add(specific_artist)
        added_artists.update(get_similar_artists(specific_artist, limit=random.randint(2, 10)))
    all_artists = list(added_artists)
    random.shuffle(all_artists)
    for artist in all_artists:
        tracks = get_top_tracks_for_artist(artist, limit=random.randint(2, 10))
        for track in tracks:
            key = f"{track['name']}::{artist}"
            if key not in all_tracks:
                album_image, spotify_url = fetch_spotify_album_art(artist, track['name'], session['token'])
                all_tracks[key] = {
                    'name': track['name'],
                    'artist': artist,
                    'lastfm_url': track.get('url'),
                    'spotify_url': spotify_url,
                    'image': album_image
                }
    return render_template('generated.html', tracks=list(all_tracks.values()), playlist_link=None, playlist_name=playlist_name)

@app.route('/save_to_spotify', methods=['POST'])
def save_to_spotify():
    if 'token' not in session:
        flash("You're not logged in to Spotify.", "warning")
        return redirect(url_for('login'))
    token = session['token']
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    tracks_data = json.loads(request.form.get('tracks'))
    playlist_name = request.form.get('playlist_name', 'Mood Playlist')
    track_uris = []
    for track in tracks_data:
        spotify_url = track.get('spotify_url')
        if spotify_url and "track/" in spotify_url:
            track_id = spotify_url.split("track/")[1].split("?")[0]
            track_uris.append(f"spotify:track:{track_id}")
    user_response = requests.get("https://api.spotify.com/v1/me", headers=headers)
    if user_response.status_code != 200:
        flash("Failed to get Spotify user profile.", "danger")
        return redirect(url_for("index"))
    user_id = user_response.json().get("id")
    if not user_id:
        flash("Could not retrieve user ID from Spotify.", "danger")
        return redirect(url_for("index"))
    payload = {
        "name": playlist_name,
        "description": "Auto-generated by Mood Playlist!",
        "public": False
    }
    playlist_response = requests.post(f"https://api.spotify.com/v1/users/{user_id}/playlists", headers=headers, json=payload)
    playlist = playlist_response.json()
    if playlist_response.status_code != 201 or 'id' not in playlist:
        flash(f"Error creating playlist: {playlist.get('error', {}).get('message', 'Unknown error')}", "danger")
        return redirect(url_for("index"))
    playlist_id = playlist["id"]
    playlist_url = playlist["external_urls"]["spotify"]
    for i in range(0, len(track_uris), 100):
        batch = track_uris[i:i+100]
        requests.post(f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks", headers=headers, json={"uris": batch})
    cover_file = request.files.get('cover_image')
    if cover_file and cover_file.filename.lower().endswith('.jpg'):
        image_data = cover_file.read()
        print("Cover image size:", len(image_data), "bytes")
        if len(image_data) > 256000:
            flash("Cover image is too large (max 256KB).", "warning")
        else:
            encoded_image = base64.b64encode(image_data).decode('utf-8')
            image_response = requests.put(
                f"https://api.spotify.com/v1/playlists/{playlist_id}/images",
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'image/jpeg'
                },
                data=encoded_image
            )
            print("Cover upload response:", image_response.status_code, image_response.text)
            if image_response.status_code != 202:
                flash("Failed to upload playlist cover image.", "warning")
    return render_template("generated.html", tracks=tracks_data, playlist_link=playlist_url, playlist_name=playlist_name)

if __name__ == '__main__':
    app.run(debug=True, port=3000)
