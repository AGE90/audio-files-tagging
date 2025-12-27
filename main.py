"""
This module provides a main function to process audio files and update their tags with metadata from Discogs.
It uses the AudioTagger class to update the tags of audio files and the DiscogsClient class to search for matching releases on Discogs.
"""
import logging
from pathlib import Path
from typing import List, Tuple

from aft.audio_tagger import AudioTagger
from aft.credentials import discogs_user_token
from aft.discogs_client import DiscogsClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_release_info(file_path: Path) -> Tuple[str, str, str]:
    """
    Extract artist, release name, and track name from file path.
    Expected structure: music_dir/artist/release_name/track_name.mp3

    Returns:
        Tuple of (artist_name, release_name, track_name)
    """
    # Get the parent directories
    parent_dirs = list(file_path.parent.parts)

    # The last directory is the release name
    release_name = parent_dirs[-1]

    # The second-to-last directory is the artist name
    artist_name = parent_dirs[-2]

    # The file name (without extension) is the track name
    track_name = file_path.stem

    return artist_name, release_name, track_name


def process_audio_file(file_path: Path, discogs_client: DiscogsClient) -> bool:
    """
    Process a single audio file:
    1. Extract artist, release name, and track name from directory structure
    2. Search Discogs for matching release
    3. Update audio file tags with metadata
    """
    try:
        # Extract artist, release name, and track name from directory structure
        artist_name, release_name, track_name = get_release_info(file_path)

        # Search for release on Discogs
        releases = discogs_client.search_release(release_name, artist_name)
        if not releases:
            logger.warning(
                f"No matching releases found for {release_name} by {artist_name}")
            return False

        # Use the first matching release
        release = releases[0]
        logger.info(
            f"Found matching release: {release['title']} by {', '.join(release['artist'])}")

        # Update audio file tags
        tagger = AudioTagger(str(file_path))
        success = tagger.update_tags(release)

        return success

    except Exception as e:
        logger.error(f"Error processing {file_path}: {str(e)}")
        return False


def process_release_directory(release_dir: Path, discogs_client: DiscogsClient) -> int:
    """
    Process all audio files in a release directory.

    Args:
        release_dir: Path to the release directory
        discogs_client: DiscogsClient instance

    Returns:
        Number of successfully processed files
    """
    success_count = 0

    # Get all audio files in the release directory
    audio_files = []
    for ext in ['.mp3', '.flac']:
        audio_files.extend(release_dir.glob(f"*{ext}"))

    # Process each audio file
    for file_path in audio_files:
        logger.info(f"Processing {file_path}")
        if process_audio_file(file_path, discogs_client):
            success_count += 1

    return success_count


def main():
    # Initialize Discogs client
    discogs_client = DiscogsClient(discogs_user_token)

    # Get list of artist directories
    music_dir = Path("D:/Music Collection")
    artist_dirs = [d for d in music_dir.iterdir() if d.is_dir()]

    # Process each artist directory
    total_success_count = 0
    total_file_count = 0

    for artist_dir in artist_dirs:
        logger.info(f"Processing artist: {artist_dir.name}")

        # Get all release directories
        release_dirs = [d for d in artist_dir.iterdir() if d.is_dir()]

        # Process each release directory
        for release_dir in release_dirs:
            logger.info(f"Processing release: {release_dir.name}")

            # Count files in this release
            audio_files = []
            for ext in ['.mp3', '.flac']:
                audio_files.extend(release_dir.glob(f"*{ext}"))
            total_file_count += len(audio_files)

            # Process all files in this release
            success_count = process_release_directory(
                release_dir, discogs_client)
            total_success_count += success_count

    logger.info(
        f"Processing complete. Successfully updated {total_success_count} out of {total_file_count} files.")


if __name__ == "__main__":
    main()
