# Отчёт по практической работе. Вариант 13

**Задача:** инструмент визуализации графа зависимостей для менеджера пакетов Maven
(Java). Готовые менеджеры пакетов и библиотеки для получения зависимостей не
используются: POM-файлы скачиваются через `urllib`, разбираются через
`xml.etree.ElementTree` (стандартная библиотека Python 3.10+).

## Итоговая структура проекта

```
depviz/
├── main.py                 точка входа CLI
├── config.csv              конфигурация по умолчанию
├── depviz/
│   ├── config.py           чтение и проверка CSV-конфигурации   (этап 1)
│   ├── maven.py            работа с Maven-репозиторием           (этап 2)
│   ├── test_repo.py        тестовый репозиторий (A, B, C…)       (этап 3)
│   ├── graph.py            DFS, циклы, дерево, порядок загрузки (этапы 3–4)
│   └── d2.py               генерация описания на языке D2       (этап 5)
├── configs/                примеры конфигураций (configs/errors — ошибочные)
├── tests_repo/             файлы тестовых репозиториев
├── local_maven/            офлайн-мини-зеркало Maven (вымышленные com.example)
├── examples/               готовые .d2-файлы
└── tests/                  модульные тесты (python -m unittest)
```

## Ветки и история коммитов

Каждый этап разрабатывается в **отдельной ветке**, созданной от `main`:
`stage-1`, `stage-2`, `stage-3`, `stage-4`, `stage-5`. После завершения
этапа ветка вливается в `main` командой `git merge --no-ff`, поэтому в
истории видно, какие коммиты относятся к какому этапу, а каждая ветка
хранит состояние проекта на момент сдачи своего этапа. Следующая ветка
создаётся от обновлённого `main`, т.е. содержит результаты предыдущих этапов.

Общая схема для этапа N:

```bash
git checkout main
git checkout -b stage-N          # новая ветка этапа
# ... правки, проверка ...
git add .
git commit                       # один или несколько коммитов этапа
git checkout main
git merge --no-ff stage-N -m "Merge branch 'stage-N'" -m "Этап N: ..."
git push origin main stage-N     # при работе с удалённым репозиторием
```

Посмотреть результат этапа: `git checkout stage-2` (и вернуться: `git checkout main`).

Коммиты оформлены по соглашению **Conventional Commits**:
`тип(область): краткое описание` в повелительном/безличном виде, пустая строка,
затем тело со списком изменений. Типы: `feat` — новая функциональность,
`fix` — исправление, `docs` — документация, `chore` — служебные изменения.

```
*   ffec375 Merge branch 'stage-5'  (main)
|\  
| * 0b224d0 feat(d2): визуализация графа зависимостей на языке D2  (stage-5)
|/  
*   0531ad7 Merge branch 'stage-4' 
|\  
| * 1260cf2 feat(order): режим вывода порядка загрузки зависимостей  (stage-4)
|/  
*   9f022da Merge branch 'stage-3' 
|\  
| * 0a963ce feat(graph): транзитивный граф зависимостей (рекурсивный DFS)  (stage-3)
|/  
*   a705a4c Merge branch 'stage-2' 
|\  
| * 4265e0f fix(maven): единое сообщение об отсутствии артефакта для file:// URL  (stage-2)
| * 2df37ae feat(maven): получение прямых зависимостей из Maven-репозитория 
|/  
*   88b5c53 Merge branch 'stage-1' 
|\  
| * d83425c feat(config): минимальный CLI-прототип с конфигурацией в CSV  (stage-1)
|/  
* 7a507c2 chore: инициализация репозитория
(+ ветка docs с этим отчётом)
```

Перед каждым коммитом выполнялись: `git status` (что изменилось),
`git diff` (проверка правок), `git add .`, `git commit` (сообщение пишется
в редакторе: заголовок до ~72 символов, пустая строка, тело).

---

## Подготовка

```bash
mkdir depviz && cd depviz
git init -b main
git config user.name  "Иванов Иван"
git config user.email "ivanov@example.com"
```

Создаются `.gitignore` (исключает `__pycache__/`, `*.pyc`, отрендеренные
`*.svg`/`*.png`) и короткий `README.md`, и делается начальный коммит прямо в
`main` — от него будут ответвляться ветки этапов:

```bash
git add .
git commit -m "chore: инициализация репозитория"
```

---

## Этап 1. Минимальный прототип с конфигурацией

**Ветка `stage-1`** (создаётся от `main`):

```bash
git checkout main
git checkout -b stage-1
```

**Создано:** `main.py`, `depviz/__init__.py`, `depviz/config.py`, `config.csv`,
`tests_repo/simple.txt`, `configs/test_simple.csv`, 12 файлов `configs/errors/*.csv`.
**Изменено:** `README.md` (описание запуска и параметров конфигурации).

Формат конфигурации — CSV с заголовком `key,value`:

```csv
key,value
package_name,org.apache.commons:commons-text:1.12.0
repository,https://repo1.maven.org/maven2
test_mode,false
```

| Параметр       | Смысл                                   | Проверка |
|----------------|-----------------------------------------|----------|
| `package_name` | имя анализируемого пакета               | Maven: `groupId:artifactId[:version]`; тестовый режим: только `A–Z` |
| `repository`   | URL репозитория или путь к тестовому файлу | обычный режим: схема `http/https/file` и хост; тестовый: файл существует и это не URL |
| `test_mode`    | режим работы с тестовым репозиторием    | `true/false` (`yes/no`, `1/0`, `on/off`) |

Как устроен `config.py`: `_read_rows()` читает файл модулем `csv`, отбрасывает
пустые строки и комментарии `#`, запоминая исходные номера строк (чтобы
сообщения об ошибках указывали на конкретную строку). `load_config()` проверяет
заголовок, число столбцов, неизвестные, повторные, пустые и отсутствующие ключи,
затем по очереди валидирует каждый параметр. Порядок важен: сначала
`test_mode`, потому что от него зависят правила проверки двух других
параметров. Любая ошибка — исключение `ConfigError`; `main.py` перехватывает
его, печатает сообщение в `stderr` и завершается с кодом 1.

Только на этом этапе `main.py` печатает параметры в виде `ключ=значение`.

**Демонстрация (корректные конфиги):**

```
$ python main.py
package_name=org.apache.commons:commons-text:1.12.0
repository=https://repo1.maven.org/maven2
test_mode=false

$ python main.py configs/test_simple.csv
package_name=A
repository=/…/depviz/tests_repo/simple.txt
test_mode=true
```

**Демонстрация обработки ошибок (по каждому параметру и формату файла):**

```
$ python main.py nope.csv
Ошибка конфигурации: конфигурационный файл не найден: nope.csv
$ python main.py configs/errors/bad_header.csv
Ошибка конфигурации: строка 1: ожидается заголовок 'key,value', получено 'name;value'
$ python main.py configs/errors/extra_column.csv
Ошибка конфигурации: строка 2: ожидается 2 столбца (key,value), получено 3
$ python main.py configs/errors/unknown_key.csv
Ошибка конфигурации: строка 5: неизвестный параметр 'color'. Допустимые: package_name, repository, test_mode
$ python main.py configs/errors/duplicate_key.csv
Ошибка конфигурации: строка 3: параметр 'package_name' указан повторно
$ python main.py configs/errors/empty_value.csv
Ошибка конфигурации: строка 2: у параметра 'package_name' пустое значение
$ python main.py configs/errors/missing_key.csv
Ошибка конфигурации: не заданы обязательные параметры: test_mode
$ python main.py configs/errors/bad_test_mode.csv
Ошибка конфигурации: test_mode: недопустимое значение 'maybe', ожидается true или false
$ python main.py configs/errors/bad_package_maven.csv
Ошибка конфигурации: package_name: 'commons-text' — ожидается формат groupId:artifactId[:version], например org.apache.commons:commons-text:1.12.0
$ python main.py configs/errors/bad_package_test.csv
Ошибка конфигурации: package_name: 'a1' — в тестовом режиме имя пакета должно состоять только из больших латинских букв (например, A)
$ python main.py configs/errors/bad_url.csv
Ошибка конфигурации: repository: 'repo1.maven.org/maven2' — ожидается URL со схемой http://, https:// или file://
$ python main.py configs/errors/url_in_test_mode.csv
Ошибка конфигурации: repository: 'https://repo1.maven.org/maven2' — в тестовом режиме нужен путь к файлу, а не URL
$ python main.py configs/errors/missing_repo_file.csv
Ошибка конфигурации: repository: файл тестового репозитория не найден: /…/depviz/tests_repo/no_such_file.txt
```

**Коммит:**

```bash
git add .
git commit
```
```
feat(config): минимальный CLI-прототип с конфигурацией в CSV

- добавлена точка входа main.py
- модуль depviz/config.py читает параметры package_name,
  repository, test_mode из CSV-файла
- проверка всех параметров: заголовок, число столбцов, неизвестные,
  повторные, пустые и отсутствующие ключи, формат имени пакета,
  URL / путь к файлу, значение test_mode
- при запуске параметры выводятся в формате ключ=значение
- примеры ошибочных конфигураций в configs/errors/
```

**Слияние этапа в `main`:**

```bash
git checkout main
git merge --no-ff stage-1 -m "Merge branch 'stage-1'" -m "Этап 1: минимальный прототип с конфигурацией"
```

---

## Этап 2. Сбор данных

**Ветка `stage-2`** (создаётся от `main`):

```bash
git checkout main
git checkout -b stage-2
```

**Создано:** `depviz/maven.py`, `local_maven/` (мини-зеркало), конфиги
`configs/local_*.csv`, `configs/real_*.csv`.
**Изменено:** `main.py` (вместо печати параметров — печать прямых
зависимостей), `depviz/config.py` (поддержка `file:` URL относительно папки
конфига), `README.md`.

Как Maven хранит пакеты: для координат `g:a:v` POM лежит по адресу
`<repo>/<g с заменой . на />/<a>/<v>/<a>-<v>.pom`, а список версий — в
`<repo>/<g>/<a>/maven-metadata.xml`. Класс `MavenRepository`:

1. `_fetch()` — скачивает файл через `urllib.request`, переводит HTTP 404,
   сетевые ошибки и ошибки файловой системы в `MavenError`;
2. `latest_version()` — если версия в `package_name` не указана, берёт
   `<release>` из `maven-metadata.xml`;
3. `_model()` — строит «эффективную модель» POM, как это делает Maven:
   рекурсивно загружает родительский `<parent>`, наследует его свойства,
   `dependencyManagement` и зависимости; подставляет свойства `${...}`
   (`${project.version}`, пользовательские `<properties>`), импортирует
   BOM (`<scope>import</scope>`), берёт недостающую версию и scope
   зависимости из `dependencyManagement`;
4. `direct_dependencies()` — возвращает список `Dependency(group, artifact,
   version, scope, optional)`.

Без этого разбора у многих реальных пакетов (Spring, Jackson) версии
зависимостей были бы пустыми или вида `${...}`, потому что они задаются в
родительских POM/BOM.

Поскольку сеть в среде разработки могла быть недоступна, создано мини-зеркало
`local_maven/` с вымышленными артефактами `com.example`, где специально
собраны все сложные случаи: parent, свойства, dependencyManagement, импорт
BOM, scope `test`/`provided`/`runtime`, `optional`, отсутствующий артефакт и
цикл. Оно подключается URL `file:../local_maven`.

**Демонстрация:**

```
$ python main.py configs/local_app.csv     # версия не указана → из maven-metadata.xml
Прямые зависимости com.example:app:1.0 (6):
  com.example:core:1.5 [compile]           # версия из свойства ${lib.version} родителя
  com.example:json:3.0 [compile]           # версия из dependencyManagement родителя
  com.example:logger:2.1 [compile]         # версия из импортированного BOM
  junit:junit:4.13.2 [test]
  com.example:annotations:1.0 [provided]
  com.example:extras:1.0 [compile] (optional)

$ python main.py configs/local_core.csv
Прямые зависимости com.example:core:1.5 (2):
  com.example:util:1.5 [compile]           # ${project.version}
  com.example:logger:2.0 [compile]

$ python main.py configs/local_missing.csv
Ошибка репозитория: не найдено в репозитории: file:///…/local_maven/com/example/nothing/1.0/nothing-1.0.pom

$ python main.py                           # без доступа к сети
Ошибка репозитория: не удалось подключиться к https://repo1.maven.org/maven2/…: [Errno -2] Name or service not known
```

Реальный репозиторий: `python main.py configs/real_commons_text.csv`
(Maven Central, `org.apache.commons:commons-text:1.12.0`). Запустите при
наличии интернета и вставьте вывод в отчёт.

**Коммиты (в ветке `stage-2`):**

```
feat(maven): получение прямых зависимостей из Maven-репозитория

- модуль depviz/maven.py: загрузка POM и maven-metadata.xml через
  urllib, разбор XML через xml.etree (без менеджеров пакетов и
  сторонних библиотек)
- учёт parent POM, свойств ${...}, dependencyManagement, импорта BOM,
  scope и optional
- поддержка URL file: для локального зеркала (относительно конфига)
- main.py выводит прямые зависимости заданного пакета
- добавлено офлайн-зеркало local_maven/ и примеры конфигов
```

После проверки обнаружилось, что для `file://` отсутствующий файл давал
другое сообщение, чем HTTP 404. Это исправлено отдельным коммитом (правка
одной ветки `except` в `_fetch()`):

```bash
git commit -am "fix(maven): единое сообщение об отсутствии артефакта для file:// URL"
```

**Слияние этапа в `main`:**

```bash
git checkout main
git merge --no-ff stage-2 -m "Merge branch 'stage-2'" -m "Этап 2: сбор данных о зависимостях Maven"
```

---

## Этап 3. Основные операции

**Ветка `stage-3`** (создаётся от `main`):

```bash
git checkout main
git checkout -b stage-3
```

**Создано:** `depviz/graph.py`, `depviz/test_repo.py`, `tests/test_graph.py`,
тестовые репозитории `tests_repo/{cycle,self_loop,complex,bad_names,bad_format}.txt`,
конфиги `configs/test_*.csv`.
**Изменено:** `main.py` (строит граф и печатает дерево), `depviz/maven.py`
(добавлена функция `make_provider`), `README.md`.

**Алгоритм — рекурсивный DFS с трёхцветной разметкой** (`build_graph`):

- `WHITE` — узел ещё не посещён → рекурсивно вызываем `dfs(узел)`;
- `GRAY` — узел находится в текущем стеке рекурсии → найдено обратное ребро,
  т.е. **циклическая зависимость**. Цикл (участок пути от этого узла до
  текущего) сохраняется в `graph.cycles`, ребро — в `graph.back_edges`, и
  **повторный вход не выполняется**, поэтому обход всегда завершается;
- `BLACK` — узел уже полностью обработан (общая зависимость, «ромб») —
  его зависимости заново не загружаются, каждый POM скачивается один раз.

Функция получения зависимостей передаётся параметром, поэтому один и тот же
алгоритм работает и с Maven, и с тестовым файлом. Если зависимости узла
получить не удалось (артефакт отсутствует), ошибка записывается в
`graph.errors`, а обход продолжается.

Для Maven транзитивно учитываются только scope `compile` и `runtime`, без
`optional` — именно эти зависимости получает проект, подключивший пакет
(`test`, `provided`, `system` по правилам Maven не наследуются).

**Тестовый режим.** `test_mode,true`, `repository` — путь к файлу:

```
# комментарий
A: B C      ← A зависит от B и C
D:          ← D без зависимостей
```

`TestRepository` проверяет формат строк, имена (только большие латинские
буквы) и повторное описание пакета.

**Демонстрация на тестовых репозиториях.** `(*)` — узел уже раскрыт выше,
`(цикл)` — обратное ребро, `[ошибка]` — пакет отсутствует.

Ромб без циклов (`tests_repo/simple.txt`):
```
$ python main.py configs/test_simple.csv
A
+- B
|  \- D
\- C
   +- D (*)
   \- E

Узлов: 5, рёбер: 5
```

Цикл из трёх пакетов (`tests_repo/cycle.txt`):
```
$ python main.py configs/test_cycle.csv
A
\- B
   \- C
      +- A (цикл)
      \- D

Узлов: 4, рёбер: 4
Обнаружены циклические зависимости:
  A -> B -> C -> A
```

Пакет зависит сам от себя (`tests_repo/self_loop.txt`):
```
$ python main.py configs/test_self_loop.csv
A
+- A (цикл)
\- B

Узлов: 2, рёбер: 2
Обнаружены циклические зависимости:
  A -> A
```

Сложный граф: общие узлы, два цикла, отсутствующий пакет Z (`tests_repo/complex.txt`):
```
$ python main.py configs/test_complex.csv
A
+- B
|  +- E
|  |  \- I
|  \- F
|     +- I (*)
|     \- J
|        \- F (цикл)
+- C
|  +- F (*)
|  \- G
|     +- B (*)
|     \- K
|        \- L
|           \- K (цикл)
\- D
   +- G (*)
   \- H
      \- Z [ошибка]

Узлов: 13, рёбер: 18
Обнаружены циклические зависимости:
  F -> J -> F
  K -> L -> K
Предупреждение: Z: пакет Z не найден в тестовом репозитории
```

Тот же репозиторий, другой корень — G:
```
$ python main.py configs/test_complex_G.csv
G
+- B
|  +- E
|  |  \- I
|  \- F
|     +- I (*)
|     \- J
|        \- F (цикл)
\- K
   \- L
      \- K (цикл)

Узлов: 8, рёбер: 10
Обнаружены циклические зависимости:
  F -> J -> F
  K -> L -> K
```

Ошибки тестового режима:
```
$ python main.py configs/test_unknown_package.csv
Ошибка репозитория: пакет Q не найден в тестовом репозитории
$ python main.py configs/test_bad_names.csv
Ошибка репозитория: /…/depviz/tests_repo/bad_names.txt, строка 1: 'c' — имя пакета должно состоять из больших латинских букв
$ python main.py configs/test_bad_format.csv
Ошибка репозитория: /…/depviz/tests_repo/bad_format.txt, строка 1: ожидается 'ПАКЕТ: зависимости'
```

Maven (локальное зеркало): `test`, `provided` и `optional` отброшены, цикл
`core ↔ util` обнаружен, отсутствующий `ghost` не прервал анализ:
```
$ python main.py configs/local_app.csv
com.example:app:1.0
+- com.example:core:1.5
|  +- com.example:util:1.5
|  |  \- com.example:core:1.5 (цикл)
|  \- com.example:logger:2.0
+- com.example:json:3.0
|  +- com.example:util:1.5 (*)
|  \- com.example:ghost:1.0 [ошибка]
\- com.example:logger:2.1

Узлов: 7, рёбер: 8
Обнаружены циклические зависимости:
  com.example:core:1.5 -> com.example:util:1.5 -> com.example:core:1.5
Предупреждение: com.example:ghost:1.0: не найдено в репозитории: file:///…/depviz/local_maven/com/example/ghost/1.0/ghost-1.0.pom
```

Модульные тесты: `python -m unittest` (транзитивность, однократное
посещение общего узла, цикл, петля, отсутствующий пакет).

**Коммит:**

```
feat(graph): транзитивный граф зависимостей (рекурсивный DFS)

- depviz/graph.py: рекурсивный DFS с разметкой WHITE/GRAY/BLACK,
  обнаружение циклов (обратных рёбер) без зацикливания обхода
- depviz/test_repo.py: тестовый режим — файл описания графа,
  пакеты называются большими латинскими буквами, проверка формата
- maven.py: провайдер транзитивных зависимостей (compile/runtime,
  без optional)
- main.py выводит дерево зависимостей, число узлов/рёбер, циклы и
  недоступные пакеты
- тестовые репозитории: ромб, цикл, петля, сложный граф, ошибки
- модульные тесты tests/test_graph.py
```

**Слияние этапа в `main`:**

```bash
git checkout main
git merge --no-ff stage-3 -m "Merge branch 'stage-3'" -m "Этап 3: граф зависимостей, DFS, циклы, тестовый режим"
```

---

## Этап 4. Дополнительные операции

**Ветка `stage-4`** (создаётся от `main`):

```bash
git checkout main
git checkout -b stage-4
```

**Изменено:** `depviz/graph.py` (функция `load_order`), `depviz/config.py`
(новый необязательный параметр `output_mode` со значениями `tree` |
`load_order` и его проверкой), `main.py` (ветвление по режиму),
`tests/test_graph.py`, `README.md`.
**Создано:** `configs/order_*.csv`, `configs/errors/bad_output_mode.csv`.

Режим включается строкой `output_mode,load_order` в CSV (источник настроек
по-прежнему только конфигурационный файл).

**Алгоритм.** Порядок загрузки — post-order обход DFS: пакет добавляется в
список *после* всех своих зависимостей. Значит, к моменту загрузки любого
пакета всё, от чего он зависит, уже загружено; корень загружается
последним (это обратный топологический порядок). В цикле топологического
порядка не существует, поэтому обратное ребро пропускается — цикл
«разрывается» в месте обнаружения, и пользователь об этом предупреждается.

**Демонстрация:**

```
$ python main.py configs/order_simple.csv
Порядок загрузки зависимостей для A:
    1. D
    2. B
    3. E
    4. C
    5. A
```
```
$ python main.py configs/order_cycle.csv
Порядок загрузки зависимостей для A:
    1. D
    2. C
    3. B
    4. A
Обнаружены циклические зависимости (обратное ребро цикла при упорядочивании пропущено):
  A -> B -> C -> A
```
```
$ python main.py configs/order_complex.csv
Порядок загрузки зависимостей для A:
    1. I
    2. E
    3. J
    4. F
    5. B
    6. L
    7. K
    8. G
    9. C
   10. Z (недоступен)
   11. H
   12. D
   13. A
Обнаружены циклические зависимости (обратное ребро цикла при упорядочивании пропущено):
  F -> J -> F
  K -> L -> K
Предупреждение: Z: пакет Z не найден в тестовом репозитории
```
```
$ python main.py configs/order_complex_D.csv
Порядок загрузки зависимостей для D:
    1. I
    2. E
    3. J
    4. F
    5. B
    6. L
    7. K
    8. G
    9. Z (недоступен)
   10. H
   11. D
Обнаружены циклические зависимости (обратное ребро цикла при упорядочивании пропущено):
  F -> J -> F
  K -> L -> K
Предупреждение: Z: пакет Z не найден в тестовом репозитории
```
```
$ python main.py configs/order_local_app.csv
Порядок загрузки зависимостей для com.example:app:1.0:
    1. com.example:util:1.5
    2. com.example:logger:2.0
    3. com.example:core:1.5
    4. com.example:ghost:1.0 (недоступен)
    5. com.example:json:3.0
    6. com.example:logger:2.1
    7. com.example:app:1.0
Обнаружены циклические зависимости (обратное ребро цикла при упорядочивании пропущено):
  com.example:core:1.5 -> com.example:util:1.5 -> com.example:core:1.5
Предупреждение: com.example:ghost:1.0: не найдено в репозитории: file:///…/depviz/local_maven/com/example/ghost/1.0/ghost-1.0.pom
```
```
$ python main.py configs/errors/bad_output_mode.csv
Ошибка конфигурации: output_mode: недопустимое значение 'picture', ожидается одно из: d2, tree, load_order
```

### Сравнение с реальным менеджером пакетов (Maven)

Чтобы получить «эталон» Maven для пакета, создаётся пустой проект, который
зависит только от него:

```xml
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>demo</groupId><artifactId>demo</artifactId><version>1</version>
  <dependencies>
    <dependency>
      <groupId>org.apache.commons</groupId>
      <artifactId>commons-text</artifactId>
      <version>1.12.0</version>
    </dependency>
  </dependencies>
</project>
```

```bash
mvn dependency:build-classpath   # порядок classpath
mvn dependency:list              # итоговый набор артефактов
python main.py configs/order_real_commons_text.csv
```

Для небольших пакетов (например, `commons-text`) **набор** артефактов
совпадает. **Расхождения** и их причины:

1. **Смысл порядка.** depviz выдаёт порядок *загрузки*: зависимости раньше
   зависящих (снизу вверх). Maven формирует *classpath* обходом
   разрешённого дерева в прямом порядке (pre-order) по порядку объявления:
   сначала прямые зависимости, потом их зависимости. Это порядок поиска
   классов, а не порядок установки, поэтому он примерно обратный нашему.
2. **Конфликт версий.** Maven оставляет одну версию каждого
   `groupId:artifactId` — по правилу «ближайший побеждает» (nearest wins)
   и с приоритетом `dependencyManagement` корневого проекта. depviz считает
   разные версии разными узлами: в примере `local_app` присутствуют
   `logger:2.0` и `logger:2.1`, а Maven оставил бы только `2.1`.
3. **`<exclusions>`** в depviz не обрабатываются, Maven исключённые ветки
   отбрасывает — у Maven может быть меньше артефактов.
4. **Циклы.** Maven Resolver при сборе транзитивных зависимостей молча
   обрезает цикл (видно только в `dependency:tree -Dverbose`); depviz явно
   сообщает о цикле и указывает, где он был разорван.
5. **Отсутствующий артефакт.** Maven завершает сборку с ошибкой
   «Could not resolve dependencies», depviz помечает пакет как недоступный
   и продолжает анализ.
6. **Диапазоны версий** (`[1.0,2.0)`): Maven выбирает наибольшую подходящую
   версию из `maven-metadata.xml`, depviz упрощённо берёт нижнюю границу.
7. **Профили, классификаторы, relocation** в POM не учитываются.

**Коммит:**

```
feat(order): режим вывода порядка загрузки зависимостей

- graph.load_order(): post-order DFS — зависимости раньше
  зависящих пакетов, цикл разрывается на обратном ребре
- новый необязательный параметр конфигурации output_mode
  (tree | load_order) с проверкой значения
- конфиги-примеры configs/order_*.csv и errors/bad_output_mode.csv
- тесты корректности порядка для ромба и цикла
```

**Слияние этапа в `main`:**

```bash
git checkout main
git merge --no-ff stage-4 -m "Merge branch 'stage-4'" -m "Этап 4: порядок загрузки зависимостей"
```

---

## Этап 5. Визуализация

**Ветка `stage-5`** (создаётся от `main`):

```bash
git checkout main
git checkout -b stage-5
```

**Создано:** `depviz/d2.py`, `tests/test_d2.py`, `configs/d2_*.csv`, `examples/*.d2`.
**Изменено:** `depviz/config.py` (значение `d2` для `output_mode`, теперь это
режим по умолчанию), `main.py`, конфиги этапа 3 (в них явно дописано
`output_mode,tree`, чтобы демонстрации этапа 3 не изменились), конфиги
`real_*.csv` (дописано `output_mode,d2`), `README.md`.

`to_d2()` формирует текст на языке D2: каждое ребро графа — строка
`"A" -> "B"`. Идентификаторы берутся в кавычки (в именах Maven есть `:` и `.`,
которые в D2 имеют особый смысл), кавычки внутри экранируются. Корень
выделен заливкой, ребро, замыкающее цикл, — красным пунктиром с подписью
«цикл», недоступный пакет — красной пунктирной рамкой. Текст печатается на
экран; предупреждения идут в `stderr`, поэтому вывод можно сразу
перенаправить в файл и отрисовать:

```bash
python main.py configs/d2_complex.csv > graph.d2
d2 graph.d2 graph.svg        # или вставить текст на https://play.d2lang.com
```

### Пример 1 — пакет A (`tests_repo/simple.txt`)
```
$ python main.py configs/d2_simple.csv
# Граф зависимостей пакета A
direction: down

"A": {
  style.fill: "#fde68a"
  style.bold: true
}

"A" -> "B"
"A" -> "C"
"B" -> "D"
"C" -> "D"
"C" -> "E"
```

### Пример 2 — пакет A (`tests_repo/complex.txt`, циклы и отсутствующий пакет)
```
$ python main.py configs/d2_complex.csv
# Граф зависимостей пакета A
direction: down

"A": {
  style.fill: "#fde68a"
  style.bold: true
}
"Z": {
  style.stroke: "#dc2626"
  style.stroke-dash: 4
  tooltip: "не удалось получить зависимости"
}

"A" -> "B"
"A" -> "C"
"A" -> "D"
"B" -> "E"
"B" -> "F"
"E" -> "I"
"F" -> "I"
"F" -> "J"
"J" -> "F": "цикл" {
  style.stroke: "#dc2626"
  style.stroke-dash: 3
}
"C" -> "F"
"C" -> "G"
"G" -> "B"
"G" -> "K"
"K" -> "L"
"L" -> "K": "цикл" {
  style.stroke: "#dc2626"
  style.stroke-dash: 3
}
"D" -> "G"
"D" -> "H"
"H" -> "Z"
Цикл: F -> J -> F
Цикл: K -> L -> K
Предупреждение: Z: пакет Z не найден в тестовом репозитории
```

### Пример 3 — пакет com.example:app (Maven, локальное зеркало)
```
$ python main.py configs/d2_local_app.csv
# Граф зависимостей пакета com.example:app:1.0
direction: down

"com.example:app:1.0": {
  style.fill: "#fde68a"
  style.bold: true
}
"com.example:ghost:1.0": {
  style.stroke: "#dc2626"
  style.stroke-dash: 4
  tooltip: "не удалось получить зависимости"
}

"com.example:app:1.0" -> "com.example:core:1.5"
"com.example:app:1.0" -> "com.example:json:3.0"
"com.example:app:1.0" -> "com.example:logger:2.1"
"com.example:core:1.5" -> "com.example:util:1.5"
"com.example:core:1.5" -> "com.example:logger:2.0"
"com.example:util:1.5" -> "com.example:core:1.5": "цикл" {
  style.stroke: "#dc2626"
  style.stroke-dash: 3
}
"com.example:json:3.0" -> "com.example:util:1.5"
"com.example:json:3.0" -> "com.example:ghost:1.0"
Цикл: com.example:core:1.5 -> com.example:util:1.5 -> com.example:core:1.5
Предупреждение: com.example:ghost:1.0: не найдено в репозитории: file:///…/depviz/local_maven/com/example/ghost/1.0/ghost-1.0.pom
```

Дополнительно — реальные пакеты из Maven Central (запускаются при наличии
интернета, полученные рисунки вставляются в отчёт):

```bash
python main.py configs/real_commons_text.csv     > commons-text.d2
python main.py configs/real_jackson_databind.csv > jackson-databind.d2
python main.py configs/real_spring_context.csv   > spring-context.d2
```

### Сравнение со штатными средствами Maven

Штатные средства — `mvn dependency:tree` (текстовое дерево) и
`mvn dependency:tree -DoutputType=dot -DoutputFile=tree.dot` (граф Graphviz),
запускаемые на demo-проекте из этапа 4. Расхождения:

1. **Дерево vs граф.** Maven выводит *дерево*: общая зависимость показывается
   один раз, остальные вхождения опускаются (видны только с `-Dverbose`).
   В D2 это *граф*: общий узел один, но к нему ведут все рёбра (ромб
   `B → D ← C` виден явно).
2. **Версии.** Maven показывает дерево после разрешения конфликтов (одна
   версия на артефакт), depviz — «сырой» граф со всеми объявленными версиями.
3. **Scope.** Maven подписывает узлы scope (`:compile`, `:runtime`) и для
   самого проекта показывает и `test`-зависимости; depviz рисует только то,
   что попадает к потребителю пакета (`compile`/`runtime` без `optional`).
4. **Циклы и ошибки.** Maven цикл обрезает молча, а при отсутствии артефакта
   дерево не строится вообще; в D2 цикл и недоступный пакет выделены цветом.
5. **Исключения (`exclusions`)** — см. этап 4, п. 3.
6. **Корень.** В выводе Maven корнем является demo-проект, у depviz —
   сам анализируемый пакет.

**Коммит:**

```
feat(d2): визуализация графа зависимостей на языке D2

- depviz/d2.py: генерация описания графа на D2 (корень выделен,
  циклические рёбра и недоступные пакеты помечены стилем)
- output_mode=d2 стал режимом по умолчанию; демонстрационные
  конфиги этапа 3 явно используют output_mode=tree
- конфиги configs/d2_*.csv, конфиги реальных пакетов дополнены
  output_mode=d2, примеры результата в examples/*.d2
- тесты генерации D2
```

**Слияние этапа в `main`:**

```bash
git checkout main
git merge --no-ff stage-5 -m "Merge branch 'stage-5'" -m "Этап 5: визуализация на языке D2"
```

---

## Публикация

```bash
git remote add origin https://github.com/<логин>/depviz.git
git push -u origin main stage-1 stage-2 stage-3 stage-4 stage-5 docs
```
