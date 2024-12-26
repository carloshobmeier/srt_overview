import os
import re
import chardet
from datetime import timedelta
from colorama import Fore, init, Style
from typing import Dict, List, Tuple
import pandas as pd
from tabulate import tabulate

init(autoreset=True)

def detect_encoding(file_path: str) -> str:
    """Detect the encoding of the file using chardet."""
    with open(file_path, 'rb') as file:
        raw_data = file.read()
    result = chardet.detect(raw_data)
    return result['encoding'] if result else 'not found'

def parse_time(timestamp: str) -> timedelta:
    """Convert SRT timestamp (HH:MM:SS,mmm) to timedelta."""
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

def _merge_intervals(intervals: List[Tuple[timedelta, timedelta]]) -> timedelta:
    """
    Recebe uma lista de (start, end) e retorna a soma de tempo total desses intervalos,
    unificando sobreposições.
    Exemplo: [(0s,5s), (2s,6s)] => total de 6s, e não 5+4=9s.
    """
    if not intervals:
        return timedelta(0)
    
    # Ordena pelos tempos de início
    intervals.sort(key=lambda x: x[0])
    
    merged_intervals = []
    current_start, current_end = intervals[0]
    
    for i in range(1, len(intervals)):
        start, end = intervals[i]
        if start <= current_end:
            # Há sobreposição; ajusta o final se necessário
            current_end = max(current_end, end)
        else:
            # Intervalo novo não se sobrepõe
            merged_intervals.append((current_start, current_end))
            current_start, current_end = start, end
    
    # Adiciona o último intervalo
    merged_intervals.append((current_start, current_end))
    
    # Soma total dos intervalos mesclados
    total = timedelta(0)
    for st, en in merged_intervals:
        total += (en - st)
    return total

def parse_srt(file_path: str) -> List[Tuple[timedelta, timedelta, List[str], int, str]]:
    """
    Parse an SRT file and return a list of subtitles in the format:
    (start_time, end_time, [text_lines], line_number, encoding).
    """
    try:
        encoding = detect_encoding(file_path)
        with open(file_path, 'r', encoding=encoding) as file:
            content = file.read()
        
        blocks = content.strip().split('\n\n')
        subtitles = []
        
        for block in blocks:
            lines = block.split('\n')
            if len(lines) < 2:
                continue
            
            # Exemplo de linha: 00:00:01,600 --> 00:00:03,200
            time_match = re.match(r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})", lines[1])
            if not time_match:
                continue

            start_time = parse_time(time_match.group(1))
            end_time = parse_time(time_match.group(2))
            
            try:
                line_number = int(lines[0])
            except ValueError:
                line_number = 0  # Caso a primeira linha não seja um número
            
            # Limpa e filtra linhas vazias
            text_lines = [clean_text(ln) for ln in lines[2:] if clean_text(ln)]
            subtitles.append((start_time, end_time, text_lines, line_number, encoding))
        
        return subtitles
    except Exception as e:
        print(f"{Fore.RED}Error processing file {file_path}: {str(e)}")
        return []

def analyze_subtitle_file(file_path: str) -> Dict:
    """Analyze a single subtitle file and return statistics."""
    subtitles = parse_srt(file_path)
    if not subtitles:
        return None
    
    num_lines = len(subtitles)
    
    # Início e fim (p/ cálculo de duração do arquivo)
    start_time = subtitles[0][0] if subtitles else timedelta(0)
    end_time = subtitles[-1][1] if subtitles else timedelta(0)
    total_duration = end_time - start_time

    # Intervalos para cálculo real de exibição (sobreposições)
    intervals = [(s[0], s[1]) for s in subtitles]
    real_display_time = _merge_intervals(intervals)
    
    total_silence = total_duration - real_display_time

    # Cálculo de palavras, caracteres e durações
    total_words = 0
    total_chars = 0

    durations = []
    line_counts = []
    
    for (start, end, text_lines, _, _) in subtitles:
        dur = (end - start).total_seconds()
        durations.append(dur)
        
        line_count = len(text_lines)
        line_counts.append(line_count)
        
        for line in text_lines:
            total_words += len(line.split())
            total_chars += len(line)

    single_lines = sum(1 for c in line_counts if c == 1)
    double_lines = sum(1 for c in line_counts if c == 2)
    triple_plus_lines = sum(1 for c in line_counts if c >= 3)

    if durations:
        sum_durations = sum(durations)
        file_min_duration = min(durations)
        file_max_duration = max(durations)
        avg_duration = sum_durations / len(durations)
    else:
        sum_durations = 0
        file_min_duration = 0
        file_max_duration = 0
        avg_duration = 0

    # Overlap detection (contagem simples)
    overlaps = 0
    for i in range(num_lines - 1):
        if subtitles[i][1] > subtitles[i + 1][0]:
            overlaps += 1

    # Taxa de exibição (words/sec) baseada no tempo real exibido
    display_seconds = real_display_time.total_seconds()
    words_per_second = total_words / display_seconds if display_seconds > 0 else 0

    # Porcentagem de display
    duration_seconds = total_duration.total_seconds() if total_duration.total_seconds() > 0 else 1
    display_percentage = (display_seconds / duration_seconds * 100)

    return {
        'filename': os.path.basename(file_path),
        'num_lines': num_lines,
        'duration': format_timedelta(total_duration),
        'display_time': format_timedelta(real_display_time),
        'silence_time': format_timedelta(total_silence),
        'display_percentage': display_percentage,
        
        'total_words': total_words,
        'total_chars': total_chars,
        'words_per_line': total_words / num_lines if num_lines else 0,
        'chars_per_line': total_chars / num_lines if num_lines else 0,
        'words_per_second': words_per_second,

        # Para cálculo global
        'sum_durations': sum_durations,
        'file_min_duration': file_min_duration,
        'file_max_duration': file_max_duration,
        'avg_duration': avg_duration,

        'single_lines': single_lines,
        'double_lines': double_lines,
        'triple_plus_lines': triple_plus_lines,
        'overlaps': overlaps,
        'encoding': subtitles[0][4] if subtitles else "Unknown"
    }

def print_stats_dict(stats: Dict) -> None:
    """
    Imprime o dicionário de estatísticas de forma tabulada,
    com apenas 2 casas decimais para floats.
    O campo "filename" não entra na tabela: é mostrado antes como título.
    """
    from tabulate import tabulate

    # Guardamos o nome do arquivo e removemos do dicionário pra não entrar na tabela
    filename = stats.get('filename', 'Unknown File')
    
    # Criamos uma cópia do dicionário sem o campo "filename"
    # para não interferir nos dados usados posteriormente.
    stats_for_table = {k: v for k, v in stats.items() if k != 'filename'}

    print(f"{Fore.BLUE}File: {filename}{Style.RESET_ALL}")
    
    # Formatamos floats com 2 casas decimais
    data = []
    for k, v in stats_for_table.items():
        if isinstance(v, float):
            data.append((k, f"{v:.2f}"))
        else:
            data.append((k, v))

    # Exibe cabeçalhos "Field" e "Value"
    print(tabulate(data, headers=["Field", "Value"], tablefmt="pretty"))

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
            print(f"\n{Fore.CYAN}=== Stats for file: {file} ===")
            print_stats_dict(stats)
            results.append(stats)
        else:
            print(f"\n{Fore.RED}Could not process file: {file}. No stats available.")

    if not results:
        print(f"{Fore.RED}No valid subtitle files could be processed!")
        return
    
    df = pd.DataFrame(results)
    
    # Cálculo global para Average Line Duration (seconds)
    total_sum_durations = df['sum_durations'].sum()
    total_lines = df['num_lines'].sum()
    global_avg_duration = total_sum_durations / total_lines if total_lines else 0

    # --- Enhanced Comparative Statistics ---
    print(f"\n{Fore.GREEN}=== Detailed Comparative Analysis ===\n")

    # 1. Basic File Statistics
    print(f"{Fore.YELLOW}Basic File Statistics:")
    basic_stats = {
        'Total Files Analyzed': len(df),
        'Total Combined Lines': df['num_lines'].sum(),
        'Average Lines per File': df['num_lines'].mean(),
    }
    # Exibimos com 2 casas decimais se for float
    print(tabulate(
        [[k, f"{v:.2f}" if isinstance(v, float) else v] for k, v in basic_stats.items()],
        tablefmt='simple'
    ))

    # 2. Timing Analysis
    print(f"\n{Fore.YELLOW}Timing Analysis:")
    timing_stats = {
        'Average Display Time %': df['display_percentage'].mean(),
        'Average Line Duration (seconds)': global_avg_duration,
        'Shortest Line Duration (seconds)': df['file_min_duration'].min(),
        'Longest Line Duration (seconds)': df['file_max_duration'].max()
    }
    print(tabulate(
        [[k, f"{v:.2f}" if isinstance(v, float) else v] for k, v in timing_stats.items()],
        tablefmt='simple'
    ))

    # 3. Reading Speed Analysis
    print(f"\n{Fore.YELLOW}Reading Speed Analysis:")
    reading_stats = {
        'Average Words per Second': df['words_per_second'].mean(),
        'Fastest Reading Speed': df['words_per_second'].max(),
        'Slowest Reading Speed': df['words_per_second'].min(),
    }
    print(tabulate(
        [[k, f"{v:.2f}" if isinstance(v, float) else v] for k, v in reading_stats.items()],
        tablefmt='simple'
    ))

    # 4. Text Structure Analysis
    print(f"\n{Fore.YELLOW}Text Structure Analysis:")
    total_lines_all = df['num_lines'].sum()
    structure_stats = {
        'Average Words per Line': df['words_per_line'].mean(),
        'Average Characters per Line': df['chars_per_line'].mean(),
        'Single-Line Subtitles %': (df['single_lines'].sum() / total_lines_all * 100) if total_lines_all else 0,
        'Double-Line Subtitles %': (df['double_lines'].sum() / total_lines_all * 100) if total_lines_all else 0,
        'Triple+ Line Subtitles %': (df['triple_plus_lines'].sum() / total_lines_all * 100) if total_lines_all else 0
    }
    print(tabulate(
        [[k, f"{v:.2f}" if isinstance(v, float) else v] for k, v in structure_stats.items()],
        tablefmt='simple'
    ))

    # 5. Quality Metrics
    print(f"\n{Fore.YELLOW}Quality Metrics:")
    quality_stats = {
        'Total Overlaps Found': df['overlaps'].sum(),
        'Average Overlaps per File': df['overlaps'].mean(),
        'Files with Overlaps': len(df[df['overlaps'] > 0]),
        'Files with Zero Overlaps': len(df[df['overlaps'] == 0]),
    }
    print(tabulate(
        [[k, f"{v:.2f}" if isinstance(v, float) else v] for k, v in quality_stats.items()],
        tablefmt='simple'
    ))

    # 6. File Rankings (Longest/Shortest File baseados em num_lines)
    print(f"\n{Fore.YELLOW}Notable Files:")
    rankings = {}
    if len(df) > 0:
        # Garante que exista ao menos 1 arquivo para idxmax() e idxmin()
        max_idx = df['num_lines'].idxmax()
        min_idx = df['num_lines'].idxmin()
        max_spd_idx = df['words_per_second'].idxmax()
        min_spd_idx = df['words_per_second'].idxmin()
        max_ovp_idx = df['overlaps'].idxmax()

        rankings = {
            'Longest File': (
                f"{df.iloc[max_idx]['filename']} "
                f"{Fore.BLUE}({int(df.iloc[max_idx]['num_lines'])} lines){Style.RESET_ALL}"
            ),
            'Shortest File': (
                f"{df.iloc[min_idx]['filename']} "
                f"{Fore.BLUE}({int(df.iloc[min_idx]['num_lines'])} lines){Style.RESET_ALL}"
            ),
            'Fastest Reading Speed': (
                f"{df.iloc[max_spd_idx]['filename']} "
                f"{Fore.BLUE}({df.iloc[max_spd_idx]['words_per_second']:.2f} w/s){Style.RESET_ALL}"
            ),
            'Slowest Reading Speed': (
                f"{df.iloc[min_spd_idx]['filename']} "
                f"{Fore.BLUE}({df.iloc[min_spd_idx]['words_per_second']:.2f} w/s){Style.RESET_ALL}"
            ),
            'Most Overlaps': (
                f"{df.iloc[max_ovp_idx]['filename']} "
                f"{Fore.BLUE}({int(df.iloc[max_ovp_idx]['overlaps'])} overlaps){Style.RESET_ALL}"
            )
        }
    print(tabulate([[k, v] for k, v in rankings.items()], tablefmt='simple'))

    # 7. Encoding Analysis
    print(f"\n{Fore.YELLOW}Encoding Distribution:")
    encoding_dist = df['encoding'].value_counts()
    print(tabulate(
        [[enc, cnt] for enc, cnt in encoding_dist.items()],
        headers=['Encoding', 'Count'],
        tablefmt='simple'
    ))

def main():
    print(f"{Fore.CYAN}Multiple Subtitle File Analyzer\n")
    directory = input("Enter the directory path containing SRT files: ").strip()
    
    if not os.path.exists(directory):
        print(f"{Fore.RED}Directory not found!")
        return
    
    analyze_directory(directory)

if __name__ == "__main__":
    main()
