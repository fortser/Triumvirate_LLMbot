# 🔍 Комплексный код ревью — Triumvirate LLM Bot v2.2

> **Дата:** 2026-03-09  
> **Версия проекта:** 2.2.0  
> **Объём кода:** ~4500 строк, 20+ файлов  
> **Эксперты:** Архитектор ПО, Сетевой инженер, Специалист по ИИ/LLM, Специалист по безопасности, QA-инженер, DevOps/SRE, UX/UI-эксперт, Перформанс-инженер

---

# 📊 Общая оценка по экспертам

| Эксперт | Оценка | Комментарий |
|---------|--------|-------------|
| 🏗️ Архитектор | 6/10 | Хорошая модульную декомпозицию, но God-класс `bot_runner` и монолитный `gui.py` |
| 🌐 Сетевой инженер | 4/10 | Критическая проблема с connection pooling, отсутствие backoff |
| 🤖 ИИ/LLM | 8/10 | Отличная система промптов, надёжный парсинг, хорошая эскалация |
| 🔒 Безопасность | 5/10 | API-ключи в plaintext, потенциальные инъекции |
| 🧪 QA | 3/10 | Полное отсутствие тестов, множество молчащих ошибок |
| ⚙️ DevOps/SRE | 4/10 | Нет logging, нет ротации логов, нет graceful shutdown |
| 🎨 UX/UI | 7/10 | Хороший GUI, но есть проблемы с обратной связью |
| ⚡ Перформанс | 5/10 | Polling вместо WS, пересборка textarea, memory issues |

---

# 🔴 КРИТИЧЕСКИЕ ОШИБКИ

## CRIT-01: Новый HTTP-клиент создаётся на КАЖДЫЙ запрос (connection leak)

**Файлы:** [llm_client.py](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/llm_client.py#L64), [arena_client.py](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/arena_client.py#L27-L78)  
**Эксперты:** 🌐 Сетевой инженер, ⚡ Перформанс

### Описание проблемы
В проекте **12 мест**, где создаётся новый `httpx.AsyncClient` через `async with httpx.AsyncClient(...) as c:`. Каждый вызов метода (каждый ход бота, каждый опрос состояния) открывает новое TCP-соединение, проходит заново TLS-рукопожатие и закрывает соединение после использования.

### Причины проблемы
1. HTTP-клиент в `arena_client.py` не сохраняется как атрибут класса — каждый из 7 методов (`health`, `join`, `get_state`, `make_move`, `skip_waiting`, `resign`, `list_games`) создаёт свой клиент
2. `LLMClient.ask()` создаёт клиент на каждый LLM-запрос 
3. В типичной партии из 30 ходов с polling-интервалом 0.5с это означает **~200+ создаваемых и уничтожаемых TCP-соединений**

### Как исправлять
Создать один `httpx.AsyncClient` при инициализации класса и переиспользовать его:

```python
class ArenaClient:
    def __init__(self, server_url: str) -> None:
        self._base = server_url.rstrip("/") + "/api/v1"
        self._client = httpx.AsyncClient(timeout=30)  # Один клиент
        # ...
    
    async def close(self) -> None:
        await self._client.aclose()  # Явное закрытие
    
    async def get_state(self) -> dict:
        r = await self._client.get(f"{self._base}/state", headers=self._headers)
        r.raise_for_status()
        return r.json()
```

### Ожидаемый результат
- Снижение сетевых задержек на ~50-100мс на каждый запрос (экономия TLS handshake)
- Уменьшение нагрузки на сервер
- Корректное переиспользование TCP Keep-Alive соединений

---

## CRIT-02: API-ключи хранятся в открытом виде в JSON-файле

**Файл:** [settings.py](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/settings.py#L219-L232)  
**Эксперты:** 🔒 Безопасность

### Описание проблемы
Метод `Settings.save()` записывает все настройки, **включая API-ключи**, в plaintext JSON-файл `llm_bot_gui_settings_v2.json`. Любой, кто имеет доступ к файловой системе пользователя, может извлечь ключи для OpenAI, Anthropic и OpenRouter.

### Причины проблемы
1. В словаре `DEFAULTS` есть ключ `"api_key": ""` (строка 152)
2. Метод `_collect()` в `gui.py` (строка 111) записывает API-ключ в settings: `settings["api_key"] = api_key_ui`
3. Метод `save()` не фильтрует `api_key` из сохраняемых данных
4. Файл сохраняется без какого-либо шифрования

### Как исправлять
1. **Минимальное решение:** Исключить `api_key` из JSON при сохранении, всегда загружать из переменных окружения:
```python
def save(self) -> None:
    to_save = {
        k: v for k, v in self._d.items()
        if k not in _LEGACY_PROMPT_KEYS and k != "api_key"  # Не сохранять ключ
    }
```
2. **Рекомендованное:** Использовать `keyring` (cross-platform), ОС-хранилище или `.env` файл с правильными `chmod 600` правами

### Ожидаемый результат
API-ключи не будут утекать через конфигурационный файл, который может быть случайно закоммичен в Git или скопирован

---

## CRIT-03: Молчащие ошибки — `except Exception: pass`

**Файлы:** [tracer.py:185](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/tracer.py#L185), [settings.py:178,231](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/settings.py#L178), [pricing.py:86](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/pricing.py#L86), [arena_client.py:61](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/arena_client.py#L61), [data_loader.py:29](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/trace_analyzer/data_loader.py#L29)  
**Эксперты:** 🧪 QA, ⚙️ DevOps/SRE

### Описание проблемы
В проекте **5 мест** с паттерном `except Exception: pass` — когда ошибка полностью проглатывается без логирования. Это означает, что при возникновении проблемы (полный диск, повреждённый JSON, ошибка сети) пользователь **никогда не узнает** о проблеме, а данные молча потеряются.

### Причины проблемы
Критические случаи:
1. **`tracer.py:185`** — если запись trace-лога на диск не удаётся (полный диск, нет прав), trace молча теряется. Пользователь думает, что логи записываются, но они не записываются
2. **`settings.py:231`** — если настройки не удаётся сохранить, пользователь нажимает «Сохранить», получает подтверждение, но файл не записался
3. **`settings.py:178`** — при загрузке повреждённого JSON настройки молча сбрасываются на дефолтные

### Как исправлять
Минимально — добавить логирование ошибки:
```python
# tracer.py
except Exception as e:
    # Как минимум, вывести предупреждение
    import sys
    print(f"WARNING: Failed to save trace: {e}", file=sys.stderr)
```
Рекомендованно — пробрасывать ошибку вызывающему коду или использовать `logging.warning()`.

### Ожидаемый результат
Пользователь будет видеть сообщения об ошибках записи данных и сможет принять меры (освободить место, проверить права)

---

## CRIT-04: Полное отсутствие автоматических тестов

**Файлы:** весь проект  
**Эксперты:** 🧪 QA

### Описание проблемы
В проекте **нет ни одного** unit-теста, integration-теста или smoke-теста. Для проекта с 4500 строками кода и сложной логикой (парсинг JSON, конвертация нотаций, retry-стратегии) это критический риск.

### Причины проблемы
1. Нет папки `tests/`
2. Нет `pytest` в зависимостях
3. Нет CI/CD конфигурации

### Как исправлять
Начать с наиболее рискованных модулей:
- `move_parser.py` — парсинг LLM-ответов (множество edge cases)
- `notation_converter.py` — математическая конвертация (легко тестируется, высокий risk)
- `prompt_builder.py` — сборка промптов (валидация подстановки)
- `pricing.py` — расчёт стоимости (математика)

### Ожидаемый результат
Покрытие критических модулей тестами снижает риск регрессий при любых изменениях кода

---

# 🟠 ВАЖНЫЕ ПРОБЛЕМЫ

## HIGH-01: God-класс `BotRunner` — 837 строк с 10+ ответственностями

**Файл:** [bot_runner.py](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/bot_runner.py)  
**Эксперты:** 🏗️ Архитектор

### Описание проблемы
Класс `BotRunner` содержит **837 строк кода** и совмещает множество ответственностей: оркестрация игрового цикла, управление retry-логикой, сбор статистики, диагностический JSON-парсинг, логирование, обработка HTTP-кодов ответов.

Метод `_choose_move()` занимает **~400 строк** и содержит вложенную логику в 5+ уровней глубины. Метод `_run()` — ещё ~300 строк с аналогичной проблемой.

### Причины проблемы
1. Диагностический JSON-парсинг (строки 634-722) дублирует логику `move_parser.py`
2. Обработка HTTP-кодов (строки 338-386) встроена прямо в основной цикл
3. Сбор статистики (строки 59-73, 396-432) размазан по всему файлу

### Как исправлять
Извлечь ответственности в отдельные классы/функции:
- `DiagnosticLogger` — диагностический JSON-парсинг
- `MoveResponseHandler` — обработка HTTP-ответов от сервера
- `StatsCollector` — сбор и вывод статистки

### Ожидаемый результат
Снижение `BotRunner` до ~300 строк, улучшение тестируемости и читаемости

---

## HIGH-02: Монолитная функция `create_gui()` — 738 строк

**Файл:** [gui.py](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/gui.py#L29)  
**Эксперты:** 🏗️ Архитектор, 🎨 UX/UI

### Описание проблемы
Вся GUI-логика находится внутри **одной функции** `create_gui()`, длиной 710 строк. Внутри неё определены 15+ вложенных функций (callback-обработчики) и 100+ UI-элементов. Это делает код:
- Нетестируемым (невозможно протестировать отдельный callback)
- Сложным для навигации и поддержки
- Невозможным для переиспользования компонентов

### Причины проблемы
NiceGUI поощряет декларативный стиль, но не обязывает упаковывать всё в одну функцию. Код органически рос без рефакторинга.

### Как исправлять
Разбить на компоненты:
- `gui_settings_panel.py` — левая панель настроек (строки 349-583)
- `gui_game_panel.py` — правая панель с вкладками (строки 584-708)
- `gui_callbacks.py` — обработчики кнопок (строки 178-313)

### Ожидаемый результат
Улучшение читаемости, поддержки и тестируемости GUI

---

## HIGH-03: Загрузка полного каталога моделей OpenRouter

**Файл:** [pricing.py](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/pricing.py#L60-L81)  
**Эксперты:** 🌐 Сетевой инженер, ⚡ Перформанс

### Описание проблемы
Метод `fetch_openrouter()` загружает **весь каталог** моделей OpenRouter (`/api/v1/models`) — потенциально **200+ моделей** с их описаниями — чтобы найти одну по ID. Это избыточный трафик (**~500KB-1MB** данных) при старте бота.

### Причины проблемы
OpenRouter предоставляет только bulk-endpoint для моделей, но есть возможность использовать параметр `?id=model_name` или кэшировать результат.

### Как исправлять
1. Использовать endpoint для конкретной модели (если доступен)
2. Кэшировать данные каталога локально с TTL (~1 час)
3. Как минимум — параметризировать `?limit=1&id={model}` если API поддерживает

### Ожидаемый результат
Снижение объёма загружаемых данных на 90%+, ускорение старта бота

---

## HIGH-04: `Settings._file` — class-level мутация нарушает multi-instance

**Файл:** [main.py:54](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/main.py#L54), [settings.py:144](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/settings.py#L144)  
**Эксперты:** 🏗️ Архитектор, 🧪 QA

### Описание проблемы
При запуске с `--settings bot_gpt4.json`, строка `Settings._file = Path(args.settings)` мутирует **class-level атрибут**. Это означает, что ВСЕ последующие экземпляры `Settings()` будут использовать этот файл. Если бы кто-то создал два экземпляра `Settings` в одном процессе — они бы неожиданно делили один файл.

### Причины проблемы
`_file` объявлен как `_file: Path = SETTINGS_FILE` на уровне класса, но мутируется через класс `Settings._file = Path(args.settings)`, а не через экземпляр.

### Как исправлять
Передавать путь через конструктор `Settings(path=Path(args.settings))` вместо мутации class-level атрибута.

### Ожидаемый результат
Каждый экземпляр Settings будет иметь свой собственный путь к файлу

---

## HIGH-05: Отсутствие graceful shutdown — ресурсы не освобождаются

**Файл:** [bot_runner.py](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/bot_runner.py#L389-L395)  
**Эксперты:** ⚙️ DevOps/SRE, 🌐 Сетевой инженер

### Описание проблемы
При остановке бота (`stop()` или `CancelledError`) нет явного закрытия HTTP-клиентов и сетевых ресурсов. В блоке `finally` (строка 394) только выставляется `self._running = False` и выводится статистика. Если будет реализован persistent HTTP-клиент (CRIT-01), без `close()` произойдёт утечка ресурсов.

### Причины проблемы
Сейчас каждый `AsyncClient` создаётся и уничтожается в `async with` блоке, поэтому утечки формально нет. Но это маскирует архитектурную проблему — нет единого lifecycle management.

### Как исправлять
Добавить метод `async def cleanup()` в `BotRunner`, вызывать его в `finally` блоке `_run()`.

### Ожидаемый результат
Корректное освобождение всех ресурсов при остановке бота

---

## HIGH-06: Отсутствие exponential backoff при retry

**Файл:** [bot_runner.py:493-534](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/bot_runner.py#L493-L534)  
**Эксперты:** 🌐 Сетевой инженер, 🤖 ИИ/LLM

### Описание проблемы
Retry-логика при неудачном ходе повышает только температуру (`retry_temp = min(base_temperature + attempt * 0.2, 1.0)`), но **не делает паузу** между попытками для LLM-запросов. Единственная пауза в 1 секунду — только при исключении (строка 731). Для API с rate limits это может привести к 429 ошибкам.

### Причины проблемы
Retry-логика спроектирована только для улучшения качества ответа (повышение температуры), но не для защиты от перегрузки API.

### Как исправлять
Добавить экспоненциальный backoff: `await asyncio.sleep(min(2 ** attempt * 0.5, 8))` после каждого неудачного LLM-вызова.

### Ожидаемый результат
Бот не будет получать 429 от LLM-провайдеров при быстрых retry

---

## HIGH-07: Обновление textarea O(n) на каждый лог

**Файл:** [gui.py:37-47](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/gui.py#L37-L47)  
**Эксперты:** ⚡ Перформанс, 🎨 UX/UI

### Описание проблемы
Каждый вызов `_log()` пересобирает **весь текст** лога через `"\n".join(_log_lines)` и устанавливает его как значение textarea. При 2000 строк лога это означает пересборку строки из ~100KB+ текста на **каждое** событие, что может составлять десятки раз в секунду.

### Причины проблемы
NiceGUI textarea не поддерживает инкрементальное обновление (append), поэтому разработчик вынужден пересобирать весь текст.

### Как исправлять
1. Использовать `ui.log()` виджет NiceGUI — он поддерживает `push()` для инкрементального добавления
2. Или ограничить частоту обновления UI (debounce ~100мс)

### Ожидаемый результат
Снижение CPU-нагрузки GUI в 10-50x при длительных партиях

---

# 🟡 СРЕДНИЕ ПРОБЛЕМЫ

## MED-01: Нет стандартного logging — только callback-строки

**Файлы:** Все модули  
**Эксперты:** ⚙️ DevOps/SRE, 🧪 QA

Ни один модуль не использует стандартный модуль `logging` Python. Вся «логика логирования» реализована через callback-функцию `on_log`, передаваемую в `BotRunner`. Это означает:
- Невозможно настроить уровни логирования (DEBUG/INFO/WARNING/ERROR)
- Нет ротации log-файлов
- Нет вывода в файл без GUI
- Нет структурированного логирования

**Рекомендация:** Внедрить `logging.getLogger(__name__)` в каждый модуль, а GUI-callback сделать дополнительным handler.

---

## MED-02: Нет ротации trace-логов

**Файл:** [tracer.py:172-186](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/tracer.py#L172-L186)  
**Эксперты:** ⚙️ DevOps/SRE

Trace-файлы `move_*.json` неограниченно накапливаются в `logs/`. При 30 ходах/игру и ~10KB/ход, за 100 игр — 30МБ. Нет механизма очистки старых логов.

**Рекомендация:** Добавить конфигурируемый лимит на количество сохраняемых игр или общий размер директории логов.

---

## MED-03: Дублирование JSON-парсинга между `bot_runner.py` и `move_parser.py`

**Файлы:** [bot_runner.py:634-722](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/bot_runner.py#L634-L722), [move_parser.py:171-212](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/move_parser.py#L171-L212)  
**Эксперты:** 🏗️ Архитектор

Диагностический JSON-разбор в `bot_runner._choose_move()` (строки 634-722) фактически **дублирует** логику `MoveParser._from_json()`:
- Оба ищут `{` и `}` в строке
- Оба вызывают `_sanitize_json_string()`
- Оба проверяют наличие `move_from`/`move_to` ключей

**Рекомендация:** Перенести диагностику в `MoveParser`, чтобы парсер возвращал структурированный результат с диагностической информацией, а не только `None`.

---

## MED-04: `_fill_template` заменяет и `{{key}}` и `{key}` — неоднозначность

**Файл:** [prompt_builder.py:117-122](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/prompt_builder.py#L117-L122)  
**Эксперты:** 🤖 ИИ/LLM, 🧪 QA

```python
def _fill_template(self, template: str, subs: dict) -> str:
    result = template
    for key, value in subs.items():
        result = result.replace(f"{{{{{key}}}}}", value)  # {{key}}
        result = result.replace(f"{{{key}}}", value)       # {key}
    return result
```

Замена `{key}` (одинарные скобки) может непреднамеренно заменить часть JSON-примеров в промпте, например `{"move_from": "E2"}` — здесь `{` и `}` — это часть JSON, а не плейсхолдер.

**Рекомендация:** Убрать замену `{key}` и использовать только `{{key}}`.

---

## MED-05: GUI обращается к приватным атрибутам `runner._running`

**Файл:** [gui.py:180](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/gui.py#L180)  
**Эксперты:** 🏗️ Архитектор

```python
if runner and runner._running:
```

GUI напрямую обращается к приватному атрибуту `_running` класса `BotRunner`. Это нарушает инкапсуляцию.

**Рекомендация:** Добавить свойство `@property is_running` в `BotRunner`.

---

## MED-06: `ArenaClient.make_move()` не проверяет `raise_for_status()` 

**Файл:** [arena_client.py:51-63](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/arena_client.py#L51-L63)  
**Эксперты:** 🌐 Сетевой инженер, 🧪 QA

В отличие от всех других методов (`join`, `get_state`, `resign`), метод `make_move()` **не вызывает** `r.raise_for_status()`. Вместо этого он возвращает кортеж `(status_code, data)` и перекладывает обработку ошибок на вызывающий код. Это непоследовательный API-контракт внутри одного класса.

**Рекомендация:** Либо все методы возвращают `(status_code, data)`, либо все используют `raise_for_status()`.

---

## MED-07: Нет подтверждения для деструктивных действий

**Файл:** [gui.py:198-209](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/gui.py#L198-L209)  
**Эксперты:** 🎨 UX/UI

Кнопка «Сдаться» (`on_resign`) сразу отправляет запрос на сервер без подтверждения. В шахматной партии это необратимое действие.

**Рекомендация:** Добавить диалог подтверждения `ui.dialog()` перед отправкой resign.

---

## MED-08: Потенциальная JS-инъекция через clipboard

**Файл:** [gui.py:680-682](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/gui.py#L680-L682)  
**Эксперты:** 🔒 Безопасность

```python
ui.run_javascript(
    f"navigator.clipboard.writeText({json.dumps(text)})"
)
```

Хотя `json.dumps()` экранирует большинство спецсимволов, LLM-ответы могут содержать произвольный текст, который теоретически может сломать JavaScript-контекст.

**Рекомендация:** Использовать NiceGUI's встроенные механизмы для работы с clipboard, если доступны.

---

## MED-09: Trace analyzer загружает ВСЕ файлы в память

**Файл:** [data_loader.py:13-32](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/trace_analyzer/data_loader.py#L13-L32)  
**Эксперты:** ⚡ Перформанс

`scan_traces()` рекурсивно читает **все** `move_*.json` файлы и хранит их в памяти. С полными `raw_trace` (оригинальные данные), при 1000+ ходах это может потребовать сотни мегабайт RAM.

**Рекомендация:** Реализовать ленивую загрузку `raw_trace` (только по запросу) или пагинацию.

---

## MED-10: `_extract_thinking()` берёт thinking только из первого ответа

**Файл:** [data_loader.py:115-142](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/trace_analyzer/data_loader.py#L115-L142)  
**Эксперты:** 🤖 ИИ/LLM

```python
raw_resp = responses[0].get("raw_response", "")
```

Если первая попытка LLM не распарсилась и бот сделал retry, thinking из **успешной** (последней) попытки будет проигнорирован, а отображаться будет thinking из неудачной первой.

**Рекомендация:** Брать thinking из последнего LLM-ответа с валидным `move_selected`, или из ответа с наибольшим thinking.

---

# 🔵 НИЗКОПРИОРИТЕТНЫЕ ПРОБЛЕМЫ

## LOW-01: Polling вместо WebSocket для отслеживания состояния

**Файл:** [bot_runner.py:153-177, 181-188](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/bot_runner.py#L153-L177)  
**Эксперты:** ⚡ Перформанс, 🌐 Сетевой инженер

Бот использует `asyncio.sleep(poll_interval)` + HTTP GET для отслеживания чьей очереди ходить. WebSocket-подключение снизило бы задержку и нагрузку на сервер. `websockets` уже указан как опциональная зависимость.

---

## LOW-02: Нет автоскролла в log textarea

**Файл:** [gui.py:667-676](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/gui.py#L667-L676)  
**Эксперты:** 🎨 UX/UI

Textarea лога не скроллится автоматически к последней строке. Если лог длинный, пользователь должен вручную прокручивать вниз.

**Рекомендация:** Добавить `ui.run_javascript('...')` для автоскролла при каждом обновлении.

---

## LOW-03: `make_bot_name` обрезает имя до 80 символов без предупреждения

**Файл:** [constants.py:92-93](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/constants.py#L92-L93)  
**Эксперты:** 🧪 QA

```python
if len(name) > 80:
    name = name[:80]
```

Имя обрезается молча, без уведомления. При очень длинных именах моделей это может создать коллизии.

---

## LOW-04: `os.environ` для API-ключей проверяется только при смене провайдера

**Файлы:** [gui.py:109-110, 152-157](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/gui.py#L109-L110)  
**Эксперты:** 🎨 UX/UI, 🔒 Безопасность

Переменные окружения для API-ключей проверяются только в `_collect()` (при нажатии Start) и при смене провайдера. Если пользователь установит переменную после запуска приложения, она не подхватится до смены провайдера.

---

## LOW-05: Неиспользуемый `instance_label` при запуске без `--settings`

**Файл:** [main.py:57-58](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/main.py#L57-L58)  
**Эксперты:** 🧪 QA

```python
instance_label = (
    f" [{Settings._file.stem}]" if args.settings else ""
)
```

Переменная `instance_label` вычисляется всегда, но используется только для заголовка окна. Мелочь, но стоит отметить.

---

## LOW-06: Hints в `_on_fmt` используют legacy ключи `from/to`

**Файл:** [gui.py:170-174](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/gui.py#L170-L174)  
**Эксперты:** 🤖 ИИ/LLM

```python
hints = {
    "json": 'Ответ: {"from":"E2","to":"E4"}',
    "json_thinking": 'Ответ: {"thinking":"…","from":"E2","to":"E4"}',
}
```

Хинты в GUI показывают legacy ключи `from/to`, тогда как актуальный формат использует `move_from/move_to`. Это может путать пользователя.

---

## LOW-07: `_PIECE_SYMBOL` определяется внутри метода при каждом вызове

**Файл:** [prompt_builder.py:158-163](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/prompt_builder.py#L158-L163)  
**Эксперты:** ⚡ Перформанс

Словарь `_PIECE_SYMBOL` создаётся заново при каждом вызове `_fmt_board_tri()` (каждый ход). Стоит вынести на уровень модуля.

---

## LOW-08: `_TRI_PROMO` словарь создаётся при каждом вызове `_norm_promo`

**Файл:** [move_parser.py:255-258](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/move_parser.py#L255-L258)  
**Эксперты:** ⚡ Перформанс

Аналогично LOW-07, словарь `_TRI_PROMO` создаётся заново при каждом вызове метода.

---

## LOW-09: Отсутствие `requirements.txt` в корне проекта бота

**Файл:** корень `decomp/`  
**Эксперты:** ⚙️ DevOps/SRE

Нет файла `requirements.txt` или `pyproject.toml` для основного бота. Зависимости (`nicegui`, `httpx`) указаны только в docstring `main.py`.

---

## LOW-10: Trace analyzer — hardcoded `show=True` в `ui.run()`

**Файл:** [trace_analyzer/app.py:195](file:///t:/test_python/Triumvirate_LLMbot/examples/decomp/trace_analyzer/app.py#L195)  
**Эксперты:** ⚙️ DevOps/SRE

`show=True` открывает браузер автоматически — неудобно при headless-деплое.

---

# 📈 Рекомендации по оптимизации

## OPT-01: Connection Pooling
Создать единый `httpx.AsyncClient` для Arena API и один для LLM API. Использовать `limits=httpx.Limits(max_connections=5)` для ограничения.

## OPT-02: WebSocket вместо Polling
Заменить `asyncio.sleep() + GET /state` на WebSocket-подключение к серверу. Это снизит задержку отклика и нагрузку на сервер на 90%+.

## OPT-03: NiceGUI `ui.log()` вместо `ui.textarea`
Виджет `ui.log()` поддерживает инкрементальное добавление строк (`push()`), что устранит O(n) пересборку текста.

## OPT-04: Кэширование каталога моделей OpenRouter
Сохранять каталог в JSON-файл с TTL. При повторном запуске с тем же провайдером — читать из кэша.

## OPT-05: Ленивая загрузка в trace_analyzer
Загружать только мета-данные (game_id, move_number, outcome, cost) при запуске. Полный `raw_trace` — только по клику на «Move Detail».

## OPT-06: Параллельные retry к LLM
Для некоторых провайдеров можно отправлять несколько запросов параллельно с разной температурой и брать первый валидный ответ.

---

# ✅ Рекомендации по лучшим практикам

## BP-01: Использовать стандартный `logging`
```python
import logging
logger = logging.getLogger(__name__)
```
Это обеспечит уровни логирования, ротацию, вывод в файл и интеграцию с внешними системами.

## BP-02: Типизация и dataclasses
Заменить `dict` для Settings на `@dataclass` или `pydantic.BaseModel` — это даст валидацию типов, автокомплит и документацию полей.

## BP-03: Интерфейсы/протоколы для DI
Определить `Protocol` для `LLMClient`, `ArenaClient` — это позволит создавать моки для тестов.

## BP-04: Конфигурация через `.env` / env vars
API-ключи должны загружаться ТОЛЬКО из переменных окружения или `.env` файла (через `python-dotenv`), никогда не сохраняться в JSON.

## BP-05: CI/CD pipeline
Добавить GitHub Actions / GitLab CI с:
- `pytest` (когда тесты будут добавлены)
- `ruff` / `flake8` для lint
- `mypy` для проверки типов

## BP-06: Добавить `requirements.txt`
```
nicegui>=2.0
httpx>=0.25
```

## BP-07: Docstrings для всех публичных методов
Несколько методов (`_on_state`, `_collect`, `_on_provider`) не имеют docstring.

## BP-08: Error boundaries в GUI
Обернуть callback'и в `try/except` с пользовательским уведомлением, чтобы ошибка в одном callback'е не сломала весь GUI.

## BP-09: Prometheus / StatsD метрики
Для production-деплоя — экспортировать метрики (moves/sec, retry rate, cost/move) через Prometheus endpoint.

## BP-10: Версионирование trace-формата
Добавить поле `"trace_version": "2.2"` в каждый trace-файл. Если формат изменится, `data_loader` сможет корректно мигрировать старые файлы.

---

# 📊 Сводная таблица всех находок

| ID | Уровень | Эксперт(ы) | Файл(ы) | Краткое описание |
|----|---------|------------|---------|-----------------|
| CRIT-01 | 🔴 Крит | Сеть, Перф | llm_client, arena_client | Новый HTTP-клиент на каждый запрос |
| CRIT-02 | 🔴 Крит | Без | settings | API-ключи в plaintext JSON |
| CRIT-03 | 🔴 Крит | QA, DevOps | 5 файлов | `except Exception: pass` — молчащие ошибки |
| CRIT-04 | 🔴 Крит | QA | весь проект | Нет ни одного теста |
| HIGH-01 | 🟠 Важн | Арх | bot_runner | God-класс 837 строк |
| HIGH-02 | 🟠 Важн | Арх, UX | gui | Монолитная функция 738 строк |
| HIGH-03 | 🟠 Важн | Сеть, Перф | pricing | Загрузка всего каталога OpenRouter |
| HIGH-04 | 🟠 Важн | Арх, QA | main, settings | Class-level мутация `_file` |
| HIGH-05 | 🟠 Важн | DevOps, Сеть | bot_runner | Нет graceful shutdown |
| HIGH-06 | 🟠 Важн | Сеть, ИИ | bot_runner | Нет backoff при retry |
| HIGH-07 | 🟠 Важн | Перф, UX | gui | O(n) обновление textarea |
| MED-01 | 🟡 Сред | DevOps, QA | все | Нет стандартного logging |
| MED-02 | 🟡 Сред | DevOps | tracer | Нет ротации trace-логов |
| MED-03 | 🟡 Сред | Арх | bot_runner, move_parser | Дублирование JSON-парсинга |
| MED-04 | 🟡 Сред | ИИ, QA | prompt_builder | Неоднозначная замена `{key}` |
| MED-05 | 🟡 Сред | Арх | gui | Доступ к приватному `_running` |
| MED-06 | 🟡 Сред | Сеть, QA | arena_client | Непоследовательный API-контракт |
| MED-07 | 🟡 Сред | UX | gui | Нет подтверждения resign |
| MED-08 | 🟡 Сред | Без | gui | Потенциальная JS-инъекция |
| MED-09 | 🟡 Сред | Перф | data_loader | Все traces в памяти |
| MED-10 | 🟡 Сред | ИИ | data_loader | Thinking из первого ответа |
| LOW-01 | 🔵 Низ | Перф, Сеть | bot_runner | Polling вместо WebSocket |
| LOW-02 | 🔵 Низ | UX | gui | Нет автоскролла лога |
| LOW-03 | 🔵 Низ | QA | constants | Молчаливое обрезание имени |
| LOW-04 | 🔵 Низ | UX, Без | gui | ENV проверяется не всегда |
| LOW-05 | 🔵 Низ | QA | main | Мелочь: instance_label |
| LOW-06 | 🔵 Низ | ИИ | gui | Legacy ключи в GUI hints |
| LOW-07 | 🔵 Низ | Перф | prompt_builder | Dict создаётся в методе |
| LOW-08 | 🔵 Низ | Перф | move_parser | Dict создаётся в методе |
| LOW-09 | 🔵 Низ | DevOps | — | Нет requirements.txt |
| LOW-10 | 🔵 Низ | DevOps | trace_analyzer/app | show=True hardcoded |

**Итого: 4 критических, 7 важных, 10 средних, 10 низких = 31 находка**

---

# 🏆 Положительные стороны проекта

Несмотря на найденные проблемы, проект имеет ряд сильных сторон:

1. **Отличная модульная декомпозиция** — плоская структура, без циклических зависимостей
2. **Продуманная система промптов** — файловые шаблоны + плейсхолдеры + эскалация
3. **Надёжный двойной парсинг** — JSON + regex fallback
4. **Полная трассировка** — каждый ход записывается с исчерпывающей информацией
5. **Хороший GUI** — информативный, с 3 вкладками и диагностикой
6. **Поддержка 6+ LLM-провайдеров** — универсальность
7. **Конвертер нотаций** — чистая реализация с O(1) lookup
8. **Миграция legacy настроек** — обратная совместимость
