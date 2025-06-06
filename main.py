from flask import Flask, render_template, request, redirect, url_for, session
import requests
import os
import random
import base64
import json
from dotenv import load_dotenv
from flask import send_from_directory
from flask import flash

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

GENRE_TAGS = ['pop', 'rock', 'hip-hop', 'indie', 'alternative','r&b', 'soul', 'bedroom pop', 'electronic', 'jazz', 'metal', 'lo-fi', 'folk', 'edm', 'classical']
REGIONS = ['global', 'united states', 'united kingdom', 'canada', 'australia', 'japan', 'south korea', 'brazil', 'nigeria', 'mexico', 'germany', 'france', 'spain', 'italy', 'sweden', 'india', 'south africa', 'philippines']

CLIENT_ID = os.getenv("SPOT_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOT_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:3000/callback"
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
SCOPE = "user-read-recently-played ugc-image-upload user-read-private user-read-email user-top-read playlist-modify-private playlist-modify-public"


API_KEY = os.getenv('LAST_FM_ID')
BASE_URL = 'http://ws.audioscrobbler.com/2.0/'


def fetch_spotify_album_art(artist_name, track_name, token):
    search_query = f"track:{track_name} artist:{artist_name}"
    search_url = "https://api.spotify.com/v1/search"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    search_params = {
        'q': search_query,
        'type': 'track',
        'limit': 10
    }
    search_response = requests.get(search_url, headers=headers, params=search_params)
    if search_response.status_code != 200:
        return None, None
    items = search_response.json().get('tracks', {}).get('items', [])
    if not items:
        return None, None
    for item in items:
        for artist in item['artists']:
            if artist['name'].lower() == artist_name.lower():
                track_id = item['id']
                break
        else:
            continue
        break
    else:
        track_id = items[0]['id']

    track_url = f"https://api.spotify.com/v1/tracks/{track_id}"
    track_response = requests.get(track_url, headers=headers)
    if track_response.status_code == 200:
        track_data = track_response.json()
        album_images = track_data.get('album', {}).get('images', [])
        album_image = album_images[0]['url'] if album_images else None
        spotify_url = track_data['external_urls']['spotify']
        return album_image, spotify_url

    return None, None



def get_user_top_artists(token, limit=20, time_range='medium_term'):
    url = f"https://api.spotify.com/v1/me/top/artists"
    headers = {'Authorization': f'Bearer {token}'}
    params = {'limit': limit, 'time_range': time_range}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        return [artist['name'] for artist in data.get('items', [])]
    return []



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


@app.route('/about')
def about():
    return render_template('about.html')

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
    tracks = data.get('toptracks', {}).get('track', [])
    results = []
    for track in tracks:
        image_url = None
        if 'image' in track and len(track['image']) > 0:
            image_url = track['image'][-1]['#text']
            if image_url == "":
                image_url = None
        print(f"Track: {track['name']}, Image URL: {image_url or 'No image available'}")
        track_info = {
            'name': track['name'],
            'artist': artist,
            'url': track.get('url', ''),
            'image': image_url or 'https://via.placeholder.com/150'
        }
        results.append(track_info)
    return results



def get_track_tags(artist, track):
    data = api_call({
        'method': 'track.getTopTags',
        'artist': artist,
        'track': track,
        'api_key': API_KEY,
        'format': 'json'
    })
    return [tag['name'].lower() for tag in data.get('toptags', {}).get('tag', [])]

@app.route('/finding')
def finding():
    return render_template("finding.html")

@app.route('/generate', methods=['POST'])
def generate():
    if 'token' not in session:
        return redirect(url_for('login'))

    print("Starting playlist generation...")

    mood_tags = request.form.getlist('tags')
    genre = request.form.get('genre')
    include_artist = request.form.get('include_artist')
    exclude_artist = request.form.get('exclude_artist')
    playlist_name = request.form.get('playlist_name')
    limit = max(1, min(int(request.form.get('limit', 25)), 50))
    spotify_token = session['token']

    all_tracks = {}
    added_artists = set()
    track_tag_cache = {}

    def tag_score(tags):
        score = len(set(mood_tags) & set(tags))
        if genre:
            score += 2 if genre.lower() in tags else 0
        return score

    # 1. builds pool of artists to work off of
    if include_artist:
        print(f"Using specific artist: {include_artist}")
        added_artists.add(include_artist)
        added_artists.update(get_similar_artists(include_artist, limit=15))
    else:
        print("Using user's top Spotify artists...")
        added_artists.update(get_user_top_artists(spotify_token, limit=15))

    print(added_artists)

    all_artists = list(added_artists)
    if include_artist:
        all_artists.remove(include_artist)
        all_artists.insert(0, include_artist)  # ensure specific artist is added
    random.shuffle(all_artists[1:])  #shuffles other artists keeping specific at top

    if exclude_artist in all_artists:
        all_artists.remove(exclude_artist)
        print(f"Removed artist: {exclude_artist}")



    # 2. multiple passes are used to fill songs to the specified limit
    def try_fetch_tracks(min_score_threshold=1, max_tracks=limit):
        for artist in all_artists:
            if len(all_tracks) >= max_tracks:
                break

            print(f"Fetching for artist: {artist}")
            top_tracks = get_top_tracks_for_artist(artist, limit=5)


                

            for track in top_tracks:
                title = track['name']
                key = f"{title}::{artist}"
                if key in all_tracks:
                    continue

                if key not in track_tag_cache:
                    print(f"Fetching tags for: {title} by {artist}")
                    track_tag_cache[key] = get_track_tags(artist, title)

                tags = track_tag_cache[key]
                score = tag_score(tags)

                if score < min_score_threshold:
                    continue

                image, url = fetch_spotify_album_art(artist, title, spotify_token)
                all_tracks[key] = {
                    'name': title,
                    'artist': artist,
                    'lastfm_url': track.get('url'),
                    'spotify_url': url,
                    'image': image or 'https://via.placeholder.com/150',
                    'score': score 
                }


                if len(all_tracks) >= max_tracks:
                    break

    # songs with highest relevance added first
    try_fetch_tracks(min_score_threshold=2)

    # adds songs with lower relevance second
    if len(all_tracks) < limit:
        print("Not enough tracks found. Trying with lower threshold...")
        try_fetch_tracks(min_score_threshold=1)

    # last measure if no more songs can be found adds songs with 0 relevance
    if len(all_tracks) < limit:
        print("Still under limit. Trying final pass to fill...")
        try_fetch_tracks(min_score_threshold=0)

    # trims playlist to limit
    final_tracks = list(all_tracks.values())[:limit]
    print(f"Generated {len(final_tracks)} tracks.")
    #sorts songs by more relevance at the top
    final_tracks = sorted(all_tracks.values(), key=lambda x: x['score'], reverse=True)[:limit]


    return render_template('generated.html',
                           tracks=final_tracks,
                           playlist_link=None,
                           playlist_name=playlist_name)

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

    from PIL import Image
    import io

    cover_file = request.files.get('cover_image')
    if cover_file:
        filename = cover_file.filename.lower()
        try:
            img = Image.open(cover_file.stream).convert("RGB")
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG")
            jpeg_data = buffer.getvalue()
            print("Converted image size:", len(jpeg_data), "bytes")

            if len(jpeg_data) > 256000:
                flash("Cover image is too large (max 256KB).", "warning")
            else:
                encoded_image = base64.b64encode(jpeg_data).decode('utf-8')
                image_response = requests.put(
                    f"https://api.spotify.com/v1/playlists/{playlist_id}/images",
                    headers={
                        'Authorization': f'Bearer {token}',
                        'Content-Type': 'image/jpeg'
                    },
                    data=encoded_image
                )
                print("Cover upload response:", image_response.status_code, image_response.text)
                if image_response.status_code == 202:
                    flash("Cover image uploaded successfully!", "success")
                else:
                    flash(f"Failed to upload playlist cover image: {image_response.text}", "warning")
        except Exception as e:
            flash(f"Image processing failed: {str(e)}", "danger")

    return render_template("generated.html", tracks=tracks_data, playlist_link=playlist_url, playlist_name=playlist_name)


if __name__ == '__main__':
    app.run(debug=True, port=3000)
