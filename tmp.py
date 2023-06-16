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

def upload_image(filename):
    url = f"{URL_BASE}/items"
    headers = {
        'Authorization': f"Token {token}",
        'x-meural-api-version': '3'
    }
    files = {'image': open(f"{filename}", 'rb')}
    response = session.post(url, headers=headers, files=files, allow_redirects=True, timeout=30)
    return response.json()

def update_metadata(token, image_id, metadata):
    url = f"{URL_BASE}/items/{image_id}"
    headers = {
        'Authorization': f"Token {token}",
        'x-meural-api-version': '3'
    }
    response = session.put(url, headers=headers, data=metadata, allow_redirects=True, timeout=15, verify=False)
    return response.content

def get_playlist_ids_by_name(token):
    url = f"{URL_BASE}/user/galleries?count=500&page=1"
    headers = {
        'Authorization': f"Token {token}",
        'x-meural-api-version': '3'
    }
    response = session.get(url, headers=headers, allow_redirects=True, timeout=15)
    return {playlist['name']: playlist['id'] for playlist in response.json()['data']}

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
    with open("meural.json", 'r') as json_file:
        records = json.load(json_file)

    token = get_authentication_token()
    images = get_uploaded_images(token)
    playlist_ids_by_name = {'Landscape': 423081, 'Portrait': 423080}

    fixes = {
        "16364899": {"checksum": "014ad306fc44a5a66ced38e5116d2add12c13380dd", "icloud_album_id": "B0uGY8gBYGebWnz", "playlist_name": "Portrait"},
        "16364894": {"checksum": "01c65ef831d9881d15a353ed29cabab8af625dd207", "icloud_album_id": "B0uGY8gBYGebWnz", "playlist_name": "Landscape"},
        "16364893": {"checksum": "01c65ef831d9881d15a353ed29cabab8af625dd207", "icloud_album_id": "B0uGY8gBYGebWnz", "playlist_name": "Portrait"},
        "16364892": {"checksum": "01083a027a805a61f921321b8ac5cd452badbc7211", "icloud_album_id": "B0uGY8gBYGebWnz", "playlist_name": "Landscape"},
        "16364891": {"checksum": "01083a027a805a61f921321b8ac5cd452badbc7211", "icloud_album_id": "B0uGY8gBYGebWnz", "playlist_name": "Portrait"},
        "16364847": {"checksum": "018e39ddf6285a9bc509d46cf9ec145e05ffd6b238", "icloud_album_id": "B0uGY8gBYGebWnz", "playlist_name": "Portrait"},
        "16364814": {"checksum": "010f0118077c589a0823eeb9e775974e4cf659b9fe", "icloud_album_id": "B0uGY8gBYGebWnz", "playlist_name": "Landscape"},
        "16364813": {"checksum": "010f0118077c589a0823eeb9e775974e4cf659b9fe", "icloud_album_id": "B0uGY8gBYGebWnz", "playlist_name": "Portrait"},
        "16364781": {"checksum": "015500f2c14c8f13d47e382a572ef4b2dd9665ccb1", "icloud_album_id": "B0uGY8gBYGebWnz", "playlist_name": "Portrait"},
        "16364718": {"checksum": "01f6b22921a613b40fa24c9aa3f2f1b69b99938989", "icloud_album_id": "B0uGY8gBYGebWnz", "playlist_name": "Landscape"},
        "16364717": {"checksum": "01f6b22921a613b40fa24c9aa3f2f1b69b99938989", "icloud_album_id": "B0uGY8gBYGebWnz", "playlist_name": "Portrait"},
        "16364711": {"checksum": "0119ea6777e7ae7956fb89d48fe0bc361788734ad8", "icloud_album_id": "B0uGY8gBYGebWnz", "playlist_name": "Portrait"},
        "16364606": {"checksum": "01cab1510f8230447940e4d3628ff39d68d13daa7c", "icloud_album_id": "B0uGY8gBYGebWnz", "playlist_name": "Portrait"},
        "16364568": {"checksum": "0141bc0a3c1739ba462268d55bb020a0bb86f9859f", "icloud_album_id": "B0uGY8gBYGebWnz", "playlist_name": "Landscape"},
        "16364566": {"checksum": "0141bc0a3c1739ba462268d55bb020a0bb86f9859f", "icloud_album_id": "B0uGY8gBYGebWnz", "playlist_name": "Portrait"},
        "16364558": {"checksum": "01374c7316205ead07d4cba447136320804f6a3df0", "icloud_album_id": "B0uGY8gBYGebWnz", "playlist_name": "Portrait"},
        "16364531": {"checksum": "01276e244c9c6382b8fa4a06c9cb4f54e6c50c4be4", "icloud_album_id": "B0uGY8gBYGebWnz", "playlist_name": "Landscape"},
        "16364530": {"checksum": "01276e244c9c6382b8fa4a06c9cb4f54e6c50c4be4", "icloud_album_id": "B0uGY8gBYGebWnz", "playlist_name": "Portrait"}
    }

    for idx, meural_image in enumerate(images, 1):
        if str(meural_image['id']) in fixes:
            description = fixes[str(meural_image['id'])]
            playlist_id = playlist_ids_by_name[description['playlist_name']]
            image_name = f"{description['checksum']}_{playlist_id}"

            print(f"[{idx}] Updating {meural_image['name']}")
            metadata = {
                "name": image_name
            }
            update_metadata(token, meural_image['id'], metadata)

