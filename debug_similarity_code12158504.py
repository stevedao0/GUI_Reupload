"""Debug similarity for Code 12158504"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from src.utils import get_config
from src.analysis import AudioAnalyzer, VideoAnalyzer

print("=" * 70)
print("DEBUG: Code 12158504 Similarity Check")
print("=" * 70)

# Load config
config = get_config('config.yaml')

# Load data
df = pd.read_excel('import check reup3.xlsx')
code_df = df[df['Code'] == 12158504]

print(f"\nCode 12158504 has {len(code_df)} videos:")
for _, row in code_df.iterrows():
    print(f"  STT {row['STT']}: {row['ID Video']} - Type: {row['Type']}")

# Focus on STT 15 & 17
stt15_id = 'aQwKwnaO_CE'
stt17_id = '9YOH4eGJQsU'

# Find downloaded files
temp_dir = Path('temp_downloads')
audio15 = list(temp_dir.glob(f'{stt15_id}*.mp3'))
audio17 = list(temp_dir.glob(f'{stt17_id}_2423*.mp3'))  # The one at 2423s
video15 = list(temp_dir.glob(f'{stt15_id}*.mp4'))
video17 = list(temp_dir.glob(f'{stt17_id}_2423*.mp4'))

if not audio15 or not audio17:
    print("\nERROR: Downloaded files not found!")
    print(f"Looking in: {temp_dir}")
    print(f"Audio 15 found: {audio15}")
    print(f"Audio 17 found: {audio17}")
    sys.exit(1)

audio15_path = str(audio15[0])
audio17_path = str(audio17[0])
video15_path = str(video15[0]) if video15 else None
video17_path = str(video17[0]) if video17 else None

print(f"\nFiles found:")
print(f"  STT 15 audio: {audio15_path}")
print(f"  STT 17 audio: {audio17_path}")
print(f"  STT 15 video: {video15_path}")
print(f"  STT 17 video: {video17_path}")

# Initialize analyzers
print("\nInitializing analyzers...")
audio_analyzer = AudioAnalyzer(config)
video_analyzer = VideoAnalyzer(config)

# Extract audio features
print("\nExtracting audio features...")
audio_features15 = audio_analyzer.extract_features(audio15_path)
audio_features17 = audio_analyzer.extract_features(audio17_path)

# Calculate audio similarity
audio_sim = audio_analyzer.calculate_similarity(audio_features15, audio_features17)
print(f"\nAudio similarity (STT 15 <-> STT 17): {audio_sim:.4f} ({audio_sim*100:.2f}%)")

# Extract video features if available
if video15_path and video17_path:
    print("\nExtracting video features...")
    video_features15 = video_analyzer.extract_features(video15_path)
    video_features17 = video_analyzer.extract_features(video17_path)

    # Calculate video similarity
    video_sim = video_analyzer.calculate_similarity(video_features15, video_features17)
    print(f"Video similarity (STT 15 <-> STT 17): {video_sim:.4f} ({video_sim*100:.2f}%)")

    # Calculate combined
    audio_weight = config.get('weights.audio', 0.4)
    video_weight = config.get('weights.video', 0.4)
    combined_sim = audio_weight * audio_sim + video_weight * video_sim
    print(f"\nCombined similarity: {combined_sim:.4f} ({combined_sim*100:.2f}%)")
    print(f"  = {audio_weight} * {audio_sim:.4f} + {video_weight} * {video_sim:.4f}")

    threshold = config.get('thresholds.combined_similarity', 0.72)
    print(f"\nThreshold: {threshold:.4f} ({threshold*100:.2f}%)")

    if combined_sim >= threshold:
        print(f"✓ PASS: Combined similarity {combined_sim:.4f} >= threshold {threshold:.4f}")
    else:
        print(f"✗ FAIL: Combined similarity {combined_sim:.4f} < threshold {threshold:.4f}")
        print(f"  Difference: {(threshold - combined_sim)*100:.2f}%")
else:
    print("\nVideo files not found - cannot calculate video similarity")

print("\n" + "=" * 70)
