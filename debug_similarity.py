"""Debug script to check actual similarity scores"""
import numpy as np
import pandas as pd
from pathlib import Path

# Read the latest exported results if available
# Or we can add debug output to the pipeline

# For now, let's add detailed logging to the detection step

print("=" * 80)
print("SIMILARITY DEBUG HELPER")
print("=" * 80)
print()
print("Để debug similarity scores:")
print()
print("1. Kiểm tra logs trong GUI tab 'Logs'")
print("2. Tìm các dòng:")
print("   - 'Audio similarity: X.XXX'")
print("   - 'Video similarity: CLIP=X.XXX, Enhanced=X.XXX, Final=X.XXX'")
print()
print("3. Kiểm tra sheet 'Detailed Comparisons' trong Excel output")
print("   - Xem similarity scores cho từng cặp")
print("   - Sorted by similarity cao → thấp")
print()
print("4. Kiểm tra sheet 'Similarity Matrix'")
print("   - Ma trận NxN với scores")
print()
print("=" * 80)
print()
print("Expected scores cho videos giống nhau:")
print("  - Audio: > 0.75 (threshold)")
print("  - Video: > 0.85 (threshold)")
print("  - Combined: > 0.80 (threshold chính)")
print()
print("Nếu scores < threshold:")
print("  → Cần giảm threshold HOẶC")
print("  → Segments khác nhau quá nhiều")
print("=" * 80)

