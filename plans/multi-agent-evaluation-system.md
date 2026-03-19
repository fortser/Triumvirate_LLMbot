# Мульти-агентная система оценки LLM-моделей

## Принятые решения

### Решение 1: Архитектура "2 агента + 1 Python-модуль"

Вместо одного монолитного агента широкого профиля принята трёхкомпонентная архитектура:

| Компонент | Тип | Роль |
|-----------|-----|------|
| `trace_analyzer/metrics.py` | Python-модуль (детерминированный) | Парсинг трейсов, автоматические метрики, агрегация |
| Agent 1: **Model Evaluator** | Claude Code skill (LLM-based) | Шахматная оценка качества модели |
| Agent 2: **Prompt Optimizer** | Claude Code skill (LLM-based) | Анализ промптов, рекомендации по оптимизации |

**Причины выбора:**

1. **Детерминированное отделено от стохастического.** `metrics.py` даёт одинаковый результат при каждом запуске. Агенты стохастичны. Смешивание в одном pipeline делает результаты невоспроизводимыми.

2. **Разные профили экспертизы.** Model Evaluator — эксперт по шахматной стратегии Three-Player Chess. Prompt Optimizer — эксперт по prompt engineering и поведению LLM. Один system prompt не может быть одновременно хорош в обоих.

3. **Контекстное окно.** 1719 трейсов, 28 моделей, 62 игры — загрузка всего в один контекст невозможна. Модуль metrics.py агрегирует данные, агенты работают с компактными сводками.

4. **Независимость вызова.** Каждый компонент полезен сам по себе. Не обязательно запускать всё.

### Решение 2: Данные текут в одном направлении

```
metrics.py → Model Evaluator → Prompt Optimizer
 (факты)       (суждения)        (рекомендации)
```

Каждый следующий слой обогащает предыдущий. Prompt Optimizer может работать без Evaluator'а (только на автометриках), но работает лучше с его результатами.

### Решение 3: Кеширование LLM-оценок

Результаты агентов сохраняются в файлы (`evaluation_results.json`, `prompt_recommendations.json`). При повторном запуске — агент читает предыдущие результаты и обновляет только новые/изменённые данные, а не пересчитывает всё.

### Решение 4: Добавление `parse_triumvirate()` в notation_converter.py

Для расчёта buried level нужен парсинг компонентов TRIUMVIRATE нотации. Это leaf-функция, добавляется в существующий модуль.

### Решение 5: Game outcome выводится из данных

Последний трейс каждой игры + `server_move_response.data.game_over` / `winner` / `eliminated_player` дают финальный результат. Это ground truth для валидации composite score.

### Решение 6: Composite score — простой на MVP, расширяемый

MVP использует только автоматические метрики. LLM-оценки (reasoning quality) подключаются на этапе 2 после калибровки.

---

## Архитектура системы

### Общая схема

```
┌──────────────────────────────────────────────────────────────────┐
│                     Пользователь / Claude Code                    │
│                                                                    │
│  /evaluate-models           /optimize-prompts          CLI         │
│  "оценить модели"           "оптимизировать промпты"   metrics.py  │
└──────┬───────────────────────────┬────────────────────────┬───────┘
       │                           │                        │
       │                           │                        │
┌──────▼──────────┐   ┌───────────▼─────────┐   ┌─────────▼────────┐
│   Agent 1       │   │   Agent 2           │   │                  │
│   Model         │   │   Prompt            │   │  python -m       │
│   Evaluator     │   │   Optimizer         │   │  trace_analyzer  │
│                 │   │                     │   │  .metrics        │
│  Шахматная      │   │  Prompt             │   │                  │
│  оценка,        │   │  engineering,       │   │  Автоматические  │
│  пригодность    │   │  рекомендации       │   │  метрики         │
│  модели         │   │  по промптам        │   │                  │
└────────┬────────┘   └──────────┬──────────┘   └────────┬─────────┘
         │                       │                       │
         │  читает               │  читает               │  создаёт
         ▼                       ▼                       ▼
┌────────────────────────────────────────────────────────────────────┐
│                        Файловый слой данных                        │
│                                                                    │
│  logs/                          logs/evaluations/                   │
│    game_<id>__<model>/            metrics.json                     │
│      move_001.json                model_rankings.json              │
│      move_002.json                evaluation_results.json          │
│      ...                          prompt_recommendations.json      │
│                                   evaluation_report_<ts>.md        │
│                                                                    │
│  prompts/                       settings.json                      │
│    system_prompt.txt                                               │
│    user_prompt_template.txt                                        │
│    format_*.txt                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### Поток данных (подробный)

```
Шаг 1: metrics.py (автоматически, без LLM)
  ┌─────────────┐     ┌──────────────────┐     ┌────────────────────┐
  │ logs/       │────▶│ scan + parse     │────▶│ metrics.json       │
  │ 1719 трейсов│     │ + compute metrics│     │ model_rankings.json│
  └─────────────┘     └──────────────────┘     └────────────────────┘

Шаг 2: Model Evaluator (LLM-based, по запросу)
  ┌────────────────┐   ┌──────────────┐     ┌──────────────────────┐
  │ metrics.json   │──▶│ Agent 1      │────▶│ evaluation_results   │
  │ + raw traces   │   │ deep chess   │     │ .json                │
  │ (выборочно)    │   │ analysis     │     │                      │
  └────────────────┘   └──────────────┘     └──────────────────────┘

Шаг 3: Prompt Optimizer (LLM-based, по запросу)
  ┌────────────────┐   ┌──────────────┐     ┌──────────────────────┐
  │ metrics.json   │──▶│ Agent 2      │────▶│ prompt_               │
  │ + evaluation   │   │ prompt       │     │ recommendations.json │
  │   _results     │   │ analysis     │     │ + report.md          │
  │ + prompts/*.txt│   └──────────────┘     └──────────────────────┘
  └────────────────┘
```

---

## Компонент 0: `trace_analyzer/metrics.py`

### Назначение

Детерминированный Python-модуль. Парсит все трейсы, вычисляет автоматические метрики, агрегирует по моделям и играм. Никаких LLM-вызовов. Быстрый, бесплатный, воспроизводимый.

### Входные данные

- `logs/game_<id>__<model>/move_*.json` — 1719 трейсов, 62 игры, 28 моделей

### Зависимости

- `trace_analyzer/data_loader.py` — `scan_traces()` для загрузки
- `notation_converter.py` — `parse_triumvirate()` для buried level (будет добавлена)

### Реальная структура трейс-файла

```
Корневые ключи move_*.json:
├── game_id: str                     — UUID игры
├── move_number: int                 — номер хода в игре
├── timestamp: str                   — ISO datetime
├── outcome: str                     — "success" | "fallback_random" | "error"
├── model_pricing: {...}             — тарифы модели
├── server_interactions: [...]       — сырые HTTP-запросы к серверу
│
├── server_state_raw:                — СОСТОЯНИЕ ДОСКИ ДО ХОДА
│   ├── game_id: str
│   ├── board: [{notation, type, color, owner, is_stuck, promotion_target_color}, ...]
│   ├── current_player: str          — "white" | "black" | "red"
│   ├── legal_moves: {str: [str]}    — {"B1": ["A3","C3"], ...} серверная нотация
│   ├── promotion_moves: {...}
│   ├── last_move: {...} | null
│   ├── prev_move: {...} | null
│   ├── players: [
│   │     {color, name, player_type, model, status, is_replacement}, ...
│   │   ]                            — model=null для smartbot/human
│   ├── move_number: int
│   ├── game_status: str             — "playing" | "finished"
│   ├── check: str | null            — цвет игрока под шахом
│   ├── position_3pf: str            — 3-fold repetition key
│   └── server_version: str
│
├── prompt_pipeline:                 — ПРОМПТЫ
│   ├── system_prompt: str           — шаблон system prompt
│   ├── user_template: str           — шаблон user prompt
│   ├── additional_rules: str
│   ├── response_format_instruction: str
│   ├── rendered_system: str         — финальный system prompt
│   ├── rendered_user_prompt: str    — финальный user prompt
│   └── use_triumvirate_notation: bool
│
├── llm_requests: [...]              — сырые запросы к LLM API
│
├── llm_responses: [                 — ОТВЕТЫ LLM
│     {
│       attempt: int,                — номер попытки (1, 2, ...)
│       raw_response: str,           — полный текст ответа (может быть JSON с thinking)
│       response_chars: int,
│       time_sec: float,
│       usage: {
│         prompt_tokens, completion_tokens, reasoning_tokens,
│         total_tokens, provider_reported_cost_usd
│       },
│       cost: {
│         input_cost_usd, output_cost_usd, reasoning_cost_usd,
│         total_cost_usd, provider_reported_cost_usd
│       }
│     }, ...
│   ]
│
├── parser_attempts: [               — ПАРСИНГ ОТВЕТА
│     {
│       attempt: int,
│       coordinates_found: [str],    — найденные координаты (TRIUMVIRATE)
│       pairs_tested: [str],         — "W2/B2.3→C/W.B(OK)" | "(ILLEGAL)"
│       valid: bool
│     }, ...
│   ]
│
├── move_selected:                   — ВЫБРАННЫЙ ХОД
│   ├── from: str                    — TRIUMVIRATE нотация, напр. "W2/B2.3"
│   ├── to: str                      — TRIUMVIRATE нотация, напр. "C/W.B"
│   └── promotion: str | null
│
├── server_move_request: {...}       — запрос к серверу на выполнение хода
│
├── server_move_response:            — РЕЗУЛЬТАТ ХОДА
│   ├── status_code: int             — HTTP status (200 = ok)
│   └── data:
│       ├── success: bool
│       ├── is_check: bool           — ход дал шах
│       ├── is_checkmate: bool       — ход дал мат
│       ├── is_stalemate: bool       — пат
│       ├── eliminated_player: str|null — цвет выбывшего игрока
│       ├── inherited_pieces: [...]  — фигуры перешедшие от выбывшего
│       ├── game_over: bool
│       ├── winner: str | null       — цвет победителя
│       ├── reason: str | null       — причина завершения
│       └── state: {<server_state_raw>} — полное состояние ПОСЛЕ хода
│
└── statistics:                      — СТАТИСТИКА
    ├── time_total_sec: float
    ├── llm_time_sec: float
    ├── prompt_chars: int
    ├── response_chars: int
    ├── total_llm_chars: int
    ├── llm_calls: int
    ├── retries: int                 — количество повторных попыток
    ├── total_prompt_tokens: int
    ├── total_completion_tokens: int
    ├── total_reasoning_tokens: int
    ├── total_tokens: int
    ├── total_cost_usd: float
    ├── provider_reported_cost_usd: float | null
    └── model_pricing: {prompt_per_1m_usd, completion_per_1m_usd, source}
```

### Метрики per-move (вычисляемые автоматически)

| Метрика | Источник | Формула / логика |
|---------|----------|-----------------|
| `outcome` | `trace.outcome` | "success" / "fallback_random" / "error" |
| `is_check` | `server_move_response.data.is_check` | bool |
| `is_checkmate` | `server_move_response.data.is_checkmate` | bool |
| `eliminated_player` | `server_move_response.data.eliminated_player` | str или null |
| `game_over` | `server_move_response.data.game_over` | bool |
| `winner` | `server_move_response.data.winner` | str или null |
| `buried_from` | `parse_triumvirate(move_selected.from)` | ring + depth |
| `buried_to` | `parse_triumvirate(move_selected.to)` | ring + depth |
| `buried_delta` | `buried_from - buried_to` | >0 = улучшение (движение к центру) |
| `is_rosette_move` | `move_selected.to` starts with "C/" | bool — ход на rosette |
| `is_capture` | compare board before/after: piece removed | bool |
| `captured_piece_type` | type of captured piece | str или null |
| `material_delta` | piece_value(captured) - piece_value(lost) | int (Q=9, R=5, B=3, N=3, P=1) |
| `legal_moves_count` | `len(legal_moves)` total targets | int — мера стеснённости |
| `retries` | `statistics.retries` | int |
| `llm_calls` | `statistics.llm_calls` | int |
| `cost_usd` | `statistics.total_cost_usd` | float |
| `time_total_sec` | `statistics.time_total_sec` | float |
| `llm_time_sec` | `statistics.llm_time_sec` | float |
| `prompt_tokens` | `statistics.total_prompt_tokens` | int |
| `completion_tokens` | `statistics.total_completion_tokens` | int |
| `reasoning_tokens` | `statistics.total_reasoning_tokens` | int |
| `thinking_length` | `len(extracted_thinking)` | int (символов) |
| `has_thinking` | `thinking_length > 0` | bool |
| `is_promotion` | `move_selected.promotion is not None` | bool |
| `first_attempt_success` | `parser_attempts[0].valid == true` | bool |

### Метрики per-model (агрегированные)

| Метрика | Формула |
|---------|---------|
| `total_games` | count(distinct game_id) |
| `total_moves` | count(moves) |
| `success_rate` | success_moves / total_moves |
| `fallback_rate` | fallback_random_moves / total_moves |
| `retry_rate` | moves_with_retries / total_moves |
| `first_attempt_rate` | first_attempt_success / total_moves |
| `avg_cost_per_move` | sum(cost_usd) / total_moves |
| `total_cost` | sum(cost_usd) |
| `avg_time_per_move` | mean(llm_time_sec) |
| `median_time_per_move` | median(llm_time_sec) |
| `avg_tokens_per_move` | mean(total_tokens) |
| `avg_buried_delta` | mean(buried_delta) where outcome=success |
| `rosette_move_rate` | rosette_moves / success_moves |
| `check_rate` | check_moves / success_moves |
| `capture_rate` | capture_moves / success_moves |
| `avg_material_delta` | mean(material_delta) where is_capture |
| `avg_thinking_length` | mean(thinking_length) |
| `games_won` | count(games where winner = this model's color) |
| `games_eliminated` | count(games where this model was eliminated) |
| `win_rate` | games_won / total_games |
| `survival_rate` | (total_games - games_eliminated) / total_games |
| `avg_moves_per_game` | total_moves / total_games |

### Метрики per-game

| Метрика | Формула |
|---------|---------|
| `total_moves` | count(moves in game) |
| `game_result` | "win" / "eliminated" / "playing" / "draw" |
| `final_move_number` | max(move_number) |
| `total_cost` | sum(cost_usd) |
| `total_time` | sum(llm_time_sec) |
| `checks_delivered` | count(is_check=true) |
| `captures_made` | count(is_capture=true) |
| `fallback_count` | count(outcome=fallback_random) |
| `avg_buried_delta` | mean(buried_delta) |

### Composite Score (MVP — только автометрики)

```
AutoComposite = 0.35 * Reliability + 0.30 * MoveActivity + 0.20 * TacticalImpact + 0.15 * Efficiency

Reliability = success_rate * (1 - retry_rate * 0.5) * first_attempt_rate^0.5
  Нормализуется в [0, 1]

MoveActivity = normalize(avg_buried_delta, min_across_models, max_across_models)
  + 0.3 * rosette_move_rate
  Нормализуется в [0, 1]

TacticalImpact = normalize(
    check_rate * 2 + capture_rate * 1.5 + avg_material_delta * 0.5,
    min_across_models, max_across_models
  )
  Нормализуется в [0, 1]

Efficiency = normalize(
    1 / (avg_cost_per_move + epsilon),
    min_across_models, max_across_models
  )
  Нормализуется в [0, 1]
```

**После подключения Agent 1 (Model Evaluator):**

```
FullComposite = 0.30 * MoveQuality      (от Agent 1)
              + 0.20 * ReasoningQuality  (от Agent 1)
              + 0.15 * TacticalImpact    (от metrics.py)
              + 0.20 * Reliability       (от metrics.py)
              + 0.15 * Efficiency        (от metrics.py)
```

Веса калибруются по корреляции с win_rate (ground truth).

### Выходные файлы

```
logs/evaluations/
├── metrics.json              — все per-move метрики (массив объектов)
├── model_rankings.json       — per-model агрегаты + composite score + rank
└── game_results.json         — per-game результаты и агрегаты
```

### CLI-интерфейс

```bash
# Полный пересчёт
python -m trace_analyzer.metrics

# Только конкретная модель
python -m trace_analyzer.metrics --model "openai/gpt-4.1-mini"

# Только конкретная игра
python -m trace_analyzer.metrics --game "0b2d2966-..."

# Вывод в stdout вместо файла
python -m trace_analyzer.metrics --stdout --format table

# Указать папку логов
python -m trace_analyzer.metrics --logs-dir ./other_logs/
```

### Файловая структура модуля

```
trace_analyzer/
├── metrics.py           — точка входа, CLI, оркестрация
├── move_metrics.py      — per-move метрики (MoveMetrics dataclass + compute)
├── aggregator.py        — агрегация per-model, per-game, composite score
├── data_loader.py       — существующий (без изменений)
├── export_utils.py      — существующий (без изменений)
├── app.py               — существующий (без изменений)
└── views/               — существующие (без изменений)
```

Новые файлы: `metrics.py` (~150 строк), `move_metrics.py` (~200 строк), `aggregator.py` (~200 строк).

---

## Компонент 1: Agent "Model Evaluator"

### Назначение

Оценка пригодности LLM-моделей для использования в качестве движка бота Three-Player Chess. Глубокий шахматный анализ качества ходов и рассуждений, который невозможно автоматизировать детерминированно.

### Триггер

- Slash-команда: `/evaluate-models`
- Фразы: "оценить модели", "сравнить модели", "качество ходов", "пригодность моделей", "какая модель лучше"

### Файл skill

`.claude/agents/model-evaluator.md`

### Входные данные

| Источник | Что берёт | Когда |
|----------|-----------|-------|
| `logs/evaluations/metrics.json` | Автометрики per-move | Всегда (обязательно) |
| `logs/evaluations/model_rankings.json` | Агрегаты per-model | Всегда (обязательно) |
| `logs/game_<id>__<model>/move_*.json` | Полные трейсы (thinking, board) | Для deep analysis |
| `notation_converter.py` | Конвертация координат | При анализе позиций |

### Режимы работы

#### Mode 1: Quick Rankings (по умолчанию)

Когда: пользователь спрашивает "какая модель лучше?" без уточнений.

1. Читает `model_rankings.json` (уже готовые автометрики)
2. Дополняет комментариями: сильные/слабые стороны каждой модели
3. Выделяет аномалии (модель с высоким success rate но низким tactical impact)
4. Выдаёт таблицу рейтинга с пояснениями

Стоимость: минимальная (1 LLM-вызов для комментирования готовых данных).

#### Mode 2: Deep Model Analysis (для конкретной модели)

Когда: пользователь говорит "оцени gpt-4.1-mini подробно" или "почему deepseek играет плохо?"

1. Загружает все трейсы указанной модели
2. Выбирает 10-15 наиболее информативных ходов:
   - 3-5 лучших (check, capture, low buried delta)
   - 3-5 худших (fallback, high retries, retreat)
   - 3-5 средних (для калибровки)
3. Для каждого хода оценивает по полной шахматной рубрике (см. ниже)
4. Анализирует thinking-блоки на hallucinations
5. Формирует профиль модели

Стоимость: средняя (1-2 LLM-вызова на большие контексты).

#### Mode 3: Head-to-Head Comparison

Когда: пользователь говорит "сравни gpt-4.1-mini и claude-haiku"

1. Загружает автометрики обеих моделей
2. Находит матчи где обе модели играли (если есть)
3. Сравнивает по каждому критерию
4. Выделяет статистически значимые различия
5. Даёт рекомендацию: какую модель использовать и когда

### Шахматная рубрика оценки хода (Move Quality: 0-15 баллов)

| Критерий | 0 | 1 | 2 | 3 | Как оценивать |
|----------|---|---|---|---|---------------|
| **Leader Safety** | Ход оставляет Leader под шахом/угрозой | Leader не защищён | Leader защищён | Leader в полной безопасности | Анализ позиции Leader'а после хода (из board after). Есть ли фигуры противников, атакующие клетку Leader'а? |
| **Center Control** | Ход удаляет от центра (buried↑) | Нейтральный | Приближает к ring 1-2 | Занимает rosette или ring 0 | Из автометрик: `buried_delta`, `is_rosette_move` |
| **Material** | Теряет фигуру без компенсации | Равноценный размен | Выигрывает пешку | Выигрывает фигуру / создаёт форк | Из автометрик: `material_delta`, `is_capture` |
| **Development** | Ход назад / повторение | Нейтральный | Выводит новую фигуру | Активирует фигуру на ring 0-1 | Анализ: была ли фигура на стартовой позиции? Улучшилась ли активность? |
| **Three-Player Awareness** | Ход явно помогает третьему | Игнорирует третьего | Учитывает позицию третьего | Атакует слабого / защищается от обоих | Анализ thinking: упомянут ли третий игрок? Ход учитывает расстановку всех трёх? |

### Рубрика оценки рассуждений (Reasoning Quality: 0-18 баллов)

| Критерий | 0 | 1 | 2 | 3 | Как оценивать |
|----------|---|---|---|---|---------------|
| **Threat Recognition** | Угрозы не упомянуты | Упомянута 1 угроза | Основные угрозы найдены | Все угрозы + тактика (вилки, связки) | Сравнение thinking с реальными угрозами из board state |
| **Strategic Planning** | Нет плана | Упомянут 1 ход вперёд | План на 2 хода | План на 3+ ходов с ветвлениями | Анализ thinking на наличие "if... then...", вариантных линий |
| **Three-Player Dynamics** | Третий не упомянут | Упомянут формально | Оценён баланс сил | Дипломатическое мышление (кого атаковать) | Наличие упоминаний обоих противников в thinking |
| **Board Accuracy** | >50% галлюцинаций | 30-50% ошибок | <30% ошибок | Все упомянутые фигуры совпадают с доской | Cross-reference координат из thinking с board state |
| **Move-Reasoning Consistency** | Ход противоречит анализу | Слабая связь | Ход следует из анализа | Ход = лучший кандидат по собственному анализу модели | Сравнение: что модель назвала лучшим → что сыграла |
| **Analysis Depth** | 1 предложение | Поверхностный обзор | 2-3 кандидата рассмотрены | Вариантные линии для нескольких ходов | Подсчёт кандидатских ходов в thinking |

### Hallucination Detection

Агент при deep analysis проверяет координаты, упомянутые в thinking:

1. Извлекает все координаты (regex для TRIUMVIRATE `[WBR]\d/[WBR]\d\.\d` и `C/[WBR]\.[WBR]`, и серверных `[A-L]\d{1,2}`)
2. Для каждой координаты проверяет в `server_state_raw.board`: какая фигура реально стоит?
3. Сравнивает с тем, что утверждает модель в thinking
4. Классифицирует ошибки:
   - **Phantom piece**: модель видит фигуру, которой нет
   - **Missing piece**: модель не замечает фигуру (особенно атакующую Leader)
   - **Wrong color**: модель путает чьи фигуры
   - **Invalid coordinate**: координата не существует на доске

**Метрика:** `hallucination_rate = phantom_count / (phantom_count + correct_count)`

### Выходные данные

```json
// logs/evaluations/evaluation_results.json
{
  "timestamp": "2026-03-18T14:30:00",
  "models_evaluated": 28,
  "evaluation_mode": "quick_rankings",

  "rankings": [
    {
      "rank": 1,
      "model": "openai/gpt-4.1-mini",
      "auto_composite": 0.82,
      "full_composite": null,
      "reliability": 0.95,
      "move_activity": 0.78,
      "tactical_impact": 0.71,
      "efficiency": 0.88,
      "strengths": ["high success rate", "fast response time", "good center control"],
      "weaknesses": ["ignores third player", "shallow thinking"],
      "recommendation": "suitable"
    }
  ],

  "deep_analyses": {
    "openai/gpt-4.1-mini": {
      "move_quality_avg": 9.2,
      "reasoning_quality_avg": 11.5,
      "hallucination_rate": 0.15,
      "best_moves": [...],
      "worst_moves": [...],
      "error_patterns": [...],
      "fitness_verdict": "Хорошо подходит для быстрых игр, слабо в эндшпиле"
    }
  }
}
```

### Формат отчёта (markdown)

```markdown
# Model Evaluation Report — {date}

## Rankings
| # | Model | Composite | Reliability | Activity | Tactical | Efficiency | Verdict |
|---|-------|-----------|-------------|----------|----------|------------|---------|

## Per-Model Analysis
### {model_name}
**Verdict:** {suitable / marginal / not suitable}
**Strengths:** ...
**Weaknesses:** ...
**Best move:** game {id}, move {n} — {описание почему хорош}
**Worst move:** game {id}, move {n} — {описание проблемы}
**Hallucination rate:** {x}%
**Error patterns:** ...
```

---

## Компонент 2: Agent "Prompt Optimizer"

### Назначение

Анализ эффективности текущих системных промптов и генерация конкретных рекомендаций по их улучшению. Фокус на prompt engineering, а не на шахматной оценке.

### Триггер

- Slash-команда: `/optimize-prompts`
- Фразы: "оптимизировать промпты", "улучшить промпт", "почему модель не понимает формат", "промпт-инжиниринг", "системный запрос"

### Файл skill

`.claude/agents/prompt-optimizer.md`

### Входные данные

| Источник | Что берёт | Когда |
|----------|-----------|-------|
| `logs/evaluations/metrics.json` | Автометрики (retry_rate, thinking_length) | Всегда |
| `logs/evaluations/evaluation_results.json` | Результаты Model Evaluator | Если есть (опционально) |
| `prompts/*.txt` | Текущие файлы промптов | Всегда |
| `logs/game_*/move_*.json` | Полные трейсы (для анализа thinking) | Выборочно |

### Режимы работы

#### Mode 1: Prompt Audit (по умолчанию)

Когда: пользователь говорит "оптимизируй промпты" без уточнений.

1. Читает текущие промпты из `prompts/`
2. Читает агрегированные метрики
3. Идентифицирует паттерны проблем (таблица ниже)
4. Генерирует рекомендации с конкретными diff'ами

#### Mode 2: Model-Specific Optimization

Когда: "оптимизируй промпт для deepseek-chat"

1. Загружает метрики + 10-20 трейсов указанной модели
2. Анализирует thinking на:
   - % пересказа правил vs реальный анализ
   - Самоповторы
   - Format compliance
3. Генерирует конфиг, оптимальный для этой модели

#### Mode 3: A/B Comparison

Когда: "сравни результаты с разными промптами"

1. Группирует трейсы по `rendered_system` (разные версии промптов)
2. Сравнивает метрики между группами
3. Определяет какая версия промпта лучше и для каких моделей

### Таблица паттернов ошибок → рекомендаций

| Паттерн | Детекция (автометрики) | Рекомендация |
|---------|----------------------|--------------|
| Модель не выдаёт валидный ход | `fallback_rate > 20%` | Переключить на `format_simple`; усилить format instruction |
| Много retry | `retry_rate > 15%` | Упростить response format; добавить пример ответа |
| Модель пересказывает правила | `thinking` содержит >30% текста из `rendered_system` | Сократить system prompt; заменить правила на "You know the rules" |
| Самоповторы в thinking | >30% повторяющихся n-gram в thinking | Уменьшить max_tokens; сделать промпт более структурированным |
| Пассивная игра | `avg_buried_delta < 0` по модели | Добавить "Prefer moves that decrease buried level. Target ring 0-1." |
| Не видит угрозы Leader'у | (из evaluation_results) threat_recognition < 1 | Добавить "CRITICAL: Check if YOUR Leader is under attack FIRST" |
| Игнорирует третьего | (из evaluation_results) three_player_dynamics < 1 | Добавить секцию "Opponent Analysis" в user template |
| Нет вариантных линий | `avg_thinking_length < 100` и `outcome=success` | Добавить "Consider at least 3 candidate moves" |
| Ходы повторяются | >3 одинаковых ходов подряд в игре | Добавить "Avoid repeating moves. History: {last_3_moves}" |
| Высокая стоимость без пользы | `cost_per_move > $0.01` и `tactical_impact < 0.3` | Уменьшить max_tokens; убрать verbose instructions |

### Анализ содержимого thinking

Агент классифицирует содержимое thinking-блоков:

| Категория | Примеры | Полезность |
|-----------|---------|------------|
| **Rule recap** | "The game is played on 96 cells..." | Waste — модель пересказывает промпт |
| **Position analysis** | "My bishop on W2/R1.2 controls..." | Useful — описание текущего состояния |
| **Variant lines** | "If I play W2/B2.3→C/W.B, then opponent can..." | Very useful — if-then рассуждения |
| **Strategic assessment** | "Black is stronger, I should focus on Red..." | Useful — оценка баланса сил |
| **Self-repetition** | Повтор одних и тех же мыслей 2+ раз | Waste — бесполезные токены |
| **Format filler** | "I will respond in JSON format..." | Waste — модель оправдывает свой формат |

**Метрика:** `useful_content_ratio = (position + variants + strategy) / total_thinking_chars`

### Выходные данные

```json
// logs/evaluations/prompt_recommendations.json
{
  "timestamp": "2026-03-18T15:00:00",
  "current_prompts_hash": "abc123",

  "global_recommendations": [
    {
      "id": "rec_001",
      "priority": "high",
      "pattern": "high_retry_rate",
      "affected_models": ["deepseek/deepseek-v3.2", "qwen/qwen3-coder_free"],
      "problem": "Модели часто не попадают в формат с первой попытки",
      "evidence": "retry_rate > 15% у 5 из 28 моделей",
      "suggestion": "Для моделей с retry_rate > 10% — переключить на format_simple",
      "diff": {
        "file": "settings.json",
        "change": "response_format: 'simple' для слабых моделей"
      },
      "expected_impact": "retry_rate → <5%, cost снизится на ~20%"
    }
  ],

  "model_specific": {
    "deepseek/deepseek-v3.2": {
      "optimal_config": {
        "response_format": "simple",
        "temperature": 0.4,
        "additional_rules": "Focus on position analysis. Limit thinking to 200 words."
      },
      "prompt_patches": [
        {
          "file": "prompts/system_prompt.txt",
          "action": "add_after_line",
          "target": "CRITICAL RULES",
          "content": "Check if YOUR Leader is under attack BEFORE considering offensive moves."
        }
      ]
    }
  },

  "thinking_analysis": {
    "openai/gpt-4.1-mini": {
      "useful_content_ratio": 0.72,
      "rule_recap_ratio": 0.08,
      "self_repetition_ratio": 0.05,
      "avg_candidates_considered": 2.1
    }
  }
}
```

### Формат отчёта (markdown)

```markdown
# Prompt Optimization Report — {date}

## Executive Summary
- Проанализировано N моделей, M ходов
- Найдено K паттернов, требующих оптимизации
- Приоритетная рекомендация: {самая важная}

## Global Recommendations
### [HIGH] {title}
- **Проблема:** {описание}
- **Затронутые модели:** {список}
- **Доказательство:** {метрики}
- **Рекомендация:** {что изменить}
- **Конкретное изменение:**
  ```diff
  - старый текст
  + новый текст
  ```
- **Ожидаемый эффект:** {на какие метрики повлияет}

## Model-Specific Optimizations
### {model_name}
- **Текущие проблемы:** ...
- **Оптимальный конфиг:** format={}, temp={}, max_tokens={}
- **Thinking efficiency:** {x}% полезного контента
- **Рекомендуемые правки промпта:** ...
```

---

## Оркестрация

### Пользовательские сценарии

#### Сценарий 1: "Какая модель лучше?"

```
Пользователь: /evaluate-models
                  │
                  ▼
         [Проверка: есть ли metrics.json?]
              │             │
           Нет ✗          Да ✓
              │             │
              ▼             ▼
    Подсказка:          Agent 1 → Quick Rankings
    "Сначала запустите   → таблица рейтинга
     python -m trace_    → комментарии к каждой модели
     analyzer.metrics"   → топ-3 находки
```

#### Сценарий 2: "Оцени deepseek подробно"

```
Пользователь: /evaluate-models deepseek-v3.2
                  │
                  ▼
         Agent 1 → Deep Analysis
              │
              ├── Читает metrics.json (агрегаты)
              ├── Загружает 10-15 трейсов deepseek
              ├── Оценивает по рубрике
              ├── Проверяет hallucinations
              │
              ▼
         evaluation_results.json + отчёт
```

#### Сценарий 3: "Оптимизируй промпты"

```
Пользователь: /optimize-prompts
                  │
                  ▼
         Agent 2 → Prompt Audit
              │
              ├── Читает metrics.json
              ├── Читает evaluation_results.json (если есть)
              ├── Читает prompts/*.txt
              ├── Анализирует thinking 20-30 трейсов
              │
              ▼
         prompt_recommendations.json + отчёт + diff'ы
```

#### Сценарий 4: "Полный анализ" (все три компонента)

```
Пользователь: "Проведи полный анализ всех моделей и промптов"
                  │
                  ▼
         1. python -m trace_analyzer.metrics
              │
              ▼
         2. /evaluate-models (Agent 1)
              │
              ▼
         3. /optimize-prompts (Agent 2, использует результаты Agent 1)
              │
              ▼
         Итоговый отчёт: logs/evaluations/evaluation_report_<ts>.md
```

### Взаимодействие агентов через файлы

Агенты НЕ вызывают друг друга напрямую. Взаимодействие — через файловую систему:

```
metrics.py  ──записывает──▶  metrics.json  ◀──читает──  Agent 1
metrics.py  ──записывает──▶  model_rankings.json  ◀──читает──  Agent 1, Agent 2
Agent 1     ──записывает──▶  evaluation_results.json  ◀──читает──  Agent 2
Agent 2     ──записывает──▶  prompt_recommendations.json
```

Это означает:
- Каждый компонент можно запустить независимо
- Результаты накапливаются — не теряются между запусками
- Нет проблем с синхронизацией — файл либо есть, либо нет
- Agent 2 явно проверяет: "есть ли evaluation_results.json?" — если да, использует; если нет, работает только на автометриках

---

## Добавление parse_triumvirate() в notation_converter.py

### API

```python
def parse_triumvirate(tri: str) -> dict:
    """Парсит TRIUMVIRATE нотацию в компоненты.

    Примеры:
        'W2/B2.3' → {'sector': 'W', 'ring': 2, 'opponent': 'B',
                      'depth': 2, 'flank': 3, 'buried': 4, 'rosette': False}
        'C/W.B'   → {'sector': 'W', 'ring': 0, 'opponent': 'B',
                      'depth': 0, 'flank': 0, 'buried': 0, 'rosette': True}

    Raises KeyError if notation is invalid.
    """
```

### Логика

- Rosette: `C/{sector}.{opponent}` → ring=0, depth=0, buried=0, rosette=True
- Обычная: `{sector}{ring}/{opponent}{depth}.{flank}` → buried = ring + depth

### Использование

```python
from notation_converter import parse_triumvirate

p = parse_triumvirate("W2/B2.3")
buried_level = p["buried"]  # 4
```

---

## Порядок реализации

### Этап 1: Фундамент данных (P0)

| # | Задача | Файл | ~Строк |
|---|--------|------|--------|
| 1.1 | Добавить `parse_triumvirate()` | `notation_converter.py` | +30 |
| 1.2 | Создать `move_metrics.py` — MoveMetrics dataclass + compute | `trace_analyzer/move_metrics.py` | ~200 |
| 1.3 | Создать `aggregator.py` — агрегация per-model/game, composite | `trace_analyzer/aggregator.py` | ~200 |
| 1.4 | Создать `metrics.py` — CLI entry point, оркестрация | `trace_analyzer/metrics.py` | ~150 |
| 1.5 | Тесты для metrics pipeline | `tests/test_metrics.py` | ~150 |

**Результат:** `python -m trace_analyzer.metrics` выдаёт `metrics.json` + `model_rankings.json` + `game_results.json`.

**Валидация:** проверить что модели с высоким win_rate оказываются выше в рейтинге (корреляция composite ↔ win_rate).

### Этап 2: Agent Model Evaluator (P1)

| # | Задача | Файл | ~Строк |
|---|--------|------|--------|
| 2.1 | Skill-определение агента | `.claude/agents/model-evaluator.md` | ~200 |
| 2.2 | Тестирование на 3-5 моделях | Ручной QA | — |
| 2.3 | Калибровка рубрик (10-20 ходов, ручная разметка) | — | — |

**Результат:** `/evaluate-models` выдаёт рейтинг с шахматными комментариями.

**Валидация:** оценки агента для калибровочного набора совпадают с ручной разметкой (>70% agreement).

### Этап 3: Agent Prompt Optimizer (P2)

| # | Задача | Файл | ~Строк |
|---|--------|------|--------|
| 3.1 | Skill-определение агента | `.claude/agents/prompt-optimizer.md` | ~200 |
| 3.2 | Тестирование: генерация рекомендаций | Ручной QA | — |
| 3.3 | A/B тест: применить рекомендацию → сыграть 10 игр → сравнить метрики | — | — |

**Результат:** `/optimize-prompts` выдаёт конкретные diff'ы для промптов.

**Валидация:** применение рекомендации улучшает composite score на ≥5%.

### Этап 4: Интеграция и UI (P3, опционально)

| # | Задача | Файл |
|---|--------|------|
| 4.1 | Таб "Evaluation" в trace_analyzer app | `trace_analyzer/views/evaluation.py` |
| 4.2 | Визуализация рейтингов и трендов | — |
| 4.3 | Кнопка "Run evaluation" из UI | — |

---

## Критерии успеха

| # | Критерий | Метрика | Порог |
|---|----------|---------|-------|
| 1 | Автометрики коррелируют с win rate | Spearman ρ (composite ↔ win_rate) | ≥ 0.5 |
| 2 | Model Evaluator ранжирует корректно | Top-3 модели по composite ∈ top-5 по win_rate | Да |
| 3 | Рекомендации по промптам actionable | Каждая рекомендация содержит конкретный diff | 100% |
| 4 | Рекомендации улучшают качество | A/B тест: composite_after > composite_before | ≥ +5% |
| 5 | Hallucination detection работает | Precision ≥ 70% на ручной выборке из 20 ходов | ≥ 70% |
| 6 | Скорость metrics.py | 1719 трейсов → metrics.json | < 10 секунд |
| 7 | Агенты не дублируют работу | Нет повторного парсинга трейсов в агентах | Проверка ручная |

---

## Ограничения и риски

| Риск | Митигация |
|------|-----------|
| Шахматная оценка ограничена (нет движка для three-player chess) | Опираемся на автометрики (buried level, captures, checks) как объективную базу; LLM-оценка — дополнение |
| LLM-оценки reasoning нестабильны между запусками | Кешируем результаты; используем temperature=0; калибруем на ручной выборке |
| Недостаточно данных для статистической значимости | Минимум 30 ходов на модель; для моделей с <30 — показываем disclaimer |
| Game outcome не всегда доступен (бот мог быть остановлен) | Для незавершённых игр — используем только per-move метрики, не win_rate |
| Prompt Optimizer может генерировать вредные рекомендации | Рекомендации — предложения; применение только после ревью пользователем |
| Трейсы могут не содержать thinking (модели без thinking block) | Если `thinking_length == 0` — reasoning quality не оценивается, только move quality |

---

## Текущее состояние данных

| Параметр | Значение |
|----------|----------|
| Всего игр | 62 |
| Всего трейсов (ходов) | 1719 |
| Уникальных моделей | 28 |
| Формат координат в move_selected | TRIUMVIRATE нотация |
| Формат координат в legal_moves | Серверная нотация (A1-L12) |
| Наличие thinking в ответах | Зависит от модели |
| Наличие game_over/winner в трейсах | Да — в `server_move_response.data` |
| Наличие is_check/is_checkmate | Да — в `server_move_response.data` |
| Наличие eliminated_player | Да — в `server_move_response.data` |
