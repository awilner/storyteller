"""Utilities shared between the Scrivener importer and exporter."""


def hex_to_scriv_colour(hex_str):
    """Convert hex colour (e.g. '#F3EA54') to Scrivener RGB float string."""
    if not hex_str or len(hex_str) < 7:
        return ""
    try:
        r = int(hex_str[1:3], 16) / 255.0
        g = int(hex_str[3:5], 16) / 255.0
        b = int(hex_str[5:7], 16) / 255.0
        return f"{r:.6f} {g:.6f} {b:.6f}"
    except (ValueError, IndexError):
        return ""


def scriv_colour_to_hex(colour_str):
    """Convert Scrivener RGB float string (e.g. '0.952941 0.917647 0.329412') to hex."""
    if not colour_str:
        return ""
    try:
        parts = colour_str.strip().split()
        r = int(float(parts[0]) * 255)
        g = int(float(parts[1]) * 255)
        b = int(float(parts[2]) * 255)
        return f"#{r:02X}{g:02X}{b:02X}"
    except (IndexError, ValueError):
        return ""
