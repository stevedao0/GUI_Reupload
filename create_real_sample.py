"""Create sample Excel file matching user's format"""
import pandas as pd

# Sample data matching user's format
data = {
    'STT': [1, 2, 3, 4, 5, 6],
    'ID Video': [
        'IE5iS4grmOI',
        'xQJJnE1hSeU',
        'LwzWyXlKA74',
        'WEzYeWILPig',
        'eUIJbQvt5B4',
        'Ax0FrAwNeAw'
    ],
    'Link YouTube Timestamp': [
        'https://www.youtube.com/watch?v=IE5iS4grmOI&t=230s',
        'https://www.youtube.com/watch?v=xQJJnE1hSeU&t=398s',
        'https://www.youtube.com/watch?v=LwzWyXlKA74&t=830s',
        'https://www.youtube.com/watch?v=WEzYeWILPig&t=1530s',
        'https://www.youtube.com/watch?v=eUIJbQvt5B4&t=0s',
        'https://www.youtube.com/watch?v=Ax0FrAwNeAw&t=1980s'
    ],
    'Thoi gian': [
        '00:03:50 - 00:08:16',
        '00:06:38 - 00:10:52',
        '00:13:50 - 00:18:10',
        '00:25:30 - 00:29:30',
        '00:00:00 - 00:04:29',
        '00:33:00 - 00:37:10'
    ],
    'Type': [
        'Video',
        'Video',
        'Video',
        'Audio',
        'Audio',
        'Audio'
    ]
}

# Create DataFrame
df = pd.DataFrame(data)

# Save to Excel
output_file = 'sample_input.xlsx'
df.to_excel(output_file, index=False, engine='openpyxl')

print(f"Sample Excel file created: {output_file}")
print(f"Number of videos: {len(df)}")
print("\nColumns:")
for col in df.columns:
    print(f"  - {col}")
print("\nFile is ready to use with the application!")

