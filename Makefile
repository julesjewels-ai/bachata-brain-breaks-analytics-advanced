.PHONY: install run test clean

venv:
	python3.11 -m venv venv

install: venv
	. venv/bin/activate && pip install -r requirements.txt

run:
	. venv/bin/activate && python main.py

run-real:
	. venv/bin/activate && python main.py --real-data

test:
	. venv/bin/activate && pytest

clean:
	rm -rf venv
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
