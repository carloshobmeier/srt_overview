import re
import chardet
from datetime import timedelta
from colorama import Fore, init, Back, Style

init(autoreset=True)

def detect_encoding(file_path):
    """Detect the encoding of the file."""
    with open(file_path, 'rb') as file:
        raw_data = file.read()
    result = chardet.detect(raw_data)
    return result['encoding']

def parse_srt(file_path):
    """Parse an SRT file and return a list of subtitles with start time, end time, and text."""
    encoding = detect_encoding(file_path)
    with open(file_path, 'r', encoding=encoding) as file:
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
        subtitles.append((start_time, end_time, text_lines, int(lines[0]), encoding))
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

def format_timedelta(td):
    """Formata um timedelta para string no formato HH:MM:SS,mmm"""
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    milliseconds = td.microseconds // 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

def calculate_statistics(subtitles):
    """Calculate statistics from the subtitles."""
    num_lines = len(subtitles)
    start_time = subtitles[0][0] if subtitles else timedelta(0)  # Get the first subtitle's start time
    total_duration = subtitles[-1][1] if subtitles else timedelta(0)
    total_display_time = sum((end - start for start, end, _, _, _ in subtitles), timedelta(0))
    
    # Calculate total time without subtitles
    total_time_without_subtitles = total_duration - total_display_time
    
    # Calculate percentages
    total_seconds = total_duration.total_seconds()
    display_percentage = (total_display_time.total_seconds() / total_seconds * 100) if total_seconds > 0 else 0
    without_subtitles_percentage = (total_time_without_subtitles.total_seconds() / total_seconds * 100) if total_seconds > 0 else 0

    # Line count statistics
    single_lines = []
    double_lines = []
    triple_lines = []
    quadruple_lines = []
    
    for subtitle in subtitles:
        text_lines = [line for line in subtitle[2] if clean_text(line)]
        num_text_lines = len(text_lines)
        if num_text_lines == 1:
            single_lines.append(subtitle[3])
        elif num_text_lines == 2:
            double_lines.append(subtitle[3])
        elif num_text_lines == 3:
            triple_lines.append(subtitle[3])
        elif num_text_lines >= 4:
            quadruple_lines.append(subtitle[3])

    total_words = sum(len(clean_text(line).split()) for _, _, text_lines, _, _ in subtitles for line in text_lines)
    total_characters = sum(len(clean_text(line)) for _, _, text_lines, _, _ in subtitles for line in text_lines)
    avg_words_per_line = total_words / num_lines if num_lines > 0 else 0
    avg_chars_per_line = total_characters / num_lines if num_lines > 0 else 0

    durations = [end - start for start, end, _, _, _ in subtitles]
    avg_duration = sum(durations, timedelta(0)) / num_lines if num_lines > 0 else timedelta(0)
    min_duration = min(durations, default=timedelta(0))
    max_duration = max(durations, default=timedelta(0))

    reading_rate_words = total_words / total_display_time.total_seconds() if total_display_time.total_seconds() > 0 else 0
    reading_rate_chars = total_characters / total_display_time.total_seconds() if total_display_time.total_seconds() > 0 else 0

    # Find longest line and similar length lines
    all_lines = [(subtitle[3], line) for subtitle in subtitles for line in subtitle[2]]
    longest_length = max(len(clean_text(line)) for _, line in all_lines)
    longest_lines = [(num, line) for num, line in all_lines if len(clean_text(line)) == longest_length]
    
    longest_line = longest_lines[0][1] if longest_lines else ""
    max_chars_line = longest_line

    # Modified to only include unique subtitle numbers
    lines_with_more_than_42_chars = set()  # Using a set to store unique line numbers
    line_contents = []  # Store line contents for display
    for _, _, text_lines, line_num, _ in subtitles:
        if any(len(clean_text(line)) > 42 for line in text_lines):
            lines_with_more_than_42_chars.add(line_num)
            line_contents.append((line_num, [clean_text(l) for l in text_lines if clean_text(l)]))

    # Detectar legendas com menos de 0,9 segundos
    short_duration_lines = []
    one_second = timedelta(seconds=0.9)
    for subtitle in subtitles:
        duration = subtitle[1] - subtitle[0]
        if duration < one_second:
            short_duration_lines.append({
                'number': subtitle[3],
                'start': subtitle[0],
                'end': subtitle[1],
                'duration': duration,
                'text': subtitle[2]
            })

    overlaps = []
    for i in range(len(subtitles) - 1):
        if subtitles[i][1] > subtitles[i + 1][0]:
            # Calcular o tempo de overlap
            overlap_start = subtitles[i + 1][0]
            overlap_end = min(subtitles[i][1], subtitles[i + 1][1])
            overlap_duration = overlap_end - overlap_start
            overlaps.append((
                (subtitles[i], subtitles[i][0], subtitles[i][1]),  # Primeira legenda com seus tempos
                (subtitles[i + 1], subtitles[i + 1][0], subtitles[i + 1][1]),  # Segunda legenda com seus tempos
                overlap_duration  # Duração do overlap
            ))

    encoding = subtitles[0][4] if subtitles else "Unknown"

    return {
        "num_lines": num_lines,
        "start_time": start_time,  # Added start time
        "total_duration": total_duration,
        "total_display_time": total_display_time,
        "total_time_without_subtitles": total_time_without_subtitles,  # Added time without subtitles
        "display_percentage": display_percentage,  # Added display percentage
        "without_subtitles_percentage": without_subtitles_percentage,  # Added without subtitles percentage
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
        "lines_with_more_than_42_chars": (lines_with_more_than_42_chars, line_contents),
        "overlaps": overlaps,
        "short_duration_lines": short_duration_lines,
        "single_lines": single_lines,
        "double_lines": double_lines,
        "triple_lines": triple_lines,
        "quadruple_lines": quadruple_lines,
        "longest_lines": longest_lines,
        "encoding": encoding
    }

def main():
    file_path = input("Enter the path to the SRT file: ").strip()
    subtitles = parse_srt(file_path)
    stats = calculate_statistics(subtitles)

    print("\n====================")
    print("SUBTITLE STATISTICS:")
    print("====================\n")

    print(f"File encoding: {Fore.BLUE}{stats['encoding']}")
    print()
    print(f"Number of lines: {Fore.BLUE}{stats['num_lines']}")
    print()
    print(f"Subtitles starts at: {Fore.BLUE}{format_timedelta(stats['start_time'])}")
    print(f"Subtitle ends at:    {Fore.BLUE}{format_timedelta(stats['total_duration'])}")
    print()
    print(f"Total subtitle display time:  {Fore.BLUE}{format_timedelta(stats['total_display_time'])}  {Fore.CYAN}({stats['display_percentage']:.1f}%)")
    print(f"Total time without subtitles: {Fore.BLUE}{format_timedelta(stats['total_time_without_subtitles'])}  {Fore.CYAN}({stats['without_subtitles_percentage']:.1f}%)")
    print()
    print(f"Single lines: {Fore.BLUE}{len(stats['single_lines'])}")
    print(f"Double lines: {Fore.BLUE}{len(stats['double_lines'])}")
    print(f"Triple lines: {Fore.BLUE}{len(stats['triple_lines'])}")
    print(f"Quadruple+ lines: {Fore.BLUE}{len(stats['quadruple_lines'])}")
    print()
    if stats['triple_lines']:
        print(f"Triple line numbers:")
        for num in stats['triple_lines']:
            print(f"  - Line {Fore.BLUE}{num}")
    if stats['quadruple_lines']:
        print(f"Quadruple or more line numbers:")
        for num in stats['quadruple_lines']:
            print(f"  - Line {Fore.BLUE}{num}")
    print()
    print(f"Total of words: {Fore.BLUE}{stats['total_words']}")
    print(f"Total of characters: {Fore.BLUE}{stats['total_characters']}")
    print()
    print(f"Average words per line: {Fore.BLUE}{stats['avg_words_per_line']:.2f}")
    print(f"Average characters per line: {Fore.BLUE}{stats['avg_chars_per_line']:.2f}")
    print(f"Average duration per line: {Fore.BLUE}{stats['avg_duration']}")
    print()
    print(f"Shortest line duration: {Fore.BLUE}{stats['min_duration']}")
    print(f"Longest line duration:  {Fore.BLUE}{stats['max_duration']}")
    print()
    print(f"Reading rate (words/sec):      {Fore.BLUE}{stats['reading_rate_words']:.2f}")
    print(f"Reading rate (characters/sec): {Fore.BLUE}{stats['reading_rate_chars']:.2f}")
    print()
    print(f"Maximum characters in a line: {Fore.BLUE}{len(clean_text(stats['max_chars_line']))}")
    print(f"Lines with maximum length ({len(clean_text(stats['max_chars_line']))} characters): {Fore.BLUE}{len(stats['longest_lines'])}")
    for num, line in stats['longest_lines']:
        print(f"  {Fore.YELLOW}- Line {num}:\t{Style.RESET_ALL} {clean_text(line)}")

    long_lines_set, line_contents = stats['lines_with_more_than_42_chars']
    if line_contents:
        print("\n------------------------------------------")
        print(f"\n{Fore.YELLOW}LINES{Style.RESET_ALL} WITH MORE THAN 42 {Fore.GREEN}CHARACTERS{Style.RESET_ALL}: {Fore.BLUE}{len(long_lines_set)}\n")
        for line_num, text_lines in line_contents:
            print(f"{Fore.YELLOW}({line_num})\t{Style.RESET_ALL}", end=" ")
            first_line = True
            for line in text_lines:
                if not first_line:
                    print("\t ", end="")
                print(f"{line} {Fore.GREEN}({len(line)})")
                first_line = False
            print()
    else:
        print("\n------------------------------------------")
        print(f"\n{Fore.GREEN}No lines with more than 42 characters detected")

    if stats['short_duration_lines']:
        print("------------------------------------------")
        print(f"\nLINES WITH LESS THAN 1 SECOND DURATION:\n")
        for line in stats['short_duration_lines']:
            print(f"{Fore.YELLOW}Line ({line['number']}):")
            print(f"Time: {format_timedelta(line['start'])} --> {format_timedelta(line['end'])}")
            print(f"Duration: {Fore.RED}{format_timedelta(line['duration'])}")
            for text in line['text']:
                print(f"  {clean_text(text)} {Fore.GREEN}({len(clean_text(text))})")
            print()
        print(f"Total lines with less than 1s duration: {Fore.BLUE}{len(stats['short_duration_lines'])}")
    else:
        print("------------------------------------------")     
        print(f"\n{Fore.GREEN}No lines with less than 1 second detected.")

    if stats['overlaps']:
        print("------------------------------------------")
        counter = 0
        for overlap_info in stats['overlaps']:
            counter += 1
        print(f"\nOVERLAPPING LINES DETECTED: {Fore.BLUE}{counter}\n")
        counter = 1
        for overlap_info in stats['overlaps']:
            subtitle1, start1, end1 = overlap_info[0]
            subtitle2, start2, end2 = overlap_info[1]
            overlap_duration = overlap_info[2]

            print(f"{Fore.BLUE}{counter}")
            counter += 1
            print(f"{Fore.RED}1th subtitle {Fore.YELLOW}(line {subtitle1[3]}){Style.RESET_ALL}:")
            print(f"Time: {Fore.BLUE}{format_timedelta(start1)}{Style.RESET_ALL} --> {Fore.BLUE}{format_timedelta(end1)}")
            for text_line in subtitle1[2]:
                print(f"  {clean_text(text_line)} {Fore.GREEN}({len(clean_text(text_line))})")
            
            print(f"\n{Fore.RED}2nd subtitle {Fore.YELLOW}(line {subtitle2[3]}){Style.RESET_ALL}:")
            print(f"Time: {Fore.BLUE}{format_timedelta(start2)}{Style.RESET_ALL} --> {Fore.BLUE}{format_timedelta(end2)}")
            for text_line in subtitle2[2]:
                print(f"  {clean_text(text_line)} {Fore.GREEN}({len(clean_text(text_line))})")
            
            print(f"\nOverlap duration: {Fore.RED}{format_timedelta(overlap_duration)}")
            print(f"Overlap time: {Fore.BLUE}{format_timedelta(start2)}{Style.RESET_ALL} --> {Fore.BLUE}{format_timedelta(end1)}")
            print("\n" + "- " * 10 + "\n")
    else:
        print("\n------------------------------------------")
        print(f"\n{Fore.GREEN}No overlapping lines detected.\n")

if __name__ == "__main__":
    main()