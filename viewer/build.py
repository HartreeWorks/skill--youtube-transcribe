#!/usr/bin/env python3
"""
Build script for YouTube Transcript Summary Viewer.
Scans the summaries directory and generates a static HTML viewer.

Usage:
    python viewer/build.py
    open index.html
"""

import json
import re
from pathlib import Path


def extract_video_id(filename: str, url: str | None = None) -> str | None:
    """Extract YouTube video ID from filename or URL."""
    # Try URL first
    if url:
        match = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', url)
        if match:
            return match.group(1)
        match = re.search(r'youtu\.be/([a-zA-Z0-9_-]{11})', url)
        if match:
            return match.group(1)

    # Fall back to filename: ends with -{VIDEO_ID}.md
    match = re.search(r'-([a-zA-Z0-9_-]{11})\.md$', filename)
    if match:
        return match.group(1)

    return None


def parse_summary(filepath: Path) -> dict | None:
    """Parse a summary markdown file and extract metadata."""
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception as e:
        print(f"  Warning: Could not read {filepath.name}: {e}")
        return None

    # Extract title from first # heading
    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else filepath.stem

    # Extract metadata fields
    channel_match = re.search(r'\*\*Channel:\*\*\s*(.+)', content)
    channel = channel_match.group(1).strip() if channel_match else "Unknown"

    url_match = re.search(r'\*\*URL:\*\*\s*(https?://[^\s]+)', content)
    url = url_match.group(1).strip() if url_match else None

    # Extract date from filename (YYYY-MM-DD prefix)
    date_match = re.match(r'^(\d{4}-\d{2}-\d{2})', filepath.stem)
    date = date_match.group(1) if date_match else "2025-01-01"

    # Get video ID
    video_id = extract_video_id(filepath.name, url)
    if not video_id:
        print(f"  Warning: Could not extract video ID from {filepath.name}")
        return None

    # Construct URL if missing
    if not url:
        url = f"https://www.youtube.com/watch?v={video_id}"

    # Thumbnail URL
    thumbnail = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"

    return {
        'id': video_id,
        'title': title,
        'channel': channel,
        'url': url,
        'date': date,
        'thumbnail': thumbnail,
        'content': content
    }


def build_viewer():
    """Build the viewer HTML file."""
    # Paths
    script_dir = Path(__file__).parent
    skill_dir = script_dir.parent
    summaries_dir = skill_dir / 'summaries'
    template_path = script_dir / 'template.html'
    output_path = skill_dir / 'index.html'

    print("Building YouTube Transcript Viewer...")
    print(f"  Summaries: {summaries_dir}")
    print(f"  Template:  {template_path}")
    print(f"  Output:    {output_path}")

    # Check paths
    if not summaries_dir.exists():
        print(f"Error: Summaries directory not found: {summaries_dir}")
        return False

    if not template_path.exists():
        print(f"Error: Template file not found: {template_path}")
        return False

    # Parse all summaries
    summaries = []
    md_files = sorted(summaries_dir.glob('*.md'), reverse=True)

    print(f"\nParsing {len(md_files)} summary files...")
    for filepath in md_files:
        print(f"  - {filepath.name}")
        summary = parse_summary(filepath)
        if summary:
            summaries.append(summary)

    print(f"\nSuccessfully parsed {len(summaries)} summaries.")

    # Read template
    template = template_path.read_text(encoding='utf-8')

    # Inject data
    data_json = json.dumps(summaries, ensure_ascii=False, indent=None)
    html = template.replace('/*SUMMARIES_DATA*/[]', data_json)

    # Write output
    output_path.write_text(html, encoding='utf-8')
    print(f"\nViewer built successfully!")
    print(f"  Output: {output_path}")
    print(f"\nTo view, run:")
    print(f"  open {output_path}")
    print(f"  # or")
    print(f"  python -m http.server 8000 --directory {skill_dir}")

    return True


if __name__ == '__main__':
    build_viewer()
