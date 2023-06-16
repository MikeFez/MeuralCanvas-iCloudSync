from configuration import Env, logger
import requests
import os

URL_BASE = "https://api.meural.com/v0"

class MeuralAPI:
    def __init__(self, username, password):
        self.session = requests.Session()
        self.api_token = self.get_authentication_token(username, password)
        self.headers = {
            'Authorization': f"Token {self.api_token}",
            'x-meural-api-version': '3'
        }

        self.playlist_ids_by_name = self.get_playlist_ids_by_name()
        self.all_uploaded_image_data = self.get_uploaded_image_data()
        self.uploaded_filenames = [image['name'] for image in self.all_uploaded_image_data]



    def get_authentication_token(self, username, password):
        url = f"{URL_BASE}/authenticate"
        data = {
            'username': username,
            'password': password
        }
        headers = {
            'x-meural-api-version': '3'
        }
        response = self.session.post(url, headers=headers, data=data, allow_redirects=True, timeout=15)
        return response.json()['token']

    def get_uploaded_image_data(self):
        url = f"{URL_BASE}/user/items?count=500&page=1"
        response = self.session.get(url, headers=self.headers, allow_redirects=True, timeout=15)
        return response.json()['data']

    def get_playlist_ids_by_name(self):
        url = f"{URL_BASE}/user/galleries?count=500&page=1"
        response = self.session.get(url, headers=self.headers, allow_redirects=True, timeout=15)
        return {playlist['name']: playlist['id'] for playlist in response.json()['data']}

    def upload_image(self, image_location):
        url = f"{URL_BASE}/items"
        files = {'image': open(image_location, 'rb')}
        response = self.session.post(url, headers=self.headers, files=files, allow_redirects=True, timeout=30)
        return response.json()['data']['id']

    def update_image_metadata(self, image_id, metadata):
        url = f"{URL_BASE}/items/{image_id}"
        response = self.session.put(url, headers=self.headers, data=metadata, allow_redirects=True, timeout=15, verify=False)
        return response.content

    def delete_image(self, image_id):
        url = f"{URL_BASE}/items/{image_id}"
        response = self.session.delete(url, headers=self.headers, allow_redirects=True, timeout=15)
        print(response.json())
        return response.json()

    def add_image_to_playlist(self, image_id, playlist_id):
        url = f"{URL_BASE}/galleries/{playlist_id}/items/{image_id}"
        response = self.session.post(url, headers=self.headers, allow_redirects=True, timeout=15)
        return response.json()['data']['itemIds']

# if __name__ == "__main__":
#     token = get_authentication_token()
#     playlist_id = get_playlist_ids(token)
#     print(token)
#     print(playlist_id)