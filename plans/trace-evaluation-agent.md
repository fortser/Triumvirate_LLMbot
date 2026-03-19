# План разработки агента анализа и оценки качества LLM-ответов

## Цель

Агент в среде Claude Code, который:
1. Анализирует трассировочные логи игр Three-Player Chess
2. Оценивает качество ответов LLM-моделей (рассуждения, ходы, стратегия)
3. Ранжирует модели по composite score
4. Генерирует рекомендации по оптимизации системных промптов

---

## Фаза 1: Инфраструктура агента

### 1.1 Skill-определение для Claude Code

**Файл:** `.claude/agents/trace-evaluator.md`

**Trigger:** `/evaluate-traces`, "анализ логов", "оценка моделей", "сравнить модели", "качество ходов"

**Системная инструкция агента** (высокоуровневая структура):

```
Ты — эксперт-аналитик по Three-Player Chess AI. Твоя задача — оценивать качество
игры LLM-моделей на основе трассировочных логов.

КОНТЕКСТ ПРЕДМЕТНОЙ ОБЛАСТИ:
- Игра ведётся на 96-клеточной гексагональной доске (секторы W/B/R)
- Нотация TRIUMVIRATE v4.0: S#/O#.# (сектор/ring/opponent/depth.flank)
- Rosette cells (C/S.N) — центральные, стратегически важные
- Buried level = Ring + Depth (0=центр, 6=максимальная пассивность, ≤4 порог активности)
- Три игрока: каждый ход влияет на двух противников

ДОСТУПНЫЕ ДАННЫЕ (из трейс-файлов):
- prompt_pipeline: полные промпты отправленные модели
- llm_responses[].raw_response: полный ответ модели включая thinking
- parser_attempts[]: какие координаты найдены, какие пары валидны
- server_state_raw: полное состояние доски ДО хода (фигуры, легальные ходы)
- move_selected: выбранный ход (from/to/promotion)
- server_move_response: результат хода (шах, мат, выбытие игрока)
- statistics: время, токены, стоимость, retry-count
- outcome: success/fallback_random/error

ПРОЦЕДУРА АНАЛИЗА:
1. Загрузи трейсы через scan_traces() из data_loader.py
2. Для batch-анализа — агрегируй метрики по модели/игре
3. Для deep-анализа — оценивай конкретные ходы по рубрике
4. Сравнивай модели статистически
5. Генерируй рекомендации по промптам на основе паттернов ошибок
```

### 1.2 Формат вывода агента

**Файл отчёта:** `logs/evaluation_report_{timestamp}.md`

**Структура отчёта:**
```markdown
# Evaluation Report — {date}

## Executive Summary
- Лучшая модель: X (composite score: Y)
- Худшая модель: Z (composite score: W)
- Ключевые находки: 3-5 bullet points

## Model Rankings
| Rank | Model | Composite | Move Q | Reasoning Q | Efficiency | Reliability |
|------|-------|-----------|--------|-------------|------------|-------------|

## Per-Model Analysis
### Model: {name}
- Games: N, Moves: M
- Strengths: ...
- Weaknesses: ...
- Typical errors: ...

## Prompt Recommendations
### Recommendation 1: {title}
- Problem: {описание паттерна ошибки}
- Evidence: {конкретные ходы/игры}
- Suggestion: {что изменить в промпте}
- Expected impact: {на какие модели повлияет}

## Statistical Appendix
- Confidence intervals
- Effect sizes
- Temporal trends
```

---

## Фаза 2: Система оценки качества ходов (Move Quality)

### 2.1 Шахматная оценка хода

**Метрики (каждая 0-3 балла):**

| Критерий | 0 (плохо) | 1 (слабо) | 2 (хорошо) | 3 (отлично) |
|----------|-----------|-----------|------------|-------------|
| Leader Safety | Ход оставляет лидера под шахом/угрозой | Лидер не защищён, но нет прямой угрозы | Лидер защищён одной фигурой | Лидер в безопасности, множественная защита |
| Center Control | Ход уходит от центра (ring↑) | Нейтральный по позиции | Приближает фигуру к ring 1-2 | Занимает/контролирует rosette |
| Material | Теряет материал без компенсации | Равноценный размен | Выигрывает пешку/позицию | Выигрывает фигуру / создаёт форк |
| Development | Ход назад или повтор | Нейтральный | Выводит новую фигуру или улучшает buried level | Активирует фигуру на ring 0-1 |
| Three-Player Awareness | Ход явно помогает третьему игроку | Игнорирует третьего | Учитывает позицию третьего | Атакует слабого / защищается от обоих |

**Автоматически вычисляемые индикаторы** (из данных трейса):
- `outcome == "success"` → базовый ход легален и принят сервером
- `outcome == "fallback_random"` → модель не смогла выдать ход (score = 0)
- `server_move_response.is_check` → ход дал шах (bonus)
- `server_move_response.is_checkmate` → мат (maximum bonus)
- `server_move_response.eliminated_player` → выбивание игрока (major bonus)
- `retries > 0` → penalty за нестабильность

**Расчёт buried level delta:**
- Из `move_selected.from` и `move_selected.to` в TRIUMVIRATE нотации
- `buried_from = ring(from) + depth(from)`
- `buried_to = ring(to) + depth(to)`
- `delta = buried_from - buried_to` (положительный = улучшение)

### 2.2 Анализ тактических паттернов

**Автоматически детектируемые из legal_moves + move_selected:**
- **Количество легальных ходов**: мало (<5) = стеснённая позиция
- **Capture detection**: если `to` занято фигурой противника (из board state)
- **Check delivery**: из `server_move_response.is_check`
- **Promotion**: из `move_selected.promotion`
- **Retreat detection**: если `buried_to > buried_from`

---

## Фаза 3: Система оценки качества рассуждений (Reasoning Quality)

### 3.1 Рубрика для thinking-анализа

**Оценка агентом (Claude) каждого thinking-блока:**

| Критерий | Вопросы для оценки | Баллы |
|----------|-------------------|-------|
| **Threat Recognition** | Перечислены ли угрозы лидеру? Замечены ли атаки противников? Найдены ли тактические мотивы (вилки, связки)? | 0-3 |
| **Strategic Planning** | Есть ли план на 2+ хода? Оцениваются ли последствия? Учитываются ли позиционные факторы? | 0-3 |
| **Three-Player Dynamics** | Упомянут ли третий игрок? Оценивается ли баланс сил? Есть ли дипломатическое мышление? | 0-3 |
| **Board Accuracy** | Упомянутые координаты существуют на доске? Описанные фигуры совпадают с board state? Нет "галлюцинаций"? | 0-3 |
| **Move-Reasoning Consistency** | Выбранный ход соответствует заявленному анализу? Нет противоречий типа "лучше X" → играет Y? | 0-3 |
| **Analysis Depth** | Поверхностный (1 предложение) vs глубокий (вариантные линии)? Рассмотрено ли >1 кандидатского хода? | 0-3 |

**Верификация через board state:**
- Извлечь из `thinking` все упоминания координат (regex для TRIUMVIRATE и server нотации)
- Сравнить с `server_state_raw.board` — какие фигуры реально стоят на этих клетках
- Считать % совпадений = Board Accuracy Score

### 3.2 Hallucination Detection

**Типы галлюцинаций:**
1. **Phantom pieces**: модель упоминает фигуру на клетке где её нет
2. **Missing pieces**: модель не замечает критическую фигуру (атакующую лидера)
3. **Wrong color**: модель путает чьи фигуры
4. **Invalid coordinates**: координаты которые не существуют на доске
5. **Illegal move reasoning**: модель "рассматривает" ход которого нет в legal_moves

**Детекция:**
- Парсить thinking на координаты + фигуры
- Cross-reference с `server_state_raw` board
- Подсчитать hallucination rate = phantom / (phantom + correct)

---

## Фаза 4: Оценка эффективности (Efficiency Score)

### 4.1 Метрики эффективности

| Метрика | Формула | Хорошо | Плохо |
|---------|---------|--------|-------|
| **Cost per quality point** | `cost_usd / composite_score` | < $0.001/point | > $0.01/point |
| **Tokens per quality point** | `total_tokens / composite_score` | < 200 tok/point | > 1000 tok/point |
| **Time per move** | `llm_time_sec` | < 5s | > 30s |
| **Thinking efficiency** | `analysis_content / total_thinking_chars` | > 60% analysis | < 30% analysis |
| **Retry rate** | `moves_with_retries / total_moves` | < 5% | > 20% |
| **Format compliance** | `success_moves / total_moves` | > 95% | < 80% |

### 4.2 Thinking Content Analysis

**Классификация содержимого thinking:**
- **Правила пересказ**: модель повторяет правила из промпта (waste)
- **Анализ позиции**: описание текущего состояния (useful)
- **Вариантные линии**: if-then рассуждения о ходах (very useful)
- **Стратегические соображения**: оценка баланса сил (useful)
- **Самоповтор**: повторение одних и тех же мыслей (waste)

**Metric:** `useful_content_ratio = (analysis + variants + strategy) / total_chars`

---

## Фаза 5: Composite Score и Model Ranking

### 5.1 Composite Score Formula

```
Composite = w1 * MoveQuality + w2 * ReasoningQuality + w3 * Efficiency + w4 * Reliability

Предложенные веса (настраиваемые):
  w1 = 0.40  (качество хода — главное)
  w2 = 0.25  (качество рассуждений)
  w3 = 0.15  (эффективность: cost/time/tokens)
  w4 = 0.20  (надёжность: success rate, format compliance)

Каждый компонент нормализуется в диапазон [0, 1]:
  MoveQuality = sum(criteria_scores) / max_possible
  ReasoningQuality = sum(rubric_scores) / max_possible
  Efficiency = 1 - normalize(cost_per_quality, min, max)
  Reliability = success_rate * (1 - retry_rate * 0.5)
```

### 5.2 Model Comparison

**Для каждой модели:**
- Median composite score (с 95% CI через bootstrap)
- Trend: composite vs move_number (деградация по ходу игры?)
- Best/worst moves с примерами
- Failure mode distribution (типы ошибок)

**Ranking output:**
```
1. claude-sonnet-4-20250514    Composite: 0.82 ± 0.04  [Move: 0.85, Reason: 0.78, Eff: 0.71, Rel: 0.95]
2. gpt-4o                      Composite: 0.76 ± 0.06  [Move: 0.79, Reason: 0.82, Eff: 0.62, Rel: 0.88]
3. gemini-2.0-flash            Composite: 0.69 ± 0.05  [Move: 0.71, Reason: 0.65, Eff: 0.85, Rel: 0.58]
```

---

## Фаза 6: Генерация рекомендаций по промптам

### 6.1 Pattern → Recommendation Mapping

| Паттерн ошибки | Детекция | Рекомендация по промпту |
|----------------|----------|------------------------|
| Модель не замечает шахи | Board Accuracy < 1 при наличии check в state | Добавить в промпт: "CRITICAL: Check if YOUR Leader is under attack FIRST" |
| Игнорирует третьего игрока | Three-Player Dynamics score < 1 для >50% ходов | Добавить: "Before each move, assess: who is winning? who is weakest? how does your move change the balance?" |
| Пересказывает правила | thinking_efficiency < 30% | Сократить system_prompt, убрать правила которые модель и так знает, заменить на "You know the rules. Focus on position analysis." |
| Низкий format compliance | retry_rate > 15% | Переключить на format_simple для слабых моделей; усилить format instruction |
| Пассивная игра (high buried level) | avg buried_to > 4 | Добавить: "Prefer moves that decrease buried level. Target ring 0-1." |
| Нет вариантных линий | Analysis Depth < 1 для >50% ходов | Добавить: "Consider at least 3 candidate moves. For each, think 2 moves ahead." |
| Repetitive moves | >3 одинаковых ходов подряд | Добавить: "Avoid repeating the same move. If you played X last turn, consider other options." |
| Высокий self-repetition в thinking | >30% повторов в тексте | Уменьшить max_tokens для thinking; сделать промпт более structured |

### 6.2 Model-Specific Recommendations

**По результатам анализа агент генерирует:**

```markdown
## Рекомендации для модели: deepseek/deepseek-chat

### Проблема 1: Низкая format compliance (72%)
- Причина: модель часто добавляет текст до/после JSON
- Рекомендация: переключить на format_simple (plain text)
- Альтернатива: добавить в промпт "Output ONLY the JSON object, no other text"

### Проблема 2: Слабый three-player awareness (score 0.8/3)
- Причина: в 68% ходов третий игрок не упоминается
- Рекомендация: добавить в user_template секцию "Opponent analysis"
  с принудительным анализом каждого из двух противников

### Оптимальный промпт-конфиг:
- response_format: simple
- temperature: 0.4 (вместо 0.3 — меньше retries)
- additional_rules: "Focus analysis on threats and center control. Limit thinking to 200 words."
```

---

## Фаза 7: Реализация (этапы и файлы)

### Этап 1: Базовый анализатор (MVP)

**Новые файлы:**

| Файл | Назначение | ~Строк |
|------|-----------|--------|
| `.claude/agents/trace-evaluator.md` | Skill-определение агента | ~150 |
| `trace_analyzer/evaluator.py` | Автоматические метрики (buried level, capture, retry) | ~200 |
| `trace_analyzer/scorer.py` | Composite score calculation | ~150 |

**Что делает:**
- Загружает трейсы через существующий `data_loader.scan_traces()`
- Вычисляет автоматические метрики для каждого хода
- Агрегирует per-model statistics
- Выводит ranking таблицу

### Этап 2: Глубокий анализ рассуждений

**Новые файлы:**

| Файл | Назначение | ~Строк |
|------|-----------|--------|
| `trace_analyzer/reasoning_analyzer.py` | Парсинг thinking, hallucination detection | ~250 |
| `trace_analyzer/board_verifier.py` | Сравнение thinking с board state | ~150 |

**Что делает:**
- Парсит thinking-блоки на структурные компоненты
- Извлекает упомянутые координаты и фигуры
- Сравнивает с реальным board state → hallucination score
- Оценивает consistency move ↔ reasoning

### Этап 3: Промпт-рекомендации

**Новые файлы:**

| Файл | Назначение | ~Строк |
|------|-----------|--------|
| `trace_analyzer/prompt_advisor.py` | Pattern detection → recommendations | ~200 |

**Что делает:**
- Детектирует паттерны ошибок из таблицы 6.1
- Генерирует конкретные рекомендации per-model
- Предлагает оптимальный конфиг (format, temperature, additional_rules)

### Этап 4: Отчёты и интеграция

**Новые файлы:**

| Файл | Назначение | ~Строк |
|------|-----------|--------|
| `trace_analyzer/report_generator.py` | Markdown-отчёт | ~150 |

**Изменения в существующих:**
- `trace_analyzer/app.py` — новый таб "Evaluation" (опционально)
- `trace_analyzer/views/evaluation.py` — UI для оценок (опционально)

---

## Фаза 8: Системный промпт агента (полный текст)

```markdown
# Trace Evaluator Agent — System Instructions

You are an expert analyst for Three-Player Chess AI evaluation. You analyze
game trace logs to assess LLM model quality and generate optimization recommendations.

## Your Domain Knowledge

### Three-Player Chess (Triumvirate)
- 96-cell hexagonal board, 3 sectors: White, Black, Red
- TRIUMVIRATE notation: S#/O#.# where S=sector, #=ring, O=opponent, #=depth, .#=flank
- Rosette cells (C/S.N) = center, strategically dominant
- Buried level = Ring + Depth (0=best, 6=worst, ≤4 is the activity threshold)
- Capturing a Leader eliminates that player; their pieces transfer to the captor
- Win = checkmate both opponents

### Trace File Structure
Each move trace contains:
- `prompt_pipeline` — full prompts sent to model
- `llm_responses[].raw_response` — full model output including thinking
- `server_state_raw` — complete board state BEFORE the move
- `move_selected` — chosen move (from/to/promotion)
- `server_move_response` — server result (check/checkmate/elimination)
- `parser_attempts[]` — parsing details (coordinates found, pairs tested)
- `statistics` — time, tokens, cost, retries
- `outcome` — success/fallback_random/error

### Available Code
- `trace_analyzer/data_loader.py` — `scan_traces()`, `get_games_summary()`
- `trace_analyzer/evaluator.py` — automatic metrics
- `trace_analyzer/scorer.py` — composite scoring
- `notation_converter.py` — server ↔ TRIUMVIRATE conversion

## Evaluation Rubric

### Move Quality (0-15 points)
1. Leader Safety (0-3): Is the Leader safe after this move?
2. Center Control (0-3): Does the move improve ring position?
3. Material (0-3): Material gain/loss?
4. Development (0-3): Does buried level decrease?
5. Three-Player Awareness (0-3): Does the move account for both opponents?

### Reasoning Quality (0-18 points)
1. Threat Recognition (0-3): Are threats identified?
2. Strategic Planning (0-3): Is there a multi-move plan?
3. Three-Player Dynamics (0-3): Is the third player considered?
4. Board Accuracy (0-3): Do mentioned pieces match reality?
5. Move-Reasoning Consistency (0-3): Does the move match the analysis?
6. Analysis Depth (0-3): Are multiple candidates considered?

### Efficiency (0-1 normalized)
- Cost per quality point
- Token efficiency (useful analysis / total tokens)
- Time per move

### Reliability (0-1 normalized)
- Success rate (no fallback, no error)
- Format compliance (first attempt success)

### Composite Score
Composite = 0.40 * MoveQuality_norm + 0.25 * ReasoningQuality_norm
          + 0.15 * Efficiency + 0.20 * Reliability

## Your Tasks

When invoked, determine which analysis mode is needed:

### Mode 1: Batch Analysis (default)
1. Load all traces from logs/
2. Compute per-move automatic metrics
3. Aggregate per-model statistics
4. Produce ranking table with confidence intervals
5. Identify top 3 patterns of errors
6. Generate prompt recommendations

### Mode 2: Deep Analysis (when user specifies a game/model)
1. Load traces for specified game/model
2. Evaluate each move using full rubric
3. Identify best and worst moves with explanations
4. Analyze thinking quality with examples
5. Detect hallucinations
6. Generate model-specific recommendations

### Mode 3: Prompt Comparison (when user provides prompt variants)
1. Group traces by prompt configuration
2. Compare quality metrics between groups
3. Identify statistically significant differences
4. Recommend winning configuration

## Output Format

Always produce a structured report with:
1. Executive Summary (3-5 sentences)
2. Rankings Table
3. Per-Model Analysis (strengths, weaknesses, error patterns)
4. Prompt Recommendations (problem → evidence → suggestion)
5. Statistical Notes (sample sizes, confidence)

Save report to: logs/evaluation_report_{timestamp}.md
```

---

## Зависимости и ограничения

### Зависимости
- Существующий `data_loader.py` для загрузки трейсов
- `notation_converter.py` для вычисления buried level
- Claude Code SDK для skill-интеграции
- Достаточный объём трейсов (минимум 10 ходов на модель для значимых выводов)

### Ограничения
- Шахматная оценка хода ограничена информацией в трейсе (нет stockfish-подобного движка для three-player chess)
- Оценка reasoning субъективна (делается Claude'ом, а не алгоритмом) — нужна калибровка
- Для статистической значимости нужно ≥30 ходов на модель
- Агент не может сам запускать игры для тестирования рекомендаций

### Приоритеты реализации
1. **P0**: Skill-файл агента + базовые автоматические метрики (Этапы 1)
2. **P1**: Reasoning analysis + hallucination detection (Этап 2)
3. **P2**: Prompt recommendations (Этап 3)
4. **P3**: UI-интеграция в trace_analyzer (Этап 4, опционально)

---

## Критерии успеха

1. Агент корректно ранжирует модели по качеству игры (валидация: модель с большим win rate должна быть выше)
2. Рекомендации по промптам приводят к измеримому улучшению composite score при A/B тестировании
3. Hallucination detection находит ≥80% случаев когда модель упоминает несуществующие фигуры
4. Время batch-анализа 300 трейсов — < 5 минут
5. Отчёт содержит actionable recommendations, а не абстрактные оценки
