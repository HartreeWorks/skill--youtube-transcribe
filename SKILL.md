---
name: youtube-transcribe
description: This skill should be used when the user asks to transcribe a YouTube video or get its transcript. Uses Parakeet MLX (fast, local). AssemblyAI available for diarisation.
---

# YouTube Transcribe Skill

Transcribe YouTube videos locally using Parakeet MLX (fast, runs on Apple Silicon), then generate a summary. Optionally supports speaker diarisation via AssemblyAI when explicitly requested.

## Directory Structure

```
~/.claude/skills/youtube-transcribe/
├── audio/        # Downloaded audio files (MP3)
├── transcripts/  # Transcription files (.txt plain text, .md with speaker labels if diarised, .srt with timestamps)
├── metadata/     # Video metadata JSON (title, description, links, etc.)
└── summaries/    # Markdown summaries with chapters and timestamped quotes
```

## Prerequisites

- `yt-dlp` for downloading audio
- `ffmpeg` for audio processing
- [transcribe-audio](https://github.com/HartreeWorks/skill--transcribe-audio) skill for transcription (uses Parakeet MLX)

## Workflow

### Step 0: Ensure viewer server is running

Before starting transcription, check if the transcript viewer server is running. If not, start it as a background process:

```bash
# Check if server is running
python ~/.claude/skills/youtube-transcribe/serve.py --check

# If not running (exit code 1), start it in background
if ! python ~/.claude/skills/youtube-transcribe/serve.py --check 2>/dev/null; then
    nohup python ~/.claude/skills/youtube-transcribe/serve.py > /dev/null 2>&1 &
    echo "Started transcript viewer server at http://localhost:4322"
fi
```

### Step 1: Get video metadata and generate filename

**IMPORTANT:** Use `bash -c '...'` to avoid zsh glob pattern issues with special characters in video titles (e.g., `[SFI]`, `(2024)`, etc.).

```bash
# Extract video ID from URL
VIDEO_ID="<extracted_video_id>"

# Get title and generate filename in a single bash command to avoid zsh issues
bash -c '
VIDEO_ID="<VIDEO_ID>"
VIDEO_TITLE=$(yt-dlp --get-title "<YOUTUBE_URL>" 2>/dev/null)
DATE=$(date +%Y-%m-%d)
# Create slug from title: lowercase, replace spaces/special chars with hyphens
SLUG=$(echo "$VIDEO_TITLE" | tr "[:upper:]" "[:lower:]" | sed "s/[^a-z0-9]/-/g" | sed "s/--*/-/g" | sed "s/^-//" | sed "s/-$//")
FILENAME="${DATE}-${SLUG}-${VIDEO_ID}"
echo "FILENAME=${FILENAME}"
'
```

Then use the FILENAME value in subsequent commands.

### Step 2: Download audio and extract lean metadata

Download audio (without the bloated info.json), then extract only useful metadata fields.

**IMPORTANT:** Wrap in `bash -c '...'` to handle special characters in filenames.

```bash
bash -c '
VIDEO_ID="<VIDEO_ID>"
FILENAME="<FILENAME_FROM_STEP_1>"

# Download audio only (no --write-info-json to avoid 500KB+ files)
yt-dlp -x --audio-format mp3 \
  -o "$HOME/.claude/skills/youtube-transcribe/audio/${FILENAME}.%(ext)s" \
  "<YOUTUBE_URL>"

# Extract lean metadata (~2-5KB instead of 500KB+)
# Excludes: automatic_captions (400KB+), formats array (80KB+), thumbnails
yt-dlp --dump-json "<YOUTUBE_URL>" 2>/dev/null | jq "{
  id,
  title,
  fulltitle,
  description,
  channel,
  channel_id,
  channel_url,
  uploader,
  upload_date,
  duration,
  duration_string,
  view_count,
  like_count,
  comment_count,
  tags,
  categories,
  chapters,
  webpage_url,
  thumbnail,
  availability,
  live_status,
  was_live
}" > ~/.claude/skills/youtube-transcribe/metadata/${FILENAME}.json
'
```

The lean metadata JSON contains: title, description (with links), upload date, channel, duration, view count, tags, chapters, and audio quality info.

### Step 3: Transcribe using transcribe-audio skill

Invoke the **transcribe-audio** skill to transcribe the downloaded audio:

- **Audio file**: `~/.claude/skills/youtube-transcribe/audio/${FILENAME}.mp3`
- **Output directory**: `~/.claude/skills/youtube-transcribe/transcripts`

**Default (Parakeet):** Unless the user explicitly requests diarisation/speaker identification, use Parakeet MLX. The transcribe-audio skill will output:
- `${FILENAME}.txt` - Plain text transcript for easy reading
- `${FILENAME}.srt` - Timestamped subtitle file for generating chapters and quote timestamps

**With diarisation (AssemblyAI):** Only if the user explicitly requests speaker identification/diarisation, invoke transcribe-audio with the diarisation option. This uses AssemblyAI and outputs:
- `${FILENAME}.md` - Markdown transcript with speaker labels
- `${FILENAME}.srt` - Timestamped subtitle file

### Step 4: Read metadata for context

Read the metadata JSON to extract useful info for the summary:
- Video description (may contain links, timestamps, resources)
- Channel name
- Upload date
- Chapters (if any)

### Step 5: Generate summary with chapters and timestamps

Read the transcript (.txt or .md if diarisation was used), SRT file (.srt), and metadata, then create a markdown summary.

Save to `~/.claude/skills/youtube-transcribe/summaries/${FILENAME}.md`

**Generating Chapters:**
1. Read the SRT file to understand content timing
2. Identify 5-8 major topic shifts per hour of content
3. For each chapter, find the SRT segment where that topic begins
4. Convert the timestamp to YouTube link format: `https://youtube.com/watch?v=VIDEO_ID&t=XXs` (where XX is total seconds)

**Generating Timestamped Quotes:**
1. For each notable quote, search the SRT file to find the segment containing that text
2. Use the start time of that segment for the timestamp link

**Timestamp format:** `[MM:SS](URL)` for videos under 1 hour, `[H:MM:SS](URL)` for longer videos.

Summary template:

```markdown
# [Video Title]

**Channel:** [Channel Name]
**URL:** [YouTube URL]
**Published:** [Upload Date]
**Duration:** [Duration]
**Transcribed:** YYYY-MM-DD

## Chapters

- [00:00](https://youtube.com/watch?v=VIDEO_ID&t=0s) Introduction
- [05:23](https://youtube.com/watch?v=VIDEO_ID&t=323s) [Topic 2 title]
- [18:45](https://youtube.com/watch?v=VIDEO_ID&t=1125s) [Topic 3 title]
- [32:10](https://youtube.com/watch?v=VIDEO_ID&t=1930s) [Topic 4 title]
...

## Summary

[2-3 paragraph summary of the content]

## Key Points

- [Main point 1]
- [Main point 2]
- [Main point 3]
...

## Notable Quotes

> "[Quote 1]" — [MM:SS](https://youtube.com/watch?v=VIDEO_ID&t=XXs)

> "[Quote 2]" — [MM:SS](https://youtube.com/watch?v=VIDEO_ID&t=XXs)

## Links from Description

- [Link 1]
- [Link 2]
(Extract any URLs from the video description)
```

### Step 6: Rebuild the viewer

After creating the summary file, rebuild the viewer so the new transcript appears in the library:

```bash
python ~/.claude/skills/youtube-transcribe/viewer/build.py
```

### Step 7: Display summary in chat

**IMPORTANT:** After generating the summary, display the full markdown summary content directly in the chat response so the user can:
- Read the summary immediately
- Discuss the content
- Ask follow-up questions about the transcript

Also report file locations and the viewer URL:
- Viewer: http://localhost:4322

## File Naming Convention

All files use: `YYYY-MM-DD-video-title-slug-VIDEO_ID`

Example: `2025-12-19-never-gonna-give-you-up-dQw4w9WgXcQ`

## Notes

- First run downloads the Parakeet model (~1.2GB)
- Transcription is very fast (~300x realtime on Apple Silicon)
- English only (Parakeet is optimised for English)
- For other languages, consider using whisper-cpp instead
- **zsh compatibility**: Video titles often contain special characters like `[brackets]` or `(parentheses)` which zsh interprets as glob patterns. Always wrap commands involving video titles in `bash -c '...'` to avoid parse errors.


## Update check

This skill is managed by [skills.sh](https://skills.sh). To check for updates, run `npx skills update`.

