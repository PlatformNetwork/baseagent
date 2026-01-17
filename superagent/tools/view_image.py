"""
View image tool - loads images into context.

Allows the agent to load and view local image files.
The image is encoded as base64 and injected into the conversation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from superagent.tools.base import ToolResult
from superagent.images.loader import load_image_as_data_uri, make_image_content


def get_image_dimensions(data: bytes) -> Optional[Tuple[int, int]]:
    """Parse image dimensions from raw bytes without PIL."""
    if len(data) < 24:
        return None
    
    # PNG: signature 0x89 PNG, dimensions at offset 16-23
    if data[:4] == b'\x89PNG' and len(data) >= 24:
        width = int.from_bytes(data[16:20], 'big')
        height = int.from_bytes(data[20:24], 'big')
        return (width, height)
    
    # JPEG: signature 0xFF 0xD8 0xFF, parse SOF markers
    if data[:3] == b'\xff\xd8\xff':
        return _parse_jpeg_dimensions(data)
    
    # GIF: signature GIF87a or GIF89a, dimensions at offset 6-9 (little-endian)
    if data[:6] in (b'GIF87a', b'GIF89a') and len(data) >= 10:
        width = int.from_bytes(data[6:8], 'little')
        height = int.from_bytes(data[8:10], 'little')
        return (width, height)
    
    # BMP: signature BM, dimensions at offset 18-25 (little-endian, signed)
    if data[:2] == b'BM' and len(data) >= 26:
        width = abs(int.from_bytes(data[18:22], 'little', signed=True))
        height = abs(int.from_bytes(data[22:26], 'little', signed=True))
        return (width, height)
    
    # WebP: RIFF....WEBP
    if len(data) >= 30 and data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return _parse_webp_dimensions(data)
    
    return None


def _parse_jpeg_dimensions(data: bytes) -> Optional[Tuple[int, int]]:
    """Parse JPEG dimensions from SOF markers."""
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        
        marker = data[i + 1]
        
        # SOF markers: C0, C1, C2, C3, C5, C6, C7, C9, CA, CB, CD, CE, CF
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 
                      0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            if i + 9 < len(data):
                height = int.from_bytes(data[i+5:i+7], 'big')
                width = int.from_bytes(data[i+7:i+9], 'big')
                return (width, height)
        
        # Skip to next marker
        if marker in (0xFF, 0x00, 0x01) or 0xD0 <= marker <= 0xD9:
            i += 2
        elif i + 3 < len(data):
            length = int.from_bytes(data[i+2:i+4], 'big')
            i += 2 + length
        else:
            break
    
    return None


def _parse_webp_dimensions(data: bytes) -> Optional[Tuple[int, int]]:
    """Parse WebP dimensions (VP8 and VP8L formats)."""
    # VP8 format
    if data[12:16] == b'VP8 ' and len(data) >= 30:
        width = (int.from_bytes(data[26:28], 'little') & 0x3FFF)
        height = (int.from_bytes(data[28:30], 'little') & 0x3FFF)
        return (width, height)
    
    # VP8L format
    if data[12:16] == b'VP8L' and len(data) >= 25:
        b0, b1, b2, b3 = data[21], data[22], data[23], data[24]
        width = ((b1 & 0x3F) << 8 | b0) + 1
        height = ((b3 & 0x0F) << 10 | b2 << 2 | (b1 >> 6)) + 1
        return (width, height)
    
    return None


def view_image(
    file_path: str,
    cwd: Path,
) -> ToolResult:
    """
    Load a local image and return it for the model context.
    
    Args:
        file_path: Path to the image file (relative or absolute)
        cwd: Current working directory
        
    Returns:
        ToolResult with success status and optional image content
    """
    # Resolve path
    path = Path(file_path)
    if not path.is_absolute():
        path = cwd / path
    path = path.resolve()
    
    # Check if file exists
    if not path.exists():
        return ToolResult(
            success=False,
            output=f"Image not found: {path}",
        )
    
    if not path.is_file():
        return ToolResult(
            success=False,
            output=f"Not a file: {path}",
        )
    
    # Check if it's an image file
    valid_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
    if path.suffix.lower() not in valid_extensions:
        return ToolResult(
            success=False,
            output=f"Not a valid image file: {path} (supported: {', '.join(valid_extensions)})",
        )
    
    try:
        # Read raw bytes first to get dimensions
        image_data = path.read_bytes()
        dimensions = get_image_dimensions(image_data)
        
        # Load and encode the image
        data_uri = load_image_as_data_uri(path)
        
        # Create content block for injection
        image_content = make_image_content(data_uri)
        
        # Build output message with dimensions if available
        if dimensions:
            width, height = dimensions
            output_msg = f"attached local image: {path.name} ({width}x{height})"
        else:
            output_msg = f"attached local image: {path.name}"
        
        return ToolResult(
            success=True,
            output=output_msg,
            inject_content=image_content,
        )
        
    except FileNotFoundError:
        return ToolResult(
            success=False,
            output=f"Image file not found: {path}",
        )
    except Exception as e:
        return ToolResult(
            success=False,
            output=f"Failed to load image: {e}",
        )


# Tool specification for LLM
VIEW_IMAGE_SPEC: Dict[str, Any] = {
    "name": "view_image",
    "description": """View a local image from the filesystem.
Only use this if given a full filepath by the user, and the image isn't already attached.
Supported formats: PNG, JPEG, GIF, WebP, BMP.""",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Local filesystem path to the image file",
            },
        },
        "required": ["path"],
    },
}
