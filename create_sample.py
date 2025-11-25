import pandas as pd

# Tạo sample chỉ với Code 12158504
df = pd.read_excel('import check reup3.xlsx')
sample = df[df['Code'] == 12158504].copy()

# Lưu ra file mới
sample.to_excel('sample_code12158504.xlsx', index=False)
print(f"Created sample_code12158504.xlsx with {len(sample)} videos")
print("\nVideos in sample:")
for _, row in sample.iterrows():
    print(f"  STT {row['STT']:2d}: {row['ID Video']:15s} Type={row['Type']:12s}")
