# MeuralCanvas-iCloudSync
Synchronize shared iCloud photo albums with your Netgear Meural Canvas.

## What is this?
The [Netgear Meural Canvas](https://www.netgear.com/home/digital-art-canvas/) is a digital photo frame which allows you to display your own photos, or photos from their library. While it has the ability to manually upload photos or link a iOS photo library to it, their software tends to choke on iOS Live Photos & those taken in portrait mode. Using their app's sync tool for an album of 204 photos, I was only able to get 134 of them to upload properly - with no option to retry or see the ones which had failed.

**This docker image downloads the highest resolution images available in a shared iCloud album as stills (converting Live/Portrait photos to jpeg), and uploads them via api to Meural while also linking them to an album. It will also delete images from Meural which have been removed from the iCloud album.**

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
      - ICLOUD_ALBUM_URL="XXXX"
      - MEURAL_USERNAME=XXXX
      - MEURAL_PASSWORD=XXXX
      - MEURAL_PLAYLISTS=XXXX
      - UPDATE_FREQUENCY_MINS=30
    volumes:
      - /foo/bar/MeuralCanvas-iCloudSync:/data
    restart: unless-stopped
```

## Parameters

Container images are configured using parameters passed at runtime (such as those above). These parameters are separated by a colon and indicate `<external>:<internal>` respectively. For example, `-p 8080:80` would expose port `80` from inside the container to be accessible from the host's IP on port `8080` outside the container.

**Note: There are no defaults for the parameters mentioned here - each one MUST be provided**

| Parameter | Function |
| :----: | --- |
| `-e ICLOUD_ALBUM_URL` | URL to the iCloud album which contains the photos you want synced. |
| `-e MEURAL_USERNAME` | Your Netgear Meural email address. |
| `-e MEURAL_PASSWORD` | Your Netgear Meural email password. |
| `-e MEURAL_PLAYLISTS` | The name(s) of the Meural playlist which photos should be added to. Multiple playlists can be added, separated by comma. |
| `-e UPDATE_FREQUENCY_MINS` | The frequency between syncronization runs. |

