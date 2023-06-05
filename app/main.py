import icloud, meural
import json
import os
from loguru import logger
import time
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
    env_vars = ["ICLOUD_ALBUM_URL", "MEURAL_USERNAME", "MEURAL_PASSWORD", "MEURAL_PLAYLIST", "UPDATE_FREQUENCY"]
    for env_var in env_vars:
        if os.getenv(env_var, None) is None:
            raise ValueError(f"{env_var} Environment variable not set")

IMAGE_DIR = os.path.join(os.getcwd(), "icloud") if not os.getenv("IN_CONTAINER", False) else "/data"
MEURAL_PLAYLIST = os.getenv("MEURAL_PLAYLIST")
UPDATE_FREQUENCY_MINS = os.getenv("UPDATE_FREQUENCY_MINS")

class Metadata:
    metadata_loc = f"{IMAGE_DIR}/records.json"
    db = {}
    item_template = {
        "filename": None,
        "meural_id": None,
        "added_to_playlist": None
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
            uploaded_path = f"{IMAGE_DIR}/uploaded/{file_data['filename']}"
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
    def update_item(cls, image_checksum, meural_id=None, added_to_playlist=False):
        if meural_id is not None:
            cls.db[image_checksum]['meural_id'] = meural_id
        if added_to_playlist is not None:
            cls.db[image_checksum]['added_to_playlist'] = added_to_playlist
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
    def get_items_not_added_to_playlist(cls):
        not_added_to_playlist = []
        for checksum, file_data in cls.db.items():
            if file_data['meural_id'] is not None and file_data['added_to_playlist'] is False:
                not_added_to_playlist.append((checksum, file_data['filename'], file_data['meural_id']))
        return not_added_to_playlist

Metadata.initialize()
Metadata.verify_integrity_and_cleanup()

def add_image_to_meural_playlist(meural_token, meural_playlist_id, image_id, image_checksum, image_filename):
    logger.info(f"Adding image to {MEURAL_PLAYLIST} Meural playlist")
    added_to_playlist = False
    try:
        image_ids_in_playlist = meural.add_image_to_playlist(meural_token, image_id, meural_playlist_id)
        added_to_playlist = True
    except:
        pass
    if not added_to_playlist or image_id not in image_ids_in_playlist:
        logger.error(f"[X] Failed to add {image_filename} to playlist")
    else:
        logger.info(f"[✓] Successfully added {image_filename} to playlist")
        Metadata.update_item(image_checksum, added_to_playlist=True)
    return

def scheduled_task(meural_token, meural_playlist_id):
    # Download items from iCloud which have not already been downloaded
    icloud.download_album(Metadata, image_dir=IMAGE_DIR)

    # Now find items not yet uploaded to Meural
    not_uploaded = Metadata.get_items_not_yet_uploaded()
    len_items_not_uploaded = len(not_uploaded)
    logger.info(f"Preparing to upload {len_items_not_uploaded} items to the {MEURAL_PLAYLIST} Meural playlist")
    for idx, (image_checksum, image_filename) in enumerate(not_uploaded, start=1):
        logger.info(f"[{idx}/{len_items_not_uploaded}] Uploading {image_filename}")
        try:
            image_id = meural.upload_image(meural_token, IMAGE_DIR+"/not_uploaded", image_filename)
            logger.info(f"[X] Successfully uploaded {image_filename}")
            image_path = f"{IMAGE_DIR}/not_uploaded/{image_filename}"
            os.rename(image_path, image_path.replace("not_uploaded", "uploaded"))
        except:
            logger.error(f"[X] Failed to upload image {image_filename}")
            continue
        Metadata.update_item(image_checksum, meural_id=image_id)
        add_image_to_meural_playlist(meural_token, meural_playlist_id, image_id, image_checksum, image_filename)

    # Now find items which were previously uploaded, but not added to the Meural playlist
    not_added_to_playlist = Metadata.get_items_not_added_to_playlist()
    len_items_not_added_to_playlist = len(not_added_to_playlist)
    if not_added_to_playlist:
        logger.info(f"{len_items_not_added_to_playlist} items were previously uploaded, but not added to the {MEURAL_PLAYLIST} Meural playlist")
        for idx, (image_checksum, image_filename, image_id) in enumerate(not_added_to_playlist, start=1):
            logger.info(f"[{idx}/{len_items_not_added_to_playlist}] Adding {image_filename} to playlist")
            add_image_to_meural_playlist(meural_token, meural_playlist_id, image_id, image_checksum, image_filename)


#TODO: Prune items that are no longer in iCloud
if __name__ == "__main__":
    logger.info(f"MeuralCanvas-iCloudSync Launched For {MEURAL_PLAYLIST} Meural Playlist")
    validate_env_vars()
    meural_token = meural.get_authentication_token()
    meural_playlist_id = meural.get_playlist_id(meural_token)
    while True:
        logger.info("Starting scheduled update!")
        scheduled_task(meural_token, meural_playlist_id)
        logger.info(f"Done! Pausing for {UPDATE_FREQUENCY_MINS} minutes until next update...")
        time.sleep(UPDATE_FREQUENCY_MINS*60)
