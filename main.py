from flask import Flask, render_template, request, redirect, url_for, session
import requests
import os
import random
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)
API_KEY = os.getenv('LAST_FM_ID')
BASE_URL = 'http://ws.audioscrobbler.com/2.0/'

MOOD_TAG_MAP = {
    'chill': ['chill', 'ambient', 'lo-fi',],
    'sad': ['sad', 'slow', 'acoustic'],
    'happy': ['happy', 'feelgood', 'dance'],
    'angry': ['angry', 'workout', 'fast'],
}

GENRE_TAGS = ['pop', 'rock', 'hip-hop', 'electronic', 'jazz', 'metal', 'lo-fi', 'folk', 'edm', 'classical']
REGIONS = ['global', 'united states', 'united kingdom', 'germany', 'france', 'japan', 'canada', 'australia']
CLIENT_ID = os.getenv("SPOT_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOT_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:3000/callback"
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
SCOPE = "user-read-private user-read-email"

API_KEY = os.getenv('LAST_FM_ID')
BASE_URL = 'http://ws.audioscrobbler.com/2.0/'


@app.route('/login')
def login():
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
    ## get username from spotify
    headers = {
        'Authorization': f'Bearer {session["token"]}',
    }
    user_response = requests.get("https://api.spotify.com/v1/me", headers=headers)
    user_info = user_response.json()
    session['user_name'] = user_info.get('display_name', 'User') 


    return redirect(url_for("index"))

@app.route('/')
def index():
    if 'token' not in session:
        return redirect(url_for('login'))

    user_name = session.get('user_name', 'Guest')
    moods = list(MOOD_TAG_MAP.keys())
    return render_template('index.html', moods=moods, user_name=user_name)

@app.route('/logout')
def logout():
    session.pop('token', None)
    session.clear()
    return redirect(url_for('login'))

@app.route('/customize', methods=['GET'])
def customize():
    mood = request.args.get('mood')
    if mood not in MOOD_TAG_MAP:
        return "Invalid mood."
    default_tags = MOOD_TAG_MAP[mood]
    genres = GENRE_TAGS
    regions = REGIONS
    return render_template('customize.html', tags=default_tags, mood=mood, genres=genres, regions=regions)

def api_call(params):
    response = requests.get(BASE_URL, params=params)
    if response.status_code == 200:
        return response.json()
    return {}

def get_artist_top_tags(artist):
    data = api_call({
        'method': 'artist.getTopTags',
        'artist': artist,
        'api_key': API_KEY,
        'format': 'json'
    })
    return [tag['name'].lower() for tag in data.get('toptags', {}).get('tag', [])]

def get_similar_artists(artist, limit=5):
    data = api_call({
        'method': 'artist.getSimilar',
        'artist': artist,
        'api_key': API_KEY,
        'format': 'json',
        'limit': 50
    })
    all_similar = [a['name'] for a in data.get('similarartists', {}).get('artist', [])]
    random.shuffle(all_similar)
    return all_similar[:limit]

def get_top_tracks_for_artist(artist, limit=5):
    data = api_call({
        'method': 'artist.getTopTracks',
        'artist': artist,
        'api_key': API_KEY,
        'format': 'json',
        'limit': limit
    })
    return data.get('toptracks', {}).get('track', [])

def get_track_tags(artist, track):
    data = api_call({
        'method': 'track.getTopTags',
        'artist': artist,
        'track': track,
        'api_key': API_KEY,
        'format': 'json'
    })
    return [tag['name'].lower() for tag in data.get('toptags', {}).get('tag', [])]

@app.route('/generate', methods=['POST'])
def generate():
    mood_tags = request.form.getlist('tags')
    genre = request.form.get('genre')
    specific_artist = request.form.get('artist')

    all_tracks = {}
    added_artists = set()

    if specific_artist:
        artist_tags = get_artist_top_tags(specific_artist)
        mood_tags = list(set(mood_tags + artist_tags))
        added_artists.add(specific_artist)
        similar = get_similar_artists(specific_artist, limit=random.randint(2, 10))
        added_artists.update(similar)

    all_artists = list(added_artists)
    random.shuffle(all_artists)

    for artist in all_artists:
        tracks = get_top_tracks_for_artist(artist, limit=random.randint(2, 10))
        for track in tracks:
            title = track['name']
            key = f"{title}::{artist}"
            if key not in all_tracks:
                all_tracks[key] = {
                    'name': title,
                    'artist': artist,
                    'url': track.get('url')
                }

    final_tracks = list(all_tracks.values())

    if genre:
        genre = genre.lower()
        filtered = []
        for track in final_tracks:
            tags = get_track_tags(track['artist'], track['name'])
            if genre in tags:
                filtered.append(track)
        final_tracks = filtered

    random.shuffle(final_tracks)

    return render_template('generated.html', tracks=final_tracks[:50])


if __name__ == '__main__':
    app.run(debug=True, port=3000)