# MeuralCanvas-iCloudSync
Synchronize shared iCloud photo albums with your Netgear Meural Canvas.

## What is this?
The [Netgear Meural Canvas](https://www.netgear.com/home/digital-art-canvas/) is a digital photo frame which allows you to display your own photos, or photos from their library. While it has the ability to manually upload photos or link a iOS photo library to it, their software tends to choke on iOS Live Photos & those taken in portrait mode. Using their app's sync tool for an album of 204 photos, I was only able to get 134 of them to upload properly - with no option to retry or see the ones which had failed.

**This docker image downloads the highest resolution images available in a shared iCloud album as stills (converting Live/Portrait photos to jpeg), and uploads them via api to Meural while also linking them to an album. It will also delete images from Meural which have been removed from the iCloud album.**

Note: In order to access the iCloud album, it must first be [shared with a public link](https://support.apple.com/guide/icloud/share-photos-and-videos-mm93a9b98683/icloud). The link generated allows public viewing of the album, but only to those which are given the URL.

## FAQ
### Why not just use the Meural app?
The as of June 2023, the Meural app seems to have issues syncing certain types of images in a linked iOS album. Live Photos & photos taken in Portrait mode seem to cause it issue, with the items being skipped. When skipped, theres no indication of WHAT was skipped. Therefore, I built out this tool which actually works.

### When I delete an item from my shared iCloud album, is it deleted from Meural?
Yes. Whenever you delete an item in your iCloud album, that item will be removed from Meural (and therefore all associated playlists) when the next sync occurs.

### When I remove an item from a Meural playlist, is it deleted from my shared iCloud album?
No, and this is by design. As an example, I have a shared album which my wife and I both post images to. These images are synced to multiple meural playlists, which serve different purposes. An image that suits one playlist may not suit the second, and so we remove the image from the second playlist. However, the image should remain in my Meural uploads as it is still displayed in the first playlist.

### I deleted an image from Meural, how can I have it re-synced?
To re-sync an item to Meural, you must first delete the item from your shared iCloud album, and wait for the next sync to occur. Once `MeuralCanvas-iCloudSync` considers the item to be deleted, re-add the image to your album. On the next sync, the image will be re-uploaded to Meural.

## Usage
### docker-compose (recommended, [click here for more info](https://docs.linuxserver.io/general/docker-compose))

```yaml
---
version: "3.9"
services:
  meural-canvas-icloud-sync:
    image: ghcr.io/mikefez/meuralcanvas-icloudsync:main
    container_name: meural-canvas-icloud-sync
    environment:
      - MEURAL_USERNAME=XXXX
      - MEURAL_PASSWORD=XXXX
      - UPDATE_FREQUENCY_MINS=30
    volumes:
      - path/to/config/dir:/config
      - path/to/photo/download/dir:/images
    restart: unless-stopped
```

## Parameters

Container images are configured using parameters passed at runtime (such as those above). These parameters are separated by a colon and indicate `<external>:<internal>` respectively. For example, `-p 8080:80` would expose port `80` from inside the container to be accessible from the host's IP on port `8080` outside the container.

**Note: There are no defaults for the parameters mentioned here - each one MUST be provided**

| Parameter | Function |
| :----: | --- |
| `-e MEURAL_USERNAME` | Your Netgear Meural email address. |
| `-e MEURAL_PASSWORD` | Your Netgear Meural email password. |
| `-e UPDATE_FREQUENCY_MINS` | The frequency between syncronization runs. |

## Configuration
Configuration is managed via `config.yaml`, which should be mounted into the `/config` directory. This file must exist prior to launching the container, and will be validated before syncing occurs. An example of the file can be seen here:

```yaml
sync:
  - icloud_album: "https://hyperlink_to_album_1"
    meural_playlists:
      - "Playlist to sync to"
  - icloud_album: "https://hyperlink_to_album_2"
    meural_playlists:
      - "Playlist to sync to"
      - "Another playlist to sync to"
```

