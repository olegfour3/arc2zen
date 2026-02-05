#!/usr/bin/env python3
"""Common data models for Arc bookmarks export/import."""

from dataclasses import dataclass, field
from typing import List, Union


@dataclass
class Bookmark:
    """Represents a single bookmark."""
    title: str
    url: str


@dataclass
class BookmarkFolder:
    """Represents a bookmark folder containing other bookmarks or folders."""
    title: str
    children: List[Union["Bookmark", "BookmarkFolder"]] = field(default_factory=list)


@dataclass
class ArcSpace:
    """Represents an Arc Browser Space (top-level container)."""
    name: str
    # Children can be BookmarkFolder or Bookmark (tabs without folder)
    children: List[Union[BookmarkFolder, Bookmark]] = field(default_factory=list)


@dataclass
class Space:
    """Represents an Arc browser space with container info."""
    name: str
    container_id: str
    is_pinned: bool
