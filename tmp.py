import requests
import json
import os
from dotenv import load_dotenv
load_dotenv()

URL_BASE = "https://api.meural.com/v0"

session = requests.Session()

def get_authentication_token():
    url = f"{URL_BASE}/authenticate"
    data = {
        'username': os.getenv("MEURAL_USERNAME", None),
        'password': os.getenv("MEURAL_PASSWORD", None)
    }
    headers = {
        'x-meural-api-version': '3'
    }
    response = session.post(url, headers=headers, data=data, allow_redirects=True, timeout=15, verify=False)
    return response.json()['token']

def get_uploaded_images(token):
    url = f"{URL_BASE}/user/items?count=500&page=1"
    headers = {
        'Authorization': f"Token {token}",
        'x-meural-api-version': '3'
    }
    response = session.get(url, headers=headers, allow_redirects=True, timeout=15, verify=False)
    return response.json()['data']

def update_metadata(token, image_id, metadata):
    url = f"{URL_BASE}/items/{image_id}"
    headers = {
        'Authorization': f"Token {token}",
        'x-meural-api-version': '3'
    }
    response = session.put(url, headers=headers, data=metadata, allow_redirects=True, timeout=15, verify=False)
    return response.content


def find_image(records, meural_image):
    meural_image_name = meural_image['name']
    for checksum, playlist_data in records['B0uGY8gBYGebWnz'].items():
        for playlist_name, record_data in playlist_data.items():
            record_filename = record_data['filename'].rsplit('.', 1)[0]
            if len(record_filename) > 64:
                record_filename = record_filename[:64]
            if record_filename.rsplit('.', 1)[0] == meural_image_name:
                print(f"\tFound {meural_image_name} in {playlist_name}")
                return 'B0uGY8gBYGebWnz', checksum, playlist_name
    return None, None, None

if __name__ == "__main__":
    records = {}
    with open("records.json", 'r') as json_file:
        records = json.load(json_file)
    token = get_authentication_token()
    images = get_uploaded_images(token)
    full_len = len(images)
    for idx, image in enumerate(images, 1):
        # if idx != 57:
        #     continue
        print(f"[{idx}/{full_len}] Updating {image['name']}")
        icloud_id, checksum, playlist_name = find_image(records, image)
        metadata = {
            "description": f'{{"icloud_album_id": "{icloud_id}", "checksum": "{checksum}", "playlist_name": "{playlist_name}"}}'
        }
        update_metadata(token, image['id'], metadata)
        print(f"\tUpdated {image['name']}: {image['id']}")