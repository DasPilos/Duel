import os

# Текущая папка проекта
PROJECT_PATH = r"."
# Имя итогового файла, который мы загрузим в ИИ
OUTPUT_FILE = "full_project_code.txt"

# Считаем только важные текстовые файлы кода и документации
EXTENSIONS = ('.py', '.js', '.ts', '.html', '.css', '.json', '.md', '.sql')

# Точный список папок-исключений (тот же, что и для подсчета)
IGNORE_DIRS = {
    'venv', '.venv', '.venv_313', '.git', 'node_modules', '__pycache__', 
    'dist', 'build', '.idea', '.vscode',
    'assets', 'backup_20260914', 'battle_archive', 'sound original', 'ui'
}

# Файлы-исключения, которые не нужно добавлять в общую сборку
IGNORE_FILES = {
    'debug.log', 'debug_out.txt', 'cards.sqlite3', 'client_package.zip', OUTPUT_FILE
}

def pack_project():
    file_count = 0
    
    print("Начинаю сборку проекта в один файл...")
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as outfile:
        # Пишем вводную инструкцию для ИИ в самом начале файла
        outfile.write("Ниже представлен полный исходный код проекта.\n")
        outfile.write("Каждый файл начинается со строки-разделителя с указанием его пути.\n\n")
        
        for root, dirs, files in os.walk(PROJECT_PATH):
            # Пропускаем ненужные папки
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            
            for file in files:
                if file.endswith(EXTENSIONS) and file not in IGNORE_FILES:
                    file_path = os.path.join(root, file)
                    # Получаем красивый относительный путь (например, combat/core.py)
                    rel_path = os.path.relpath(file_path, PROJECT_PATH)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as infile:
                            content = infile.read()
                            
                            # Пишем красивый разделитель для ИИ
                            outfile.write(f"\n\n{'='*40}\n")
                            outfile.write(f"ФАЙЛ: {rel_path}\n")
                            outfile.write(f"{'='*40}\n\n")
                            
                            # Записываем сам код файла
                            outfile.write(content)
                            file_count += 1
                    except Exception as e:
                        print(f"Не удалось прочитать файл {rel_path}: {e}")
                        
    print("\n" + "="*30)
    print(f"Успешно объединено файлов: {file_count}")
    print(f"Файл сборки создан: {OUTPUT_FILE}")
    print("="*30)

if __name__ == "__main__":
    pack_project()
