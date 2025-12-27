"""
GUI widgets for the audio tagging application.

This package contains all the main UI components.
"""
from .dashboard import DashboardWidget
from .discogs import DiscogsLookupWidget
from .ingest import IngestWidget, IngestWorker
from .query import QueryWidget

__all__ = [
    'DashboardWidget',
    'DiscogsLookupWidget',
    'IngestWidget',
    'IngestWorker',
    'QueryWidget',
]
