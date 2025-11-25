"""Create sample input Excel file"""
import pandas as pd

# Sample data
data = {
    'URL': [
        'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        'https://www.youtube.com/watch?v=9bZkp7q19f0',
        'https://www.youtube.com/watch?v=kJQP7kiw5Fk',
        'https://www.youtube.com/watch?v=fJ9rUzIMcZQ',
        'https://www.youtube.com/watch?v=YQHsXMglC9A',
    ],
    'Hình thức sử dụng': [
        'Audio',
        'Video',
        'Midi Karaoke',
        'MV Karaoke',
        'Video',
    ],
    'Ghi chú': [
        'Ví dụ audio với hình tĩnh',
        'Ví dụ MV có người',
        'Ví dụ karaoke chữ chạy, hình tĩnh',
        'Ví dụ MV karaoke có người + chữ',
        'Ví dụ video ca nhạc',
    ]
}

# Create DataFrame
df = pd.DataFrame(data)

# Save to Excel
output_file = 'sample_input.xlsx'
df.to_excel(output_file, index=False, engine='openpyxl')

print(f"[OK] Sample Excel file created: {output_file}")
print(f"  {len(df)} sample URLs included")
print()
print("File structure:")
print(df.to_string(index=False))

