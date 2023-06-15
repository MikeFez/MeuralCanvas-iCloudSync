from loguru import logger
import json
import os
import requests

if not os.getenv("IN_CONTAINER", False):
    from dotenv import load_dotenv
    load_dotenv()

def post_json(url, data):
    response = requests.post(url, data=json.dumps(data), headers={'Content-Type': 'application/json'})
    return response.json()

def download_album(Metadata, icloud_album_url, image_dir):
    logger.info("Retrieving iCloud album information...")
    album_id = icloud_album_url.split('#')[1]
    base_api_url = f"https://p23-sharedstreams.icloud.com/{album_id}/sharedstreams"

    stream_data = {"streamCtag": None}
    stream = post_json(f"{base_api_url}/webstream", stream_data)
    host = stream.get("X-Apple-MMe-Host")
    if host:
        host = host.rsplit(':')[0]
        base_api_url = f"https://{host}/{album_id}/sharedstreams"
        stream = post_json(f"{base_api_url}/webstream", stream_data)

    icloud_album_name = stream["streamName"]
    logger.info(f"\tConnected to {icloud_album_name} album: acquiring photo checksums & guids...")

    # Get the checksums for the highest available resolution of each photo
    checksums = []
    for photo in stream["photos"]:
        checksums.append(photo['derivatives'][str(max(int(x) for x in photo["derivatives"].keys()))]['checksum'])

    # Get all photo guids and request all asset urls
    photo_guids = {"photoGuids": [photo["photoGuid"] for photo in stream["photos"]]}
    asset_urls = post_json(f"{base_api_url}/webasseturls", photo_guids)["items"]
    num_items_downloaded = 0
    for key, value in asset_urls.items():
        url = f"https://{value['url_location']}{value['url_path']}&{key}"
        for checksum in checksums:
            if checksum in url:
                original_filename = url.split('?')[0].split('/')[-1]
                actual_filename = original_filename
                if checksum not in Metadata.db:
                    final_path = f"{image_dir}/not_uploaded/{actual_filename}"
                    appended_int = 1
                    while os.path.isfile(final_path):
                        actual_filename = original_filename.replace(".", f" ({appended_int}).")
                        final_path = f"{image_dir}/not_uploaded/{actual_filename}"
                        appended_int += 1

                    logger.info(f"\tDownloading {actual_filename}")
                    res = requests.get(url)
                    with open(final_path, 'wb') as f:
                        f.write(res.content)
                    Metadata.add_item(icloud_album_name, checksum, actual_filename)
                    num_items_downloaded += 1
                break
    logger.info(f"Downloaded {num_items_downloaded} new items from iCloud")
    return icloud_album_name, checksums
