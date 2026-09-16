"""
This module provides a client for interacting with the Discogs API.
"""
import logging
import time
from itertools import islice

import discogs_client as discogs
from discogs_client.exceptions import HTTPError, DiscogsAPIError

logger = logging.getLogger(__name__)


class DiscogsClient:
    """
    A client for interacting with the Discogs API.

    Handles rate limiting and provides methods to search for artists and releases.
    """

    def __init__(self, user_token: str, rate_limit_delay: float = 1.0):
        """
        Initialize the Discogs client with user token.

        Parameters
        ----------
        user_token : str
            Discogs API user token for authentication.
        rate_limit_delay : float
            Delay in seconds between API requests to avoid rate limiting (default: 1.0).

        Raises
        ------
        ValueError
            If user_token is empty/None.
        """
        if not user_token:
            raise ValueError("Discogs user token is required")
        self.client = discogs.Client(
            'audio_files_tagging/0.1.0',
            user_token=user_token
        )
        self.rate_limit_delay = rate_limit_delay
        self._last_request_time = 0.0

    def _rate_limit(self) -> None:
        """Implement rate limiting to avoid hitting API limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    def search_artist(self, artist_name: str, max_results: int = 10) -> list[dict]:
        """
        Search for artists by name.

        Parameters
        ----------
        artist_name : str
            Name of the artist to search for.
        max_results : int
            Maximum number of results to return (default: 10).

        Returns
        -------
        List[Dict]
            A list of dictionaries containing artist metadata.
        """
        if not artist_name or not artist_name.strip():
            logger.warning("Empty artist name provided")
            return []

        try:
            self._rate_limit()
            search_results = self.client.search(artist_name, type='artist')

            artists = []
            artist_name_lower = artist_name.lower()

            for artist in islice(search_results, max_results * 2):  # Get more to filter
                try:
                    # Check if artist name matches (case-insensitive)
                    if artist_name_lower in artist.name.lower():
                        artist_data = {
                            'id': artist.id,
                            'name': artist.name,
                        }
                        artists.append(artist_data)

                        if len(artists) >= max_results:
                            break
                except AttributeError as e:
                    logger.warning(
                        "Skipping artist due to missing attribute: %s", e)
                    continue

            logger.info("Found %d artists matching '%s'",
                        len(artists), artist_name)
            return artists

        except HTTPError as e:
            logger.error("HTTP error searching for artist '%s': %s",
                         artist_name, str(e))
            return []
        except DiscogsAPIError as e:
            logger.error(
                "Discogs API error searching for artist '%s': %s", artist_name, str(e))
            return []
        except Exception as e:
            logger.error(
                "Unexpected error searching for artist '%s': %s", artist_name, str(e))
            return []

    def get_artist_by_id(self, artist_id: int) -> dict | None:
        """
        Get artist information by artist ID.

        Parameters
        ----------
        artist_id : int
            ID of the artist to retrieve.

        Returns
        -------
        Optional[Dict]
            A dictionary containing artist metadata, or None if not found.
        """
        try:
            self._rate_limit()
            artist = self.client.artist(artist_id)

            # Safely get list attributes
            members = getattr(artist, 'members', [])
            aliases = getattr(artist, 'aliases', [])

            artist_data = {
                'id': artist.id,
                'name': artist.name,
                'real_name': getattr(artist, 'real_name', ''),
                'profile': getattr(artist, 'profile', ''),
                'members': [member.name for member in members] if members else [],
                'aliases': [alias.name for alias in aliases] if aliases else [],
                'name_variations': getattr(artist, 'name_variations', []),
                'urls': getattr(artist, 'urls', []),
                'images': getattr(artist, 'images', []),
            }

            logger.info("Retrieved artist ID %d: %s", artist_id, artist.name)
            return artist_data

        except HTTPError as e:
            logger.error("HTTP error retrieving artist ID %d: %s",
                         artist_id, str(e))
            return None
        except DiscogsAPIError as e:
            logger.error(
                "Discogs API error retrieving artist ID %d: %s", artist_id, str(e))
            return None
        except Exception as e:
            logger.error(
                "Unexpected error retrieving artist ID %d: %s", artist_id, str(e))
            return None

    def search_release(
        self,
        release_title: str,
        artist: str | None = None,
        max_results: int = 10
    ) -> list[dict]:
        """
        Search for releases by title and optionally filter by artist.

        Parameters
        ----------
        release_title : str
            Release title to search for.
        artist : Optional[str]
            Artist name to filter the search results (optional).
        max_results : int
            Maximum number of results to return (default: 10).

        Returns
        -------
        List[Dict]
            A list of matching releases.
        """
        if not release_title or not release_title.strip():
            logger.warning("Empty release title provided")
            return []

        try:
            self._rate_limit()
            search_results = self.client.search(
                release_title,
                type='release',
                artist=artist
            )

            releases = []
            release_title_lower = release_title.lower()

            for release in islice(search_results, max_results * 2):  # Get more to filter
                try:
                    # Check if release title matches (case-insensitive)
                    if release_title_lower in release.title.lower():
                        artists_list = getattr(release, 'artists', [])
                        formats_list = getattr(release, 'formats', [])

                        release_data = {
                            'id': release.id,
                            'title': release.title,
                            'artist': [a.name for a in artists_list] if artists_list else [],
                            'year': getattr(release, 'year', None),
                            'format': [fmt.get('name', '') for fmt in formats_list] if formats_list else [],
                            'country': getattr(release, 'country', None),
                        }
                        releases.append(release_data)

                        if len(releases) >= max_results:
                            break
                except (AttributeError, KeyError) as e:
                    logger.warning(
                        "Skipping release due to missing attribute: %s", e)
                    continue

            logger.info("Found %d releases matching '%s'",
                        len(releases), release_title)
            return releases

        except HTTPError as e:
            logger.error("HTTP error searching for release '%s': %s",
                         release_title, str(e))
            return []
        except DiscogsAPIError as e:
            logger.error(
                "Discogs API error searching for release '%s': %s", release_title, str(e))
            return []
        except Exception as e:
            logger.error(
                "Unexpected error searching for release '%s': %s", release_title, str(e))
            return []

    def get_release_by_id(self, release_id: int) -> dict | None:
        """
        Get release information by release ID.

        Parameters
        ----------
        release_id : int
            ID of the release to retrieve.

        Returns
        -------
        Optional[Dict]
            A dictionary containing release metadata, or None if not found.
        """
        try:
            self._rate_limit()
            release = self.client.release(release_id)

            # Safely get list attributes
            artists_list = getattr(release, 'artists', [])
            labels_list = getattr(release, 'labels', [])
            formats_list = getattr(release, 'formats', [])
            tracklist = getattr(release, 'tracklist', [])

            release_data = {
                'id': release.id,
                'title': release.title,
                'artist': [artist.name for artist in artists_list] if artists_list else [],
                'year': getattr(release, 'year', None),
                'genres': getattr(release, 'genres', []),
                'styles': getattr(release, 'styles', []),
                'labels': [label.name for label in labels_list] if labels_list else [],
                'format': [fmt.get('name', '') for fmt in formats_list] if formats_list else [],
                'catalog_numbers': [
                    label.data.get('catno', '')
                    for label in labels_list
                    if hasattr(label, 'data')
                ] if labels_list else [],
                'country': getattr(release, 'country', None),
                'notes': getattr(release, 'notes', ''),
                'images': getattr(release, 'images', []),
                'tracklist': [
                    {
                        'position': getattr(track, 'position', ''),
                        'title': getattr(track, 'title', ''),
                        'duration': getattr(track, 'duration', ''),
                    }
                    for track in tracklist
                ] if tracklist else []
            }

            logger.info("Retrieved release ID %d: %s",
                        release_id, release.title)
            return release_data

        except HTTPError as e:
            logger.error("HTTP error retrieving release ID %d: %s",
                         release_id, str(e))
            return None
        except DiscogsAPIError as e:
            logger.error(
                "Discogs API error retrieving release ID %d: %s", release_id, str(e))
            return None
        except Exception as e:
            logger.error(
                "Unexpected error retrieving release ID %d: %s", release_id, str(e))
            return None

    def get_master_release(self, master_id: int) -> dict | None:
        """
        Get master release information by master ID.

        A master release represents the main version of a release,
        with all its variations grouped together.

        Parameters
        ----------
        master_id : int
            ID of the master release to retrieve.

        Returns
        -------
        Optional[Dict]
            A dictionary containing master release metadata, or None if not found.
        """
        try:
            self._rate_limit()
            master = self.client.master(master_id)

            artists_list = getattr(master, 'artists', [])

            master_data = {
                'id': master.id,
                'title': master.title,
                'artist': [artist.name for artist in artists_list] if artists_list else [],
                'year': getattr(master, 'year', None),
                'genres': getattr(master, 'genres', []),
                'styles': getattr(master, 'styles', []),
                'main_release': getattr(master, 'main_release', None),
                'versions_url': getattr(master, 'versions_url', None),
                'images': getattr(master, 'images', []),
            }

            logger.info("Retrieved master release ID %d: %s",
                        master_id, master.title)
            return master_data

        except HTTPError as e:
            logger.error("HTTP error retrieving master ID %d: %s",
                         master_id, str(e))
            return None
        except DiscogsAPIError as e:
            logger.error(
                "Discogs API error retrieving master ID %d: %s", master_id, str(e))
            return None
        except Exception as e:
            logger.error(
                "Unexpected error retrieving master ID %d: %s", master_id, str(e))
            return None
