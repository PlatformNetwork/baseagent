"""
Image loading, resizing, and base64 encoding.

Handles loading images from disk, resizing if needed, and encoding
as base64 data URIs for the LLM API.

Matches Codex behavior:
- Max dimensions: 2048x768
- LRU cache for repeated loads
- PNG/JPEG support
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Tuple

# Maximum image dimensions (like Codex)
MAX_WIDTH = 2048
MAX_HEIGHT = 768

# Try to import PIL for image processing
try:
    from PIL import Image

    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    Image = None


def _get_mime_type(path: Path) -> str:
    """Get MIME type from file extension."""
    ext = path.suffix.lower()
    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    return mime_types.get(ext, "image/png")


def _file_hash(path: Path) -> str:
    """Get SHA1 hash of file for caching."""
    with open(path, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()


def load_image_bytes(path: Path) -> Tuple[bytes, str]:
    """
    Load image bytes from disk.

    Args:
        path: Path to image file

    Returns:
        Tuple of (bytes, mime_type)
    """
    with open(path, "rb") as f:
        data = f.read()
    mime = _get_mime_type(path)
    return data, mime


def resize_image(
    data: bytes,
    mime: str,
    max_width: int = MAX_WIDTH,
    max_height: int = MAX_HEIGHT,
) -> Tuple[bytes, str]:
    """
    Resize image if it exceeds max dimensions.

    Args:
        data: Image bytes
        mime: MIME type
        max_width: Maximum width
        max_height: Maximum height

    Returns:
        Tuple of (resized_bytes, mime_type)
    """
    if not HAS_PIL:
        # Can't resize without PIL, return as-is
        return data, mime

    try:
        img = Image.open(BytesIO(data))

        # Check if resize needed
        if img.width <= max_width and img.height <= max_height:
            return data, mime

        # Resize maintaining aspect ratio
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

        # Encode back to bytes
        output = BytesIO()

        # Use PNG for transparency, JPEG for photos
        if img.mode in ("RGBA", "LA") or mime == "image/png":
            img.save(output, format="PNG", optimize=True)
            return output.getvalue(), "image/png"
        else:
            # Convert to RGB if needed
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(output, format="JPEG", quality=85, optimize=True)
            return output.getvalue(), "image/jpeg"

    except Exception:
        # On any error, return original
        return data, mime


@lru_cache(maxsize=32)
def _load_cached(path_str: str, file_hash: str) -> str:
    """Load and cache image as data URI (internal)."""
    path = Path(path_str)

    # Load raw bytes
    data, mime = load_image_bytes(path)

    # Resize if needed
    data, mime = resize_image(data, mime)

    # Encode as base64
    b64 = base64.b64encode(data).decode("ascii")

    return f"data:{mime};base64,{b64}"


def load_image_as_data_uri(path: Path) -> str:
    """
    Load image, resize if needed, encode as base64 data URI.

    Uses LRU cache based on file path and content hash.

    Args:
        path: Path to image file

    Returns:
        Data URI string (data:image/png;base64,...)

    Raises:
        FileNotFoundError: If image doesn't exist
        ValueError: If file is not a valid image
    """
    path = Path(path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    if not path.is_file():
        raise ValueError(f"Not a file: {path}")

    # Get file hash for cache key
    file_hash = _file_hash(path)

    # Load with caching
    return _load_cached(str(path), file_hash)


def make_image_content(data_uri: str) -> dict:
    """
    Create image content block for LLM API.

    Args:
        data_uri: Base64 data URI

    Returns:
        Content block dict for API
    """
    return {
        "type": "image_url",
        "image_url": {
            "url": data_uri,
        },
    }


def clear_cache() -> None:
    """Clear the image cache."""
    _load_cached.cache_clear()
