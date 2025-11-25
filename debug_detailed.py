"""Debug script to check audio and video similarities in detail"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from src.utils import get_config
from src.analysis import AudioAnalyzer, VideoAnalyzer

print("=" * 80)
print("DETAILED DEBUG - Code 12158504")
print("=" * 80)

# Load config
config = get_config('config.yaml')
print("\nThresholds from config:")
print(f"  audio_threshold: {config.get('thresholds.audio_similarity')}")
print(f"  video_threshold: {config.get('thresholds.video_similarity')}")
print(f"  combined_threshold: {config.get('thresholds.combined_similarity')}")

# Initialize analyzers
audio_analyzer = AudioAnalyzer(config)
video_analyzer = VideoAnalyzer(config)

# Define the 2 videos we want to compare (STT 15 & 17)
video_ids = {
    15: ('aQwKwnaO_CE', '1s', '268s'),
    17: ('9YOH4eGJQsU', '2423s', '2685s')
}

print("\n" + "=" * 80)
print("CHECKING DOWNLOADED FILES")
print("=" * 80)

temp_dir = Path('temp_downloads')
audio_dir = temp_dir / 'audios'
video_dir = temp_dir / 'videos'

files_found = {}
for stt, (video_id, start, end) in video_ids.items():
    # Tìm files dựa trên video_id
    audio_files = list(audio_dir.glob(f'{video_id}*.mp3'))
    video_files = list(video_dir.glob(f'{video_id}*.mp4'))

    print(f"\nSTT {stt} ({video_id}):")
    print(f"  Audio files: {[f.name for f in audio_files]}")
    print(f"  Video files: {[f.name for f in video_files]}")

    if audio_files and video_files:
        files_found[stt] = {
            'audio': str(audio_files[0]),
            'video': str(video_files[0])
        }

if len(files_found) < 2:
    print("\nERROR: Not enough files found! Need both STT 15 and 17.")
    print("Please run the main program first to download the files.")
    sys.exit(1)

print("\n" + "=" * 80)
print("EXTRACTING FEATURES")
print("=" * 80)

features = {}
for stt in [15, 17]:
    print(f"\nSTT {stt}:")
    audio_path = files_found[stt]['audio']
    video_path = files_found[stt]['video']

    print(f"  Extracting audio features from: {Path(audio_path).name}")
    audio_feat = audio_analyzer.extract_features(audio_path)

    print(f"  Extracting video features from: {Path(video_path).name}")
    video_feat = video_analyzer.extract_features(video_path)

    features[stt] = {
        'audio': audio_feat,
        'video': video_feat
    }

print("\n" + "=" * 80)
print("CALCULATING SIMILARITIES")
print("=" * 80)

# Calculate audio similarity
audio_sim = audio_analyzer.compare_features(
    features[15]['audio'],
    features[17]['audio']
)

# Calculate video similarity
video_sim = video_analyzer.compare_features(
    features[15]['video'],
    features[17]['video']
)

# Calculate combined
audio_weight = config.get('weights.audio', 0.4)
video_weight = config.get('weights.video', 0.4)
combined_sim = audio_weight * audio_sim + video_weight * video_sim

print(f"\nSTT 15 <-> STT 17:")
print(f"  Audio similarity:    {audio_sim:.4f} ({audio_sim*100:.2f}%)")
print(f"  Video similarity:    {video_sim:.4f} ({video_sim*100:.2f}%)")
print(f"  Combined similarity: {combined_sim:.4f} ({combined_sim*100:.2f}%)")
print(f"    = {audio_weight} * {audio_sim:.4f} + {video_weight} * {video_sim:.4f}")

print("\n" + "=" * 80)
print("CHECKING AGAINST THRESHOLDS")
print("=" * 80)

audio_threshold = config.get('thresholds.audio_similarity')
video_threshold = config.get('thresholds.video_similarity')
combined_threshold = config.get('thresholds.combined_similarity')

print(f"\nAudio check:")
print(f"  {audio_sim:.4f} >= {audio_threshold:.4f}? ", end="")
if audio_sim >= audio_threshold:
    print("YES")
else:
    print(f"NO (need {(audio_threshold - audio_sim)*100:.2f}% more)")

print(f"\nVideo check:")
print(f"  {video_sim:.4f} >= {video_threshold:.4f}? ", end="")
if video_sim >= video_threshold:
    print("YES")
else:
    print(f"NO (need {(video_threshold - video_sim)*100:.2f}% more)")

print(f"\nStrict gating (BOTH must pass):")
if audio_sim >= audio_threshold and video_sim >= video_threshold:
    print("  PASS - Both audio and video meet thresholds")
    print(f"  Combined: {combined_sim:.4f} >= {combined_threshold:.4f}? ", end="")
    if combined_sim >= combined_threshold:
        print("YES - Would be detected as reupload")
    else:
        print(f"NO - Need {(combined_threshold - combined_sim)*100:.2f}% more")
else:
    print("  REJECT - At least one modality below threshold")
    print("  This pair will NOT be detected as reupload")

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)

if audio_sim >= audio_threshold and video_sim >= video_threshold and combined_sim >= combined_threshold:
    print("\nResult: SHOULD BE DETECTED as reupload")
    print("If not detected, there may be a bug in the code.")
elif audio_sim < audio_threshold:
    print("\nResult: NOT DETECTED - Audio similarity too low")
    print(f"Audio is only {audio_sim*100:.1f}% but needs {audio_threshold*100:.1f}%")
elif video_sim < video_threshold:
    print("\nResult: NOT DETECTED - Video similarity too low")
    print(f"Video is only {video_sim*100:.1f}% but needs {video_threshold*100:.1f}%")
    print("\nThis suggests STT 15 and 17 have different visual content,")
    print("even though they may have similar/same audio.")
else:
    print("\nResult: NOT DETECTED - Combined similarity too low")
    print(f"Combined is {combined_sim*100:.1f}% but needs {combined_threshold*100:.1f}%")

print("\n" + "=" * 80)
