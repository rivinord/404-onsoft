PYTHON := $(shell if [ -f ./venv/bin/python3 ]; then echo "./venv/bin/python3"; elif [ -f ../hackathon21/venv/bin/python3 ]; then echo "../hackathon21/venv/bin/python3"; else echo "python3"; fi)
STREAMLIT := $(shell if [ -f ./venv/bin/streamlit ]; then echo "./venv/bin/streamlit"; elif [ -f ../hackathon21/venv/bin/streamlit ]; then echo "../hackathon21/venv/bin/streamlit"; else echo "streamlit"; fi)

.PHONY: all run run-nocache test app clean help install venv

all: run

venv:
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt

install:
	$(PYTHON) -m pip install -r requirements.txt

run:
	$(PYTHON) solution.py

run-nocache:
	$(PYTHON) solution.py --no-cache

test:
	$(PYTHON) test_stress.py
	$(PYTHON) school21-onsoft-data/check.py answers.csv

app:
	$(STREAMLIT) run app.py

clean:
	rm -rf uploads/ __pycache__/ .pytest_cache/
	@echo "Временные файлы и кэш очищены."

help:
	@echo "Команда «404» — Кейс ОНСОФТ: «ИИ, который не обманывает»"
	@echo "Доступные команды:"
	@echo "  make venv        - Создать локальное виртуальное окружение и установить зависимости"
	@echo "  make run         - Запустить решение и сгенерировать answers.csv"
	@echo "  make run-nocache - Запустить конвейер без кэша (прямые запросы к GigaChat API)"
	@echo "  make test        - Запустить стресс-тесты и чекер"
	@echo "  make app         - Запустить интерактивный веб-дашборд в браузере"
	@echo "  make clean       - Очистить временные файлы и загрузки"
