import icloud, meural
import json
import os
from loguru import logger
import time
from glob import glob
import sys

if not os.getenv("IN_CONTAINER", False):
    from dotenv import load_dotenv
    load_dotenv()

try:
    logger.remove(0)
except ValueError:
    pass
logger.add(sys.stderr, level="INFO")

def validate_env_vars():
    env_vars = ["ICLOUD_ALBUM_URL", "MEURAL_USERNAME", "MEURAL_PASSWORD", "MEURAL_PLAYLISTS", "UPDATE_FREQUENCY_MINS"]
    for env_var in env_vars:
        if os.getenv(env_var, None) is None:
            raise ValueError(f"{env_var} Environment variable not set")

IMAGE_DIR = os.path.join(os.getcwd(), "data") if not os.getenv("IN_CONTAINER", False) else "/data"
UPDATE_FREQUENCY_MINS = os.getenv("UPDATE_FREQUENCY_MINS")

class Metadata:
    metadata_loc = f"{IMAGE_DIR}/records.json"
    db = {}
    item_template = {
        "filename": None,
        "meural_id": None,
        "added_to_playlist": []
    }

    @classmethod
    def initialize(cls):
        if os.path.isfile(cls.metadata_loc):
            with open(cls.metadata_loc, 'r') as json_file:
                records = json.load(json_file)
        else:
            records = {}
        cls.db = records

    @classmethod
    def verify_integrity_and_cleanup(cls):
        logger.info("Verifying integrity of files")
        make_paths = [IMAGE_DIR, f"{IMAGE_DIR}/uploaded", f"{IMAGE_DIR}/not_uploaded"]
        for path in make_paths:
            if not os.path.isdir(path):
                logger.info(f"Creating directory {path}")
                os.makedirs(path)

        for checksum, file_data in cls.db.items():
            not_uploaded_path = f"{IMAGE_DIR}/not_uploaded/{file_data['filename']}"
            uploaded_path = not_uploaded_path.replace("/not_uploaded/", "/uploaded/")
            if file_data['meural_id'] is None:
                # File was not uploaded
                if not os.path.isfile(not_uploaded_path):
                    logger.warning(f"File {file_data['filename']} not found in {IMAGE_DIR}/not_uploaded")
                    if not os.path.isfile(uploaded_path):
                        logger.error(f"File {file_data['filename']} also was not found in {IMAGE_DIR}/uploaded")
                        raise EnvironmentError("File is missing!")
                    else:
                        logger.info(f"File {file_data['filename']} found in {IMAGE_DIR}/uploaded - moving to proper directory")
                        os.rename(uploaded_path, not_uploaded_path)
            else:
                # File was uploaded
                if not os.path.isfile(uploaded_path):
                    logger.warning(f"File {file_data['filename']} not found in {IMAGE_DIR}/uploaded")
                    if not os.path.isfile(not_uploaded_path):
                        logger.error(f"File {file_data['filename']} also was not found in {IMAGE_DIR}/not_uploaded")
                        raise EnvironmentError("File is missing!")
                    else:
                        logger.info(f"File {file_data['filename']} found in {IMAGE_DIR}/not_uploaded - moving to proper directory")
                        os.rename(not_uploaded_path, uploaded_path)


    @classmethod
    def add_item(cls, checksum=None, filename=None):
        record = cls.item_template.copy()
        record['filename'] = filename
        cls.db[checksum] = record
        with open(cls.metadata_loc, 'w') as json_file:
            json.dump(cls.db, json_file, indent=4)

    @classmethod
    def mark_uploaded_to_meural(cls, image_checksum, meural_id):
        cls.db[image_checksum]['meural_id'] = meural_id
        with open(cls.metadata_loc, 'w') as json_file:
            json.dump(cls.db, json_file, indent=4)

    @classmethod
    def mark_added_to_playlist(cls, image_checksum, playlist):
        cls.db[image_checksum]['added_to_playlist'].append(playlist)
        with open(cls.metadata_loc, 'w') as json_file:
            json.dump(cls.db, json_file, indent=4)

    @classmethod
    def delete_item(cls, image_checksum):
        del cls.db[image_checksum]
        with open(cls.metadata_loc, 'w') as json_file:
            json.dump(cls.db, json_file, indent=4)

    @classmethod
    def get_items_not_yet_uploaded(cls):
        not_uploaded = []
        for checksum, file_data in cls.db.items():
            if file_data['meural_id'] is None:
                not_uploaded.append((checksum, file_data['filename']))
        return not_uploaded

    @classmethod
    def get_items_not_added_to_playlist(cls, playlists_to_check):
        not_added_to_playlist = {playlist: [] for playlist in playlists_to_check}
        for checksum, file_data in cls.db.items():
            for playlist in playlists_to_check:
                if file_data['meural_id'] is not None and playlist not in file_data['added_to_playlist']:
                    not_added_to_playlist[playlist].append((checksum, file_data['filename'], file_data['meural_id']))
        return not_added_to_playlist

Metadata.initialize()
Metadata.verify_integrity_and_cleanup()

def add_image_to_meural_playlists(meural_token, meural_playlist_name, meural_playlist_id, image_id, image_checksum, image_filename):
    try:
        logger.info(f"Adding image to {meural_playlist_name} Meural playlist")
        image_ids_in_playlist = meural.add_image_to_playlist(meural_token, image_id, meural_playlist_id)
        if image_id not in image_ids_in_playlist:
            raise Exception("Meural indicated the image was not added to the playlist!")
        logger.info(f"[✓] Successfully added {image_filename} to playlist")
        Metadata.mark_added_to_playlist(image_checksum, meural_playlist_name)
    except Exception as e:
        logger.error(f"[X] Failed to add {image_filename} to playlist: {e}")
    return

def delete_images_from_meural_if_needed(meural_token, album_checksums):
    since_been_deleted_checksums = [checksum for checksum in Metadata.db.keys() if checksum not in album_checksums]
    logger.info(f"Preparing to delete {len(since_been_deleted_checksums)} items from Meural")
    for checksum in since_been_deleted_checksums:
        image_filename = Metadata.db[checksum]['filename']
        try:
            meural.delete_image(meural_token, Metadata.db[checksum]['meural_id'])
            Metadata.delete_item(checksum)

            potential_image_location = f"{IMAGE_DIR}/not_uploaded/{image_filename}"
            for potential_location in (potential_image_location, potential_image_location.replace('/not_uploaded/', '/uploaded/')):
                if os.path.isfile(potential_location):
                    os.remove(potential_location)
                    logger.info(f"[✓] Successfully deleted {image_filename} from local storage")
                    break
            logger.info(f"[✓] Successfully deleted {image_filename} from Meural")
        except Exception as e:
            logger.error(f"[X] Failed to delete {image_filename} from Meural: {e}")
        return

def scheduled_task(meural_token, meural_playlist_data):
    # Download items from iCloud which have not already been downloaded
    album_checksums = icloud.download_album(Metadata, image_dir=IMAGE_DIR)
    if album_checksums:
        delete_images_from_meural_if_needed(meural_token, album_checksums)

    # Now find items not yet uploaded to Meural
    not_uploaded = Metadata.get_items_not_yet_uploaded()
    len_items_not_uploaded = len(not_uploaded)
    logger.info(f"Preparing to upload {len_items_not_uploaded} items to Meural")
    for idx, (image_checksum, image_filename) in enumerate(not_uploaded, start=1):
        logger.info(f"[{idx}/{len_items_not_uploaded}] Uploading {image_filename}")
        try:
            image_id = meural.upload_image(meural_token, IMAGE_DIR+"/not_uploaded", image_filename)
            logger.info(f"[X] Successfully uploaded {image_filename}")
            image_path = f"{IMAGE_DIR}/not_uploaded/{image_filename}"
            os.rename(image_path, image_path.replace("/not_uploaded/", "/uploaded/"))
        except Exception as e:
            logger.error(f"[X] Failed to upload image {image_filename}: {e}")
            continue
        Metadata.mark_uploaded_to_meural(image_checksum, image_id)
        for playlist_name, playlist_id in meural_playlist_data.items():
            add_image_to_meural_playlists(meural_token, playlist_name, playlist_id, image_id, image_checksum, image_filename)

    # Now find items which were previously uploaded, but not added to the Meural playlist
    not_added_to_playlist = Metadata.get_items_not_added_to_playlist(meural_playlist_data.keys())
    if not_added_to_playlist:
        for playlist_name, items_not_added in not_added_to_playlist.items():
            len_items_not_added_to_playlist = len(items_not_added)
            playlist_id = meural_playlist_data[playlist_name]
            logger.info(f"{len_items_not_added_to_playlist} items were previously uploaded, but not added to the {playlist_name} Meural playlist")
            for idx, (image_checksum, image_filename, image_id) in enumerate(items_not_added, start=1):
                logger.info(f"[{idx}/{len_items_not_added_to_playlist}] Adding {image_filename} to playlist")
                add_image_to_meural_playlists(meural_token, playlist_name, playlist_id, image_id, image_checksum, image_filename)


#TODO: Prune items that are no longer in iCloud
if __name__ == "__main__":
    logger.info(f"MeuralCanvas-iCloudSync Launched")
    validate_env_vars()
    meural_token = meural.get_authentication_token()
    meural_playlist_data = meural.get_playlist_ids(meural_token)
    while True:
        logger.info("Starting scheduled update!")
        scheduled_task(meural_token, meural_playlist_data)
        logger.info(f"Done! Pausing for {UPDATE_FREQUENCY_MINS} minutes until next update...")
        time.sleep(int(UPDATE_FREQUENCY_MINS)*60)
