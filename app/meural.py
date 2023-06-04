from loguru import logger
import requests
import os

if not os.getenv("IN_CONTAINER", False):
    from dotenv import load_dotenv
    load_dotenv()

URL_BASE = "https://api.meural.com/v0/"
MEURAL_PLAYLIST = os.getenv("MEURAL_PLAYLIST")
MEURAL_USERNAME = os.getenv("MEURAL_USERNAME")
MEURAL_PASSWORD = os.getenv("MEURAL_PASSWORD")

session = requests.Session()
MAX_REQEUST_ATTEMPTS = 3

def get_authentication_token():
    url = URL_BASE + "authenticate"
    data = {
        'username': MEURAL_USERNAME,
        'password': MEURAL_PASSWORD
    }
    headers = {
        'x-meural-api-version': '3'
    }
    response = session.post(url, headers=headers, data=data, allow_redirects=True)
    return response.json()['token']

def get_playlist_id(token):
    url = URL_BASE + "user/galleries?count=10&page=1"
    headers = {
        'Authorization': f"Token {token}",
        'x-meural-api-version': '3'
    }
    response = session.get(url, headers=headers, allow_redirects=True)
    return [playlist['id'] for playlist in response.json()['data'] if playlist['name'] == MEURAL_PLAYLIST][0]

def upload_image(token, image_dir, filename):
    url = URL_BASE + "items"
    headers = {
        'Authorization': f"Token {token}",
        'x-meural-api-version': '3'
    }
    files = {'image': open(f"{image_dir}/{filename}", 'rb')}
    uploaded = False
    attempts = 1
    while not uploaded and attempts <= 3:
        try:
            response = session.post(url, headers=headers, files=files, allow_redirects=True)
        except requests.exceptions.RequestException as e:
            logger.error(f"Error uploading image {filename}: {e}")
            attempts += 1
            logger.info(f"Retrying, attempt {attempts} of {MAX_REQEUST_ATTEMPTS}...")
    return response.json()['data']['id']

def add_image_to_playlist(token, image_id, playlist_id):
    url = URL_BASE + f"galleries/{playlist_id}/items/{image_id}"
    headers = {
        'Authorization': f"Token {token}",
        'x-meural-api-version': '3'
    }
    uploaded = False
    attempts = 1
    while not uploaded and attempts <= 3:
        try:
            response = session.post(url, headers=headers, allow_redirects=True)
        except requests.exceptions.RequestException as e:
            logger.error(f"Error adding image to playlist: {e}")
            attempts += 1
            logger.info(f"Retrying, attempt {attempts} of {MAX_REQEUST_ATTEMPTS}...")

    return response.json()['data']['itemIds']
