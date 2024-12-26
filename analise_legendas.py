import os
import re
import chardet
from datetime import timedelta
from colorama import Fore, init, Back, Style
from typing import Dict, List, Tuple
import pandas as pd
from tabulate import tabulate

init(autoreset=True)

def detect_encoding(file_path: str) -> str:
    """Detect the encoding of the file."""
    with open(file_path, 'rb') as file:
        raw_data = file.read()
    result = chardet.detect(raw_data)
    if result:
        return result['encoding']
    else:
        return 'not found'

def parse_time(timestamp: str) -> timedelta:
    """Convert SRT timestamp to timedelta."""
    hours, minutes, seconds = map(int, timestamp[:8].split(':'))
    milliseconds = int(timestamp[9:12])
    return timedelta(hours=hours, minutes=minutes, seconds=seconds, milliseconds=milliseconds)

def format_timedelta(td: timedelta) -> str:
    """Format timedelta to string in HH:MM:SS,mmm format."""
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    milliseconds = td.microseconds // 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

def clean_text(text: str) -> str:
    """Remove HTML tags and special formatting codes."""
    text = re.sub(r'<.*?>', '', text)
    text = re.sub(r'\{.*?\}', '', text)
    text = re.sub(r'\\[a-zA-Z]+\b', '', text)
    return text.strip()

def parse_srt(file_path: str) -> List[Tuple]:
    """Parse an SRT file and return subtitle information."""
    try:
        encoding = detect_encoding(file_path)
        with open(file_path, 'r', encoding=encoding) as file:
            content = file.read()
        
        blocks = content.strip().split('\n\n')
        subtitles = []
        
        for block in blocks:
            lines = block.split('\n')
            if len(lines) < 3:
                continue
            
            time_match = re.match(r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})", lines[1])
            if not time_match:
                continue

            start_time = parse_time(time_match.group(1))
            end_time = parse_time(time_match.group(2))
            text_lines = lines[2:]
            subtitles.append((start_time, end_time, text_lines, int(lines[0]), encoding))
        
        return subtitles
    except Exception as e:
        print(f"{Fore.RED}Error processing file {file_path}: {str(e)}")
        return []

def analyze_subtitle_file(file_path: str) -> Dict:
    """Analyze a single subtitle file and return statistics."""
    subtitles = parse_srt(file_path)
    if not subtitles:
        return None

    # Basic statistics
    num_lines = len(subtitles)
    start_time = subtitles[0][0] if subtitles else timedelta(0)
    end_time = subtitles[-1][1] if subtitles else timedelta(0)
    total_duration = end_time - start_time
    total_display_time = sum((end - start for start, end, _, _, _ in subtitles), timedelta(0))
    total_silence = total_duration - total_display_time
    
    # Calculate text statistics
    total_words = sum(len(clean_text(line).split()) for _, _, text_lines, _, _ in subtitles for line in text_lines)
    total_chars = sum(len(clean_text(line)) for _, _, text_lines, _, _ in subtitles for line in text_lines)
    
    # Line distribution
    line_counts = [len([line for line in s[2] if clean_text(line)]) for s in subtitles]
    single_lines = sum(1 for x in line_counts if x == 1)
    double_lines = sum(1 for x in line_counts if x == 2)
    triple_plus_lines = sum(1 for x in line_counts if x >= 3)
    
    # Duration analysis
    durations = [(end - start).total_seconds() for start, end, _, _, _ in subtitles]
    avg_duration = sum(durations) / len(durations) if durations else 0
    
    # Overlap detection
    overlaps = 0
    for i in range(len(subtitles) - 1):
        if subtitles[i][1] > subtitles[i + 1][0]:
            overlaps += 1
    
    return {
        'filename': os.path.basename(file_path),
        'num_lines': num_lines,
        'duration': format_timedelta(total_duration),
        'display_time': format_timedelta(total_display_time),
        'silence_time': format_timedelta(total_silence),
        'display_percentage': (total_display_time.total_seconds() / total_duration.total_seconds() * 100) if total_duration.total_seconds() > 0 else 0,
        'total_words': total_words,
        'total_chars': total_chars,
        'words_per_line': total_words / num_lines if num_lines > 0 else 0,
        'chars_per_line': total_chars / num_lines if num_lines > 0 else 0,
        'words_per_second': total_words / total_display_time.total_seconds() if total_display_time.total_seconds() > 0 else 0,
        'single_lines': single_lines,
        'double_lines': double_lines,
        'triple_plus_lines': triple_plus_lines,
        'avg_duration': avg_duration,
        'overlaps': overlaps,
        'encoding': subtitles[0][4] if subtitles else "Unknown"
    }

def analyze_directory(directory_path: str) -> None:
    """Analyze all SRT files in the given directory with enhanced comparative statistics."""
    srt_files = [f for f in os.listdir(directory_path) if f.lower().endswith('.srt')]
    
    if not srt_files:
        print(f"{Fore.RED}No SRT files found in the directory!")
        return
    
    results = []
    for file in srt_files:
        file_path = os.path.join(directory_path, file)
        stats = analyze_subtitle_file(file_path)
        if stats:
            results.append(stats)
    
    if not results:
        print(f"{Fore.RED}No valid subtitle files could be processed!")
        return
    
    df = pd.DataFrame(results)
    
    # Enhanced Comparative Statistics
    print(f"\n{Fore.GREEN}=== Detailed Comparative Analysis ===\n")
    
    # 1. Basic File Statistics
    print(f"{Fore.YELLOW}Basic File Statistics:")
    basic_stats = {
        'Total Files Analyzed': len(results),
        'Total Combined Lines': df['num_lines'].sum(),
        'Average Lines per File': df['num_lines'].mean(),
    }
    print(tabulate([[k, f"{v:,.2f}"] for k, v in basic_stats.items()], tablefmt='simple'))

    # 2. Timing Analysis
    print(f"\n{Fore.YELLOW}Timing Analysis:")
    timing_stats = {
        'Average Display Time %': df['display_percentage'].mean(),
        'Average Line Duration (seconds)': df['avg_duration'].mean(),
        'Shortest Line Duration (seconds)': df['avg_duration'].min(),
        'Longest Line Duration (seconds)': df['avg_duration'].max()
    }
    print(tabulate([[k, f"{v:,.2f}"] for k, v in timing_stats.items()], tablefmt='simple'))

    # 3. Reading Speed Analysis
    print(f"\n{Fore.YELLOW}Reading Speed Analysis:")
    reading_stats = {
        'Average Words per Second': df['words_per_second'].mean(),
        'Fastest Reading Speed': df['words_per_second'].max(),
        'Slowest Reading Speed': df['words_per_second'].min(),
    }
    print(tabulate([[k, f"{v:,.2f}"] for k, v in reading_stats.items()], tablefmt='simple'))

    # 4. Text Structure Analysis
    print(f"\n{Fore.YELLOW}Text Structure Analysis:")
    structure_stats = {
        'Average Words per Line': df['words_per_line'].mean(),
        'Average Characters per Line': df['chars_per_line'].mean(),
        'Single-Line Subtitles %': (df['single_lines'].sum() / df['num_lines'].sum() * 100),
        'Double-Line Subtitles %': (df['double_lines'].sum() / df['num_lines'].sum() * 100),
        'Triple+ Line Subtitles %': (df['triple_plus_lines'].sum() / df['num_lines'].sum() * 100)
    }
    print(tabulate([[k, f"{v:,.2f}"] for k, v in structure_stats.items()], tablefmt='simple'))

    # 5. Quality Metrics
    print(f"\n{Fore.YELLOW}Quality Metrics:")
    quality_stats = {
        'Total Overlaps Found': df['overlaps'].sum(),
        'Average Overlaps per File': df['overlaps'].mean(),
        'Files with Overlaps': len(results) - len(df[df['overlaps'] == 0]),
        'Files with Zero Overlaps': len(df[df['overlaps'] == 0]),
    }
    print(tabulate([[k, f"{v:,.2f}"] for k, v in quality_stats.items()], tablefmt='simple'))

    # 6. File Rankings
    print(f"\n{Fore.YELLOW}Notable Files:")
    rankings = {
        'Longest File': f"{df.iloc[df['num_lines'].idxmax()]['filename']} {Fore.BLUE}({int(df.iloc[df['num_lines'].idxmax()]['num_lines'])} lines){Style.RESET_ALL}",
        'Shortest File': f"{df.iloc[df['num_lines'].idxmin()]['filename']} {Fore.BLUE}({int(df.iloc[df['num_lines'].idxmin()]['num_lines'])} lines){Style.RESET_ALL}",
        'Fastest Reading Speed': f"{df.iloc[df['words_per_second'].idxmax()]['filename']} {Fore.BLUE}({df.iloc[df['words_per_second'].idxmax()]['words_per_second']:.1f} w/s){Style.RESET_ALL}",
        'Slowest Reading Speed': f"{df.iloc[df['words_per_second'].idxmin()]['filename']} {Fore.BLUE}({df.iloc[df['words_per_second'].idxmin()]['words_per_second']:.1f} w/s){Style.RESET_ALL}",
        'Most Overlaps': f"{df.iloc[df['overlaps'].idxmax()]['filename']} {Fore.BLUE}({int(df.iloc[df['overlaps'].idxmax()]['overlaps'])} overlaps){Style.RESET_ALL}"
    }
    print(tabulate([[k, v] for k, v in rankings.items()], tablefmt='simple'))

    # 7. Encoding Analysis
    print(f"\n{Fore.YELLOW}Encoding Distribution:")
    encoding_dist = df['encoding'].value_counts()
    print(tabulate([[encoding, count] for encoding, count in encoding_dist.items()], 
                  headers=['Encoding', 'Count'], 
                  tablefmt='simple'))
def main():
    print(f"{Fore.CYAN}Multiple Subtitle File Analyzer\n")
    directory = input("Enter the directory path containing SRT files: ").strip()
    
    if not os.path.exists(directory):
        print(f"{Fore.RED}Directory not found!")
        return
    
    analyze_directory(directory)

if __name__ == "__main__":
    main()