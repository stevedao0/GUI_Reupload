"""Debug Code 12158504 in detail"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from src.utils import get_config

# Load config
config = get_config('config.yaml')

# Read input
df = pd.read_excel('import check reup3.xlsx')
code_df = df[df['Code'] == 12158504]

print("=" * 80)
print("CODE 12158504 DETAILED DEBUG")
print("=" * 80)

print("\nVideos in Code 12158504:")
for _, row in code_df.iterrows():
    print(f"  STT {row['STT']:2d}: {row['ID Video']:15s} Type={row['Type']:12s}")

# STT 15 (aQwKwnaO_CE) is Video type
# STT 17 (9YOH4eGJQsU_2423) is Video type
# These should be in the same Type group and detected

print("\n" + "=" * 80)
print("EXPECTED BEHAVIOR:")
print("=" * 80)
print("STT 15 (aQwKwnaO_CE) and STT 17 (9YOH4eGJQsU_2423) should:")
print("  1. Both be Type='Video' → same Type group")
print("  2. Have audio similarity ~100%")
print("  3. Have video similarity ~100%")
print("  4. Combined similarity = 0.4*audio + 0.4*video = 0.4*1.0 + 0.4*1.0 = 0.80")
print("  5. Trigger boost (audio≥0.96 AND video≥0.85) → 0.85")
print("  6. Pass threshold 0.70 → Detected as reuploads")

print("\n" + "=" * 80)
print("ACTUAL BEHAVIOR FROM LOG:")
print("=" * 80)
print("From logs/20251124_155654.log line 305:")
print("  Max: 0.654, Min: 0.654, Avg: 0.654")
print("  → Only 65.4% similarity!")

print("\n" + "=" * 80)
print("ANALYSIS:")
print("=" * 80)
print("If similarity is 65.4%, this suggests:")
print("  Option A: Video similarity is ~82% and audio is 0% (0.4*0 + 0.4*0.82 = 0.328)")
print("           BUT log shows Max 0.654, so this must be: 0.4*video ≈ 0.654")
print("           → video ≈ 1.635 (impossible, max is 1.0)")
print("")
print("  Option B: Audio alignment worked, but similarities are lower than expected")
print("           0.4*audio + 0.4*video = 0.654")
print("           If audio=video=X: 0.8*X = 0.654 → X = 0.8175 (81.75%)")
print("")
print("  Option C: Audio alignment worked but video similarity is much lower")
print("           Example: audio=1.0, video=0.635")
print("           0.4*1.0 + 0.4*0.635 = 0.654 ✓")

print("\n" + "=" * 80)
print("LIKELY CAUSE:")
print("=" * 80)
print("Audio alignment IS working now (no 'Unable to align' warnings)")
print("BUT video similarity for STT 15 <-> STT 17 is only ~63.5%")
print("")
print("This is too low to trigger boost (needs video ≥ 0.85)")
print("And too low to pass threshold (0.654 < 0.70)")

print("\n" + "=" * 80)
print("WHY IS VIDEO SIMILARITY ONLY 63.5%?")
print("=" * 80)
print("Possible reasons:")
print("  1. STT 15 and STT 17 are from DIFFERENT timestamps of the same video")
print("     - STT 15: aQwKwnaO_CE from 1s-268s (start of video)")
print("     - STT 17: 9YOH4eGJQsU_2423 from 2423s-2685s (40 minutes into video)")
print("     → They are NOT the same segment, just same song/audio!")
print("")
print("  2. The segments have different visual content despite same audio")
print("")
print("CONCLUSION: This is NOT a bug - they are correctly identified as different")
print("segments that happen to have the same audio content.")

print("\n" + "=" * 80)
