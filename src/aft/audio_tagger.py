"""
This module provides a class for tagging audio files with metadata.
The AudioTagger class can handle MP3 and FLAC files.
It supports updating basic tags (title, artist, year) and genres/styles.
"""
from pathlib import Path
from typing import Dict
import logging
from mutagen import File
from mutagen.id3 import ID3, TCON, TIT2, TPE1, TDRC, TPUB, TCOP
from mutagen.flac import FLAC

logger = logging.getLogger(__name__)


class AudioTagger:
    """
    Class for tagging audio files with metadata.
    This class can handle MP3 and FLAC files.
    It supports updating basic tags (title, artist, year) and genres/styles.
    """

    def __init__(self, file_path: str):
        """Initialize the audio tagger with a file path."""
        self.file_path = Path(file_path)
        self.audio = None
        self._load_file()

    def _load_file(self):
        """Load the audio file and initialize appropriate tag handler."""
        try:
            self.audio = File(self.file_path)
            if self.audio is None:
                logger.error(f"Could not load file: {self.file_path}")
                return

            # Initialize ID3 tags if they don't exist (for MP3)
            if hasattr(self.audio, 'tags') and self.audio.tags is None:
                self.audio.add_tags()

        except Exception as e:
            logger.error(f"Error loading file {self.file_path}: {str(e)}")

    def update_tags(self, metadata: Dict) -> bool:
        """
        Update audio file tags with metadata from Discogs.
        Returns True if successful, False otherwise.
        """
        if self.audio is None:
            logger.error("No audio file loaded")
            return False

        try:
            # Handle MP3 files
            if isinstance(self.audio, ID3):
                self._update_mp3_tags(metadata)
            # Handle FLAC files
            elif isinstance(self.audio, FLAC):
                self._update_flac_tags(metadata)
            else:
                logger.warning(f"Unsupported audio format: {type(self.audio)}")
                return False

            self.audio.save()
            logger.info(f"Successfully updated tags for {self.file_path}")
            return True

        except Exception as e:
            logger.error(f"Error updating tags for {self.file_path}: {str(e)}")
            return False

    def _update_mp3_tags(self, metadata: Dict):
        """Update tags for MP3 files."""
        tags = self.audio.tags

        # # Update basic tags
        # if 'title' in metadata:
        #     tags['TIT2'] = TIT2(encoding=3, text=metadata['title'])
        # if 'artist' in metadata:
        #     tags['TPE1'] = TPE1(encoding=3, text=metadata['artist'])
        # if 'year' in metadata:
        #     tags['TDRC'] = TDRC(encoding=3, text=str(metadata['year']))

        # Update genres and styles
        genres = []
        if 'genres' in metadata:
            genres.extend(metadata['genres'])
        if 'styles' in metadata:
            genres.extend(metadata['styles'])
        if genres:
            tags['TCON'] = TCON(encoding=3, text=genres)

        # Update label and catalog information
        if 'labels' in metadata:
            tags['TPUB'] = TPUB(encoding=3, text=metadata['labels'])
        if 'catalog_numbers' in metadata:
            tags['TCOP'] = TCOP(encoding=3, text=metadata['catalog_numbers'])

    def _update_flac_tags(self, metadata: Dict):
        """Update tags for FLAC files."""
        tags = self.audio.tags

        # Update basic tags
        if 'title' in metadata:
            tags['TITLE'] = metadata['title']
        if 'artist' in metadata:
            tags['ARTIST'] = metadata['artist']
        if 'year' in metadata:
            tags['DATE'] = str(metadata['year'])

        # Update genres and styles
        genres = []
        if 'genres' in metadata:
            genres.extend(metadata['genres'])
        if 'styles' in metadata:
            genres.extend(metadata['styles'])
        if genres:
            tags['GENRE'] = genres

        # Update label and catalog information
        if 'labels' in metadata:
            tags['LABEL'] = metadata['labels']
        if 'catalog_numbers' in metadata:
            tags['CATALOGNUMBER'] = metadata['catalog_numbers']
