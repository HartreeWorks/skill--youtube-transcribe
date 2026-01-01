#!/usr/bin/env python3
"""
Local server for YouTube Transcript Viewer with state management and delete.

Serves the viewer on localhost:4322 and provides APIs for:
- Viewing transcripts
- Marking as read/unread
- Starring/unstarring
- Archiving/unarchiving
- Deleting transcripts

Usage:
    python serve.py           # Start server
    python serve.py --check   # Check if server is running
"""

import argparse
import http.server
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

PORT = 4322
SKILL_DIR = Path(__file__).parent.resolve()
STATE_FILE = SKILL_DIR / 'state.json'


def load_state() -> dict:
    """Load state from JSON file."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except:
            pass
    return {}


def save_state(state: dict):
    """Save state to JSON file."""
    STATE_FILE.write_text(json.dumps(state, indent=2))


def is_server_running() -> bool:
    """Check if server is already running on the port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(('127.0.0.1', PORT))
            return result == 0
    except:
        return False


def rebuild_viewer():
    """Rebuild the index.html after deletion."""
    build_script = SKILL_DIR / 'viewer' / 'build.py'
    if build_script.exists():
        subprocess.run([sys.executable, str(build_script)],
                      capture_output=True, cwd=str(SKILL_DIR))


def delete_transcript(video_id: str) -> tuple[bool, str]:
    """Delete all files associated with a video ID."""
    deleted_files = []

    patterns = [
        ('summaries', f'*-{video_id}.md'),
        ('metadata', f'*-{video_id}.json'),
        ('transcripts', f'*-{video_id}.txt'),
        ('transcripts', f'*-{video_id}.srt'),
        ('audio', f'*-{video_id}.mp3'),
    ]

    for subdir, pattern in patterns:
        dir_path = SKILL_DIR / subdir
        if dir_path.exists():
            for filepath in dir_path.glob(pattern):
                try:
                    filepath.unlink()
                    deleted_files.append(str(filepath.relative_to(SKILL_DIR)))
                except Exception as e:
                    return False, f"Failed to delete {filepath.name}: {e}"

    if not deleted_files:
        return False, f"No files found for video ID: {video_id}"

    # Remove from state
    state = load_state()
    if video_id in state:
        del state[video_id]
        save_state(state)

    # Rebuild the viewer
    rebuild_viewer()

    return True, f"Deleted {len(deleted_files)} files"


class TranscriptHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler with state management and DELETE support."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SKILL_DIR), **kwargs)

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)

        if parsed.path == '/api/state':
            state = load_state()
            self.send_json_response(200, state)
        else:
            super().do_GET()

    def do_PATCH(self):
        """Handle PATCH requests for state updates."""
        parsed = urlparse(self.path)

        # Expect /api/state/<video_id>
        if parsed.path.startswith('/api/state/'):
            video_id = parsed.path.split('/')[-1]

            if not video_id or len(video_id) != 11:
                self.send_json_response(400, {'error': 'Invalid video ID'})
                return

            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)

            try:
                updates = json.loads(body) if body else {}
            except json.JSONDecodeError:
                self.send_json_response(400, {'error': 'Invalid JSON'})
                return

            # Update state
            state = load_state()
            if video_id not in state:
                state[video_id] = {'read': False, 'starred': False, 'archived': False}

            # Only allow valid keys
            for key in ['read', 'starred', 'archived']:
                if key in updates:
                    state[video_id][key] = bool(updates[key])

            save_state(state)
            self.send_json_response(200, {'success': True, 'state': state[video_id]})
        else:
            self.send_json_response(404, {'error': 'Not found'})

    def do_DELETE(self):
        """Handle DELETE requests for transcript removal."""
        parsed = urlparse(self.path)

        if parsed.path.startswith('/api/delete/'):
            video_id = parsed.path.split('/')[-1]

            if not video_id or len(video_id) != 11:
                self.send_json_response(400, {'error': 'Invalid video ID'})
                return

            success, message = delete_transcript(video_id)

            if success:
                self.send_json_response(200, {'success': True, 'message': message})
            else:
                self.send_json_response(404, {'error': message})
        else:
            self.send_json_response(404, {'error': 'Not found'})

    def send_json_response(self, status: int, data: dict):
        """Send a JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, PATCH, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        """Suppress routine GET logging, show others."""
        if 'DELETE' in str(args) or 'PATCH' in str(args) or '404' in str(args) or '500' in str(args):
            super().log_message(format, *args)


def start_server():
    """Start the HTTP server."""
    print(f"Starting Transcript Viewer server on http://localhost:{PORT}")
    print(f"Serving from: {SKILL_DIR}")
    print(f"Press Ctrl+C to stop\n")

    with http.server.HTTPServer(('', PORT), TranscriptHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


def main():
    parser = argparse.ArgumentParser(description='Transcript Viewer Server')
    parser.add_argument('--check', action='store_true',
                       help='Check if server is running (exit 0 if yes, 1 if no)')
    args = parser.parse_args()

    if args.check:
        if is_server_running():
            print(f"Server is running on port {PORT}")
            sys.exit(0)
        else:
            print(f"Server is not running on port {PORT}")
            sys.exit(1)
    else:
        if is_server_running():
            print(f"Server already running on port {PORT}")
            print(f"Visit: http://localhost:{PORT}")
            sys.exit(0)
        start_server()


if __name__ == '__main__':
    main()
