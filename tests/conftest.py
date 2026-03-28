"""
Общая конфигурация тестов.
Добавляет src/ в sys.path, чтобы импорты работали.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
