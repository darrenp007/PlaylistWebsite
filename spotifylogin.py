import os
import requests
from flask import Flask, request, redirect, session, url_for

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = "http://localhost:3000/callback"
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
SCOPE = "user-read-private user-read-email playlist-modify-private playlist-modify-public"

app = Flask(__name__)
app.secret_key = os.urandom(24)

@app.route('/')
def home():
    return '''
    Welcome to the Spotify Auth App!
    <a href="/login">Login with Spotify</a>
    <form action="/search_songs" method="get">
        <label for="pod">Select a Mood:</label>
        <select name="mood" id="mood">
            <option value="happy">Happy</option>
            <option value="sad">Sad</option>
            <option value="chill">Chill</option>
            <option value="angry">Angry</option>  <!-- Updated mood -->
        </select>
        <input type="submit" value="Get Songs">
    </form>
    '''

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

    headers = {"Authorization": f"Bearer {token_info['access_token']}"}
    user_profile = requests.get("https://api.spotify.com/v1/me", headers=headers).json()
    session["user_id"] = user_profile["id"]

    return redirect(url_for("profile"))

@app.route('/profile')
def profile():
    if "token" not in session:
        return redirect(url_for("login"))

    headers = {"Authorization": f"Bearer {session['token']}"}
    user_info = requests.get("https://api.spotify.com/v1/me", headers=headers).json()

    return f"""
    <h1>Logged in as {user_info.get('display_name', 'Unknown')}</h1>
    <p>Email: {user_info.get('email', 'No email')}</p>
    <p>Country: {user_info.get('country', 'Unknown')}</p>
    <p>Followers: {user_info.get('followers', {}).get('total', 0)}</p>
    <img src="{user_info.get('images', [{}])[0].get('url', '')}" width="200px">
    <a href="/">Go Back</a>
    """

MOOD_PLAYLISTS = {
    "happy": "37i9dQZF1DXdPec7aLTmlC",
    "sad": "37i9dQZF1DX7qK8ma5wgG1",
    "chill": "37i9dQZF1DX2yvmlOdMYzV",
    "angry": "37i9dQZF1DX1H4LbvY4OJi"
}

@app.route('/search_songs', methods=['GET'])
def search_songs():
    if "token" not in session:
        return redirect(url_for("login"))

    mood = request.args.get("mood")
    if not mood or mood not in MOOD_PLAYLISTS:
        return "Invalid mood!", 400

    playlist_id = create_playlist(f"{mood.capitalize()} Mood Playlist")

    if isinstance(playlist_id, str):
        return f"Playlist created! <a href='https://open.spotify.com/playlist/{playlist_id}' target='_blank'>View on Spotify</a>"
    else:
        return "Error creating playlist!", 500

def create_playlist(playlist_name):
    user_id = session["user_id"]
    headers = {
        "Authorization": f"Bearer {session['token']}",
        "Content-Type": "application/json"
    }
    
    data = {
        "name": playlist_name,
        "description": "Generated playlist based on your mood",
        "public": False
    }

    response = requests.post(f"https://api.spotify.com/v1/users/{user_id}/playlists", json=data, headers=headers)

    print("Create Playlist Response:", response.status_code, response.text)  # 🔍

    if response.status_code != 201:
        return None

    playlist_id = response.json()["id"]
    add_songs_to_playlist(playlist_id)
    return playlist_id

def add_songs_to_playlist(playlist_id):
    """ Fetches songs from the mood-based playlist and adds them to a new playlist """
    mood = request.args.get("mood")
    if not mood or mood not in MOOD_PLAYLISTS:
        return "Invalid mood!", 400

    playlist_uri = MOOD_PLAYLISTS[mood]

    headers = {
        "Authorization": f"Bearer {session['token']}",
        "Content-Type": "application/json"
    }

    response = requests.get(f"https://api.spotify.com/v1/playlists/{playlist_uri}/tracks", headers=headers)
    if response.status_code != 200:
        return "Error fetching songs!"

    songs_info = response.json()
    songs_uris = [song["track"]["uri"] for song in songs_info.get("items", [])] 

    if not songs_uris:
        return "No songs available for this mood!", 404

    add_tracks_url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    add_response = requests.post(add_tracks_url, json={"uris": songs_uris}, headers=headers)

    if add_response.status_code != 201:
        return "Error adding songs!"

    return "Songs added successfully!"

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=3000)
