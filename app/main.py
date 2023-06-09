import icloud, meural
from configuration import Env, logger, halt_with_error
from models import Metadata, UserConfiguration
import time
import json
import sys, traceback

def scheduled_task(user_configuration, meural_api):
    for sync_task in user_configuration.sync_tasks:
        # Validate playlist has items
        if len(sync_task.meural_playlists) == 0:
            halt_with_error(f"Cannot sync {sync_task.icloud_album} because no Meural playlists were specified. Please update your configuration file.")

        # Validate playlists that we will sync to exist
        for sync_to_playlist in sync_task.meural_playlists:
            if sync_to_playlist.name not in meural_api.playlist_ids_by_name:
                halt_with_error(f"Cannot sync {sync_task.icloud_album} because {sync_to_playlist.name} Meural playlist does not exist. Please create it in Meural, or update your configuration file.")

        # Instantiate the iCloud album object. This queries iCloud for the album's contents, which we'll download and sync one by one.
        # All images will also have their expected filename per Meural playlist defined.
        icloud_album_obj = icloud.iCloudAlbum(sync_task, meural_api)

        # First delete items from Meural which no longer exist in iCloud. This automatically removes them from playlists too.
        # Note: This will only delete items uploaded via this tool - other uploads will be skipped.
        _subtask_delete_orphaned_images_from_meural(icloud_album_obj, meural_api)

        # Now upload images which exist in iCloud but not in Meural, and add them to applicable playlists.
        # This will also add uploaded images to new playlists should the configuration have updated.
        _subtask_upload_new_images_to_meural(icloud_album_obj, meural_api)

        # Finally, we want to mark images which have had all images deleted from Meural. To do so,
        # we're going to add them to a "Delete From iCloud Album" playlist
        _subtask_add_orphaned_images_to_remove_from_icloud_album(icloud_album_obj, meural_api)
        return

def _subtask_delete_orphaned_images_from_meural(icloud_album_obj, meural_api):
    logger.info("[*] Determining if there are missing iCloud images that should be deleted from Meural")
    num_images_deleted = 0
    if icloud_album_obj.id in meural_api.uploaded_images_by_icloud_album_id:
        for meural_image_data in meural_api.uploaded_images_by_icloud_album_id[icloud_album_obj.id]:
            json_data = json.loads(meural_image_data['description'])
            if json_data["checksum"] not in icloud_album_obj.images_by_checksum:
                logger.info(f"\tDeleting orphaned image {meural_image_data['name']} in Meural - it no longer exists in the {icloud_album_obj.name} iCloud album")
                if not Env.DRY_RUN:
                    meural_api.delete_image(meural_image_data['id'])
                    Metadata.mark_image_deleted_from_meural(icloud_album_obj.id, meural_image_data['name'])
                else:
                    logger.info(f"\t[DRY RUN]: Would have deleted {meural_image_data['name']} from Meural")
                num_images_deleted += 1
    else:
        logger.info(f"\tMeural has no uploaded images from the {icloud_album_obj.name} iCloud album. Skipping orphaned image deletion")

    # If an image has been deleted, refresh uploaded meural information
    if num_images_deleted > 0:
        logger.info(f"{num_images_deleted} images were deleted from Meural")
        meural_api.refresh_playlist_data()
        meural_api.refresh_uploaded_image_data()
    else:
        logger.info("\tThere are no images which need to be deleted from Meural")
    return

def _subtask_upload_new_images_to_meural(icloud_album_obj, meural_api):
    logger.info("[*] Determining if there are added iCloud images that should be uploaded to Meural")
    num_images_added = 0
    # Iterate through the images in the album. We're going to download them, and then add them to the associated meural playlists.
    for icloud_image in icloud_album_obj.images_by_checksum.values():
        this_image_was_uploaded = False
        for meural_playlist_name, save_filename in icloud_image.save_as_filenames.items():
            meural_filename = save_filename.rsplit('.', 1)[0]
            meural_playlist_id = meural_api.playlist_ids_by_name[meural_playlist_name]
            if meural_filename not in meural_api.uploaded_filenames_by_icloud_album_id[icloud_album_obj.id]:
                if meural_filename not in Metadata.db[icloud_album_obj.id]:
                    if not Env.DRY_RUN:
                        icloud_image.download(save_filename)  # Only downloads once per image - if already downloaded, this just makes another file to avoid Meural dedupe
                        # Upload the image & get the meural id
                        image_id = meural_api.upload_image(save_filename)
                        # Update the image metadata in meural. If "_" is in the filename, it means that there was an associated playlist. Otherwise, the image is non-unique.
                        metadata_playlist = meural_playlist_name if "_" in meural_filename else None
                        metadata = {
                            "description": f'{{"icloud_album_id": "{icloud_album_obj.id}", "checksum": "{icloud_image.checksum}", "playlist_name": "{metadata_playlist}"}}'
                        }
                        meural_api.update_image_metadata(image_id, metadata)
                        # Finally, add it to the playlist and verify it's actually been added
                        image_ids_in_playlist = meural_api.add_image_to_playlist(image_id, meural_playlist_id)
                        if image_id not in image_ids_in_playlist:
                            halt_with_error(f"Failed to add image {image_id} to playlist {meural_playlist_name}")
                        Metadata.mark_image_added_to_playlist(icloud_album_obj.id, meural_filename)
                        logger.info(f"\tUploaded {save_filename} to {meural_playlist_name}")
                    else:
                        logger.info(f"[DRY RUN]: Would have uploaded {save_filename} to {meural_playlist_name}")
                        meural_api.dry_run_added_checksums.append(icloud_image.checksum)
                    this_image_was_uploaded = True
                else:
                    logger.debug(f"{meural_filename} was previously uploaded to Meural, but has since been deleted")
        if this_image_was_uploaded:
            num_images_added += 1

            # All work is done for this image, so delete it from the filesystem
            if not Env.DRY_RUN:
                logger.info(f"\tDeleting temporary images from local filesystem")
                icloud_image.delete_downloaded_images()


    # If an image has been added, refresh uploaded meural information
    if num_images_added > 0:
        logger.info(f"{num_images_added} images were uploaded to Meural")
        meural_api.refresh_playlist_data()
        meural_api.refresh_uploaded_image_data()
    else:
        logger.info("\tThere are no images which need to be uploaded to Meural")
    return

def _subtask_add_orphaned_images_to_remove_from_icloud_album(icloud_album_obj, meural_api):
    logger.info("[*] Determining if there are new missing Meural images that should be marked for deletion from iCloud")
    orphaned_icloud_images = []
    for checksum, icloud_image in icloud_album_obj.images_by_checksum.items():
        # If dry run, check if the checksum is in the dry run added names first
        if Env.DRY_RUN and checksum in meural_api.dry_run_added_checksums:
            # If so, continue on to the next item
            continue
        this_checksum_is_in_meural = False
        for meural_image_data in meural_api.all_uploaded_images:
            if checksum in meural_image_data['name']:
                this_checksum_is_in_meural = True
                break
        if this_checksum_is_in_meural is False:
            logger.info(f"\t{icloud_image.icloud_filename} is not in Meural, and should be removed from iCloud")
            orphaned_icloud_images.append(icloud_image)

    # If there were images that were orphaned in iCloud
    if orphaned_icloud_images:
        # Create the playlist that indicates items should be deleted from iCloud if it does not exist, but only if there are items to add
        orphaned_album_id = meural_api.playlist_ids_by_name.get(Env.DELETE_FROM_ICLOUD_PLAYLIST_NAME, None)
        if orphaned_album_id is None:
            if not Env.DRY_RUN:
                logger.info(f"\t'{Env.DELETE_FROM_ICLOUD_PLAYLIST_NAME}' playlist not found in Meural - creating it")
                meural_api.create_playlist(
                    name=Env.DELETE_FROM_ICLOUD_PLAYLIST_NAME,
                    description="Items which have no versions located in Meural, and should be removed from the iCloud playlist",
                    orientation="vertical"
                )
                meural_api.refresh_playlist_data()
                orphaned_album_id = meural_api.playlist_ids_by_name.get(Env.DELETE_FROM_ICLOUD_PLAYLIST_NAME)
            else:
                logger.info(f"\t[DRY RUN]: Would have created playlist '{Env.DELETE_FROM_ICLOUD_PLAYLIST_NAME}' in Meural")

        else:
            logger.debug(f"\t'{Env.DELETE_FROM_ICLOUD_PLAYLIST_NAME}' playlist already exists in Meural")

        # For each orphaned item, we'll upload it and add it to the orphaned playlist
        for orphaned_icloud_image in orphaned_icloud_images:
            if not Env.DRY_RUN:
                logger.info(f"\tPreparing to add orphaned {orphaned_icloud_image.icloud_filename} to the '{Env.DELETE_FROM_ICLOUD_PLAYLIST_NAME}' Meural playlist.")
                original_extension = orphaned_icloud_image.icloud_filename.rsplit('.', 1)[-1]
                save_filename = f"{orphaned_icloud_image.checksum}_{orphaned_album_id}.{original_extension}"
                orphaned_icloud_image.download(save_filename)

                # Upload the image & get the meural id
                image_id = meural_api.upload_image(save_filename)
                # Update the image metadata in meural. If "_" is in the filename, it means that there was an associated playlist. Otherwise, the image is non-unique.
                metadata = {
                    "description": f'{{"icloud_album_id": "{icloud_album_obj.id}", "checksum": "{orphaned_icloud_image.checksum}", "playlist_name": "{Env.DELETE_FROM_ICLOUD_PLAYLIST_NAME}"}}'
                }
                meural_api.update_image_metadata(image_id, metadata)
                image_ids_in_playlist = meural_api.add_image_to_playlist(image_id, orphaned_album_id)
                if image_id not in image_ids_in_playlist:
                    halt_with_error(f"Failed to add image {image_id} to playlist {Env.DELETE_FROM_ICLOUD_PLAYLIST_NAME}")
                logger.info(f"\tUploaded {save_filename} to {Env.DELETE_FROM_ICLOUD_PLAYLIST_NAME}")
            else:
                logger.info(f"\t[DRY RUN]: Would have added orphaned {orphaned_icloud_image.icloud_filename} to {Env.DELETE_FROM_ICLOUD_PLAYLIST_NAME} Meural playlist")
    else:
        logger.info("\tThere are no images which need to be deleted from iCloud")
    return


if __name__ == "__main__":
    logger.info(f"MeuralCanvas-iCloudSync Launched")
    if Env.DRY_RUN:
        logger.warning("Dry Run mode enabled!")
    try:
        Env.validate_environment()
        Metadata.initialize()

        user_configuration = UserConfiguration()
        meural_api = meural.MeuralAPI(
            username=Env.MEURAL_USERNAME,
            password=Env.MEURAL_PASSWORD
        )

        while True:
            logger.info("============================== Starting scheduled update ==============================")
            scheduled_task(user_configuration, meural_api)
            logger.info(f"Done! Pausing for {Env.UPDATE_FREQUENCY_MINS} minutes until next update...")
            time.sleep(int(Env.UPDATE_FREQUENCY_MINS)*60)
    except Exception as e:
        halt_with_error(f"Fatal error occurred: {e}\n{traceback.format_exc()}")
