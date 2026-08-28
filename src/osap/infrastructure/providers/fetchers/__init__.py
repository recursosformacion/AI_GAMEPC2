from .github_fetcher import GitHubFetcher
from .iiif_fetcher import IIIFFetcher
from .kernscores_fetcher import KernScoresFetcher
from .mediawiki_fetcher import MediaWikiFetcher
from .musicbrainz_fetcher import MusicBrainzFetcher
from .mutopia_fetcher import MutopiaFetcher
from .omr_fetcher import OmrStorageFetcher
from .rism_fetcher import RismFetcher

__all__ = [
    "GitHubFetcher",
    "IIIFFetcher",
    "KernScoresFetcher",
    "MediaWikiFetcher",
    "MusicBrainzFetcher",
    "MutopiaFetcher",
    "OmrStorageFetcher",
    "RismFetcher",
]
