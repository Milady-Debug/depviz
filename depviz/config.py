"""Загрузка и проверка конфигурационного файла формата CSV.

Формат файла: первая строка — заголовок ``key,value``, далее пары
«параметр, значение». Пустые строки и строки, начинающиеся с ``#``,
игнорируются.
"""
import csv
import os
import re
from urllib.parse import urlparse


class ConfigError(Exception):
    """Ошибка в конфигурационном файле."""


# Обязательные параметры (порядок важен для вывода).
REQUIRED_KEYS = ("package_name", "repository", "test_mode")
KNOWN_KEYS = REQUIRED_KEYS

TRUE_VALUES = {"true", "yes", "1", "on"}
FALSE_VALUES = {"false", "no", "0", "off"}

# groupId:artifactId[:version]
MAVEN_NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]+:[A-Za-z0-9_.\-]+(:[A-Za-z0-9_.\-]+)?$")
# В тестовом репозитории пакеты называются большими латинскими буквами.
TEST_NAME_RE = re.compile(r"^[A-Z]+$")


def _read_rows(path):
    """Читает CSV и возвращает список (номер_строки, [ячейки])."""
    if not os.path.exists(path):
        raise ConfigError(f"конфигурационный файл не найден: {path}")
    if not os.path.isfile(path):
        raise ConfigError(f"путь не является файлом: {path}")
    try:
        with open(path, encoding="utf-8", newline="") as f:
            rows = list(enumerate(csv.reader(f), start=1))
    except UnicodeDecodeError:
        raise ConfigError("конфигурационный файл должен быть в кодировке UTF-8")
    except csv.Error as e:
        raise ConfigError(f"некорректный CSV: {e}")
    except OSError as e:
        raise ConfigError(f"не удалось прочитать файл: {e}")
    # убираем пустые строки и комментарии
    return [(n, r) for n, r in rows
            if r and any(c.strip() for c in r) and not r[0].strip().startswith("#")]


def _parse_bool(value):
    v = value.strip().lower()
    if v in TRUE_VALUES:
        return True
    if v in FALSE_VALUES:
        return False
    raise ConfigError(
        f"test_mode: недопустимое значение '{value}', ожидается true или false")


def _check_package(name, test_mode):
    if test_mode:
        if not TEST_NAME_RE.match(name):
            raise ConfigError(
                f"package_name: '{name}' — в тестовом режиме имя пакета должно "
                f"состоять только из больших латинских букв (например, A)")
    elif not MAVEN_NAME_RE.match(name):
        raise ConfigError(
            f"package_name: '{name}' — ожидается формат groupId:artifactId[:version], "
            f"например org.apache.commons:commons-text:1.12.0")


def _check_repository(repo, test_mode, config_dir):
    parsed = urlparse(repo)
    looks_like_url = parsed.scheme in ("http", "https", "file", "ftp")
    if test_mode:
        if looks_like_url:
            raise ConfigError(
                f"repository: '{repo}' — в тестовом режиме нужен путь к файлу, а не URL")
        path = repo if os.path.isabs(repo) else os.path.join(config_dir, repo)
        path = os.path.normpath(path)
        if not os.path.exists(path):
            raise ConfigError(f"repository: файл тестового репозитория не найден: {path}")
        if not os.path.isfile(path):
            raise ConfigError(f"repository: путь не является файлом: {path}")
        return path
    if parsed.scheme not in ("http", "https", "file"):
        raise ConfigError(
            f"repository: '{repo}' — ожидается URL со схемой http://, https:// или file://")
    if parsed.scheme in ("http", "https") and not parsed.netloc:
        raise ConfigError(f"repository: в URL '{repo}' не указан хост")
    return repo.rstrip("/")


def load_config(path):
    """Читает и проверяет конфигурацию. Возвращает словарь параметров."""
    rows = _read_rows(path)
    if not rows:
        raise ConfigError("конфигурационный файл пуст")

    header_line, header = rows[0]
    if [c.strip().lower() for c in header] != ["key", "value"]:
        raise ConfigError(
            f"строка {header_line}: ожидается заголовок 'key,value', получено '{','.join(header)}'")

    raw = {}
    for line, row in rows[1:]:
        if len(row) != 2:
            raise ConfigError(
                f"строка {line}: ожидается 2 столбца (key,value), получено {len(row)}")
        key, value = row[0].strip(), row[1].strip()
        if key not in KNOWN_KEYS:
            raise ConfigError(
                f"строка {line}: неизвестный параметр '{key}'. "
                f"Допустимые: {', '.join(KNOWN_KEYS)}")
        if key in raw:
            raise ConfigError(f"строка {line}: параметр '{key}' указан повторно")
        if not value:
            raise ConfigError(f"строка {line}: у параметра '{key}' пустое значение")
        raw[key] = value

    missing = [k for k in REQUIRED_KEYS if k not in raw]
    if missing:
        raise ConfigError(f"не заданы обязательные параметры: {', '.join(missing)}")

    config_dir = os.path.dirname(os.path.abspath(path))
    test_mode = _parse_bool(raw["test_mode"])
    _check_package(raw["package_name"], test_mode)
    repository = _check_repository(raw["repository"], test_mode, config_dir)

    return {
        "package_name": raw["package_name"],
        "repository": repository,
        "test_mode": test_mode,
    }
