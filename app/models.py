from configuration import Env, logger, halt_with_error
import icloud
import json
import os
import yaml

class Metadata:
    metadata_loc = f"{Env.CONFIG_DIR}/db.json"
    db = {}

    @classmethod
    def initialize(cls):
        # Now populate metadata db
        cls.db = {}
        if os.path.isfile(cls.metadata_loc):
            with open(cls.metadata_loc, 'r') as json_file:
                cls.db = json.load(json_file)

    @classmethod
    def save_db(cls):
        with open(cls.metadata_loc, 'w') as json_file:
            json.dump(cls.db, json_file, indent=4)

    @classmethod
    def mark_image_added_to_playlist(cls, icloud_album_id, meural_image_name):
        if icloud_album_id not in cls.db:
            cls.db[icloud_album_id] = {}
        if meural_image_name not in cls.db[icloud_album_id]:
            cls.db[icloud_album_id].append(meural_image_name)
        else:
            halt_with_error(f"Image {meural_image_name} already exists in db - somehow it was uploaded twice?")
        cls.save_db()

    @classmethod
    def mark_image_deleted_from_meural(cls, icloud_album_id, meural_image_name):
        if meural_image_name in cls.db[icloud_album_id]:
            cls.db[icloud_album_id].remove(meural_image_name)
        else:
            halt_with_error(f"Image {meural_image_name} does not exist in db - somehow it was deleted twice?")
        cls.save_db()

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
        self.meural_playlists = [UserConfiguration_SyncTask_MeuralPlaylist(data) for data in sync_task_dict['meural_playlists']]

class UserConfiguration_SyncTask_MeuralPlaylist:
    def __init__(self, meural_playlist_dict):
        self.name = meural_playlist_dict['name']
        self.unique_upload = meural_playlist_dict['unique_upload']