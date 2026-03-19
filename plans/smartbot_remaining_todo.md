# SmartBot Integration — Remaining TODO

**Дата создания:** 2026-03-19
**Статус базовой системы:** Работает end-to-end (Phase 0-4, 8, 10 partial)
**Текущая скорость:** ~7-8 трейсов/сек, ~7 мин на 2976 ходов

---

## Оглавление

- [1. Unit-тесты SmartBot pipeline](#1-unit-тесты-smartbot-pipeline)
- [2. Allows Mate Detection](#2-allows-mate-detection)
- [3. Views — NiceGUI UI обновления](#3-views--nicegui-ui-обновления)
- [4. Обновление model-evaluator агента](#4-обновление-model-evaluator-агента)
- [5. Hallucination Detection](#5-hallucination-detection)
- [6. Параллелизация evaluation](#6-параллелизация-evaluation)

---

## 1. Unit-тесты SmartBot pipeline

**Phase из плана:** 12
**Приоритет:** Высокий
**Оценка сложности:** Средняя

### Зачем нужно

SmartBot adapter и evaluator — ядро новой системы оценки. Без тестов любое изменение в SmartBot или в trace_analyzer может сломать pipeline незаметно. Тесты гарантируют:
- Backward compatibility (без --smartbot всё работает как раньше)
- Корректность classify_move() на граничных случаях
- Graceful degradation при отсутствии SmartBot
- Правильность агрегации smartbot_* полей

### Ожидаемый эффект

- Уверенность при рефакторинге и добавлении новых метрик
- CI-ready: тесты с мок-данными работают без SmartBot на любой машине
- Покрытие новых модулей > 80%

### TODO

- [ ] **1.1** Unit-тесты для `classify_move()` в `tests/unit/test_classify_move.py`
  - [ ] `test_forced_move` — единственный легальный ход → "forced"
  - [ ] `test_brilliant_move` — llm_rating >= best_rating → "brilliant"
  - [ ] `test_good_move` — потеря < 10% → "good"
  - [ ] `test_inaccuracy_move` — потеря 10-40% → "inaccuracy"
  - [ ] `test_mistake_move` — потеря 40-80% → "mistake"
  - [ ] `test_blunder_move` — потеря > 80% → "blunder"
  - [ ] `test_losing_position` — все ходы с отрицательным рейтингом → "losing_position"
  - [ ] `test_zero_best_rating` — best_rating = 0, llm_rating = 0 → "losing_position"
  - [ ] `test_negative_gap` — llm_rating > best_rating → "brilliant"
  - [ ] Parametrize: таблица из 15+ пар (llm_rating, best_rating, total) → expected category

- [ ] **1.2** Unit-тесты для `MoveMetrics` с SmartBot данными в `tests/unit/test_move_metrics_smartbot.py`
  - [ ] `test_move_metrics_without_smartbot` — все smartbot_* поля дефолтные, to_dict() работает
  - [ ] `test_move_metrics_with_smartbot_eval` — передан smartbot_eval dict → поля заполнены
  - [ ] `test_move_metrics_to_dict_json_serializable` — json.dumps(m.to_dict()) без ошибок
  - [ ] `test_move_metrics_smartbot_category_computed` — classify_move() вызывается автоматически
  - [ ] Фикстура: `sample_smartbot_eval` — реалистичный dict с smartbot_* полями

- [ ] **1.3** Unit-тесты для агрегации SmartBot в `tests/unit/test_aggregator_smartbot.py`
  - [ ] `test_aggregate_by_model_with_smartbot` — smartbot_avg_rating_gap, median, p90 вычислены
  - [ ] `test_aggregate_by_model_without_smartbot` — smartbot поля = 0 (backward compat)
  - [ ] `test_composite_with_smartbot` — новая формула composite (35% SmartBot quality)
  - [ ] `test_composite_without_smartbot` — старая формула (35% reliability)
  - [ ] `test_category_distribution_sums_to_one` — brilliant + good + inaccuracy + mistake + blunder ≈ 1.0
  - [ ] `test_game_result_smartbot_fields` — blunder_count, allows_mate_count заполнены
  - [ ] Фикстура: `sample_moves_with_smartbot` — список из 20+ move dicts с smartbot полями

- [ ] **1.4** Тесты для `smartbot_adapter.py` в `tests/unit/test_smartbot_adapter.py`
  - [ ] `test_is_smartbot_available_true` — с реальным путём (skip если SmartBot нет)
  - [ ] `test_is_smartbot_available_false` — с несуществующим путём
  - [ ] `test_evaluate_position_no_smartbot` — SMARTBOT_PATH = /nonexistent → возвращает None
  - [ ] `test_position_evaluation_dataclass` — все поля инициализируются дефолтами
  - [ ] `test_move_evaluation_dataclass` — все поля инициализируются дефолтами

- [ ] **1.5** Integration-тесты (требуют SmartBot) в `tests/integration/test_smartbot_pipeline.py`
  - [ ] Маркер `@pytest.mark.skipif(not is_smartbot_available(), reason="SmartBot not found")`
  - [ ] `test_evaluate_position_real_trace` — оценка реальной позиции из логов
  - [ ] `test_evaluate_traces_real_game` — оценка 10 ходов из одной игры
  - [ ] `test_full_pipeline_with_smartbot` — от сырых трейсов до model_rankings.json
  - [ ] `test_evaluate_position_opening` — начальная позиция, все ходы равны
  - [ ] `test_evaluate_position_capture` — позиция с capture → exchange_classification заполнен
  - [ ] `test_caching_works` — повторная позиция не вычисляется заново

---

## 2. Allows Mate Detection

**Phase из плана:** 5.3
**Приоритет:** Средний
**Оценка сложности:** Средняя

### Зачем нужно

Сейчас `smartbot_allows_mate` всегда `False` (заглушка). Это самая грубая ошибка, которую может допустить модель — сделать ход, после которого противник ставит мат. Метрика `allows_mate_rate` покажет, насколько модель "видит" опасность. Например: "модель X допускает мат в 3% ходов" — конкретный, измеримый сигнал для оптимизации промпта.

### Ожидаемый эффект

- Новая метрика `allows_mate_rate` в ModelStats — % ходов, допускающих мат
- Автоматическое обнаружение самых грубых ошибок без ручного анализа
- Данные для `/optimize-prompts`: "добавьте в промпт проверку безопасности короля"

### TODO

- [ ] **2.1** Реализовать `_check_allows_mate()` в `smartbot_adapter.py`
  - [ ] Для хода LLM: вызвать `simulate_move_fast(llm_move, game_state)` → board_after
  - [ ] Создать временный GameState с board_after и следующим игроком
  - [ ] Для каждого противника: вызвать `find_all_threats()` и проверить `gives_mate` среди их ходов
  - [ ] Альтернатива: использовать SmartBot's `tactical_verify._check_mate_threat()` если доступен
  - [ ] Результат: `bool` — может ли хотя бы один противник поставить мат после хода LLM

- [ ] **2.2** Интегрировать в `evaluate_position()`
  - [ ] Добавить параметр `check_mates: bool = False`
  - [ ] Если `check_mates=True` → вызывать `_check_allows_mate()` для хода LLM
  - [ ] Записать результат в `PositionEvaluation.llm_allows_mate`

- [ ] **2.3** Прокинуть параметр через `evaluate_traces()` и CLI `--check-mates`
  - [ ] `evaluate_traces(raw_traces, check_mates=True)` → передаёт в `evaluate_position()`
  - [ ] CLI `--check-mates` уже добавлен, нужно прокинуть в adapter

- [ ] **2.4** Замерить производительность
  - [ ] Запустить с `--check-mates` на 100 трейсах, сравнить время с/без
  - [ ] Ожидание: 2-5x замедление (допустимо для opt-in)
  - [ ] Если > 5x — оптимизировать (проверять только ходы с `smartbot_threats_critical > 0`)

- [ ] **2.5** Тесты
  - [ ] `test_allows_mate_detected` — позиция, где ход LLM допускает мат
  - [ ] `test_allows_mate_false` — безопасный ход → False
  - [ ] `test_check_mates_disabled` — без флага → всегда False

---

## 3. Views — NiceGUI UI обновления

**Phase из плана:** 10.3, 10.4, 10.5
**Приоритет:** Средний
**Оценка сложности:** Средняя (много UI-кода, требует визуальной проверки)

### Зачем нужно

Данные SmartBot уже есть в metrics.json и model_rankings.json, но просматривать JSON руками неудобно. Views дают:
- Наглядное сравнение моделей по качеству ходов (pie chart категорий)
- Быстрый drill-down: кликнул на blunder → увидел позицию, ход LLM vs лучший ход
- Scatter plot rating_gap по номеру хода → видно, ухудшается ли модель к эндшпилю

### Ожидаемый эффект

- Визуальный анализ без ковыряния в JSON
- Фильтрация ходов по категории (показать только blunder'ы)
- Цветовая кодировка: brilliant=зелёный, blunder=красный

### TODO

- [ ] **3.1** Обновить `overview.py`
  - [ ] Новая секция "SmartBot Analysis" (показывать только если smartbot данные есть)
  - [ ] Карточки: Median Rating Gap, Best Move Rate (rank 1 %), Blunder Rate
  - [ ] Pie chart: распределение категорий (brilliant/good/inaccuracy/mistake/blunder)
  - [ ] Scatter plot: Rating Gap по Move Number (тренд качества по ходу партии)
  - [ ] Bar chart: 5 компонентов (material, defense, tactical, positional, risk) — weakness profile

- [ ] **3.2** Обновить `moves_table.py`
  - [ ] Новые столбцы: SB Rating, Gap, Category
  - [ ] Цветовая кодировка категорий:
    - brilliant: зелёный фон
    - good: светло-зелёный
    - inaccuracy: жёлтый
    - mistake: оранжевый
    - blunder: красный
  - [ ] Фильтр-dropdown по категории
  - [ ] Сортировка по rating_gap (показать самые плохие ходы сверху)

- [ ] **3.3** Обновить `move_detail.py`
  - [ ] Секция "SmartBot Evaluation" (если smartbot_available)
  - [ ] Рейтинг хода LLM vs лучший (horizontal bar)
  - [ ] 5 компонентов рейтинга (stacked bar chart)
  - [ ] Список угроз: severity, target, attacker
  - [ ] Exchange details (если capture): classification, net_value, is_free
  - [ ] Badges: "Threat Addressed" / "Allows Mate" / "Missed Mate"
  - [ ] Top-5 альтернативных ходов с рейтингами (из smartbot_top_moves)

- [ ] **3.4** Graceful degradation
  - [ ] Если smartbot_available = False для всех ходов — секции скрыты, показано "SmartBot data not available. Run with --smartbot to enable."
  - [ ] Если smartbot_available частично — показать данные только для доступных ходов

---

## 4. Обновление model-evaluator агента

**Phase из плана:** 11
**Приоритет:** Средний
**Оценка сложности:** Низкая (редактура текста, не код)

### Зачем нужно

Агент `/evaluate-models` сейчас оценивает ходы субъективно (рубрика 0-15 баллов, LLM-оценщик). С SmartBot данными он может:
- Заменить субъективную оценку объективной (rating_gap + category)
- Давать конкретные рекомендации на основе weakness profile
- Тратить LLM-бюджет на анализ reasoning (thinking-блоков), а не на оценку ходов

### Ожидаемый эффект

- Оценка моделей дешевле (не нужны LLM-вызовы для оценки ходов)
- Результаты детерминированные и воспроизводимые
- Агент фокусируется на том, что LLM делает лучше SmartBot — анализ мышления

### TODO

- [ ] **4.1** Обновить `.claude/agents/model-evaluator.md`
  - [ ] Добавить описание SmartBot-метрик и где их найти (metrics.json)
  - [ ] Новый режим: "SmartBot-Calibrated Analysis"
  - [ ] Инструкция: если smartbot данные есть — использовать rating_gap и category вместо ручной оценки 0-15

- [ ] **4.2** Обновить шахматную рубрику
  - [ ] Leader Safety → `smartbot_allows_mate`, `smartbot_threats_critical`
  - [ ] Center Control → `smartbot_positional` component
  - [ ] Material → `smartbot_material` component + `exchange_classification`
  - [ ] Development → `smartbot_positional` component
  - [ ] Three-Player Awareness → `smartbot_player_role` + weakness profile

- [ ] **4.3** Обновить Reasoning Quality рубрику
  - [ ] Threat Recognition → `smartbot_threat_addressed` vs реальные угрозы
  - [ ] Board Accuracy → `hallucination_accuracy` (Phase 5, если реализован)
  - [ ] Move-Reasoning Consistency → сравнить category из SmartBot с утверждениями в thinking

- [ ] **4.4** Обновить prompt-optimizer агент
  - [ ] `.claude/agents/prompt-optimizer.md` — описать новые SmartBot метрики
  - [ ] Примеры рекомендаций на основе weakness profile:
    - `weakness_defense` высокий → "добавить в промпт: check if your King is safe before moving"
    - `weakness_material` высокий → "добавить: evaluate piece values before capturing"
    - `smartbot_missed_mate > 0` → "добавить: always check for checkmate opportunities"

---

## 5. Hallucination Detection

**Phase из плана:** 9
**Приоритет:** Низкий
**Оценка сложности:** Высокая (NLP/regex, много edge cases)

### Зачем нужно

Модели часто "галлюцинируют" в thinking-блоках — упоминают фигуры, которых нет на доске, путают цвета, указывают невозможные координаты. Сейчас это можно обнаружить только вручную (агент model-evaluator анализирует 10-15 ходов). Автоматический детектор позволит:
- Измерить `board_accuracy_rate` для каждой модели
- Понять, "видит" ли модель доску или работает вслепую
- Оптимизировать формат описания позиции в промпте

### Ожидаемый эффект

- Метрика `hallucination_accuracy` для каждого хода и модели
- Автоматический сигнал: "модель X галлюцинирует в 34% координат"
- Данные для оптимизации: возможно, упрощение описания позиции снизит галлюцинации

### TODO

- [ ] **5.1** Создать `trace_analyzer/hallucination_detector.py`
  - [ ] Функция `detect_hallucinations(thinking: str, board: list[dict]) → HallucinationReport`
  - [ ] Построить dict `{координата: Piece}` из board для O(1) lookup

- [ ] **5.2** Regex для извлечения координат из thinking
  - [ ] Серверная нотация: `[A-L](?:1[0-2]|[1-9])` (A1-L12, 96 клеток)
  - [ ] TRIUMVIRATE нотация: `[WBR]\d/[WBR]\d\.\d` и `C/[WBR]\.[WBR]`
  - [ ] Фильтрация false positives: исключить координаты в контексте "move A1 to B2" (это ход, не утверждение о фигуре)
  - [ ] Контекстный анализ: "pawn on E4" → проверить, есть ли пешка на E4
  - [ ] Поддержка английских и русских названий фигур

- [ ] **5.3** Dataclass `HallucinationReport`
  - [ ] `total_coordinates_mentioned: int`
  - [ ] `coordinates_verified: int`
  - [ ] `phantom_pieces: int` — модель упоминает фигуру, которой нет
  - [ ] `wrong_color: int` — модель перепутала цвет фигуры
  - [ ] `wrong_type: int` — модель перепутала тип фигуры (назвала ладью конём)
  - [ ] `accuracy_rate: float` — correct / verified
  - [ ] `examples: list[dict]` — первые 5 примеров ошибок (для отладки)

- [ ] **5.4** Интеграция в MoveMetrics
  - [ ] Поля: `hallucination_total_coords`, `hallucination_phantom`, `hallucination_wrong_color`, `hallucination_accuracy`
  - [ ] Заполняются только если thinking-блок не пустой
  - [ ] Агрегация в ModelStats: `avg_hallucination_accuracy`

- [ ] **5.5** CLI флаг `--hallucinations`
  - [ ] Включает hallucination detection (по умолчанию выключен)
  - [ ] Работает независимо от `--smartbot`
  - [ ] Новый столбец в таблице: `Hal%` (accuracy rate)

- [ ] **5.6** Тесты
  - [ ] `test_extract_coordinates_server` — "pawn on E4" → ["E4"]
  - [ ] `test_extract_coordinates_triumvirate` — "piece at W2/R1.2" → ["W2/R1.2"]
  - [ ] `test_phantom_piece` — "knight on A1" при отсутствии коня → phantom=1
  - [ ] `test_no_false_positives` — "scored 12 points" → не считать "12" координатой
  - [ ] `test_empty_thinking` — пустой thinking → все поля = 0
  - [ ] `test_real_thinking_block` — 3+ реальных thinking-блока из логов

---

## 6. Параллелизация evaluation

**Phase из плана:** 2.3
**Приоритет:** Низкий
**Оценка сложности:** Средняя (pickling, process pool, error handling)

### Зачем нужно

Текущая скорость ~7-8 трейсов/сек означает ~7 минут на 2976 ходов. При росте количества игр (10000+ ходов) это станет 20+ минут. Параллелизация через ProcessPoolExecutor может ускорить в 3-4x на 4-ядерной машине.

### Ожидаемый эффект

- 2976 ходов за ~2 минуты вместо ~7 (на 4 ядрах)
- 10000 ходов за ~5 минут вместо ~20
- Масштабируемость: больше ядер = быстрее

### TODO

- [ ] **6.1** Проверить picklability SmartBot объектов
  - [ ] `GameState`, `BoardState`, `Piece`, `Coordinate` — можно ли pickle?
  - [ ] Если нет — определить стратегию: передавать строку position_3pf + legal_moves dict (примитивы) в worker, парсить в worker

- [ ] **6.2** Реализовать parallel evaluation в `smartbot_evaluator.py`
  - [ ] `concurrent.futures.ProcessPoolExecutor(max_workers=N)`
  - [ ] Worker function: принимает (position_3pf, legal_moves, llm_from, llm_to, player_color) → dict
  - [ ] Каждый worker делает свой `_import_smartbot()` (lazy import в каждом процессе)
  - [ ] Сборка результатов в основном процессе

- [ ] **6.3** CLI параметр `--workers N`
  - [ ] Дефолт: 1 (последовательно, текущее поведение)
  - [ ] `--workers 4` → 4 параллельных воркера
  - [ ] `--workers 0` → auto (cpu_count)

- [ ] **6.4** Error handling
  - [ ] Worker crash → graceful skip, warning в лог
  - [ ] Timeout per worker → skip после 30 секунд на позицию
  - [ ] Progress reporting из параллельных воркеров (shared counter)

- [ ] **6.5** Тесты и бенчмарк
  - [ ] `test_parallel_same_results` — последовательный и параллельный дают одинаковые результаты
  - [ ] Бенчмарк: 500 трейсов × workers=[1,2,4] → таблица скоростей
  - [ ] Проверить на Windows (ProcessPoolExecutor требует `if __name__ == "__main__"`)

---

## Порядок реализации

```
1. Unit-тесты (Phase 12)        ← СЛЕДУЮЩИЙ ШАГ, высокий приоритет
   Не требует внешних зависимостей, стабилизирует текущий код

2. Allows Mate (Phase 5.3)      ← после тестов
   Простая реализация, высокий ROI (ловит самые грубые ошибки)

3. Views UI (Phase 10.3-10.5)   ← после стабилизации полей
   Визуализация данных, которые уже есть

4. Model-evaluator агент (Phase 11)  ← после Views
   Текстовая правка, зависит от финальных метрик

5. Hallucination Detection (Phase 9) ← отдельная итерация
   Research-задача, независимый модуль

6. Параллелизация (Phase 2.3)   ← когда данных станет > 10000 ходов
   Оптимизация, не влияет на функционал
```
