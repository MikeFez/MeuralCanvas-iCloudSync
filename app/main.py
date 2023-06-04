import icloud, meural
import json
import os
from loguru import logger
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
    env_vars = ["ICLOUD_ALBUM_URL", "MEURAL_USERNAME", "MEURAL_PASSWORD", "MEURAL_PLAYLIST"]
    for env_var in env_vars:
        if os.getenv(env_var, None) is None:
            raise ValueError(f"{env_var} Environment variable not set")

IMAGE_DIR = os.path.join(os.getcwd(), "icloud") if not os.getenv("IN_CONTAINER", False) else "/data"

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
        not_uploaded = []
        for checksum, file_data in cls.db.items():
            if file_data['meural_id'] is not None and file_data['added_to_playlist'] is None:
                not_uploaded.append((checksum, file_data['filename'], file_data['meural_id']))
        return not_uploaded

Metadata.initialize()

def scheduled_task(meural_token, meural_playlist_id):
    # Download items from iCloud which have not already been downloaded
    icloud.download_album(Metadata, image_dir=IMAGE_DIR)

    # Now find items not yet uploaded to Meural
    not_uploaded = Metadata.get_items_not_yet_uploaded()
    len_items_not_uploaded = len(not_uploaded)
    logger.info(f"Preparing to upload {len_items_not_uploaded} items to the {'XXXX'} Meural playlist")
    for idx, (image_checksum, image_filename) in enumerate(not_uploaded, start=1):
        logger.info(f"\t[{idx}/{len_items_not_uploaded}] Uploading {image_filename}")
        image_id = meural.upload_image(meural_token, IMAGE_DIR, image_filename)
        Metadata.update_item(image_checksum, meural_id=image_id)
        logger.info(f"\t\tAdding image to {'XXXX'} Meural playlist")
        image_ids_in_playlist = meural.add_image_to_playlist(meural_token, image_id, meural_playlist_id)
        if image_id not in image_ids_in_playlist:
            logger.error(f"Failed to add image {image_filename} to playlist {'XXXX'}")
        else:
            logger.info(f"\t\tAdded image {image_filename} to playlist {'XXXX'}")
            Metadata.update_item(image_checksum, added_to_playlist=True)

    not_added_to_playlist = Metadata.get_items_not_added_to_playlist()
    len_items_not_added_to_playlist = len(not_added_to_playlist)
    if not_added_to_playlist:
        logger.info(f"{len_items_not_added_to_playlist} items were previously uploaded, but not added to the {'XXXX'} Meural playlist")
        for idx, (image_checksum, image_filename, image_id) in enumerate(not_uploaded, start=1):
            logger.info(f"\t[{idx}/{len_items_not_added_to_playlist}] Adding {image_filename} to playlist {'XXXX'}")
            image_ids_in_playlist = meural.add_image_to_playlist(meural_token, image_id, meural_playlist_id)
            if image_id not in image_ids_in_playlist:
                logger.error(f"Failed to add image {image_filename} to playlist {'XXXX'}")
            else:
                logger.info(f"\t\tAdded image {image_filename} to playlist {'XXXX'}")
                Metadata.update_item(image_checksum, added_to_playlist=True)

    logger.info(f"Done! Pausing until next update...")

#TODO: Prune items that are no longer in iCloud
if __name__ == "__main__":
    validate_env_vars()
    meural_token = meural.get_authentication_token()
    meural_playlist_id = meural.get_playlist_id(meural_token)
    scheduled_task(meural_token, meural_playlist_id)