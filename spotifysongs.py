import os
import requests
from flask import Flask, request, redirect, session, url_for

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = "http://localhost:3000/callback"
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
SCOPE = "user-read-private user-read-email"

app = Flask(__name__)
app.secret_key = os.urandom(24)

@app.route('/')
def home():
    return '''
    Welcome to the Spotify Auth App!
    <a href="/login">Login with Spotify</a>
    <form action="/search_songs" method="get">
        <label for="mood">Select a Mood:</label>
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

@app.route('/search_songs', methods=['GET'])
def search_songs_form():
    mood = request.args.get('mood')
    return redirect(url_for('search_songs', mood=mood))

@app.route('/search_songs/<mood>')
def search_songs(mood):
    if "token" not in session:
        return redirect(url_for("login"))

    headers = {"Authorization": f"Bearer {session['token']}"}
    query = mood 
    search_url = f"https://api.spotify.com/v1/search?q={query}&type=track&limit=10"

    response = requests.get(search_url, headers=headers)
    songs_info = response.json()

    songs = songs_info.get('tracks', {}).get('items', [])
    if not songs:
        return f"No {mood} songs found!", 404

    song_list = ""
    for song in songs:
        song_list += f"""
        <p>
            <strong>{song['name']}</strong> by {', '.join(artist['name'] for artist in song['artists'])} 
            <a href="{song['external_urls']['spotify']}" target="_blank">Listen</a>
        </p>
        """

    return f"""
    <h1>{mood.capitalize()} Songs</h1>
    {song_list}
    <a href="/">Go Back</a>
    """

if __name__ == '__main__':
    app.run(debug=True, port=3000)
