"""Time parsing utilities for video segments"""
import re
from typing import Tuple, Optional
from datetime import datetime, timedelta


def parse_timestamp(timestamp: str) -> int:
    """
    Parse timestamp string to seconds
    
    Supports formats:
    - HH:MM:SS (00:03:50)
    - MM:SS (03:50)
    - SS (230)
    
    Returns:
        int: Total seconds
    """
    timestamp = timestamp.strip()
    
    # Try HH:MM:SS format
    if timestamp.count(':') == 2:
        h, m, s = timestamp.split(':')
        return int(h) * 3600 + int(m) * 60 + int(s)
    
    # Try MM:SS format
    elif timestamp.count(':') == 1:
        m, s = timestamp.split(':')
        return int(m) * 60 + int(s)
    
    # Try plain seconds
    else:
        return int(timestamp)


def parse_time_range(time_range: str) -> Tuple[int, int, int]:
    """Parse time range string to start, end, duration in seconds.

    Accepts flexible timestamp formats on each side of the dash:
    - HH:MM:SS  (e.g. "00:03:50")
    - MM:SS     (e.g. "03:50")
    - SS        (e.g. "230")

    The overall pattern must still be "start - end" with a single '-' separator.

    Args:
        time_range: Time range string, e.g. "00:03:50 - 00:08:16" or "03:50 - 08:16".

    Returns:
        Tuple[int, int, int]: (start_seconds, end_seconds, duration_seconds)
    """
    # Normalize whitespace
    time_range = time_range.strip()

    # Split on single dash
    if '-' not in time_range:
        raise ValueError(f"Invalid time range format (missing '-'): {time_range}")

    parts = [p.strip() for p in time_range.split('-')]
    if len(parts) != 2:
        raise ValueError(f"Invalid time range format (expected 'start - end'): {time_range}")

    start_str, end_str = parts[0], parts[1]
    if not start_str or not end_str:
        raise ValueError(f"Invalid time range format (empty start or end): {time_range}")

    # Use parse_timestamp which already supports HH:MM:SS, MM:SS, and seconds
    try:
        start_time = parse_timestamp(start_str)
        end_time = parse_timestamp(end_str)
    except Exception as e:
        raise ValueError(f"Invalid timestamp in range '{time_range}': {e}") from e
    
    if end_time <= start_time:
        raise ValueError(f"End time must be greater than start time: {time_range}")
    
    duration = end_time - start_time
    
    return start_time, end_time, duration


def seconds_to_timestamp(seconds: int) -> str:
    """
    Convert seconds to HH:MM:SS format
    
    Args:
        seconds: Total seconds
    
    Returns:
        str: Formatted timestamp (HH:MM:SS)
    
    Example:
        >>> seconds_to_timestamp(230)
        '00:03:50'
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def extract_url_timestamp(url: str) -> Optional[int]:
    """
    Extract timestamp from YouTube URL
    
    Args:
        url: YouTube URL, may contain &t=XXXs parameter
    
    Returns:
        Optional[int]: Timestamp in seconds, or None if not found
    
    Example:
        >>> extract_url_timestamp("https://youtube.com/watch?v=ABC&t=230s")
        230
    """
    # If URL is not a string (e.g. NaN/float from Excel), skip
    if not isinstance(url, str):
        return None

    # Match &t=XXXs or &t=XXX
    match = re.search(r'[&?]t=(\d+)s?', url)
    if match:
        return int(match.group(1))
    
    return None


def get_segment_info(url: str, time_range: Optional[str] = None) -> Tuple[int, Optional[int], Optional[int]]:
    """
    Get segment information from URL and time range
    
    Args:
        url: YouTube URL
        time_range: Optional time range string (e.g., "00:03:50 - 00:08:16")
    
    Returns:
        Tuple[int, Optional[int], Optional[int]]: (start, end, duration)
        - If time_range provided: use it
        - Special case: "00:00:00 - 00:00:00" is treated as no range (full video)
        - If only URL timestamp: (url_timestamp, None, None)
        - If neither: (0, None, None)
    """
    # Only handle time_range if it's a non-empty string
    if isinstance(time_range, str) and time_range.strip():
        normalized = time_range.strip()

        # Special case: zero-length range treated as full video.
        # Accept both "00:00:00 - 00:00:00" and "00:00 - 00:00" style.
        try:
            parts = [p.strip() for p in normalized.split('-')]
            if len(parts) == 2:
                start_zero = parse_timestamp(parts[0]) == 0
                end_zero = parse_timestamp(parts[1]) == 0
                if start_zero and end_zero:
                    return 0, None, None
        except Exception:
            # If parsing here fails, we'll fall back to the normal range parsing below
            pass

        # Parse time range (flexible: hh:mm:ss, mm:ss, or seconds)
        start, end, duration = parse_time_range(time_range)
        return start, end, duration
    
    # Try to get timestamp from URL
    url_timestamp = extract_url_timestamp(url)
    if url_timestamp is not None:
        return url_timestamp, None, None
    
    # No timestamp information
    return 0, None, None
