# Implementation Plan: SmartBot-Powered LLM Evaluation

**Дата:** 2026-03-18
**Статус:** Draft
**Зависимости:** SmartBot (`T:\test_python\Triumvirate_Smartbot`) — read-only
**Целевой проект:** `T:\test_python\Triumvirate_LLMbot\examples\decomp`

---

## Причины: почему текущей системы оценки недостаточно

### 1. Отсутствие объективного эталона качества хода

Текущая система не знает, какой ход был бы лучшим в данной позиции. Она фиксирует *факты* (был ли шах, было ли взятие, сколько стоил вызов API), но не может ответить на главный вопрос: **насколько хорош выбранный ход по сравнению с оптимальным?**

Модель может делать шахи (высокий `check_rate`) и при этом проигрывать — потому что шахи были бессмысленными или вредными. Модель может тихо двигать фигуры к центру (высокий `buried_delta`) и при этом не замечать мат в один ход. Без эталона невозможно отличить активную игру от бессистемных действий.

### 2. Метрики измеряют симптомы, а не причины

| Что мы видим сейчас | Чего мы не видим |
|---------------------|-----------------|
| Модель сделала 5 шахов | Были ли эти шахи сильными или пустыми? |
| Модель взяла 3 фигуры | Были ли размены выгодными (SEE) или убыточными? |
| Модель двигала фигуры к центру | Был ли это лучший план или она упускала тактику? |
| Модель проиграла | На каком ходе и почему — blunder, проигнорированная угроза, стратегическая ошибка? |
| win_rate = 30% | Это из-за плохой тактики, плохой защиты, или плохого понимания трёхсторонней динамики? |

Текущий `auto_composite` = 35% reliability + 30% activity + 20% tactical + 15% efficiency — это формула, где 35% веса отдано тому, правильно ли модель форматирует JSON-ответ, а 0% — тому, хорош ли сам ход.

### 3. Невозможно определить тип слабости модели

Два разных промпта или две разные модели могут иметь одинаковый win_rate, но проигрывать по совершенно разным причинам:
- **Модель A** не видит угрозы — ей нужно лучше описать позицию в промпте
- **Модель B** подставляет фигуры — ей нужна инструкция проверять безопасность хода
- **Модель C** атакует слабого вместо сильного — ей нужно объяснить политику трёхсторонних шахмат

Без декомпозиции рейтинга на компоненты (material, defense, tactical, positional, risk) эта диагностика невозможна.

### 4. Субъективность экспертной оценки

Агент `model-evaluator` оценивает ходы по рубрике 0-15 баллов, но:
- Это стоит дорого (каждая оценка = вызов LLM)
- Результаты нестабильны (одна и та же позиция может получить разный балл)
- Оценка субъективна и зависит от "настроения" LLM-оценщика
- Невозможно оценить тысячи ходов — только выборка 10-15

SmartBot evaluation — детерминированный, бесплатный, воспроизводимый, масштабируемый.

### 5. Нет обратной связи для оптимизации промптов

Агент `/optimize-prompts` не имеет точных данных о том, *что именно* модели делают неправильно. Он видит общие метрики (win_rate, check_rate) и делает общие рекомендации. С SmartBot-данными он сможет сказать: "модели пропускают CRITICAL угрозы в 23% случаев — добавьте в промпт инструкцию проверять безопасность короля" или "модели делают убыточные размены — добавьте инструкцию оценивать стоимость фигур перед взятием".

### 6. Three-Player специфика не оценивается

Трёхсторонние шахматы принципиально отличаются от обычных:
- Нужно выбирать *кого* атаковать (political matrix)
- Третий игрок может усилить или ослабить угрозу (AMPLIFIER / DETERRENT)
- Потеря фигуры критичнее — два противника могут скоординироваться

Текущая система полностью игнорирует эту специфику. SmartBot уже имеет реализованную political matrix и анализ third_player_factor.

---

## Цели: чего мы хотим добиться

### Цель 1: Объективный, детерминированный рейтинг каждого хода LLM

**Метрика успеха:** Для каждого хода из трейса доступен `smartbot_rating_gap` — числовая разница между лучшим возможным ходом и ходом, выбранным моделью. Эта метрика:
- Детерминированная — один и тот же ход всегда получает один и тот же рейтинг
- Бесплатная — не требует вызовов LLM
- Масштабируемая — работает для тысяч ходов за минуты
- Калиброванная — основана на проверенном SmartBot evaluation с 5 компонентами, тактической верификацией и pseudo-SEE

**Результат:** `median_rating_gap` заменяет субъективный `auto_composite` как главная метрика качества модели.

### Цель 2: Диагностика слабостей — понимать *почему* модель проигрывает

**Метрика успеха:** Для каждой модели доступен профиль слабостей из 5 компонентов:
- `weakness_material` — модель плохо оценивает размены
- `weakness_defense` — модель не видит угрозы своим фигурам
- `weakness_tactical` — модель упускает тактические возможности (шахи, вилки)
- `weakness_positional` — модель не понимает позиционные нюансы (централизация, мобильность)
- `weakness_risk` — модель подставляет фигуры под атаку

**Результат:** Вместо "модель X играет плохо" мы говорим: "модель X не видит угрозы (defense -47%), но хорошо тактикует (tactical +12%). Рекомендация: усилить в промпте блок проверки безопасности фигур."

### Цель 3: Наглядная классификация ходов — brilliant / good / inaccuracy / mistake / blunder

**Метрика успеха:** Каждый ход LLM классифицирован по шкале аналогичной Chess.com. Для каждой модели доступно распределение:
```
Model A: 15% brilliant, 40% good, 25% inaccuracy, 15% mistake, 5% blunder
Model B: 5% brilliant,  20% good, 30% inaccuracy, 25% mistake, 20% blunder
```

**Результат:** Мгновенно видно, какая модель "играет чисто" (мало blunder'ов) vs "играет ярко но рискованно" (много brilliant + много blunder).

### Цель 4: Обнаружение критических ошибок — blunder'ы и пропущенные маты

**Метрика успеха:**
- `blunder_rate` — % ходов, после которых противник мог поставить мат в 1 ход
- `missed_mate_count` — количество позиций, где был доступен мат, но модель его не нашла
- `threat_addressed_rate` — % позиций с CRITICAL/HIGH угрозой, где модель правильно защитилась

**Результат:** Автоматическое обнаружение самых грубых ошибок без ручного анализа. "Модель X допустила мат в 3 из 100 партий" — конкретная, проверяемая метрика.

### Цель 5: Оценка стратегического мышления в контексте трёх игроков

**Метрика успеха:**
- `political_correctness_rate` — модель атакует правильную цель (leader атакует leader, underdog атакует leader)?
- `third_player_awareness` — модель учитывает третьего игрока при оценке позиции?
- `material_advantage_trend` — модель наращивает или теряет преимущество по ходу партии?

**Результат:** Оценка того, насколько модель понимает *специфику* трёхсторонних шахмат, а не просто играет как в обычные шахматы.

### Цель 6: Автоматизация оценки hallucinations

**Метрика успеха:** `board_accuracy_rate` — автоматически вычисленный % корректных упоминаний фигур в thinking-блоке. Не требует ручного анализа агентом.

**Результат:** "Модель X галлюцинирует в 34% координат" → конкретный сигнал для оптимизации промпта (возможно, нужно упростить описание позиции).

### Цель 7: Замкнутый цикл обратной связи для оптимизации промптов

**Метрика успеха:** Агент `/optimize-prompts` получает конкретные данные:
```
Проблема: модели пропускают CRITICAL угрозы в 23% случаев
→ Рекомендация: добавить в промпт "Before choosing a move, check if your King is safe"
→ Изменение: модифицируем промпт
→ Повторный запуск: CRITICAL miss rate снизился до 8%
```

**Результат:** Оптимизация промптов становится data-driven вместо intuition-driven. Каждое изменение промпта можно измерить по конкретным метрикам SmartBot.

### Цель 8: Снижение стоимости оценки

**Метрика успеха:** Оценка 1000 ходов:
- Текущая (model-evaluator agent): ~$5-20 за LLM вызовы, ~30 минут, нестабильная
- SmartBot evaluation: $0, ~2 минуты, детерминированная

**Результат:** Можно оценивать каждый ход каждой партии, а не выборку 10-15 ходов. Полное покрытие вместо сэмплирования.

---

## Оглавление

- [Phase 0: Подготовка и проверки](#phase-0-подготовка-и-проверки)
- [Phase 1: SmartBot Adapter](#phase-1-smartbot-adapter)
- [Phase 2: SmartBot Evaluator — per-move оценка](#phase-2-smartbot-evaluator--per-move-оценка)
- [Phase 3: Расширение MoveMetrics](#phase-3-расширение-movemetrics)
- [Phase 4: Расширение Aggregator](#phase-4-расширение-aggregator)
- [Phase 5: Threat Awareness & Blunder Detection](#phase-5-threat-awareness--blunder-detection)
- [Phase 6: Political & Three-Player Dynamics](#phase-6-political--three-player-dynamics)
- [Phase 7: Exchange Quality (SEE)](#phase-7-exchange-quality-see)
- [Phase 8: Move Category Classification](#phase-8-move-category-classification)
- [Phase 9: Hallucination Detection (Automated)](#phase-9-hallucination-detection-automated)
- [Phase 10: Views & CLI интеграция](#phase-10-views--cli-интеграция)
- [Phase 11: Обновление model-evaluator агента](#phase-11-обновление-model-evaluator-агента)
- [Phase 12: Тесты всего pipeline](#phase-12-тесты-всего-pipeline)

---

## Phase 0: Подготовка и проверки

### Preconditions

- [x] **0.1** Проверить, что SmartBot's `parse_3pf()` корректно восстанавливает `GameState` из строк, хранящихся в LLM-трейсах
  - [ ] Прочитать 5+ реальных трейсов из `logs/`
  - [ ] Извлечь `position_3pf` из `server_state_raw`
  - [ ] Вызвать `parse_3pf()` и убедиться, что результат — валидный `GameState`
  - [ ] Проверить: `legal_moves` из GameState совпадают с `legal_moves` из трейса

- [x] **0.2** Проверить, что SmartBot evaluation pipeline работает на восстановленном GameState
  - [ ] Для 3+ позиций из трейсов: `find_all_threats()` → `analyze_defenses()` → `calculate_move_rating()` для всех легальных ходов
  - [ ] Проверить, что ход LLM найден среди оценённых ходов
  - [ ] Замерить время: одна позиция = ? ms (ожидание: 50-200ms)

- [x] **0.3** Проверить структуру трейс-файлов LLM-бота
  - [ ] Подтвердить наличие `position_3pf` в каждом трейсе (поле `server_state_raw.position_3pf`)
  - [ ] Подтвердить наличие `legal_moves` в `server_state_raw`
  - [ ] Подтвердить наличие `move_selected.from` и `move_selected.to` (серверная нотация)
  - [ ] Проверить: для fallback_random ходов — есть ли move_selected?

- [x] **0.4** Проверить совместимость нотаций
  - [ ] LLM-бот хранит ходы в серверной нотации (A1, B2, ...)
  - [ ] SmartBot использует `Coordinate("A1")` — совместимо
  - [ ] SmartBot's `build_move(Coordinate(from), Coordinate(to), game_state)` — работает ли с серверными координатами из трейса?

- [x] **0.5** Проверить импортируемость SmartBot модулей
  - [ ] Добавить `T:\test_python\Triumvirate_Smartbot` в `sys.path`
  - [ ] Проверить, что нет конфликтов имён модулей (оба проекта имеют `constants.py`, `settings.py`, `bot_runner.py` и т.д.)
  - [ ] Если есть конфликты — определить стратегию изоляции (subprocess? отдельный sys.path?)

### Выход из Phase 0

Документ `phase0_validation.md` с результатами всех проверок и решениями по обнаруженным проблемам.

---

## Phase 1: SmartBot Adapter

**Цель:** Изолированный модуль, инкапсулирующий все импорты SmartBot.

### TODO

- [x] **1.1** Создать `trace_analyzer/smartbot_adapter.py`
  - [ ] Функция `_setup_smartbot_path()` — добавляет SmartBot root в sys.path с защитой от дублирования
  - [ ] Функция `evaluate_position(position_3pf: str, legal_moves: dict, llm_from: str, llm_to: str) → PositionEvaluation`
  - [ ] Dataclass `PositionEvaluation` со всеми полями результата
  - [ ] Dataclass `MoveEvaluation` — результат оценки одного хода
  - [ ] Exception handling: если SmartBot не найден / parse_3pf fails / evaluation fails → возвращать `None` с warning
  - [ ] Lazy import: SmartBot модули импортируются только при первом вызове `evaluate_position()`

- [x] **1.2** Реализовать внутренний pipeline в `evaluate_position()`:
  ```
  1. parse_3pf(position_3pf) → GameState
  2. find_all_threats(my_color, game_state) → threats
  3. analyze_defenses(my_color, game_state, threats) → threat_summary
  4. Для каждого легального хода:
     a. build_move(Coordinate(from), Coordinate(to), game_state) → Move
     b. calculate_move_rating(move, game_state, threat_summary) → MoveRating
  5. tactical_verify(rated_moves, game_state, my_color) → verified
  6. Найти ход LLM в verified list → llm_rating, llm_rank
  7. select_move(verified) → smartbot_best
  8. Собрать PositionEvaluation
  ```

- [x] **1.3** Добавить функцию `is_smartbot_available() → bool`
  - [ ] Проверяет наличие SmartBot path и ключевых модулей
  - [ ] Используется для graceful degradation: если SmartBot недоступен, старые метрики работают

- [x] **1.4** Добавить конфигурацию пути к SmartBot
  - [ ] Переменная окружения `SMARTBOT_PATH` (опционально)
  - [ ] Fallback на `T:\test_python\Triumvirate_Smartbot`
  - [ ] Документация в CLAUDE.md

### Проверки после Phase 1

- [ ] `evaluate_position()` возвращает корректный `PositionEvaluation` для 10+ реальных позиций из логов
- [ ] `llm_rank` > 0 для всех success-ходов
- [ ] `rating_gap = best_rating - llm_rating` — разумные значения (0-2000 для нормальных позиций)
- [ ] Performance: < 500ms на позицию в среднем
- [ ] `is_smartbot_available()` корректно определяет наличие/отсутствие SmartBot
- [ ] При отсутствии SmartBot — никакие существующие функции не ломаются

---

## Phase 2: SmartBot Evaluator — per-move оценка

**Цель:** Модуль, который прогоняет SmartBot evaluation по всем ходам из трейсов.

### TODO

- [x] **2.1** Создать `trace_analyzer/smartbot_evaluator.py`
  - [ ] Функция `evaluate_traces(raw_traces: list[dict]) → list[dict]` — массовая оценка
  - [ ] Для каждого трейса: извлечь `position_3pf`, `legal_moves`, `move_selected` → вызвать `evaluate_position()`
  - [ ] Результат: dict с полями `smartbot_*` для каждого хода
  - [ ] Пропуск ходов без `position_3pf` или с `outcome = error` (с warning)
  - [ ] Progress reporting: печать прогресса каждые 100 ходов

- [x] **2.2** Добавить кэширование
  - [ ] Кэш по `position_3pf` — одна и та же позиция может встречаться если LLM делал retry
  - [ ] LRU cache или dict в памяти (позиций обычно < 10000)

- [ ] **2.3** Добавить параллелизацию (опционально)
  - [ ] `concurrent.futures.ProcessPoolExecutor` для SmartBot evaluation
  - [ ] Настраиваемое число воркеров через `--workers N`
  - [ ] Fallback на последовательное выполнение если workers=1

### Проверки после Phase 2

- [ ] `evaluate_traces()` обрабатывает все трейсы из `logs/` без ошибок
- [ ] Для fallback_random ходов — тоже есть оценка (рандомный ход оценён SmartBot)
- [ ] Для ходов без position_3pf — graceful skip с warning
- [ ] Время обработки всех трейсов < 10 минут (при ~2000 ходов)
- [ ] Кэш работает: повторные позиции не пересчитываются

---

## Phase 3: Расширение MoveMetrics

**Цель:** Добавить SmartBot-поля в существующий `MoveMetrics`.

### TODO

- [x] **3.1** Расширить dataclass `MoveMetrics` в `move_metrics.py`:
  ```python
  # SmartBot evaluation (Phase 1-2)
  smartbot_available: bool = False
  smartbot_llm_rating: int = 0
  smartbot_best_rating: int = 0
  smartbot_rating_gap: int = 0
  smartbot_llm_rank: int = 0
  smartbot_total_evaluated: int = 0
  smartbot_move_category: str = ""  # brilliant/good/inaccuracy/mistake/blunder

  # SmartBot components (Phase 1)
  smartbot_material: int = 0
  smartbot_defense: int = 0
  smartbot_tactical: int = 0
  smartbot_positional: int = 0
  smartbot_risk: int = 0

  # SmartBot context (Phase 5-6)
  smartbot_threats_total: int = 0
  smartbot_threats_critical: int = 0
  smartbot_threat_addressed: bool = False
  smartbot_allows_mate: bool = False
  smartbot_has_discovery: bool = False
  smartbot_material_advantage: int = 0
  smartbot_player_role: str = ""
  smartbot_game_phase: float = 0.0

  # Exchange quality (Phase 7)
  smartbot_exchange_classification: str = ""  # winning/favorable/equal/unfavorable/losing
  ```

- [x] **3.2** Расширить `compute_move_metrics()`:
  - [ ] Добавить optional параметр `smartbot_eval: dict | None = None`
  - [ ] Если `smartbot_eval` передан — заполнить `smartbot_*` поля
  - [ ] Если нет — поля остаются дефолтными (backward-compatible)

- [x] **3.3** Обновить `to_dict()` — уже работает через `asdict()`, новые поля включатся автоматически

### Проверки после Phase 3

- [ ] Существующие тесты `move_metrics` (если есть) проходят без изменений
- [ ] `MoveMetrics` без SmartBot данных — все `smartbot_*` поля дефолтные
- [ ] `MoveMetrics` со SmartBot данными — корректно заполнены
- [ ] `to_dict()` включает все новые поля
- [ ] JSON serialization работает (нет типов, которые `json.dumps` не знает)
- [ ] Размер `metrics.json` увеличился разумно (проверить на реальных данных)

---

## Phase 4: Расширение Aggregator

**Цель:** Новые агрегированные метрики на основе SmartBot evaluation.

### TODO

- [x] **4.1** Расширить `ModelStats` в `aggregator.py`:
  ```python
  # SmartBot quality metrics
  smartbot_avg_rating_gap: float = 0.0
  smartbot_median_rating_gap: float = 0.0
  smartbot_p90_rating_gap: float = 0.0      # worst 10% of moves
  smartbot_rank_1_rate: float = 0.0          # % ходов = лучший по SmartBot
  smartbot_top3_rate: float = 0.0            # % ходов в топ-3
  smartbot_blunder_rate: float = 0.0         # % blunder moves
  smartbot_brilliant_rate: float = 0.0       # % brilliant moves
  smartbot_allows_mate_rate: float = 0.0     # % ходов, допускающих мат
  smartbot_threat_addressed_rate: float = 0.0 # % правильных реакций на угрозы
  smartbot_missed_mate_count: int = 0        # ходов с пропущенным матом

  # Move category distribution
  smartbot_cat_brilliant: float = 0.0
  smartbot_cat_good: float = 0.0
  smartbot_cat_inaccuracy: float = 0.0
  smartbot_cat_mistake: float = 0.0
  smartbot_cat_blunder: float = 0.0

  # Component weakness profile
  smartbot_avg_material: float = 0.0
  smartbot_avg_defense: float = 0.0
  smartbot_avg_tactical: float = 0.0
  smartbot_avg_positional: float = 0.0
  smartbot_avg_risk: float = 0.0

  # Overall SmartBot quality score
  smartbot_quality_score: float = 0.0  # normalized composite [0, 1]
  ```

- [x] **4.2** Расширить `aggregate_by_model()`:
  - [ ] Фильтровать только ходы с `smartbot_available = True`
  - [ ] Вычислять все `smartbot_*` метрики из per-move данных
  - [ ] Если ни один ход не имеет SmartBot данных — поля остаются дефолтными

- [x] **4.3** Расширить `GameResult`:
  ```python
  smartbot_avg_rating_gap: float = 0.0
  smartbot_blunder_count: int = 0
  smartbot_allows_mate_count: int = 0
  smartbot_avg_material_advantage: float = 0.0
  ```

- [x] **4.4** Обновить `compute_composite_scores()`:
  - [ ] Новая формула composite (если SmartBot данные есть):
    ```
    auto_composite = 0.20 × reliability_score
                   + 0.35 × smartbot_quality_score   # NEW primary
                   + 0.15 × tactical_events_score    # check_rate, capture_win_rate
                   + 0.10 × efficiency_score
                   + 0.20 × win_rate_normalized      # NEW
    ```
  - [ ] Если SmartBot данных нет — старая формула (backward-compatible)
  - [ ] `smartbot_quality_score = 1 - normalized(median_rating_gap)`

- [x] **4.5** Обновить `_print_table()`:
  - [ ] Добавить столбцы: `SB_Gap`, `SB_Q`, `Blnd%`
  - [ ] Сократить существующие столбцы если нужно для ширины

### Проверки после Phase 4

- [ ] Модели ранжируются: модель с меньшим rating_gap — выше
- [ ] Модели без SmartBot данных — ранжируются по старой формуле, но ниже моделей с SmartBot данными
- [ ] `model_rankings.json` содержит все новые поля
- [ ] Таблица в stdout читаема и не ломает форматирование
- [ ] Composite формула: модель с win_rate=100% но blunder_rate=50% — не на первом месте

---

## Phase 5: Threat Awareness & Blunder Detection

**Цель:** Оценка оборонительного мышления LLM и обнаружение грубых ошибок.

### TODO

- [ ] **5.1** В `smartbot_adapter.py` → `PositionEvaluation` добавить:
  ```python
  threats: list[dict]                 # все угрозы (severity, target, attacker)
  critical_threats: int               # кол-во CRITICAL угроз
  priority_threat: dict | None        # самая важная угроза
  llm_threat_addressed: bool          # ход LLM адресует приоритетную угрозу
  llm_allows_mate: bool               # после хода LLM противник может мат
  llm_has_discovered_attack: bool     # ход открывает атаку на свою фигуру
  missed_mate_available: bool         # был мат среди легальных, LLM не нашёл
  ```

- [ ] **5.2** Реализовать `_check_threat_addressed()` в adapter:
  - [ ] Использовать SmartBot's `find_threat_addressed(from_coord, to_coord, threats)`
  - [ ] Проверять, что ход LLM устраняет CRITICAL или HIGH угрозу

- [ ] **5.3** Реализовать `_check_allows_mate()` в adapter:
  - [ ] Использовать SmartBot's `tactical_verify._check_mate_threat()`
  - [ ] Сделать opt-in (отдельный flag `--check-mates`), т.к. это тяжёлое вычисление

- [ ] **5.4** Реализовать `_check_discovered_attacks()` в adapter:
  - [ ] Использовать SmartBot's `tactical_verify._check_discovered_attacks()`
  - [ ] Работает через `simulate_move_fast()`

- [ ] **5.5** Реализовать `_check_missed_mate()`:
  - [ ] Проверить, есть ли `gives_mate = True` среди оценённых ходов
  - [ ] Если да, а ход LLM не мат → `missed_mate = True`

### Проверки после Phase 5

- [ ] `threat_addressed_rate` > 0 для реальных данных (хотя бы некоторые ходы адресуют угрозы)
- [ ] `allows_mate_rate` разумная (обычно < 5% для нормальных моделей)
- [ ] Blunder detection не считает blunder'ом ход, после которого мат невозможен
- [ ] Missed mate корректно определяется (вручную проверить 3+ случая)
- [ ] Performance: `--check-mates` увеличивает время не более чем в 3x

---

## Phase 6: Political & Three-Player Dynamics

**Цель:** Оценка стратегического мышления в контексте трёх игроков.

### TODO

- [ ] **6.1** В `PositionEvaluation` добавить:
  ```python
  player_role: str          # leader/middle/underdog (из SmartBot)
  material_advantage: int   # мой материал vs средний противников
  game_phase: float         # 1.0=opening, 0.0=endgame
  political_target_correct: bool  # атакует ли LLM правильную цель?
  ```

- [ ] **6.2** Реализовать `_check_political_correctness()`:
  - [ ] Определить роль через SmartBot's `get_player_role()`
  - [ ] Если ход — взятие, определить цель: `get_player_role(target_owner)`
  - [ ] Проверить по `political_matrix`: оценка > 0 = правильная цель, < 0 = неправильная
  - [ ] Для не-взятий: `None` (не применимо)

- [ ] **6.3** Добавить `game_phase` для каждого хода:
  - [ ] `get_game_phase(game_state)` → float
  - [ ] `is_endgame(game_state)` → bool
  - [ ] Позволяет анализировать: как модель играет в разных фазах?

- [ ] **6.4** Добавить `material_advantage` per move:
  - [ ] `get_material_advantage(my_color, game_state)` → int
  - [ ] Трекинг тренда по ходам → `material_advantage_trend` в GameResult

### Проверки после Phase 6

- [ ] `player_role` корректно определяется для начальной позиции (все MIDDLE)
- [ ] `political_target_correct` = True когда underdog атакует leader
- [ ] `game_phase` монотонно убывает в ходе партии (фигуры снимаются)
- [ ] `material_advantage` меняется при взятиях

---

## Phase 7: Exchange Quality (SEE)

**Цель:** Детальная оценка качества разменов.

### TODO

- [ ] **7.1** В `MoveEvaluation` добавить:
  ```python
  exchange_classification: str | None  # winning/favorable/equal/unfavorable/losing
  exchange_net_value: int | None       # SEE net value
  exchange_is_free: bool | None        # захват без возможности recapture
  exchange_gives_check: bool | None    # взятие с шахом
  ```

- [ ] **7.2** Реализовать в adapter:
  - [ ] Для capture-ходов: извлечь `exchange_result` из `MoveRating`
  - [ ] Записать `classification`, `net_value`, `is_free`, `gives_check`
  - [ ] Для non-capture: `None`

- [ ] **7.3** Добавить агрегированные метрики:
  - [ ] `capture_quality_distribution` — распределение по ExchangeClassification
  - [ ] `avg_exchange_net` — средний SEE net для всех взятий
  - [ ] `free_capture_rate` — % бесплатных захватов (is_free)

### Проверки после Phase 7

- [ ] Все capture-ходы имеют `exchange_classification`
- [ ] Non-capture ходы имеют `None`
- [ ] `WINNING` captures: net_value > 200
- [ ] `LOSING` captures: net_value < -200
- [ ] Модели с высоким `capture_win_rate` имеют низкий % LOSING exchanges

---

## Phase 8: Move Category Classification

**Цель:** Наглядная классификация каждого хода LLM по шкале качества.

### TODO

- [x] **8.1** Определить шкалу классификации:
  ```python
  def classify_move(llm_rating: int, best_rating: int, total_moves: int) -> str:
      if total_moves <= 1:
          return "forced"           # единственный легальный ход
      if best_rating <= 0 and llm_rating <= 0:
          return "losing_position"  # все ходы плохие

      gap = best_rating - llm_rating
      if gap <= 0:
          return "brilliant"        # LLM нашёл лучший или лучше
      ratio = llm_rating / max(best_rating, 1)

      if ratio >= 0.90:
          return "good"             # потеря < 10%
      if ratio >= 0.60:
          return "inaccuracy"       # потеря 10-40%
      if ratio >= 0.20:
          return "mistake"          # потеря 40-80%
      return "blunder"              # потеря > 80% или отрицательный рейтинг
  ```

- [x] **8.2** Вычислять `smartbot_move_category` в `compute_move_metrics()`

- [x] **8.3** Агрегировать распределение категорий в `ModelStats`

### Проверки после Phase 8

- [ ] Каждый ход с SmartBot eval имеет категорию
- [ ] Forced moves = "forced", не "brilliant"
- [ ] Модель с winrate > 50% имеет > 50% good+brilliant
- [ ] Слабые модели (low winrate) имеют больше mistake+blunder
- [ ] Распределение суммируется до ~100% (с учётом forced)

---

## Phase 9: Hallucination Detection (Automated)

**Цель:** Автоматическая проверка board accuracy в thinking-блоках LLM.

### TODO

- [ ] **9.1** Создать `trace_analyzer/hallucination_detector.py`
  - [ ] Функция `detect_hallucinations(thinking: str, board: list[dict]) → HallucinationReport`
  - [ ] Regex для извлечения координат:
    - Серверная: `[A-L](?:1[0-2]|[1-9])`
    - TRIUMVIRATE: `[WBR]\d/[WBR]\d\.\d` и `C/[WBR]\.[WBR]`
  - [ ] Для каждой упомянутой координаты:
    - Найти фигуру на доске
    - Проверить: совпадает ли тип/цвет с контекстом в thinking

- [ ] **9.2** Dataclass `HallucinationReport`:
  ```python
  total_coordinates_mentioned: int
  coordinates_verified: int
  phantom_pieces: int           # фигура которой нет
  wrong_color: int              # перепутан цвет
  wrong_type: int               # перепутан тип фигуры
  accuracy_rate: float          # correct / verified
  examples: list[dict]          # первые 5 примеров ошибок
  ```

- [ ] **9.3** Интеграция в MoveMetrics:
  ```python
  hallucination_total_coords: int = 0
  hallucination_phantom: int = 0
  hallucination_wrong_color: int = 0
  hallucination_accuracy: float = 0.0
  ```

### Проверки после Phase 9

- [ ] Regex корректно извлекает координаты из реальных thinking-блоков (проверить 10+ примеров)
- [ ] Не считает ложные срабатывания (числа в контексте, не связанном с шахматами)
- [ ] `accuracy_rate` < 1.0 для моделей, которые известно галлюцинируют
- [ ] Для ходов без thinking — `hallucination_*` = 0

---

## Phase 10: Views & CLI интеграция

**Цель:** Отображение новых метрик в UI и CLI.

### TODO

- [x] **10.1** Обновить `metrics.py` CLI:
  - [ ] Добавить флаг `--smartbot` — включает SmartBot evaluation
  - [ ] Добавить флаг `--check-mates` — включает проверку мата (тяжёлый)
  - [ ] Добавить флаг `--hallucinations` — включает hallucination detection
  - [ ] Добавить `--smartbot-path PATH` — путь к SmartBot (override)
  - [ ] Добавить `--workers N` — число параллельных воркеров

- [x] **10.2** Обновить `_print_table()`:
  - [ ] Новые столбцы: `Gap`, `Qual`, `Bri%`, `Bln%` (SmartBot quality)
  - [ ] Показывать только если SmartBot данные доступны

- [ ] **10.3** Обновить `overview.py` view:
  - [ ] Новая секция "SmartBot Analysis" с карточками:
    - Median Rating Gap
    - Best Move Rate (rank 1 %)
    - Blunder Rate
    - Move Category Distribution (pie chart)
  - [ ] Scatter: Rating Gap by Move Number

- [ ] **10.4** Обновить `moves_table.py` view:
  - [ ] Новые столбцы: SB Rating, Gap, Category (с цветовой кодировкой)
  - [ ] Фильтр по категории (brilliant/good/inaccuracy/mistake/blunder)

- [ ] **10.5** Обновить `move_detail.py` view:
  - [ ] Секция "SmartBot Evaluation":
    - Рейтинг хода LLM vs лучший
    - 5 компонентов рейтинга (bar chart)
    - Список угроз
    - Exchange details (если capture)
    - Threat addressed? Allows mate?

### Проверки после Phase 10

- [ ] `python -m trace_analyzer.metrics --smartbot` — работает, печатает расширенную таблицу
- [ ] `python -m trace_analyzer.metrics` (без --smartbot) — работает как раньше, без SmartBot
- [ ] Views отображают SmartBot данные без ошибок
- [ ] Если SmartBot данных нет — views показывают "Not available" вместо ошибок

---

## Phase 11: Обновление model-evaluator агента

**Цель:** Агент использует SmartBot данные для более точной оценки.

### TODO

- [ ] **11.1** Обновить `.claude/agents/model-evaluator.md`:
  - [ ] Описать новые SmartBot-метрики
  - [ ] Новый Mode: "SmartBot-Calibrated Analysis"
  - [ ] Обновить рубрику Move Quality: вместо ручной оценки 0-15 → SmartBot rating_gap + category
  - [ ] Добавить: "Check logs/evaluations/metrics.json for SmartBot fields (smartbot_*)"

- [ ] **11.2** Обновить шахматную рубрику:
  - [ ] Заменить субъективные критерии на SmartBot-данные:
    - Leader Safety → `smartbot_allows_mate`, `smartbot_threats_critical`
    - Center Control → `smartbot_positional` component
    - Material → `smartbot_material` component + `exchange_classification`
    - Development → `smartbot_positional` component
    - Three-Player Awareness → `political_target_correct`

- [ ] **11.3** Обновить Reasoning Quality рубрику:
  - [ ] Threat Recognition → `smartbot_threat_addressed` vs реальные угрозы
  - [ ] Board Accuracy → `hallucination_accuracy`
  - [ ] Move-Reasoning Consistency → сравнить категорию хода из SmartBot с утверждениями в thinking

### Проверки после Phase 11

- [ ] `/evaluate-models` использует SmartBot данные если доступны
- [ ] Результаты оценки стали более конкретными (числа вместо субъективных оценок)

---

## Phase 12: Тесты всего pipeline

**Цель:** Покрытие тестами нового функционала.

### TODO

- [ ] **12.1** Тесты для `smartbot_adapter.py`:
  - [ ] `test_is_smartbot_available` — проверка обнаружения SmartBot
  - [ ] `test_evaluate_position_basic` — оценка начальной позиции
  - [ ] `test_evaluate_position_capture` — позиция с возможным взятием
  - [ ] `test_evaluate_position_check` — позиция с шахом
  - [ ] `test_evaluate_position_invalid_3pf` — graceful handling ошибки
  - [ ] `test_evaluate_position_no_smartbot` — корректный fallback

- [ ] **12.2** Тесты для `smartbot_evaluator.py`:
  - [ ] `test_evaluate_traces_empty` — пустой список
  - [ ] `test_evaluate_traces_no_3pf` — трейсы без position_3pf
  - [ ] `test_evaluate_traces_real_data` — 5 реальных трейсов
  - [ ] `test_caching` — повторная позиция не вычисляется заново

- [ ] **12.3** Тесты для расширенных `MoveMetrics`:
  - [ ] `test_move_metrics_without_smartbot` — backward compatibility
  - [ ] `test_move_metrics_with_smartbot` — все smartbot поля заполнены
  - [ ] `test_move_metrics_to_dict_serializable` — JSON serialization

- [ ] **12.4** Тесты для расширенного `aggregator.py`:
  - [ ] `test_composite_with_smartbot` — новая формула composite
  - [ ] `test_composite_without_smartbot` — старая формула (fallback)
  - [ ] `test_move_category_distribution` — суммируется до ~100%
  - [ ] `test_model_stats_smartbot_fields` — все поля вычислены

- [ ] **12.5** Тесты для `hallucination_detector.py`:
  - [ ] `test_extract_coordinates_server` — серверная нотация
  - [ ] `test_extract_coordinates_triumvirate` — TRIUMVIRATE нотация
  - [ ] `test_phantom_piece_detection` — фигура которой нет
  - [ ] `test_no_false_positives` — числа в обычном тексте

- [ ] **12.6** Тесты для `classify_move()`:
  - [ ] `test_forced_move` — единственный ход = "forced"
  - [ ] `test_brilliant_move` — лучший ход = "brilliant"
  - [ ] `test_blunder_move` — потеря > 80% = "blunder"
  - [ ] `test_losing_position` — все ходы плохие

- [ ] **12.7** Integration test:
  - [ ] `test_full_pipeline` — от сырых трейсов до model_rankings.json с SmartBot данными
  - [ ] Проверить, что все 3 output файла содержат SmartBot поля

### Проверки после Phase 12

- [ ] `pytest tests/ -v` — все новые тесты проходят
- [ ] Покрытие новых модулей > 80%
- [ ] Нет регрессий в существующих тестах

---

## Порядок выполнения и зависимости

```
Phase 0  ─── Подготовка (блокер для всего)
  │
Phase 1  ─── SmartBot Adapter (фундамент)
  │
Phase 2  ─── SmartBot Evaluator (массовая обработка)
  │
  ├── Phase 3  ─── MoveMetrics (расширение полей)
  │     │
  │     ├── Phase 4  ─── Aggregator (агрегация + composite)
  │     │     │
  │     │     └── Phase 10 ─── Views & CLI (отображение)
  │     │           │
  │     │           └── Phase 11 ─── Model Evaluator Agent
  │     │
  │     └── Phase 8  ─── Move Categories (классификация)
  │
  ├── Phase 5  ─── Threats & Blunders (параллельно с 3)
  │
  ├── Phase 6  ─── Political Dynamics (параллельно с 3)
  │
  ├── Phase 7  ─── Exchange Quality (параллельно с 3)
  │
  └── Phase 9  ─── Hallucination Detection (независимо)

Phase 12 ─── Тесты (после каждой фазы + финальный интеграционный)
```

**Параллельные треки после Phase 2:**
- Track A: Phase 3 → 4 → 8 → 10 → 11 (основной pipeline)
- Track B: Phase 5, 6, 7 (дополнительные метрики, интегрируются в Phase 3)
- Track C: Phase 9 (независимый модуль)

---

## Критерии успеха (Definition of Done)

### Must Have (MVP)

- [ ] `smartbot_adapter.py` корректно оценивает позиции через SmartBot
- [ ] `metrics.json` содержит `smartbot_rating_gap` для каждого хода
- [ ] `model_rankings.json` содержит `smartbot_quality_score` и ранжирование по нему
- [ ] CLI `--smartbot` работает end-to-end
- [ ] Backward compatibility: без `--smartbot` всё работает как раньше
- [ ] Тесты для adapter и evaluator проходят

### Should Have

- [ ] Move category classification (brilliant/good/inaccuracy/mistake/blunder)
- [ ] Blunder detection (allows_mate)
- [ ] Threat awareness metrics
- [ ] Обновлённые views с SmartBot секциями

### Nice to Have

- [ ] Hallucination detection
- [ ] Political correctness metrics
- [ ] Parallel evaluation workers
- [ ] Updated model-evaluator agent
