import os
import tiktoken

# Текущая папка проекта
PROJECT_PATH = r"."

# Считаем только важные текстовые файлы кода и документации
EXTENSIONS = ('.py', '.js', '.ts', '.html', '.css', '.json', '.md', '.sql')

# Точный список папок-исключений на основе вашей структуры
IGNORE_DIRS = {
    'venv', '.venv', '.venv_313', '.git', 'node_modules', '__pycache__', 
    'dist', 'build', '.idea', '.vscode',
    'assets', 'backup_20260914', 'battle_archive', 'sound original', 'ui'
}

# Файлы-исключения, которые забивают контекст огромным количеством текста
IGNORE_FILES = {
    'debug.log', 'debug_out.txt', 'cards.sqlite3', 'client_package.zip'
}

def count_tokens():
    if not os.path.exists(PROJECT_PATH):
        print(f"Ошибка: Путь '{PROJECT_PATH}' не найден!")
        return

    enc = tiktoken.get_encoding("cl100k_base")
    total_tokens = 0
    file_count = 0
    
    print("Начинаю повторное сканирование (без учета скрытых папок и тяжелых ресурсов)...")
    
    for root, dirs, files in os.walk(PROJECT_PATH):
        # Жестко отсекаем ненужные папки на входе, чтобы скрипт в них даже не заходил
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            # Проверяем расширение и игнорируем тяжелые системные файлы
            if file.endswith(EXTENSIONS) and file not in IGNORE_FILES:
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        tokens = len(enc.encode(content))
                        total_tokens += tokens
                        file_count += 1
                except Exception as e:
                    print(f"Не удалось прочитать файл {file_path}: {e}")
                    
    print("\n" + "="*30)
    print(f"Чистых файлов кода проверено: {file_count}")
    print(f"РЕАЛЬНЫЙ ВЕС КОДА: {total_tokens:,} токенов")
    print("="*30)

if __name__ == "__main__":
    count_tokens()
