import re
from datetime import timedelta
from colorama import Fore, init, Back, Style

init(autoreset=True)

def parse_srt(file_path):
    """Parse an SRT file and return a list of subtitles with start time, end time, and text."""
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Split subtitles by blocks
    blocks = content.strip().split('\n\n')
    subtitles = []
    
    for block in blocks:
        lines = block.split('\n')
        if len(lines) < 3:
            continue
        
        # Extract times and text
        time_match = re.match(r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})", lines[1])
        if not time_match:
            continue

        start_time = parse_time(time_match.group(1))
        end_time = parse_time(time_match.group(2))
        text_lines = lines[2:]  # Each line of text is treated separately
        subtitles.append((start_time, end_time, text_lines, int(lines[0])))
    return subtitles

def parse_time(timestamp):
    """Convert SRT timestamp to timedelta."""
    hours, minutes, seconds = map(int, timestamp[:8].split(':'))
    milliseconds = int(timestamp[9:12])
    return timedelta(hours=hours, minutes=minutes, seconds=seconds, milliseconds=milliseconds)

def clean_text(text):
    """Remove non-printable characters such as HTML tags and special formatting codes."""
    # Remove HTML tags
    text = re.sub(r'<.*?>', '', text)
    # Remove additional non-printable characters or codes
    text = re.sub(r'\{.*?\}', '', text)  # Example: formatting like {\an8}
    text = re.sub(r'\\[a-zA-Z]+\b', '', text)  # Other formatting codes like \N
    return text.strip()

def calculate_statistics(subtitles):
    """Calculate statistics from the subtitles."""
    num_lines = len(subtitles)
    total_duration = subtitles[-1][1] if subtitles else timedelta(0)
    total_display_time = sum((end - start for start, end, _, _ in subtitles), timedelta(0))

    total_words = sum(len(clean_text(line).split()) for _, _, text_lines, _ in subtitles for line in text_lines)
    total_characters = sum(len(clean_text(line)) for _, _, text_lines, _ in subtitles for line in text_lines)
    avg_words_per_line = total_words / num_lines if num_lines > 0 else 0
    avg_chars_per_line = total_characters / num_lines if num_lines > 0 else 0

    durations = [end - start for start, end, _, _ in subtitles]
    avg_duration = sum(durations, timedelta(0)) / num_lines if num_lines > 0 else timedelta(0)
    min_duration = min(durations, default=timedelta(0))
    max_duration = max(durations, default=timedelta(0))

    reading_rate_words = total_words / total_display_time.total_seconds() if total_display_time.total_seconds() > 0 else 0
    reading_rate_chars = total_characters / total_display_time.total_seconds() if total_display_time.total_seconds() > 0 else 0

    longest_line = max((line for _, _, text_lines, _ in subtitles for line in text_lines), key=lambda x: len(clean_text(x)), default="")
    max_chars_line = max((line for _, _, text_lines, _ in subtitles for line in text_lines), key=lambda x: len(clean_text(x)), default="")

    # Modified to only include unique subtitle numbers
    lines_with_more_than_40_chars = set()  # Using a set to store unique line numbers
    line_contents = []  # Store line contents for display
    for _, _, text_lines, line_num in subtitles:
        if any(len(clean_text(line)) > 40 for line in text_lines):
            lines_with_more_than_40_chars.add(line_num)
            line_contents.append((line_num, [clean_text(l) for l in text_lines if clean_text(l)]))

    overlaps = []
    for i in range(len(subtitles) - 1):
        if subtitles[i][1] > subtitles[i + 1][0]:
            overlaps.append((subtitles[i], subtitles[i + 1]))

    return {
        "num_lines": num_lines,
        "total_duration": total_duration,
        "total_display_time": total_display_time,
        "total_words": total_words,
        "total_characters": total_characters,
        "avg_words_per_line": avg_words_per_line,
        "avg_chars_per_line": avg_chars_per_line,
        "avg_duration": avg_duration,
        "min_duration": min_duration,
        "max_duration": max_duration,
        "reading_rate_words": reading_rate_words,
        "reading_rate_chars": reading_rate_chars,
        "longest_line": longest_line,
        "max_chars_line": max_chars_line,
        "lines_with_more_than_40_chars": (lines_with_more_than_40_chars, line_contents),
        "overlaps": overlaps,
    }

def main():
    file_path = input("Enter the path to the SRT file: ").strip()
    subtitles = parse_srt(file_path)
    stats = calculate_statistics(subtitles)

    print("\nSUBTITLE STATISTICS:\n")
    print(f"Number of lines: {Fore.BLUE}{stats['num_lines']}")
    print(f"Subtitle ends at: {Fore.BLUE}{stats['total_duration']}")
    print(f"Total subtitle display time: {Fore.BLUE}{stats['total_display_time']}")
    print()
    print(f"Total of words: {Fore.BLUE}{stats['total_words']}")
    print(f"Total of characters: {Fore.BLUE}{stats['total_characters']}")
    print()
    print(f"Average words per line: {Fore.BLUE}{stats['avg_words_per_line']:.2f}")
    print(f"Average characters per line: {Fore.BLUE}{stats['avg_chars_per_line']:.2f}")
    print(f"Average duration per line: {Fore.BLUE}{stats['avg_duration']}")
    print()
    print(f"Shortest line duration: {Fore.BLUE}{stats['min_duration']}")
    print(f"Longest line duration: {Fore.BLUE}{stats['max_duration']}")
    print()
    print(f"Reading rate (words/sec): {Fore.BLUE}{stats['reading_rate_words']:.2f}")
    print(f"Reading rate (characters/sec): {Fore.BLUE}{stats['reading_rate_chars']:.2f}")
    print()
    print(f"Maximum characters in a line: {Fore.BLUE}{len(clean_text(stats['max_chars_line']))}")
    print(f"Longest line: {Fore.BLUE}{clean_text(stats['longest_line'])}")

    long_lines_set, line_contents = stats['lines_with_more_than_40_chars']
    if line_contents:
        print("\n-------------------------------")
        print(f"\n{Fore.YELLOW}LINES{Style.RESET_ALL} WITH MORE THAN 40 {Fore.GREEN}CHARACTERS{Style.RESET_ALL}:\n")
        for line_num, text_lines in line_contents:
            print(f"{Fore.YELLOW}({line_num})\t{Style.RESET_ALL}", end=" ")
            first_line = True
            for line in text_lines:
                if not first_line:
                    print("\t ", end="")
                print(f"{line} {Fore.GREEN}({len(line)})")
                first_line = False
            print()
        print(f"Total of lines with more than 40 characters: {Fore.BLUE}{len(long_lines_set)}")

    if stats['overlaps']:
        print("-------------------------------")
        print("\nOVERLAPPING LINES DETECTED:\n")
        counter = 0
        for overlap in stats['overlaps']:
            for part in overlap:
                print(f"{Fore.RED}Line ({part[3]}):")
                for text_line in part[2]:
                    print(f"  {clean_text(text_line)} {Fore.GREEN}({len(clean_text(text_line))})")
            counter += 1
            print()
        print(f"Total of overlaps: {Fore.BLUE}{counter}\n")
    else:
        print("-------------------------------")
        print("No overlapping lines detected.")

if __name__ == "__main__":
    main()