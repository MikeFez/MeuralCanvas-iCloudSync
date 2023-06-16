from configuration import Env, logger
import requests
import json

if Env.VERIFY_SSL_CERTS is False:
    requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

URL_BASE = "https://api.meural.com/v0"

class MeuralAPI:
    def __init__(self, username, password):
        logger.info("Initializing Meural API")
        self.session = requests.Session()
        self.api_token = self.get_authentication_token(username, password)
        self.headers = {
            'Authorization': f"Token {self.api_token}",
            'x-meural-api-version': '3'
        }

        # Populated by self.refresh_playlist_data()
        self.playlist_ids_by_name = {}
        self.uploaded_image_ids_by_playlist_name = {}
        self.refresh_playlist_data()

        # Populated by self.refresh_uploaded_image_data()
        self.uploaded_images_by_icloud_album_id = {}
        self.uploaded_filenames_by_icloud_album_id = {}
        self.all_uploaded_images = []
        self.refresh_uploaded_image_data()


    def get_authentication_token(self, username, password):
        url = f"{URL_BASE}/authenticate"
        data = {
            'username': username,
            'password': password
        }
        headers = {
            'x-meural-api-version': '3'
        }
        response = self.session.post(url, headers=headers, data=data, allow_redirects=True, timeout=15, verify=Env.VERIFY_SSL_CERTS)
        return_value = None
        try:
            return_value = response.json()['token']
        except:
            logger.error(f"Error parsing Meural response: {response.text}")
            raise
        return return_value

    def refresh_playlist_data(self):
        logger.info("\tRefreshing Meural playlist data")
        url = f"{URL_BASE}/user/galleries?count=500&page=1"
        response = self.session.get(url, headers=self.headers, allow_redirects=True, timeout=15, verify=Env.VERIFY_SSL_CERTS)
        try:
            response.json()['data']
        except:
            logger.error(f"Error parsing Meural response: {response.text}")
            raise
        self.playlist_ids_by_name = {playlist['name']: playlist['id'] for playlist in response.json()['data']}
        self.uploaded_image_ids_by_playlist_name = {playlist['name']: playlist['itemIds'] for playlist in response.json()['data']}
        return

    def refresh_uploaded_image_data(self):
        logger.info("\tRefreshing Meural image data")
        url = f"{URL_BASE}/user/items?count=500&page=1"
        response = self.session.get(url, headers=self.headers, allow_redirects=True, timeout=15, verify=Env.VERIFY_SSL_CERTS)
        
        try:
            response.json()['data']
        except:
            logger.error(f"Error parsing Meural response: {response.text}")
            raise

        for uploaded_image_data in response.json()['data']:
            album_id = None
            if "icloud_album_id" in uploaded_image_data['description']:
                album_id = json.loads(uploaded_image_data['description'])["icloud_album_id"]

            # Store in dict
            self.all_uploaded_images.append(uploaded_image_data)
            if album_id not in self.uploaded_images_by_icloud_album_id:
                self.uploaded_images_by_icloud_album_id[album_id] = []
            self.uploaded_images_by_icloud_album_id[album_id].append(uploaded_image_data)

            if album_id not in self.uploaded_filenames_by_icloud_album_id:
                self.uploaded_filenames_by_icloud_album_id[album_id] = []
            self.uploaded_filenames_by_icloud_album_id[album_id].append(uploaded_image_data['name'])
        return

    def upload_image(self, image_filename):
        url = f"{URL_BASE}/items"
        files = {'image': open(f"{Env.IMAGE_DIR}/{image_filename}", 'rb')}
        response = self.session.post(url, headers=self.headers, files=files, allow_redirects=True, timeout=30, verify=Env.VERIFY_SSL_CERTS)
        return_value = None
        try:
            return_value = response.json()['data']['id']
        except:
            logger.error(f"Error parsing Meural response: {response.text}")
            raise
        return return_value

    def update_image_metadata(self, image_id, metadata):
        url = f"{URL_BASE}/items/{image_id}"
        response = self.session.put(url, headers=self.headers, data=metadata, allow_redirects=True, timeout=15, verify=Env.VERIFY_SSL_CERTS)
        return response.content

    def delete_image(self, image_id):
        url = f"{URL_BASE}/items/{image_id}"
        response = self.session.delete(url, headers=self.headers, allow_redirects=True, timeout=15, verify=Env.VERIFY_SSL_CERTS)
        return

    def create_playlist(self, name, description, orientation):
        url = f"{URL_BASE}/galleries"
        metadata = {
            "name": name,
            "description": description,
            "orientation": orientation
        }
        response = self.session.post(url, headers=self.headers, data=metadata, allow_redirects=True, timeout=15, verify=Env.VERIFY_SSL_CERTS)
        return_value = None
        try:
            return_value = response.json()['data']
        except:
            logger.error(f"Error parsing Meural response: {response.text}")
            raise
        return return_value

    def add_image_to_playlist(self, image_id, playlist_id):
        url = f"{URL_BASE}/galleries/{playlist_id}/items/{image_id}"
        response = self.session.post(url, headers=self.headers, allow_redirects=True, timeout=15, verify=Env.VERIFY_SSL_CERTS)
        return_value = None
        try:
            return_value = response.json()['data']['itemIds']
        except:
            logger.error(f"Error parsing Meural response: {response.text}")
            raise
        return return_value

# if __name__ == "__main__":
#     token = get_authentication_token()
#     playlist_id = get_playlist_ids(token)
#     print(token)
#     print(playlist_id)