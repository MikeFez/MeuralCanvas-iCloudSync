import icloud, meural
from configuration import Env, logger
from models import Metadata, UserConfiguration
import os
import time

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
            for playlist_name, playlist_data in Metadata.db[icloud_album_id][checksum].items():
                if not playlist_data["deleted_from_meural"]:
                    image_filename = playlist_data['filename']
                    try:
                        meural.delete_image(meural_token, playlist_data['meural_id'])
                        Metadata.mark_deleted_from_meural(icloud_album_id, checksum, playlist_name)

                        potential_image_location = f"{Env.IMAGE_DIR}/not_uploaded/{image_filename}"
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

def prune_images_that_no_longer_exist_in_meural(meural_image_ids_by_name):
    logger.info(f"Checking if there are images to prune that no longer exist in Meural")
    existing_image_names = list(meural_image_ids_by_name.keys())
    if len(existing_image_names) == 0:
        logger.warning(f"No images found in Meural to check against - skipping this check as it might be an API error")
        return

    items_to_delete_from_db = []
    for icloud_album_id, album_data in Metadata.db.items():
        for checksum, playlist_data in album_data.items():
            for playlist_name, image_data in playlist_data.items():
                if image_data['deleted_from_meural'] is False and image_data['filename'].rsplit(".")[0] not in existing_image_names:
                    items_to_delete_from_db.append((icloud_album_id, checksum, playlist_name, image_data['filename']))

    for (icloud_album_id, checksum, playlist_name, image_filename) in items_to_delete_from_db:
        logger.info(f"\tDeleting {image_filename} from metadata because it no longer exists in Meural")
        Metadata.mark_deleted_from_meural(icloud_album_id, checksum, playlist_name)

        potential_image_location = f"{Env.IMAGE_DIR}/not_uploaded/{image_filename}"
        for potential_location in (potential_image_location, potential_image_location.replace('/not_uploaded/', '/uploaded/')):
            if os.path.isfile(potential_location):
                os.remove(potential_location)
                logger.info(f"\t[✓] Successfully deleted {image_filename} from local storage")
                break
    return


# TODO: LOGIC Above this point needs to be reworked

def scheduled_task(user_configuration, meural_api):
    for sync_task in user_configuration.sync_tasks:
        # Validate playlist has items
        if len(sync_task.meural_playlists) == 0:
            raise ValueError(f"Cannot sync {sync_task.icloud_album} because no Meural playlists were specified")

        # Validate playlists that we will sync to exist
        for sync_to_playlist in sync_task.meural_playlists:
            if sync_to_playlist.name not in meural_api.playlist_ids_by_name:
                raise ValueError(f"Cannot sync {sync_task.icloud_album} because {sync_to_playlist.name} Meural playlist does not exist")

        # Instantiate the iCloud album object. This queries iCloud for the album's contents, which we'll download and sync one by one.
        # All images will also have their expected filename per Meural playlist defined.
        icloud_album_obj = icloud.iCloudAlbum(sync_task)
        # Now upload images which don't exist in Meural
        _subtask_upload_new_images_to_meural(icloud_album_obj, meural_api)
        _subtask_delete_orphaned_images_from_meural(icloud_album_obj, meural_api)
        # TODO: Validate that all items in meural match the iCloud album cfg at this point
        return

def _subtask_upload_new_images_to_meural(icloud_album_obj, meural_api):
        # Iterate through the images in the album. We're going to download them, and then add them to the associated meural playlists.
        # TODO: Metadata logging. We need this so that items deleted from meural are not re-added
        for icloud_image in icloud_album_obj.images:
            for meural_playlist_name, save_filename in icloud_image.save_as_filenames.items():
                meural_playlist_id = meural_api.playlist_ids_by_name[meural_playlist_name]
                if save_filename not in meural_api.uploaded_filenames:
                    icloud_image.download(save_filename)  # Only downloads once per image - if already downloaded, this just makes another file to avoid Meural dedupe
                    # Upload the image & get the meural id
                    image_id = meural_api.upload_image(save_filename)
                    # Update the image metadata in meural
                    metadata = {
                        "description": f'{{"icloud_album_id": "{icloud_album_obj.id}", "checksum": "{icloud_image.checksum}", "playlist_name": "{meural_playlist_name}"}}'
                    }
                    meural_api.update_metadata(image_id, metadata)
                    # Finally, add it to the playlist and verify it's actually been added
                    image_ids_in_playlist = meural_api.add_image_to_playlist(image_id, meural_playlist_id)
                    if image_id not in image_ids_in_playlist:
                        raise ValueError(f"Failed to add image {image_id} to playlist {meural_playlist_name}")
            # All work is done for this image, so delete it from the filesystem
            icloud_image.delete_downloaded_images()
        return

def _subtask_delete_orphaned_images_from_meural(icloud_album_obj, meural_api):
    # TODO: Delete items from meural that no longer exist in iCloud
    return


#TODO: Prune items that are no longer in iCloud
if __name__ == "__main__":
    logger.info(f"MeuralCanvas-iCloudSync Launched")
    Env.validate_environment()

    # TODO: Metadata rework
    Metadata.initialize()
    Metadata.verify_integrity_and_cleanup()

    user_configuration = UserConfiguration()
    meural_api = meural.MeuralAPI(
        username=Env.MEURAL_USERNAME,
        password=Env.MEURAL_PASSWORD
    )

    while True:
        logger.info("Starting scheduled update!")
        scheduled_task(user_configuration, meural_api)
        logger.info(f"Done! Pausing for {Env.UPDATE_FREQUENCY_MINS} minutes until next update...")
        time.sleep(int(Env.UPDATE_FREQUENCY_MINS)*60)
