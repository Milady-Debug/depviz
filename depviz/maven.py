"""Получение информации о зависимостях из Maven-репозитория.

Используется только стандартная библиотека: urllib для загрузки файлов
и xml.etree для разбора POM. Сторонние библиотеки и сам Maven
для получения зависимостей не используются.

Структура Maven-репозитория:
  <repo>/<groupId с / вместо .>/<artifactId>/<version>/<artifactId>-<version>.pom
  <repo>/<groupId с / вместо .>/<artifactId>/maven-metadata.xml
"""
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass


class MavenError(Exception):
    """Ошибка получения или разбора данных из репозитория."""


@dataclass(frozen=True)
class Dependency:
    group: str
    artifact: str
    version: str
    scope: str = "compile"
    optional: bool = False

    @property
    def coord(self):
        return f"{self.group}:{self.artifact}:{self.version}"


_PROP_RE = re.compile(r"\$\{([^}]+)\}")


def _strip_ns(root):
    """Убирает пространство имён из тегов, чтобы искать по 'dependency'."""
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def _text(el, tag, default=None):
    child = el.find(tag) if el is not None else None
    if child is None or child.text is None:
        return default
    return child.text.strip()


def _interpolate(value, props):
    """Подставляет ${свойства}. Неизвестные свойства остаются как есть."""
    if value is None:
        return None
    for _ in range(10):  # вложенные свойства: ${a} -> ${b} -> значение
        new = _PROP_RE.sub(lambda m: props.get(m.group(1), m.group(0)), value)
        if new == value:
            break
        value = new
    return value


def _normalize_version(version):
    """Диапазоны версий ([1.0,2.0), [1.5]) упрощаются до одной версии."""
    if version and version[0] in "[(":
        parts = [p.strip() for p in version.strip("[]()").split(",")]
        if len(parts) == 1:
            return parts[0]
        return parts[0] or parts[1]  # нижняя граница, иначе верхняя
    return version


class MavenRepository:
    """Клиент Maven-репозитория (http://, https:// или file://)."""

    def __init__(self, base_url, timeout=20):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._pom_cache = {}
        self._model_cache = {}

    # --- загрузка файлов -------------------------------------------------
    def _path(self, group, artifact):
        return f"{self.base_url}/{group.replace('.', '/')}/{artifact}"

    def _fetch(self, url):
        req = urllib.request.Request(url, headers={"User-Agent": "depviz/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise MavenError(f"не найдено в репозитории: {url}")
            raise MavenError(f"HTTP {e.code} при загрузке {url}")
        except urllib.error.URLError as e:
            if isinstance(e.reason, FileNotFoundError):  # file:// URL
                raise MavenError(f"не найдено в репозитории: {url}")
            raise MavenError(f"не удалось подключиться к {url}: {e.reason}")
        except (OSError, ValueError) as e:
            raise MavenError(f"ошибка загрузки {url}: {e}")

    def _fetch_xml(self, url):
        data = self._fetch(url)
        try:
            return _strip_ns(ET.fromstring(data))
        except ET.ParseError as e:
            raise MavenError(f"некорректный XML в {url}: {e}")

    def latest_version(self, group, artifact):
        """Последняя релизная версия по maven-metadata.xml."""
        meta = self._fetch_xml(f"{self._path(group, artifact)}/maven-metadata.xml")
        versioning = meta.find("versioning")
        version = _text(versioning, "release") or _text(versioning, "latest")
        if not version and versioning is not None:
            versions = [v.text for v in versioning.findall("versions/version") if v.text]
            version = versions[-1] if versions else None
        if not version:
            raise MavenError(f"в maven-metadata.xml для {group}:{artifact} нет версий")
        return version.strip()

    def load_pom(self, group, artifact, version):
        key = (group, artifact, version)
        if key not in self._pom_cache:
            url = f"{self._path(group, artifact)}/{version}/{artifact}-{version}.pom"
            self._pom_cache[key] = self._fetch_xml(url)
        return self._pom_cache[key]

    # --- эффективная модель POM -----------------------------------------
    def _model(self, group, artifact, version, chain=()):
        """Собирает свойства, dependencyManagement и зависимости
        с учётом родительских POM (наследование) и импорта BOM."""
        key = (group, artifact, version)
        if key in self._model_cache:
            return self._model_cache[key]
        if key in chain:
            raise MavenError(f"цикл в иерархии родительских POM: {group}:{artifact}:{version}")
        chain = chain + (key,)

        pom = self.load_pom(group, artifact, version)
        props, managed, deps = {}, {}, []

        parent = pom.find("parent")
        if parent is not None:
            pg, pa, pv = _text(parent, "groupId"), _text(parent, "artifactId"), _text(parent, "version")
            if pg and pa and pv:
                p_props, p_managed, p_deps = self._model(pg, pa, pv, chain)
                props.update(p_props)
                managed.update(p_managed)
                deps.extend(p_deps)  # зависимости родителя наследуются
                props.update({"project.parent.version": pv, "parent.version": pv,
                              "project.parent.groupId": pg})

        own_group = _text(pom, "groupId") or (parent is not None and _text(parent, "groupId")) or group
        own_version = _text(pom, "version") or (parent is not None and _text(parent, "version")) or version
        props.update({
            "project.groupId": own_group, "pom.groupId": own_group,
            "project.artifactId": artifact, "pom.artifactId": artifact,
            "project.version": own_version, "pom.version": own_version,
            "version": own_version,
        })
        properties = pom.find("properties")
        if properties is not None:
            for p in properties:
                if isinstance(p.tag, str):
                    props[p.tag] = (p.text or "").strip()

        # dependencyManagement: сначала импортируемые BOM, затем свои записи
        own_managed = {}
        for d in pom.findall("dependencyManagement/dependencies/dependency"):
            g = _interpolate(_text(d, "groupId"), props)
            a = _interpolate(_text(d, "artifactId"), props)
            v = _normalize_version(_interpolate(_text(d, "version"), props))
            scope = _text(d, "scope")
            if scope == "import" and _text(d, "type") == "pom":
                try:
                    managed.update(self._model(g, a, v, chain)[1])
                except MavenError:
                    pass  # недоступный BOM не должен ломать весь анализ
                continue
            own_managed[f"{g}:{a}"] = {"version": v, "scope": scope}
        managed.update(own_managed)

        for d in pom.findall("dependencies/dependency"):
            g = _interpolate(_text(d, "groupId"), props)
            a = _interpolate(_text(d, "artifactId"), props)
            m = managed.get(f"{g}:{a}", {})
            v = _normalize_version(_interpolate(_text(d, "version"), props)) or m.get("version")
            scope = _text(d, "scope") or m.get("scope") or "compile"
            optional = (_text(d, "optional", "false").lower() == "true")
            if not v or "${" in v:
                v = v or "?"
            deps = [x for x in deps if (x.group, x.artifact) != (g, a)]  # свои переопределяют родительские
            deps.append(Dependency(g, a, v, scope, optional))

        self._model_cache[key] = (props, managed, deps)
        return self._model_cache[key]

    def direct_dependencies(self, group, artifact, version):
        """Все прямые зависимости пакета (со scope и признаком optional)."""
        return list(self._model(group, artifact, version)[2])


def parse_coordinate(name):
    """'g:a[:v]' -> (g, a, v или None)."""
    parts = name.split(":")
    return parts[0], parts[1], (parts[2] if len(parts) > 2 else None)
