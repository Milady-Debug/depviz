"""Тестовый репозиторий: файл описания графа, пакеты — большие латинские буквы.

Формат (одна строка — один пакет):
    # комментарий
    A: B C        <- пакет A зависит от B и C (разделители: пробел или запятая)
    D:            <- пакет D без зависимостей
"""
import re

NAME_RE = re.compile(r"^[A-Z]+$")


class TestRepoError(Exception):
    """Ошибка в файле тестового репозитория."""


class TestRepository:
    def __init__(self, path):
        self.path = path
        self.packages = self._parse(path)

    @staticmethod
    def _parse(path):
        try:
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()
        except (OSError, UnicodeDecodeError) as e:
            raise TestRepoError(f"не удалось прочитать {path}: {e}")
        packages = {}
        for n, line in enumerate(lines, start=1):
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            if ":" not in line:
                raise TestRepoError(f"{path}, строка {n}: ожидается 'ПАКЕТ: зависимости'")
            name, rest = (part.strip() for part in line.split(":", 1))
            deps = [d for d in re.split(r"[\s,]+", rest) if d]
            for x in [name] + deps:
                if not NAME_RE.match(x):
                    raise TestRepoError(
                        f"{path}, строка {n}: '{x}' — имя пакета должно состоять "
                        f"из больших латинских букв")
            if name in packages:
                raise TestRepoError(f"{path}, строка {n}: пакет {name} описан повторно")
            packages[name] = list(dict.fromkeys(deps))  # без дублей, порядок сохранён
        return packages

    def dependencies(self, name):
        if name not in self.packages:
            raise TestRepoError(f"пакет {name} не найден в тестовом репозитории")
        return self.packages[name]
