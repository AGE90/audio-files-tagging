"""
SQLAlchemy ORM models for music library database.
"""
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    UniqueConstraint,
    DateTime,
    Text
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Artist(Base):
    """
    SQLAlchemy ORM model for an artist in the music library.
    """
    __tablename__ = 'artists'
    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    real_name = Column(String(255), nullable=True)
    country = Column(String(255), nullable=True)
    profile = Column(Text, nullable=True)
    members = Column(Text, nullable=True)
    aliases = Column(Text, nullable=True)
    name_variations = Column(Text, nullable=True)
    discogs_id = Column(Integer, unique=True, nullable=True)

    releases = relationship(
        'Release', back_populates='artist', cascade='all, delete-orphan')


class Release(Base):
    """
    SQLAlchemy ORM model for a music release in the library.
    """
    __tablename__ = 'releases'
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    year = Column(Integer, nullable=True)
    discogs_id = Column(Integer, unique=True, nullable=True)
    artist_id = Column(Integer, ForeignKey('artists.id'), nullable=False)
    genres = Column(String(255), nullable=True)
    styles = Column(String(255), nullable=True)
    catalog_number = Column(String(255), nullable=True)
    format = Column(String(255), nullable=True)
    country = Column(String(255), nullable=True)
    label = Column(String(255), nullable=True)

    artist = relationship('Artist', back_populates='releases')
    tracks = relationship('Track', back_populates='release',
                          cascade='all, delete-orphan')

    __table_args__ = (
        UniqueConstraint('title', 'artist_id', name='uix_title_artist'),
    )


class Track(Base):
    """
    SQLAlchemy ORM model for a track in a music release.
    """
    __tablename__ = 'tracks'
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    artist = Column(String(255), nullable=True)
    album_artist = Column(String(255), nullable=True)
    album = Column(String(255), nullable=True)
    track_number = Column(String(32), nullable=True)
    disc_number = Column(String(32), nullable=True)
    position = Column(String(32), nullable=True)
    duration = Column(Float, nullable=True)  # Duration in seconds
    file_path = Column(String(1024), unique=True, nullable=False)
    bpm = Column(Float, nullable=True)
    key = Column(String(32), nullable=True)
    genre = Column(String(255), nullable=True)
    composer = Column(String(255), nullable=True)
    year = Column(Integer, nullable=True)
    publisher = Column(String(255), nullable=True)
    catalog_number = Column(String(255), nullable=True)
    bitrate = Column(Integer, nullable=True)
    sample_rate = Column(Integer, nullable=True)
    last_modified = Column(DateTime, nullable=True)
    discogs_id = Column(Integer, nullable=True)
    release_id = Column(Integer, ForeignKey('releases.id'), nullable=True)

    release = relationship('Release', back_populates='tracks')
