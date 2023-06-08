from loguru import logger
import requests
import os

if not os.getenv("IN_CONTAINER", False):
    from dotenv import load_dotenv
    load_dotenv()

URL_BASE = "https://api.meural.com/v0"
MEURAL_PLAYLISTS = [playlist.strip() for playlist in os.getenv("MEURAL_PLAYLIST").split(',')]
MEURAL_USERNAME = os.getenv("MEURAL_USERNAME")
MEURAL_PASSWORD = os.getenv("MEURAL_PASSWORD")

session = requests.Session()

def get_authentication_token():
    url = f"{URL_BASE}/authenticate"
    data = {
        'username': MEURAL_USERNAME,
        'password': MEURAL_PASSWORD
    }
    headers = {
        'x-meural-api-version': '3'
    }
    response = session.post(url, headers=headers, data=data, allow_redirects=True, timeout=15)
    return response.json()['token']

def get_uploaded_images(token):
    url = f"{URL_BASE}/user/items?count=300&page=1"
    headers = {
        'Authorization': f"Token {token}",
        'x-meural-api-version': '3'
    }
    response = session.get(url, headers=headers, allow_redirects=True, timeout=15)
    return {image['name']: image['id'] for image in response.json()['data']}

def get_playlist_ids(token):
    url = f"{URL_BASE}/user/galleries?count=10&page=1"
    headers = {
        'Authorization': f"Token {token}",
        'x-meural-api-version': '3'
    }
    response = session.get(url, headers=headers, allow_redirects=True, timeout=15)
    return {playlist['name']: playlist['id'] for playlist in response.json()['data'] if playlist['name'] in MEURAL_PLAYLISTS}

def upload_image(token, image_dir, filename):
    url = f"{URL_BASE}/items"
    headers = {
        'Authorization': f"Token {token}",
        'x-meural-api-version': '3'
    }
    files = {'image': open(f"{image_dir}/{filename}", 'rb')}
    response = session.post(url, headers=headers, files=files, allow_redirects=True, timeout=30)
    return response.json()['data']['id']

def delete_image(token, image_id):
    url = f"{URL_BASE}/items/{image_id}"
    headers = {
        'Authorization': f"Token {token}",
        'x-meural-api-version': '3'
    }
    response = session.delete(url, headers=headers, allow_redirects=True, timeout=15)
    print(response.json())
    return response.json()

def add_image_to_playlist(token, image_id, playlist_id):
    url = f"{URL_BASE}/galleries/{playlist_id}/items/{image_id}"
    headers = {
        'Authorization': f"Token {token}",
        'x-meural-api-version': '3'
    }
    response = session.post(url, headers=headers, allow_redirects=True, timeout=15)
    return response.json()['data']['itemIds']

if __name__ == "__main__":
    token = get_authentication_token()
    playlist_id = get_playlist_ids(token)
    print(token)
    print(playlist_id)