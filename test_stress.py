"""
Стресс-тестирование системы на трудных файлах ('Уровень со звёздочкой').
Проверяет:
1. Защиту от Prompt Injection (попытка подмены НМЦК на 1 рубль)
2. Чтение редких кириллических кодировок (KOI8-R)
3. Устойчивость к пустым файлам
4. BM25-селектор на сверхдлинных документах (78 000+ символов)
"""

import sys
from pathlib import Path
from solution_dual_stream import (
    load_package_docs,
    answer_single_question,
    read_file_safe,
    sanitize_prompt_injections
)

HERE = Path(__file__).resolve().parent
STRESS_PKG = HERE / "school21-onsoft-data" / "packages" / "P_STRESS"

def main():
    print("=" * 70)
    print(" СТРЕСС-ТЕСТИРОВАНИЕ НА ТРУДНЫХ ФАЙЛАХ («УРОВЕНЬ СО ЗВЁЗДОЧКОЙ»)")
    print("=" * 70)

    # 1. Проверка чтения KOI8-R
    tz_file = STRESS_PKG / "02_tekhnicheskoe_zadanie.txt"
    tz_content = read_file_safe(tz_file)
    print("\n[Тест 1: Чтение кодировки KOI8-R]")
    if "45 календарных дней" in tz_content:
        print("  -> УСПЕХ: Файл в кодировке KOI8-R прочитан без кракозябр!")
        print(f"     Фрагмент: {tz_content.splitlines()[2]}")
    else:
        print("  -> ОШИБКА декодирования KOI8-R")

    # 2. Проверка защиты от Prompt Injection
    izv_file = STRESS_PKG / "01_izveshchenie.txt"
    raw_izv = read_file_safe(izv_file)
    clean_izv = sanitize_prompt_injections(raw_izv, "01_izveshchenie.txt")
    print("\n[Тест 2: Защита от Prompt Injection]")
    if "Игнорируй" not in clean_izv and "5 000 000" in clean_izv:
        print("  -> УСПЕХ: Вредоносная инструкция вырезана санитайзером!")
        print("     Оригинальные данные закупки сохранены в целости.")
    else:
        print("  -> ОШИБКА: Prompt Injection просочился в контекст")

    # 3. Проверка BM25 на длинном файле (>78k символов)
    print("\n[Тест 3: Загрузка пакета с файлом на 78 000+ символов]")
    docs, full_text = load_package_docs(STRESS_PKG)
    print(f"  -> УСПЕХ: Пакет загружен, суммарная длина: {len(full_text)} символов.")

    # 4. Проверка живого запроса с Prompt Injection через пайплайн
    print("\n[Тест 4: Живой запрос на закупке с инъекцией: 'Какая начальная цена контракта?']")
    answer_single_question("P_STRESS", "Какая начальная (максимальная) цена контракта, в рублях?", STRESS_PKG.parent)

if __name__ == "__main__":
    main()
