import icloud, meural
import json
import yaml
import os
from loguru import logger
import time
from glob import glob
import sys

IN_CONTAINER = os.getenv("IN_CONTAINER", False)
UPDATE_FREQUENCY_MINS = os.getenv("UPDATE_FREQUENCY_MINS", None)
IMAGE_DIR = os.path.join(os.getcwd(), "images") if not IN_CONTAINER else "/images"
CONFIG_DIR = os.path.join(os.getcwd(), "config") if not IN_CONTAINER else "/config"

if not IN_CONTAINER:
    from dotenv import load_dotenv
    load_dotenv()

# Set up loguru
try:
    logger.remove(0)
except ValueError:
    pass
logger.add(sys.stderr, level="INFO")

def validate_environment():
    # First check directories
    directories = [IMAGE_DIR, CONFIG_DIR]
    for directory in directories:
        if not os.path.isdir(directory):
            raise ValueError(f"{directory} directory was not found")

    # Second check env vars
    env_vars = ["MEURAL_USERNAME", "MEURAL_PASSWORD", "UPDATE_FREQUENCY_MINS"]
    for env_var in env_vars:
        if os.getenv(env_var, None) is None:
            raise ValueError(f"{env_var} Environment variable not set")

class Metadata:
    config_loc = f"{CONFIG_DIR}/config.yaml"
    metadata_loc = f"{CONFIG_DIR}/records.json"

    config = None
    db = {}
    item_template = {
        "filename": None,
        "meural_id": None,
        "added_to_playlist": []
    }

    @classmethod
    def initialize(cls):
        # First grab the config
        if os.path.isfile(cls.config_loc):
            with open(cls.config_loc, 'r') as yaml_file:
                config = yaml.safe_load(yaml_file)
            if "sync" not in config:
                raise ValueError(f'Config file is missing top-level "sync" key')
            elif config["sync"] is None:
                raise ValueError(f'There are no items to sync in the config. Ensure there is at least one item under "sync" prior to launching this container.')
            else:
                cls.config = config
        else:
            raise ValueError(f"Config file was not found. Please add one prior to launching this container.")

        # Now populate metadata db
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
        for icloud_album_id, album_db in cls.db.items():
            for checksum, file_data in album_db.items():
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
    def add_item(cls, icloud_album_id, checksum, filename):
        record = cls.item_template.copy()
        record['filename'] = filename
        if icloud_album_id not in cls.db:
            cls.db[icloud_album_id] = {}
        cls.db[icloud_album_id][checksum] = record
        with open(cls.metadata_loc, 'w') as json_file:
            json.dump(cls.db, json_file, indent=4)

    @classmethod
    def mark_uploaded_to_meural(cls, icloud_album_id, image_checksum, meural_id):
        cls.db[icloud_album_id][image_checksum]['meural_id'] = meural_id
        with open(cls.metadata_loc, 'w') as json_file:
            json.dump(cls.db, json_file, indent=4)

    @classmethod
    def mark_added_to_playlist(cls, icloud_album_id, image_checksum, playlist):
        cls.db[icloud_album_id][image_checksum]['added_to_playlist'].append(playlist)
        with open(cls.metadata_loc, 'w') as json_file:
            json.dump(cls.db, json_file, indent=4)

    @classmethod
    def delete_item(cls, icloud_album_id, image_checksum):
        del cls.db[icloud_album_id][image_checksum]
        with open(cls.metadata_loc, 'w') as json_file:
            json.dump(cls.db, json_file, indent=4)

    @classmethod
    def get_items_not_yet_uploaded(cls, icloud_album_id):
        not_uploaded = []
        for checksum, file_data in cls.db[icloud_album_id].items():
            if file_data['meural_id'] is None:
                not_uploaded.append((checksum, file_data['filename']))
        return not_uploaded

    @classmethod
    def get_items_not_added_to_playlist(cls, icloud_album_id, playlists_to_check):
        not_added_to_playlist = {playlist: [] for playlist in playlists_to_check}
        for checksum, file_data in cls.db[icloud_album_id].items():
            for playlist in playlists_to_check:
                if file_data['meural_id'] is not None and playlist not in file_data['added_to_playlist']:
                    not_added_to_playlist[playlist].append((checksum, file_data['filename'], file_data['meural_id']))
        return not_added_to_playlist

def add_image_to_meural_playlists(meural_token, meural_playlist_name, meural_playlist_id, icloud_album_id, image_id, image_checksum, image_filename):
    try:
        logger.info(f"Adding image to {meural_playlist_name} Meural playlist")
        image_ids_in_playlist = meural.add_image_to_playlist(meural_token, image_id, meural_playlist_id)
        if image_id not in image_ids_in_playlist:
            raise Exception("Meural indicated the image was not added to the playlist!")
        logger.info(f"[✓] Successfully added {image_filename} to playlist")
        Metadata.mark_added_to_playlist(icloud_album_id, image_checksum, meural_playlist_name)
    except Exception as e:
        logger.error(f"[X] Failed to add {image_filename} to playlist: {e}")
    return

def delete_images_from_meural_if_needed(meural_token, icloud_album_id, album_checksums):
    since_been_deleted_checksums = []
    if icloud_album_id in Metadata.db:
        since_been_deleted_checksums = [checksum for checksum in Metadata.db[icloud_album_id].keys() if checksum not in album_checksums]
    logger.info(f"Preparing to delete {len(since_been_deleted_checksums)} items from Meural")
    for checksum in since_been_deleted_checksums:
        if checksum in Metadata.db[icloud_album_id]:
            image_filename = Metadata.db[icloud_album_id][checksum]['filename']
            try:
                meural.delete_image(meural_token, Metadata.db[checksum]['meural_id'])
                Metadata.delete_item(icloud_album_id, checksum)

                potential_image_location = f"{IMAGE_DIR}/not_uploaded/{image_filename}"
                for potential_location in (potential_image_location, potential_image_location.replace('/not_uploaded/', '/uploaded/')):
                    if os.path.isfile(potential_location):
                        os.remove(potential_location)
                        logger.info(f"[✓] Successfully deleted {image_filename} from local storage")
                        break
                logger.info(f"[✓] Successfully deleted {image_filename} from Meural")
            except Exception as e:
                logger.error(f"[X] Failed to delete {image_filename} from Meural: {e}")
        else:
            logger.warning(f"Checksum {checksum} not found in metadata for album id {icloud_album_id}")
    return

def scheduled_task(meural_token, meural_playlist_ids_by_name):
    for sync_item in Metadata.config["sync"]:
        icloud_album_url = sync_item["icloud_album"]
        meural_playlists_to_sync_to = sync_item["meural_playlists"]

        # Validate playlist has items
        if meural_playlists_to_sync_to is None or len(meural_playlists_to_sync_to) == 0:
            raise ValueError(f"Cannot sync {icloud_album_url} because no Meural playlists were specified")

        # Grab name: id relationship of only those we want to sync this album to
        this_album_playlist_ids_by_name = {}
        for playlist_name in meural_playlists_to_sync_to:
            if playlist_name not in meural_playlist_ids_by_name:
                raise ValueError(f"Cannot sync {icloud_album_url} because {playlist_name} Meural playlist does not exist")
            this_album_playlist_ids_by_name[playlist_name] = meural_playlist_ids_by_name[playlist_name]

        # Download items from iCloud which have not already been downloaded
        icloud_album_id, album_checksums = icloud.download_album(Metadata, icloud_album_url, IMAGE_DIR)
        if album_checksums:
            delete_images_from_meural_if_needed(meural_token, icloud_album_id, album_checksums)

        # Now find items not yet uploaded to Meural
        not_uploaded = Metadata.get_items_not_yet_uploaded(icloud_album_id)
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
            Metadata.mark_uploaded_to_meural(icloud_album_id, image_checksum, image_id)
            for playlist_name, playlist_id in this_album_playlist_ids_by_name:
                add_image_to_meural_playlists(meural_token, playlist_name, playlist_id, icloud_album_id, image_id, image_checksum, image_filename)

        # Now find items which were previously uploaded, but not added to the Meural playlist
        not_added_to_playlist = Metadata.get_items_not_added_to_playlist(icloud_album_id, this_album_playlist_ids_by_name.keys())
        if not_added_to_playlist:
            for playlist_name, items_not_added in not_added_to_playlist.items():
                len_items_not_added_to_playlist = len(items_not_added)
                playlist_id = this_album_playlist_ids_by_name[playlist_name]
                logger.info(f"{len_items_not_added_to_playlist} items were previously uploaded, but not added to the {playlist_name} Meural playlist")
                for idx, (image_checksum, image_filename, image_id) in enumerate(items_not_added, start=1):
                    logger.info(f"[{idx}/{len_items_not_added_to_playlist}] Adding {image_filename} to playlist")
                    add_image_to_meural_playlists(meural_token, playlist_name, playlist_id, icloud_album_id, image_id, image_checksum, image_filename)


#TODO: Prune items that are no longer in iCloud
if __name__ == "__main__":
    logger.info(f"MeuralCanvas-iCloudSync Launched")
    validate_environment()
    Metadata.initialize()
    Metadata.verify_integrity_and_cleanup()

    meural_token = meural.get_authentication_token()
    meural_playlist_ids_by_name = meural.get_playlist_ids(meural_token)
    while True:
        logger.info("Starting scheduled update!")
        scheduled_task(meural_token, meural_playlist_ids_by_name)
        logger.info(f"Done! Pausing for {UPDATE_FREQUENCY_MINS} minutes until next update...")
        time.sleep(int(UPDATE_FREQUENCY_MINS)*60)
