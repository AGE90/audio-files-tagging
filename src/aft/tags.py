"""
Unified tag reading and writing module for audio files.

Provides a consistent interface for reading and writing metadata tags
across multiple audio formats: MP3, FLAC, M4A/MP4, and OGG Vorbis.
"""
import base64
import logging
from pathlib import Path
from typing import Any

from mutagen import File, MutagenError  # type: ignore
from mutagen.flac import FLAC, Picture
from mutagen.id3 import (
    APIC,
    TALB,
    TBPM,
    TCOM,
    TCON,
    TDRC,
    TIT2,  # type: ignore
    TPE1,
    TPE2,
    TPOS,
    TPUB,
    TRCK,
    TXXX,
)
from mutagen.mp4 import MP4, MP4Cover, MP4FreeForm  # type: ignore

logger = logging.getLogger(__name__)

_IMAGE_MIME_TYPES = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
}


class AudioTags:
    """
    Unified interface for reading and writing audio file tags.

    Supports MP3 (ID3v2), FLAC, M4A/MP4, and OGG Vorbis formats.

    Example
    -------
    >>> tags = AudioTags("track.mp3")
    >>> metadata = tags.read_tags()
    >>> print(metadata['title'])
    >>> tags.write_tags({'artist': 'New Artist', 'bpm': 128})
    """

    def __init__(self, file_path: str | Path):
        """
        Initialize AudioTags with a file path.

        Parameters
        ----------
        file_path : Union[str, Path]
            Path to the audio file.
        """
        self.file_path = Path(file_path)
        self.audio = None
        self._load_file()

    def _load_file(self) -> bool:
        """Load the audio file."""
        try:
            self.audio = File(str(self.file_path))

            if self.audio is None:
                logger.error("Could not load file: %s", self.file_path)
                return False

            # Initialize tags if they don't exist (MP3)
            if hasattr(self.audio, 'tags') and self.audio.tags is None:
                self.audio.add_tags()

            return True

        except (MutagenError, OSError) as e:
            logger.error("Error loading file %s: %s", self.file_path, e)
            return False

    def read_tags(self) -> dict[str, Any]:
        """
        Read all tags from the audio file.

        Returns
        -------
        Dict[str, Any]
            Dictionary containing all available metadata:
            - title: str
            - artist: str
            - album: str
            - album_artist: str
            - year: int
            - genre: List[str]
            - track_number: str
            - disc_number: str
            - bpm: int
            - key: str
            - publisher: List[str]
            - catalog_number: str
            - composer: str
            - comment: str
        """
        if self.audio is None:
            logger.error("No audio file loaded")
            return {}

        try:
            suffix = self.file_path.suffix.lower()

            if suffix == '.mp3':
                return self._read_mp3_tags()
            elif suffix == '.flac':
                return self._read_flac_tags()
            elif suffix in ['.m4a', '.mp4']:
                return self._read_mp4_tags()
            elif suffix == '.ogg':
                return self._read_ogg_tags()
            else:
                logger.warning("Unsupported format: %s", suffix)
                return {}

        except (MutagenError, KeyError, AttributeError) as e:
            logger.error("Error reading tags from %s: %s", self.file_path, e)
            return {}

    def _read_mp3_tags(self) -> dict[str, Any]:
        """Read tags from MP3 file."""
        if self.audio is None:
            return {}
        tags = self.audio.tags

        def get_text(frame_id: str, default: str = '') -> str:
            """Helper to extract text from ID3 frames."""
            frame = tags.get(frame_id)
            return str(frame.text[0]) if frame and frame.text else default

        def get_text_list(frame_id: str) -> list:
            """Helper to extract all text values from ID3 frames."""
            frame = tags.get(frame_id)
            return [str(t) for t in frame.text] if frame and frame.text else []

        def get_txxx(desc: str, default: str = '') -> str:
            """Helper to extract TXXX user-defined text frames."""
            frames = tags.getall('TXXX')
            for frame in frames:
                if frame.desc == desc:
                    return str(frame.text[0]) if frame.text else default
            return default

        def get_comm() -> str:
            """Helper to extract COMM (comment) frames."""
            frames = tags.getall('COMM')
            if frames:
                # Return the first comment's text
                return str(frames[0].text[0]) if frames[0].text else ''
            return ''

        return {
            'title': get_text('TIT2'),
            'artist': get_text('TPE1'),
            'album': get_text('TALB'),
            'album_artist': get_text('TPE2'),
            'year': get_text('TDRC'),
            'genre': '; '.join(get_text_list('TCON')),
            'track_number': get_text('TRCK'),
            'disc_number': get_text('TPOS'),
            'bpm': get_text('TBPM'),
            'key': get_text('TKEY'),
            'publisher': '; '.join(get_text_list('TPUB')),
            'catalog_number': get_txxx('CATALOGNUMBER'),
            'composer': get_text('TCOM'),
            'comment': get_comm(),
        }

    def _read_flac_tags(self) -> dict[str, Any]:
        """Read tags from FLAC file."""
        if self.audio is None:
            return {}
        tags = self.audio.tags or {}

        def get_tag(key: str, default: Any = '') -> Any:
            """Helper to extract FLAC tags."""
            value = tags.get(key, [default])
            return value[0] if value else default

        return {
            'title': get_tag('TITLE'),
            'artist': get_tag('ARTIST'),
            'album': get_tag('ALBUM'),
            'album_artist': get_tag('ALBUMARTIST'),
            'year': get_tag('DATE'),
            'genre': '; '.join(tags.get('GENRE', [])),
            'track_number': get_tag('TRACKNUMBER'),
            'disc_number': get_tag('DISCNUMBER'),
            'bpm': get_tag('BPM'),
            'key': get_tag('INITIALKEY') or get_tag('KEY'),
            'publisher': '; '.join(tags.get('LABEL', [])),
            'catalog_number': get_tag('CATALOGNUMBER'),
            'composer': get_tag('COMPOSER'),
            'comment': get_tag('COMMENT'),
        }

    def _read_mp4_tags(self) -> dict[str, Any]:
        """Read tags from MP4/M4A file."""
        if self.audio is None:
            return {}
        tags = self.audio.tags or {}

        def get_tag(key: str, default: Any = '') -> Any:
            """Helper to extract MP4 tags."""
            value = tags.get(key, [default])
            return value[0] if value else default

        def get_freeform(key: str, default: str = '') -> str:
            """Helper to extract and decode MP4 freeform (----) atoms.

            Freeform values are MP4FreeForm (a bytes subclass) - str() on
            one gives its repr (b'...'), not the decoded text.
            """
            value = tags.get(key)
            if not value:
                return default
            try:
                return bytes(value[0]).decode('utf-8')
            except (UnicodeDecodeError, TypeError):
                return default

        return {
            'title': get_tag('\xa9nam'),
            'artist': get_tag('\xa9ART'),
            'album': get_tag('\xa9alb'),
            'album_artist': get_tag('aART'),
            'year': str(get_tag('\xa9day')),
            'genre': '; '.join(tags.get('\xa9gen', [])),
            'track_number': f"{get_tag('trkn', (0, 0))[0]}/{get_tag('trkn', (0, 0))[1]}" if 'trkn' in tags else '',
            'disc_number': f"{get_tag('disk', (0, 0))[0]}/{get_tag('disk', (0, 0))[1]}" if 'disk' in tags else '',
            # Empty string (not 0) when absent - matches MP3/FLAC/OGG's
            # contract and avoids ingest.py's `if existing_bpm:` check
            # treating a stringified 0 as an already-tagged BPM, which
            # silently skipped real BPM analysis on every untagged m4a file.
            'bpm': str(get_tag('tmpo')),
            'key': get_freeform('----:com.apple.iTunes:initialkey'),
            'publisher': get_freeform('----:com.apple.iTunes:LABEL'),
            'catalog_number': get_freeform('----:com.apple.iTunes:CATALOGNUMBER'),
            'composer': get_tag('\xa9wrt'),
            'comment': get_tag('\xa9cmt'),
        }

    def _read_ogg_tags(self) -> dict[str, Any]:
        """Read tags from OGG Vorbis file."""
        if self.audio is None:
            return {}
        tags = self.audio.tags or {}

        def get_tag(key: str, default: Any = '') -> Any:
            """Helper to extract OGG tags."""
            value = tags.get(key, [default])
            return value[0] if value else default

        return {
            'title': get_tag('TITLE'),
            'artist': get_tag('ARTIST'),
            'album': get_tag('ALBUM'),
            'album_artist': get_tag('ALBUMARTIST'),
            'year': get_tag('DATE'),
            'genre': '; '.join(tags.get('GENRE', [])),
            'track_number': get_tag('TRACKNUMBER'),
            'disc_number': get_tag('DISCNUMBER'),
            'bpm': get_tag('BPM'),
            'key': get_tag('INITIALKEY') or get_tag('KEY'),
            'publisher': '; '.join(tags.get('LABEL', [])),
            'catalog_number': get_tag('CATALOGNUMBER'),
            'composer': get_tag('COMPOSER'),
            'comment': get_tag('COMMENT'),
        }

    def write_tags(self, metadata: dict[str, Any]) -> bool:
        """
        Write tags to the audio file.

        Only updates tags that are present in the metadata dict.
        Does not remove existing tags.

        Parameters
        ----------
        metadata : Dict[str, Any]
            Dictionary with tag names and values to write.
            Supported keys:
            - title: str
            - artist: str
            - album: str
            - album_artist: str
            - year: int or str
            - genre: str or List[str]
            - styles: List[str] (merged with genre)
            - track_number: str or int
            - disc_number: str or int
            - bpm: int or float
            - publisher: str or List[str]
            - labels: List[str] (merged with publisher)
            - catalog_number: str or List[str]
            - composer: str
            - comment: str

        Returns
        -------
        bool
            True if successful, False otherwise.

        Example
        -------
        >>> tags = AudioTags("track.mp3")
        >>> tags.write_tags({
        ...     'artist': 'New Artist',
        ...     'album': 'Great Album',
        ...     'bpm': 128
        ... })
        """
        if self.audio is None:
            logger.error("No audio file loaded")
            return False

        try:
            suffix = self.file_path.suffix.lower()

            if suffix == '.mp3':
                self._write_mp3_tags(metadata)
            elif suffix == '.flac':
                self._write_flac_tags(metadata)
            elif suffix in ['.m4a', '.mp4']:
                self._write_mp4_tags(metadata)
            elif suffix == '.ogg':
                self._write_ogg_tags(metadata)
            else:
                logger.warning("Unsupported format: %s", suffix)
                return False

            self.audio.save()
            logger.info("Successfully updated tags for %s",
                        self.file_path.name)
            return True

        except (MutagenError, OSError, ValueError) as e:
            logger.error("Error writing tags to %s: %s", self.file_path, e)
            return False

    def _write_mp3_tags(self, metadata: dict[str, Any]) -> None:
        """Write tags to MP3 file."""
        if self.audio is None:
            return
        tags = self.audio.tags

        # Helper function to update text frames
        def update_frame(frame_id: str, frame_cls: type, value: str) -> None:
            if frame_id not in tags or tags[frame_id].text[0] != value:
                tags[frame_id] = frame_cls(encoding=3, text=value)

        # Basic tags
        if 'title' in metadata:
            update_frame('TIT2', TIT2, metadata['title'])
        if 'artist' in metadata:
            update_frame('TPE1', TPE1, metadata['artist'])
        if 'album' in metadata:
            update_frame('TALB', TALB, metadata['album'])
        if 'album_artist' in metadata:
            update_frame('TPE2', TPE2, metadata['album_artist'])
        if 'year' in metadata:
            update_frame('TDRC', TDRC, str(metadata['year']))
        if 'composer' in metadata:
            update_frame('TCOM', TCOM, metadata['composer'])

        # Genre and styles
        genres = []
        if 'genre' in metadata:
            if isinstance(metadata['genre'], list):
                genres.extend(metadata['genre'])
            else:
                genres.append(metadata['genre'])
        if 'styles' in metadata:
            genres.extend(metadata['styles'])
        if genres:
            update_frame('TCON', TCON, '; '.join(genres))

        # Publisher and labels
        publishers = []
        if 'publisher' in metadata:
            if isinstance(metadata['publisher'], list):
                publishers.extend(metadata['publisher'])
            else:
                publishers.append(metadata['publisher'])
        if 'labels' in metadata:
            publishers.extend(metadata['labels'])
        if publishers:
            update_frame('TPUB', TPUB, '; '.join(publishers))

        # Track and disc numbers
        if 'track_number' in metadata:
            update_frame('TRCK', TRCK, str(metadata['track_number']))
        if 'disc_number' in metadata:
            update_frame('TPOS', TPOS, str(metadata['disc_number']))

        # BPM
        if 'bpm' in metadata:
            bpm_val = str(int(round(float(metadata['bpm']))))
            update_frame('TBPM', TBPM, bpm_val)

        # Catalog number (TXXX frame)
        if 'catalog_number' in metadata:
            cat_nums = metadata['catalog_number']
            if isinstance(cat_nums, list):
                cat_nums = '; '.join(cat_nums)

            # Remove existing CATALOGNUMBER frames
            txxx_frames = tags.getall('TXXX')
            for frame in txxx_frames:
                if frame.desc == 'CATALOGNUMBER':
                    tags.delall('TXXX:CATALOGNUMBER')
                    break

            tags.add(TXXX(encoding=3, desc='CATALOGNUMBER', text=cat_nums))

    def _write_flac_tags(self, metadata: dict[str, Any]) -> None:
        """Write tags to FLAC file."""
        if self.audio is None:
            return
        tags = self.audio.tags

        if 'title' in metadata:
            tags['TITLE'] = metadata['title']
        if 'artist' in metadata:
            tags['ARTIST'] = metadata['artist']
        if 'album' in metadata:
            tags['ALBUM'] = metadata['album']
        if 'album_artist' in metadata:
            tags['ALBUMARTIST'] = metadata['album_artist']
        if 'year' in metadata:
            tags['DATE'] = str(metadata['year'])
        if 'composer' in metadata:
            tags['COMPOSER'] = metadata['composer']

        # Genre and styles
        genres = []
        if 'genre' in metadata:
            if isinstance(metadata['genre'], list):
                genres.extend(metadata['genre'])
            else:
                genres.append(metadata['genre'])
        if 'styles' in metadata:
            genres.extend(metadata['styles'])
        if genres:
            tags['GENRE'] = genres

        # Publisher and labels
        publishers = []
        if 'publisher' in metadata:
            if isinstance(metadata['publisher'], list):
                publishers.extend(metadata['publisher'])
            else:
                publishers.append(metadata['publisher'])
        if 'labels' in metadata:
            publishers.extend(metadata['labels'])
        if publishers:
            tags['LABEL'] = publishers

        if 'track_number' in metadata:
            tags['TRACKNUMBER'] = str(metadata['track_number'])
        if 'disc_number' in metadata:
            tags['DISCNUMBER'] = str(metadata['disc_number'])
        if 'bpm' in metadata:
            tags['BPM'] = str(int(round(float(metadata['bpm']))))

        if 'catalog_number' in metadata:
            cat_nums = metadata['catalog_number']
            if isinstance(cat_nums, list):
                cat_nums = '; '.join(cat_nums)
            tags['CATALOGNUMBER'] = cat_nums

    def _write_mp4_tags(self, metadata: dict[str, Any]) -> None:
        """Write tags to MP4/M4A file."""
        if self.audio is None:
            return
        tags = self.audio.tags

        if 'title' in metadata:
            tags['\xa9nam'] = metadata['title']
        if 'artist' in metadata:
            tags['\xa9ART'] = metadata['artist']
        if 'album' in metadata:
            tags['\xa9alb'] = metadata['album']
        if 'album_artist' in metadata:
            tags['aART'] = metadata['album_artist']
        if 'year' in metadata:
            tags['\xa9day'] = str(metadata['year'])
        if 'composer' in metadata:
            tags['\xa9wrt'] = metadata['composer']

        # Genre and styles
        genres = []
        if 'genre' in metadata:
            if isinstance(metadata['genre'], list):
                genres.extend(metadata['genre'])
            else:
                genres.append(metadata['genre'])
        if 'styles' in metadata:
            genres.extend(metadata['styles'])
        if genres:
            tags['\xa9gen'] = genres

        if 'bpm' in metadata:
            tags['tmpo'] = [int(round(float(metadata['bpm'])))]

        # Publisher and labels. MP4 has no standard atom for this - uses a
        # freeform (----) atom, same as FLAC's LABEL / MP3's TPUB.
        publishers = []
        if 'publisher' in metadata:
            if isinstance(metadata['publisher'], list):
                publishers.extend(metadata['publisher'])
            else:
                publishers.append(metadata['publisher'])
        if 'labels' in metadata:
            publishers.extend(metadata['labels'])
        if publishers:
            tags['----:com.apple.iTunes:LABEL'] = [
                MP4FreeForm('; '.join(publishers).encode('utf-8'))
            ]

        if 'catalog_number' in metadata:
            cat_nums = metadata['catalog_number']
            if isinstance(cat_nums, list):
                cat_nums = '; '.join(cat_nums)
            tags['----:com.apple.iTunes:CATALOGNUMBER'] = [
                MP4FreeForm(str(cat_nums).encode('utf-8'))
            ]

    def _write_ogg_tags(self, metadata: dict[str, Any]) -> None:
        """Write tags to OGG Vorbis file."""
        # OGG uses same tag names as FLAC
        self._write_flac_tags(metadata)


def read_audio_tags(file_path: str | Path) -> dict[str, Any]:
    """
    Read tags from an audio file.

    Convenience function that creates AudioTags instance and reads tags.

    Parameters
    ----------
    file_path : Union[str, Path]
        Path to the audio file.

    Returns
    -------
    Dict[str, Any]
        Dictionary containing all available metadata.
    """
    tags = AudioTags(file_path)
    return tags.read_tags()


def write_audio_tags(file_path: str | Path, metadata: dict[str, Any]) -> bool:
    """
    Write tags to an audio file.

    Convenience function that creates AudioTags instance and writes tags.

    Parameters
    ----------
    file_path : Union[str, Path]
        Path to the audio file.
    metadata : Dict[str, Any]
        Dictionary with tag names and values to write.

    Returns
    -------
    bool
        True if successful, False otherwise.
    """
    tags = AudioTags(file_path)
    return tags.write_tags(metadata)


def embed_cover_art(file_path: str | Path, image_path: str | Path) -> bool:
    """
    Embed a cover art image into an audio file's tags.

    Supports MP3 (ID3v2 APIC), FLAC (Picture block), M4A/MP4 (covr atom),
    and OGG Vorbis (base64 METADATA_BLOCK_PICTURE, per the Xiph spec).

    Parameters
    ----------
    file_path : Union[str, Path]
        Path to the audio file to embed the image into.
    image_path : Union[str, Path]
        Path to a .jpg/.jpeg/.png cover art image.

    Returns
    -------
    bool
        True if successful, False otherwise.

    Example
    -------
    >>> embed_cover_art("track.mp3", "cover.jpg")
    """
    file_path = Path(file_path)
    image_path = Path(image_path)

    mime = _IMAGE_MIME_TYPES.get(image_path.suffix.lower())
    if mime is None:
        logger.error("Unsupported cover art format: %s", image_path.suffix)
        return False

    try:
        image_data = image_path.read_bytes()
    except OSError as e:
        logger.error("Could not read cover art %s: %s", image_path, e)
        return False

    try:
        audio = File(str(file_path))
        if audio is None:
            logger.error("Could not load file: %s", file_path)
            return False

        suffix = file_path.suffix.lower()

        if suffix == '.mp3':
            if audio.tags is None:
                audio.add_tags()
            # Remove any existing front-cover pictures before adding the new one
            audio.tags.delall('APIC')
            audio.tags.add(APIC(
                encoding=3, mime=mime, type=3,
                desc='Cover', data=image_data,
            ))

        elif isinstance(audio, FLAC):
            picture = Picture()
            picture.type = 3
            picture.mime = mime
            picture.data = image_data
            audio.clear_pictures()
            audio.add_picture(picture)

        elif isinstance(audio, MP4):
            cover_format = (
                MP4Cover.FORMAT_PNG if mime == 'image/png' else MP4Cover.FORMAT_JPEG
            )
            audio['covr'] = [MP4Cover(image_data, imageformat=cover_format)]

        elif hasattr(audio, 'tags') and audio.tags is not None:
            # OGG Vorbis: base64-encoded FLAC Picture block, Xiph's
            # standard convention for embedding art in Vorbis comments
            picture = Picture()
            picture.type = 3
            picture.mime = mime
            picture.data = image_data
            audio['METADATA_BLOCK_PICTURE'] = [
                base64.b64encode(picture.write()).decode('ascii')
            ]

        else:
            logger.warning("Unsupported audio format for %s", file_path)
            return False

        audio.save()
        logger.info("Successfully embedded cover art in %s", file_path.name)
        return True

    except (MutagenError, OSError, ValueError) as e:
        logger.error("Error embedding cover art in %s: %s", file_path, e)
        return False
