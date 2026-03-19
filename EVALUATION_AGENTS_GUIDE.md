# Мульти-агентная система оценки LLM-моделей — Руководство

## Обзор системы

Система состоит из трёх компонентов для анализа качества игры LLM-моделей в Three-Player Chess:

| Компонент | Тип | Назначение | Вызов |
|-----------|-----|-----------|-------|
| **metrics.py** | Python CLI | Автоматические метрики, рейтинг | `python -m trace_analyzer.metrics` |
| **Model Evaluator** | Claude Code agent | Шахматная оценка, пригодность моделей | `/evaluate-models` |
| **Prompt Optimizer** | Claude Code agent | Анализ промптов, рекомендации | `/optimize-prompts` |

### Архитектура

```
                    Пользователь
                    │         │
        ┌───────────┘         └────────────┐
        ▼                                  ▼
  /evaluate-models                  /optimize-prompts
  (Model Evaluator)                 (Prompt Optimizer)
        │                                  │
        │  читает                          │  читает
        ▼                                  ▼
  ┌─────────────────────────────────────────────┐
  │          logs/evaluations/                   │
  │  metrics.json        — per-move метрики      │
  │  model_rankings.json — рейтинг моделей       │
  │  game_results.json   — результаты игр        │
  └──────────────────────┬──────────────────────┘
                         │  создаёт
                         ▼
                python -m trace_analyzer.metrics
                         │  читает
                         ▼
                    logs/game_*/move_*.json
```

---

## Правила работы

### Правило 1: Всегда запускай metrics.py первым

Оба агента зависят от файлов в `logs/evaluations/`. Если их нет или они устарели — агенты не смогут работать эффективно.

```bash
# Перед использованием агентов
python -m trace_analyzer.metrics
```

Metrics.py пересчитывает всё за ~1.3 секунды. Запускай после каждой серии новых игр.

### Правило 2: Порядок вызова агентов имеет значение

```
metrics.py → Model Evaluator → Prompt Optimizer
```

- **Model Evaluator** читает `metrics.json` и `model_rankings.json`
- **Prompt Optimizer** читает те же файлы + опционально `evaluation_results.json` (результаты Model Evaluator)
- Prompt Optimizer даёт более точные рекомендации, если перед ним запустить Model Evaluator

Можно использовать агентов по отдельности, но для полного анализа — соблюдай порядок.

### Правило 3: Агенты не заменяют друг друга

| Вопрос | Кого вызывать |
|--------|---------------|
| "Какая модель лучше для бота?" | Model Evaluator |
| "Почему gpt-4.1-mini плохо играет?" | Model Evaluator (deep analysis) |
| "Как улучшить промпт?" | Prompt Optimizer |
| "Почему модели не попадают в формат?" | Prompt Optimizer |
| "Сравни deepseek и gpt" | Model Evaluator |
| "Оптимизируй промпт для deepseek" | Prompt Optimizer |
| "Просто покажи рейтинг" | `python -m trace_analyzer.metrics --stdout` |

### Правило 4: Указывай режим работы

Каждый агент имеет 3 режима. По умолчанию используется Mode 1 (обзорный). Для глубокого анализа — указывай модель или контекст:

```
# Mode 1 (Quick) — по умолчанию
/evaluate-models

# Mode 2 (Deep) — указываешь модель
/evaluate-models openai/gpt-4.1-mini

# Mode 3 (Comparison) — указываешь две модели
/evaluate-models сравни gpt-4.1-mini и deepseek-v3.2
```

### Правило 5: Данные накапливаются

Результаты агентов сохраняются в `logs/evaluations/`:
- `evaluation_results.json` — от Model Evaluator
- `prompt_recommendations.json` — от Prompt Optimizer

При повторном запуске агент может читать предыдущие результаты. Удаляй файлы, если хочешь "чистый" анализ.

### Правило 6: Минимальный объём данных

| Анализ | Минимум | Рекомендуется |
|--------|---------|---------------|
| Рейтинг моделей | 10 ходов на модель | 30+ ходов |
| Deep analysis модели | 5 ходов | 15+ ходов |
| Промпт-рекомендации | 20 ходов total | 50+ ходов |
| A/B сравнение промптов | 10 ходов на каждый вариант | 30+ ходов |

Модели с < 10 ходов помечаются как "insufficient data" в рейтинге.

---

## Рекомендации по использованию

### При добавлении новой модели

1. Сыграй 3-5 игр с новой моделью
2. `python -m trace_analyzer.metrics`
3. `/evaluate-models <model_name>` — получи первичную оценку
4. `/optimize-prompts <model_name>` — получи оптимальный конфиг
5. Примени рекомендации, сыграй ещё 3-5 игр
6. Повтори анализ — сравни до/после

### При изменении промптов

1. Запомни текущие метрики: `python -m trace_analyzer.metrics`
2. Внеси изменения в промпты
3. Сыграй 5-10 игр с новыми промптами
4. `python -m trace_analyzer.metrics` — пересчитай
5. `/optimize-prompts` в режиме A/B — сравни версии

### При массовом сравнении моделей

1. Запусти `python -m trace_analyzer.metrics` — получи рейтинг
2. `/evaluate-models` — получи комментарии к top-10
3. Для 3-5 лучших моделей — сделай deep analysis каждой
4. `/optimize-prompts` — получи рекомендации для каждой

### Интерпретация Composite Score

```
0.70+ — отличная модель, пригодна для использования
0.50-0.70 — средняя, работает но с ограничениями
0.30-0.50 — слабая, требует значительной оптимизации промптов
< 0.30 — непригодна (не попадает в формат, не делает легальных ходов)
```

Компоненты score:
- **Reliability (35%)** — попадает ли в формат, нет ли fallback'ов
- **Activity (30%)** — играет ли активно (центр, уменьшение buried level)
- **Tactical (20%)** — даёт ли шахи, берёт ли фигуры
- **Efficiency (15%)** — стоимость за ход

---

## Возможные сложности и решения

### Сложность 1: "Все модели показывают win_rate = 0%"

**Причина:** Большинство игр не доигрываются до конца — боты останавливаются вручную. `game_over` = false в последнем трейсе.

**Решение:** Это нормально. Composite score опирается на per-move метрики (reliability, activity, tactical impact), а не на win_rate. Win rate информативен только при полных играх.

**Обходной путь:** Если нужен win_rate — запускай ботов до конца игры (не останавливай раньше). Или добавь в `bot_runner.py` запись `game_result.json` при завершении.

### Сложность 2: "metrics.py показывает server_error_409"

**Причина:** Сервер вернул 409 Conflict — ход был сделан не в свою очередь или игра завершилась.

**Решение:** Эти ходы автоматически снижают reliability_score модели. Если таких ходов много — проблема в синхронизации с сервером (в `bot_runner.py`), а не в модели.

**Обходной путь:** Для чистого анализа — фильтруй: `python -m trace_analyzer.metrics --model <name>` покажет метрики конкретной модели без шума от других.

### Сложность 3: "Агент Model Evaluator даёт разные оценки при повторных запусках"

**Причина:** LLM-оценки (reasoning quality, hallucination detection) стохастичны. Это фундаментальное ограничение.

**Решение:**
1. Автоматические метрики (из metrics.py) стабильны — используй их как baseline
2. Для калибровки — размечай 10-20 ходов вручную и сравнивай с оценками агента
3. Запускай deep analysis 2-3 раза и бери консенсус

**Обходной путь:** Для критичных решений (выбор модели для продакшена) — опирайся на composite score из metrics.py, а не на LLM-оценки.

### Сложность 4: "Prompt Optimizer рекомендует противоречивые изменения"

**Причина:** Рекомендации для разных моделей могут конфликтовать. Например, "сократи промпт" для одной и "добавь инструкции" для другой.

**Решение:** Промпт — общий, но `additional_rules` и `response_format` можно настраивать per-model в settings.json. Применяй глобальные рекомендации к промпту, а model-specific — к конфигурации.

**Обходной путь:** Используй `--settings bot_<model>.json` для запуска ботов с разными конфигами.

### Сложность 5: "Модель с высоким thinking_length но низким quality"

**Причина:** Модель тратит токены на пересказ правил и самоповторы вместо реального анализа.

**Решение:** `/optimize-prompts <model>` — агент измерит thinking efficiency и предложит:
- Уменьшить max_tokens
- Добавить "Be concise. Skip rules you already know."
- Переключить на format_simple (убирает thinking block)

### Сложность 6: "Недостаточно данных для статистически значимых выводов"

**Причина:** Некоторые модели имеют < 10 ходов (тестовые запуски).

**Решение:** Модели с < 10 ходов помечаются "insufficient data". Не принимай решений на их основе.

**Обходной путь:** Запусти `python main.py --headless --bots 3 --models-pool models_pool.json` для быстрого набора данных.

---

## Подводные камни

### Камень 1: legal_moves в серверной нотации, move_selected в TRIUMVIRATE

В трейсах `server_state_raw.legal_moves` используют серверную нотацию (`A1`, `B3`), а `move_selected.from/to` — TRIUMVIRATE (`W2/B2.3`). Агенты должны использовать `notation_converter` для конвертации при cross-reference.

**Что может пойти не так:** При анализе "мог ли бот сделать лучший ход" нужно конвертировать legal_moves в TRIUMVIRATE для сравнения с move_selected.

**Как обойти:** `parse_triumvirate()` и `to_triumvirate()` из `notation_converter.py` — O(1) lookup, безопасно вызывать массово.

### Камень 2: Не все модели имеют thinking

Модели с `response_format: simple` или `json` не возвращают thinking block. У них `thinking_length = 0`, `has_thinking = False`.

**Что может пойти не так:** Model Evaluator может занизить Reasoning Quality для модели, которая хорошо играет но не объясняет свои ходы.

**Как обойти:** При отсутствии thinking — оценивать ТОЛЬКО Move Quality (0-15). Reasoning Quality = N/A. Это должно быть отражено в отчёте.

### Камень 3: raw_response может быть как JSON так и plain text

В зависимости от `response_format`, `llm_responses[].raw_response` может быть:
- JSON с thinking: `{"thinking": "...", "move_from": "W2/B2.3", "move_to": "C/W.B"}`
- Plain text: `W2/B2.3 C/W.B`
- Невалидный формат (при fallback)

**Что может пойти не так:** Парсинг thinking из plain text ответа выдаст весь ответ как "thinking", что исказит thinking_length.

**Как обойти:** `move_metrics.py` уже обрабатывает оба формата корректно в `_thinking_length()` — пытается распарсить JSON, а при неудаче берёт весь ответ. Для агентов: проверяй `has_thinking` перед анализом thinking.

### Камень 4: Один трейс = один ход одного бота

Трейс-файл описывает ход ОДНОГО бота. Ходы противников (smartbot/human) НЕ записываются в трейсы. Поэтому в `server_state_raw` видны последствия ходов противников, но не сами ходы.

**Что может пойти не так:** Нельзя восстановить полную историю партии из трейсов одного бота. Нельзя оценить "реакцию на ход противника" напрямую.

**Как обойти:** Сравнивай `server_state_raw` последовательных ходов (move N и move N+1) чтобы увидеть, что изменилось между ними (это косвенно показывает ход противника).

### Камень 5: Composite Score зависит от набора моделей

Activity score и tactical score нормализуются min-max по всем моделям в выборке. Если добавить очень слабую или очень сильную модель — нормализация сдвинется и scores всех моделей изменятся.

**Что может пойти не так:** Добавление nvidia/nemotron (3 хода, 0 success) обнуляет tactical score нижней границы и сдвигает всех вверх.

**Как обойти:** Фильтруй модели с малым количеством данных: `python -m trace_analyzer.metrics` автоматически включает все, но агенты должны игнорировать модели с < 10 ходов при формировании рейтинга. Либо фильтруй вручную: `python -m trace_analyzer.metrics --model "openai/"`.

---

## Примеры использования (реальные кейсы)

### Кейс 1: Быстрый рейтинг после серии игр

**Ситуация:** Запустил 5 ботов с разными моделями, каждый сыграл 3-4 игры. Хочу понять кто лучше.

**Действия:**

```bash
# Шаг 1: пересчитай метрики
python -m trace_analyzer.metrics
```

```
==========================================================================================
  Model Rankings  |  1752 moves, 28 models  |  1.3s
==========================================================================================
  # Model                                       Comp   Rel   Act   Tac   Eff  Win% Moves
------------------------------------------------------------------------------------------
  1 openrouter/hunter-alpha                    0.789 0.873 0.483 0.941 1.000    0%    23
  2 deepseek/deepseek-v3.2                     0.718 1.000 0.429 0.466 0.973    0%    28
  3 qwen/qwen3-max-thinking                    0.708 0.938 0.519 0.447 0.894    0%    16
  ...
 28 nvidia/nemotron-3-super-120b-a12b:free     0.150 0.000 0.000 0.000 1.000    0%     3
==========================================================================================
```

```
# Шаг 2: попроси агента прокомментировать
/evaluate-models
```

**Результат:** Таблица с рейтингом + комментарии агента по каждой модели из топ-10, с пояснениями почему одна модель выше другой.

---

### Кейс 2: Глубокий анализ конкретной модели

**Ситуация:** `openai/gpt-4.1-mini` занимает 14 место с composite 0.594. Хочу понять почему и можно ли улучшить.

**Действия:**

```bash
# Шаг 1: метрики конкретной модели
python -m trace_analyzer.metrics --model "gpt-4.1-mini" --stdout
```

```
  # Model                                       Comp   Rel   Act   Tac   Eff  Win% Moves
  1 openai/gpt-4.1-mini                        0.582 0.735 0.500 0.500 0.500    0%   157
```

```
# Шаг 2: deep analysis
/evaluate-models openai/gpt-4.1-mini подробно
```

Агент загрузит 10-15 трейсов, оценит по рубрике, найдёт hallucinations, покажет best/worst moves.

```
# Шаг 3: оптимизация промпта для этой модели
/optimize-prompts openai/gpt-4.1-mini
```

Агент проанализирует thinking efficiency, предложит конкретные изменения в промпте и конфигурации.

**Ожидаемый результат:**
- Профиль модели: "reliability средняя (73.5%), часто не попадает в формат с первой попытки"
- Рекомендация: переключить на format_simple, добавить пример ответа
- Конкретный diff для промпта

---

### Кейс 3: Сравнение двух моделей для выбора

**Ситуация:** Выбираю между `deepseek/deepseek-v3.2` (rank 2) и `qwen/qwen3-max-thinking` (rank 3).

**Действия:**

```
/evaluate-models сравни deepseek/deepseek-v3.2 и qwen/qwen3-max-thinking
```

**Ожидаемый результат:**

| Показатель | deepseek-v3.2 | qwen3-max-thinking |
|---|---|---|
| Composite | 0.718 | 0.708 |
| Reliability | 1.000 | 0.938 |
| Activity | 0.429 | 0.519 |
| Tactical | 0.466 | 0.447 |
| Efficiency | 0.973 | 0.894 |
| Moves | 28 | 16 |

Агент прокомментирует: "deepseek надёжнее (100% success), qwen активнее (больше центральных ходов). Для стабильной игры выбирай deepseek, для агрессивного стиля — qwen. Внимание: у qwen только 16 ходов — выборка мала."

---

### Кейс 4: Оптимизация промптов для группы слабых моделей

**Ситуация:** Модели на позициях 22-28 имеют composite < 0.20. Хочу понять можно ли их спасти промптами.

**Действия:**

```bash
# Шаг 1: общий аудит промптов
/optimize-prompts
```

**Ожидаемый результат:**

Агент выявит:
1. **[HIGH] Модели с fallback_rate > 90%:** anthropic/claude-haiku, bytedance/seedream, nvidia/nemotron — reliability=0. Эти модели вообще не попадают в формат.
   - Рекомендация: переключить на `format_simple`, снизить температуру до 0.2
   - Причина: модели не понимают JSON format instruction или не знают TRIUMVIRATE нотацию

2. **[MEDIUM] qwen/qwen3-coder:free** — reliability=0 при 96 ходах.
   - Рекомендация: эта модель-кодер, не предназначена для шахмат. Удалить из пула.

3. **[LOW] Thinking waste у дорогих моделей**
   - Рекомендация: добавить "Be concise. Skip rules recap." в additional_rules

```diff
- You are playing Three-Player Chess on a 96-cell hexagonal board...
+ You are an expert Three-Player Chess player. Focus on position analysis only.
```

---

## CLI-справочник

```bash
# Полный пересчёт метрик → файлы
python -m trace_analyzer.metrics

# Вывод в консоль (без сохранения)
python -m trace_analyzer.metrics --stdout

# JSON вывод
python -m trace_analyzer.metrics --stdout --format json

# Фильтр по модели
python -m trace_analyzer.metrics --model "gpt-4.1-mini"

# Фильтр по игре
python -m trace_analyzer.metrics --game "0b2d2966"

# Другая папка логов
python -m trace_analyzer.metrics --logs-dir ./other_logs/

# Другая папка вывода
python -m trace_analyzer.metrics --output-dir ./my_evaluations/
```

## Файловая структура

```
trace_analyzer/
├── metrics.py           — CLI entry point (python -m trace_analyzer.metrics)
├── move_metrics.py      — per-move метрики (MoveMetrics dataclass + compute)
├── aggregator.py        — агрегация per-model/game, composite score
├── data_loader.py       — загрузка + нормализация трейсов (существовал)
├── app.py               — NiceGUI trace viewer (существовал)
├── export_utils.py      — форматирование для экспорта (существовал)
└── views/               — UI views (существовали)

.claude/agents/
├── model-evaluator.md   — Agent 1: шахматная оценка моделей
└── prompt-optimizer.md  — Agent 2: оптимизация промптов

logs/evaluations/        — результаты анализа
├── metrics.json         — per-move метрики (1752 записей)
├── model_rankings.json  — рейтинг 28 моделей
└── game_results.json    — результаты 54 игр

notation_converter.py    — конвертер нотаций + parse_triumvirate() (обновлён)
```
