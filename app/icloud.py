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


def is_file_already_downloaded(Metadata, icloud_album_id, checksum, playlist_name):
    if icloud_album_id in Metadata.db:
        if checksum in Metadata.db[icloud_album_id]:
            if playlist_name in Metadata.db[icloud_album_id][checksum]:
                if Metadata.db[icloud_album_id][checksum][playlist_name]["filename"] is not None:
                    return True
    return False

def download_album(Metadata, icloud_album_url, meural_playlists_data, image_dir):
    logger.info("Retrieving iCloud album information...")
    icloud_album_id = icloud_album_url.split('#')[1]
    base_api_url = f"https://p23-sharedstreams.icloud.com/{icloud_album_id}/sharedstreams"

    stream_data = {"streamCtag": None}
    stream = post_json(f"{base_api_url}/webstream", stream_data)
    host = stream.get("X-Apple-MMe-Host")
    if host:
        host = host.rsplit(':')[0]
        base_api_url = f"https://{host}/{icloud_album_id}/sharedstreams"
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
    root_save_path = f"{image_dir}/not_uploaded/"
    for key, value in asset_urls.items():
        url = f"https://{value['url_location']}{value['url_path']}&{key}"
        for checksum in checksums:
            if checksum in url:
                original_filename = f"{icloud_album_id}_" + url.split('?')[0].split('/')[-1]
                logger.info(f"\tDownloading {original_filename}")
                res = requests.get(url)

                if not is_file_already_downloaded(Metadata, icloud_album_id, checksum, playlist_name):
                    filename_after_playlist = original_filename
                    for playlist_data in meural_playlists_data:
                        playlist_name = playlist_data['name']
                        if playlist_data['unique_upload']:
                            filename_after_playlist = original_filename.replace(f"{icloud_album_id}_", f"{icloud_album_id}_{playlist_name}_")
                        else:
                            filename_after_playlist = original_filename

                        save_as_filename = filename_after_playlist
                        appended_int = 1
                        while os.path.isfile(root_save_path+save_as_filename):
                            save_as_filename = filename_after_playlist.replace(".", f" ({appended_int}).")
                            appended_int += 1

                        with open(root_save_path+save_as_filename, 'wb') as f:
                            f.write(res.content)
                        Metadata.add_item(icloud_album_id, checksum, playlist_name, save_as_filename)
                    num_items_downloaded += 1
                break
    logger.info(f"Downloaded {num_items_downloaded} new items from iCloud")
    return icloud_album_id, checksums
