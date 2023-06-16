from configuration import Env, logger
import icloud
import json
import os
import yaml

class Metadata:
    metadata_loc = f"{Env.CONFIG_DIR}/records.json"

    config = None
    db = {}
    item_template = {
        "filename": None,
        "meural_id": None,
        "added_to_playlist": False,
        "deleted_from_meural": False
    }

    @classmethod
    def initialize(cls):
        # Now populate metadata db
        if os.path.isfile(cls.metadata_loc):
            with open(cls.metadata_loc, 'r') as json_file:
                records = json.load(json_file)
        else:
            records = {}
        cls.db = records

    @classmethod
    def save_db(cls):
        with open(cls.metadata_loc, 'w') as json_file:
            json.dump(cls.db, json_file, indent=4)


    @classmethod
    def verify_integrity_and_cleanup(cls):
        logger.info("Verifying integrity of files")
        make_paths = [Env.IMAGE_DIR, f"{Env.IMAGE_DIR}/uploaded", f"{Env.IMAGE_DIR}/not_uploaded"]
        for path in make_paths:
            if not os.path.isdir(path):
                logger.info(f"Creating directory {path}")
                os.makedirs(path)
        for icloud_album_id, album_db in cls.db.items():
            for checksum, playlist_data in album_db.items():
                for playlist_name, file_data in playlist_data.items():
                    not_uploaded_path = f"{Env.IMAGE_DIR}/not_uploaded/{file_data['filename']}"
                    uploaded_path = not_uploaded_path.replace("/not_uploaded/", "/uploaded/")
                    if not file_data["deleted_from_meural"]:
                        if file_data['meural_id'] is None:
                            # File was not uploaded
                            if not os.path.isfile(not_uploaded_path):
                                logger.warning(f"File {file_data['filename']} not found in {Env.IMAGE_DIR}/not_uploaded")
                                if not os.path.isfile(uploaded_path):
                                    logger.error(f"File {file_data['filename']} also was not found in {Env.IMAGE_DIR}/uploaded")
                                    raise EnvironmentError("File is missing!")
                                else:
                                    logger.info(f"File {file_data['filename']} found in {Env.IMAGE_DIR}/uploaded - moving to proper directory")
                                    os.rename(uploaded_path, not_uploaded_path)
                        else:
                            # File was uploaded
                            if not os.path.isfile(uploaded_path):
                                logger.warning(f"File {file_data['filename']} not found in {Env.IMAGE_DIR}/uploaded")
                                if not os.path.isfile(not_uploaded_path):
                                    logger.error(f"File {file_data['filename']} also was not found in {Env.IMAGE_DIR}/not_uploaded")
                                    raise EnvironmentError("File is missing!")
                                else:
                                    logger.info(f"File {file_data['filename']} found in {Env.IMAGE_DIR}/not_uploaded - moving to proper directory")
                                    os.rename(not_uploaded_path, uploaded_path)

    @classmethod
    def add_item(cls, icloud_album_id, checksum, playlist_name, filename):
        record = cls.item_template.copy()
        record['filename'] = filename
        if icloud_album_id not in cls.db:
            cls.db[icloud_album_id] = {}
        if checksum not in cls.db[icloud_album_id]:
            cls.db[icloud_album_id][checksum] = {}
        if playlist_name not in cls.db[icloud_album_id][checksum]:
            cls.db[icloud_album_id][checksum][playlist_name] = record
        cls.save_db()

    @classmethod
    def mark_uploaded_to_meural(cls, icloud_album_id, image_checksum, playlist_name, meural_id):
        cls.db[icloud_album_id][image_checksum][playlist_name]['meural_id'] = meural_id
        cls.save_db()

    @classmethod
    def mark_added_to_playlist(cls, icloud_album_id, image_checksum, playlist_name):
        cls.db[icloud_album_id][image_checksum][playlist_name]['added_to_playlist'] = True
        cls.save_db()

    @classmethod
    def mark_deleted_from_meural(cls, icloud_album_id, image_checksum, playlist_name):
        cls.db[icloud_album_id][image_checksum][playlist_name]["deleted_from_meural"] = True
        cls.save_db()

    @classmethod
    def get_items_not_yet_uploaded(cls, icloud_album_id):
        not_uploaded = []
        for checksum, playlist_data in cls.db[icloud_album_id].items():
            for playlist_name, image_data in playlist_data.items():
                if image_data['meural_id'] is None:
                    not_uploaded.append((checksum, playlist_name, image_data['filename']))
        return not_uploaded

    @classmethod
    def get_items_not_added_to_playlist(cls, icloud_album_id, playlists_to_check):
        not_added_to_playlist = {playlist: [] for playlist in playlists_to_check}
        for checksum, playlist_data in cls.db[icloud_album_id].items():
            for playlist_to_check in playlists_to_check:
                if playlist_to_check in playlist_data:
                    image_data = playlist_data[playlist_to_check]
                    if image_data['meural_id'] is not None and image_data['added_to_playlist'] is False:
                        not_added_to_playlist[playlist_to_check].append((checksum, image_data['filename'], image_data['meural_id']))
        return not_added_to_playlist

class UserConfiguration:
    def __init__(self, config_location=f"{Env.CONFIG_DIR}/config.yaml"):
        self._raw_config = self.load_config(config_location)
        self.sync_tasks = self.validate_and_return_tasks()

    def load_config(self, config_location):
        raw_config = None
        if os.path.isfile(config_location):
            with open(config_location, 'r') as yaml_file:
                raw_config = yaml.safe_load(yaml_file)
        else:
            raise ValueError(f"Config file was not found. Please add one prior to launching this container.")
        return raw_config 

    def validate_and_return_tasks(self):
        if "sync" not in self._raw_config:
            raise ValueError(f'Config file is missing top-level "sync" key')
        elif self._raw_config["sync"] is None:
            raise ValueError(f'There are no items to sync in the config. Ensure there is at least one item under "sync" prior to launching this container.')
        return [UserConfiguration_SyncTask(sync_task_dict) for sync_task_dict in self._raw_config["sync"]]


class UserConfiguration_SyncTask:
    def __init__(self, sync_task_dict):
        self.icloud_album = sync_task_dict['icloud_album']
        self.meural_playlists = [UserConfiguration_SyncTask_MeuralPlaylist(data) for data in sync_task_dict['meural_playlist']]

class UserConfiguration_SyncTask_MeuralPlaylist:
    def __init__(self, meural_playlist_dict):
        self.name = meural_playlist_dict['name']
        self.unique_upload = meural_playlist_dict['unique_upload']