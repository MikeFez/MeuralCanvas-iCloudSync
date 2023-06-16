from configuration import Env, logger
import json
import os
import requests

def post_json(url, data):
    response = requests.post(url, data=json.dumps(data), headers={'Content-Type': 'application/json'})
    return response.json()

class iCloudAlbum:
    class Image:
        def __init__(self, sync_task, checksum, name, url):
            self.checksum = checksum
            self.name = name
            self.url = url
            self.image_binary = None  # Stores image binary after download
            self.paths_to_images_actually_downloaded = [] # Populated via self.download()

            # Populated via self.populate_filenames(), formatted as {meural_playlist_name: filename}
            self.save_as_filenames = self.populate_filenames(sync_task)

        def populate_filenames(self, sync_task):
            for sync_to_playlist in sync_task.meural_playlists:
                # Images will be uploaded with their names in the following format:
                # "{icloud_album_id}_{checksum}_{meural_playlist_name}" if unique
                # "{icloud_album_id}_{checksum}" if not
                filename = self.checksum
                if sync_to_playlist.unique_upload is True:
                    filename = f"{self.checksum}_{sync_to_playlist.name}"
                self.save_as_filenames[sync_to_playlist.name] = f"{Env.IMAGE_DIR}/{filename}"

        def download(self, absolute_path):
            logger.info(f"Downloading {self.name}")
            if self.image_binary is None:
                self.image_binary = requests.get(self.url).content
            if not os.path.exists(absolute_path):
                with open(absolute_path, 'wb') as f:
                    f.write(self.image_binary)
                    logger.info(f"\t[✓] Saved to {absolute_path}")
            self.paths_to_images_actually_downloaded.append(absolute_path)

        def delete_downloaded_images(self):
            self.image_binary = None
            for absolute_path in self.paths_to_images_actually_downloaded:
                if os.path.exists(absolute_path):
                    os.remove(absolute_path)
                    logger.info(f"[✓] Deleted {absolute_path}")
                else:
                    logger.info(f"[!] {absolute_path} does not exist, could not delete image. It may have not been downloaded")
            self.paths_to_images_actually_downloaded = []

    def __init__(self, sync_task):
        self.url = sync_task.icloud_album
        self.id = self.url.split('#')[1]

        # Populated by query_album()
        self.name = ""
        self.images = []
        self.query_album(sync_task)
        logger.info(f"Identified {len(self.images)} images in the {self.name} iCloud album")

    def query_album(self, sync_task):
        logger.info(f"Retrieving iCloud album information ({self.url})...")
        base_api_url = f"https://p23-sharedstreams.icloud.com/{self.id}/sharedstreams"
        stream_data = {"streamCtag": None}
        stream = post_json(f"{base_api_url}/webstream", stream_data)
        host = stream.get("X-Apple-MMe-Host")
        if host:
            host = host.rsplit(':')[0]
            base_api_url = f"https://{host}/{self.id}/sharedstreams"
            stream = post_json(f"{base_api_url}/webstream", stream_data)

        self.name = stream["streamName"]
        logger.info(f"\tConnected to {self.name} iCloud album: acquiring photo checksums & guids...")

        # Get the checksums for the highest available resolution of each photo
        checksums = []
        for photo in stream["photos"]:
            checksums.append(photo['derivatives'][str(max(int(x) for x in photo["derivatives"].keys()))]['checksum'])

        # Get all photo guids and request all asset urls
        photo_guids = {"photoGuids": [photo["photoGuid"] for photo in stream["photos"]]}
        asset_urls = post_json(f"{base_api_url}/webasseturls", photo_guids)["items"]
        for key, value in asset_urls.items():
            url = f"https://{value['url_location']}{value['url_path']}&{key}"
            for checksum in checksums:
                if checksum in url:
                    self.images.append(
                        self.__class__.Image(
                            sync_task=sync_task,
                            checksum=checksum,
                            name=url.split('?')[0].split('/')[-1],
                            url=url
                        )
                    )

