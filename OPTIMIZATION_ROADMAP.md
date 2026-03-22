# Карта оптимизации шахматного анализа LLM-бота

> Версия: 1.0 | Дата: 2026-03-22
> Источник: BUGFIX_PLAN.md (оставшиеся пункты #1, #4, #5, #8, #9, #10) + баг #3 (реализован)

---

## 1. Тестовый стенд

### 1.1 Выбор моделей

Из 17 моделей в базе выбраны 3 по критериям: надёжность (fallback < 2%), достаточный baseline (8+ игр), разнообразие архитектур, доступность для массового тестирования.

| # | Модель | Тип | Игр | Ходов | Fallback | $/ход | Время/ход | Зачем в стенде |
|---|--------|-----|-----|-------|----------|-------|-----------|----------------|
| 1 | `google/gemini-3-flash-preview` | Fast, no thinking | 8 | 299 | 0% | $0.0016 | 3.0s | Быстрый, дешёвый — масштаб тестов. Показывает эффект на моделях без extended thinking |
| 2 | `openai/gpt-5-mini` | Premium, thinking | 17 | 448 | 0% | $0.0046 | 20.4s | Самый большой baseline (448 ходов), 100% first_attempt. Показывает потолок качества |
| 3 | `qwen/qwen3-max-thinking` | Deep thinking | 11 | 429 | 0% | $0.0027 | 12.5s | Thinking-модель — критична для оптимизаций #1/#4 (протокол анализа) |

**Исключённые альтернативы:**
- `minimax/minimax-m2.5` — высший quality_score (0.986), но $0.0028/ход и 30с/ход — слишком дорого для 10+ игр на фазу
- `deepseek/deepseek-v3.2` — хорошее качество (0.938), но 62с/ход делает массовое тестирование непрактичным
- `openai/gpt-4.1-mini` — только 4 игры baseline, недостаточно для сравнения

### 1.2 Baseline-метрики (до оптимизаций)

Зафиксированы на 2026-03-22 из `logs/evaluations/model_rankings.json`.

| Метрика | gemini-3-flash | gpt-5-mini | qwen3-max | Среднее | Описание |
|---------|---------------|------------|-----------|---------|----------|
| **blunder_rate** | 0.264 | 0.264 | 0.315 | 0.281 | Доля blunder-ходов (SmartBot) |
| **brilliant_rate** | 0.174 | 0.271 | 0.308 | 0.251 | Доля brilliant-ходов |
| **threat_addressed_rate** | 0.921 | 0.910 | 0.966 | 0.932 | Доля адресованных угроз |
| **rank_1_rate** | 0.167 | 0.280 | 0.268 | 0.238 | Доля ходов = лучший по SmartBot |
| **top3_rate** | 0.441 | 0.606 | 0.578 | 0.542 | Доля ходов в топ-3 SmartBot |
| **median_rating_gap** | 25 | 36 | 30 | 30 | Медианная разница с лучшим ходом (cp) |
| **p90_rating_gap** | 370 | 438 | 395 | 401 | 90-й перцентиль rating_gap (cp) |
| **cat_mistake** | 0.097 | 0.114 | 0.093 | 0.101 | Доля mistake-ходов |
| **cat_inaccuracy** | 0.064 | 0.063 | 0.037 | 0.055 | Доля inaccuracy-ходов |
| **missed_mate_count** | 0 | 7 | 5 | 4.0 | Пропущенные маты (абс.) |
| **avg_material** | -3.05 | 9.55 | 10.86 | 5.79 | Средний материальный баланс (cp) |
| **first_attempt_rate** | 0.997 | 1.000 | 0.993 | 0.997 | Успех с первой попытки |
| **avg_tokens_per_move** | 2314 | 2581 | 2081 | 2325 | Среднее токенов на ход |
| **avg_cost_per_move** | $0.0016 | $0.0046 | $0.0027 | $0.0030 | Средняя стоимость хода |

### 1.3 Статистическая значимость

**Формула размера выборки** (тест пропорций, двусторонний, alpha=0.05, power=0.80):

```
n = (Z_α/2 + Z_β)² × (p₁(1-p₁) + p₂(1-p₂)) / (p₁ - p₂)²
```

| Детектируемое изменение blunder_rate | Требуемые ходы/модель | Игр (~30 ходов/игру) |
|--------------------------------------|----------------------|----------------------|
| 30% → 25% (Δ = 5 п.п.) | ~1250 | ~42 |
| 30% → 22% (Δ = 8 п.п.) | ~490 | ~16 |
| 30% → 20% (Δ = 10 п.п.) | ~295 | ~10 |
| 30% → 15% (Δ = 15 п.п.) | ~130 | ~5 |

**Принятый компромисс: 15 игр на модель на фазу (~450 ходов).**
Это позволяет детектировать изменения ≥ 8 п.п. в blunder_rate с мощностью 80%.

Для более тонких изменений (5 п.п.) будем агрегировать данные по всем 3 моделям (~1350 ходов суммарно), что даёт достаточную мощность.

### 1.4 Протокол тестирования

1. **Запуск**: `python main.py --headless --bots 3 --models-pool test_bench.json --start-delay 10`
2. **Пул моделей**: Создать `test_bench.json` с 3 моделями из стенда
3. **Сессия**: 5 запусков по 3 бота = 15 игр на модель (3 модели × 15 игр = 45 игр на фазу)
4. **Метрики**: `python -m trace_analyzer.metrics --smartbot` после каждой фазы
5. **Сравнение**: Дельта baseline vs post-optimization по каждой метрике

**Идентификация игр**: Трейсы до оптимизаций помечены как `baseline`. После каждой фазы — отдельная папка или тег в game_id.

---

## 2. Реализованные оптимизации

### OPT-0: Таблица ценности фигур (баг #3) — DONE

**Файл:** `prompts/system_prompt.txt` (строки 23-44)

**Что добавлено:**
- Базовые ценности всех 6 фигур (по SmartBot: M=9, T=5, D=3.2, N=3, P=1, L=priceless)
- Примеры хорошего и плохого размена с числами
- Шкала ценности Private при продвижении (1 ход = 5.0, 2 хода = 2.5, 3 хода = 1.5, stuck = 0.3)
- 4 правила применения (перед взятием, перед перемещением защитника, при угрозе, продвижение Private)

**Целевые метрики:**

| Метрика | Baseline | Цель | Обоснование |
|---------|----------|------|-------------|
| blunder_rate | 0.281 | ≤ 0.260 | Меньше невыгодных разменов |
| cat_mistake | 0.101 | ≤ 0.085 | Ошибки при оценке размена → mistake, не blunder |
| avg_material | 5.79 | ≥ 8.0 | Лучшая оценка разменов → больше материала |

---

## 3. Оставшиеся оптимизации (по приоритету)

### OPT-1: Сжатие Chat Diplomacy (баг #8)

**Приоритет:** HIGH (быстрый, безрисковый, экономия токенов)
**Файл:** `prompts/chat_instructions.txt`
**Суть:** Сжать с 29 строк (~1514 байт) до ~10 строк (~400 байт). Экономия ~200 токенов/ход.

**Изменение:**
```
БЫЛО: 29 строк — 5 пунктов WHEN TO SEND, 4 WHEN TO STAY SILENT, 4 READING OPPONENT, 4 STRICT RULES
СТАЛО: ~10 строк — ключевые правила в сжатой форме
```

**Целевые метрики:**

| Метрика | Baseline | Цель | Индикатор проблемы |
|---------|----------|------|--------------------|
| avg_tokens_per_move | 2325 | ≤ 2150 | Не снизилось → сжатие не работает |
| avg_cost_per_move | $0.0030 | ≤ $0.0027 | Стоимость не снизилась |
| first_attempt_rate | 0.997 | ≥ 0.995 | Упало → модели путаются с форматом |
| blunder_rate | — | без ухудшения (≤ +2 п.п.) | Выросло → сжатие повредило промпт |

**Go/No-Go:** Если blunder_rate вырос > 2 п.п. — откатить.

---

### OPT-2: Негативные примеры COMMON BLUNDERS (баг #5)

**Приоритет:** HIGH (но с риском inverse instruction following)
**Файл:** `prompts/system_prompt.txt` (после STRATEGY)
**Суть:** 5 строк с типичными ошибками и объяснениями.

**Изменение:**
```
COMMON BLUNDERS TO AVOID (unless you have a specific tactical reason):
- Moving your Leader before move 10 — it becomes a target with no escape squares
- Trading M(9) for P(1) or N(3) — net loss of 6+ points
- Moving a piece that shields your Leader — exposes Leader to check
- Moving to a square attacked by opponent — check the destination first
- Focusing only on one opponent while the other attacks freely
```

**Целевые метрики:**

| Метрика | Baseline | Цель | Индикатор проблемы |
|---------|----------|------|--------------------|
| blunder_rate | 0.281 | ≤ 0.250 | Выросло → inverse instruction following |
| cat_mistake | 0.101 | ≤ 0.080 | Не изменилось → примеры не работают |
| allows_mate_rate | 0.0 | 0.0 | Выросло → "Moving a piece that shields Leader" навредило |
| missed_mate_count (sum) | 12 | ≤ 10 | Выросло → модели зациклились на обороне |

**Go/No-Go:** Если blunder_rate вырос > 2 п.п. — откатить НЕМЕДЛЕННО. Это самый рискованный пункт.

**A/B изоляция:** Внедрять ОТДЕЛЬНО от OPT-1, прогнать полный цикл тестов, зафиксировать результат перед следующей фазой.

---

### OPT-3: Структурированный протокол анализа (баги #1 + #4)

**Приоритет:** MEDIUM (модели уже адресуют 85-97% угроз, но качество thinking можно улучшить)
**Файл:** `prompts/format_json_thinking.txt`
**Суть:** Заменить 4 расплывчатых вопроса на жёсткий пошаговый протокол THREAT SCAN → CAPTURES → CANDIDATES → DECIDE. Заменить нарративный пример thinking на структурированный.

**Изменение:**
```
БЫЛО:
  4 вопроса ("Is my Leader safe?", "Can I capture?", ...)
  1 нарративный пример thinking

СТАЛО:
  MANDATORY ANALYSIS PROTOCOL (4 шага):
  Step 1 — THREAT SCAN: список всех угроз
  Step 2 — CAPTURES: список всех доступных взятий с оценкой
  Step 3 — CANDIDATES: топ-3 хода с обоснованием
  Step 4 — DECIDE: сравнение и выбор
  Структурированный пример thinking (~100 слов)
```

**Целевые метрики:**

| Метрика | Baseline | Цель | Индикатор проблемы |
|---------|----------|------|--------------------|
| blunder_rate | текущая* | ≤ -3 п.п. | Не снизился → протокол формально, без содержания |
| brilliant_rate | 0.251 | ≥ 0.280 | Снизился → модели тратят thinking на формат, а не на анализ |
| rank_1_rate | 0.238 | ≥ 0.270 | Лучший перебор → чаще лучший ход |
| top3_rate | 0.542 | ≥ 0.580 | Лучший перебор → чаще в топ-3 |
| median_rating_gap | 30 cp | ≤ 22 cp | Ходы ближе к оптимальным |
| avg_tokens_per_move | 2325 | ≤ 3500 | Превысило 3500 → протокол слишком дорогой |
| first_attempt_rate | 0.997 | ≥ 0.990 | Упало → модели ломают JSON из-за протокола |

*\* "текущая" — значение после OPT-0/1/2, не baseline*

**Go/No-Go:**
- Если avg_tokens_per_move > 3500 — укоротить протокол до 2 шагов
- Если first_attempt_rate < 0.99 — проверить формат JSON, возможно протокол конфликтует с JSON-парсингом
- Если blunder_rate не снизился после 10 игр — пересмотреть формулировки

---

### OPT-4: Эндшпильные инструкции (баг #9)

**Приоритет:** LOW-MEDIUM (win rate в эндшпиле ≈ 0%, но survival можно улучшить)
**Файл:** `prompts/system_prompt.txt` (после STRATEGY)
**Суть:** 5 строк с инструкциями для фазы 3- фигуры.

**Изменение:**
```
ENDGAME (when you have 3 or fewer pieces):
- Your Leader is everything. Keep it away from both opponents' attack lines.
- Seek stalemate if you cannot win — a draw is better than a loss.
- Use the third player as a shield — stay opposite the stronger opponent.
- Private near promotion is your only winning chance — protect it at all costs.
- With only a Leader: aim for positions where opponents block each other.
```

**Целевые метрики:**

| Метрика | Baseline | Цель | Как измерять |
|---------|----------|------|-------------|
| endgame_survival_moves | нет данных | +20% vs baseline | Считать ходы после "pieces ≤ 3" из трейсов |
| blunder_rate_endgame | нет данных | ≤ blunder_rate_midgame | Фильтровать метрики по smartbot_game_phase |
| allows_mate_rate | 0.0 | 0.0 | Не ухудшить |

**Важно:** Требуется добавить сегментацию метрик по фазе игры в `aggregator.py`:
- **Opening** (game_phase ≥ 0.8)
- **Middlegame** (0.3 < game_phase < 0.8)
- **Endgame** (game_phase ≤ 0.3)

Без сегментации невозможно измерить эффект OPT-4 изолированно.

---

### OPT-5: Адаптация к роли leader/underdog (баг #10)

**Приоритет:** MEDIUM-HIGH (67-77% ходов из позиции UNDERDOG, но стратегия не адаптируется)
**Файлы:** `prompts/system_prompt.txt` + `prompt_builder.py`

**Двухступенчатое изменение:**

**Шаг A — Промпт (3 строки в STRATEGY):**
```
7. Adapt to your position:
   - WINNING (more pieces): simplify, trade pieces, avoid risks.
   - LOSING (fewer pieces): seek complications, look for tactical shots. Take calculated risks.
   - MIDDLE: focus the weaker opponent, avoid provoking the stronger one.
```

**Шаг B — Код (3 строки в prompt_builder.py):**
Программно добавить в user_prompt строку с подсчётом фигур:
```
Material balance: White 8 pieces, Black 5 pieces, Red 6 pieces — you are WINNING.
```
Это устраняет необходимость для модели самостоятельно считать фигуры из Board.

**Целевые метрики:**

| Метрика | Baseline | Цель | Как измерять |
|---------|----------|------|-------------|
| blunder_rate (UNDERDOG) | нет данных | ≤ blunder_rate общий | Фильтр по smartbot_player_role = UNDERDOG |
| blunder_rate (LEADER) | нет данных | ≤ blunder_rate общий | Фильтр по smartbot_player_role = LEADER |
| brilliant_rate (UNDERDOG) | нет данных | ≥ brilliant_rate общий | Аутсайдеры должны чаще искать тактику |
| avg_material (LEADER) | нет данных | рост vs baseline | Лидеры лучше конвертируют преимущество |

**Важно:** Требуется сегментация метрик по `smartbot_player_role` в `aggregator.py`.

**Go/No-Go:**
- Шаг A — безрисковый, внедрить сразу
- Шаг B — требует изменения кода, тестировать отдельно

---

## 4. Порядок внедрения и расписание тестов

```
                                       Тестовые игры
Фаза  Оптимизация         Файлы        (3 модели × 15)    Длительность
─────────────────────────────────────────────────────────────────────────
  0   Piece Values (DONE)  system_prompt   45 игр           ~6-8 часов
  │
  1   Chat Diplomacy       chat_instr.     45 игр           ~6-8 часов
  │   (OPT-1)
  │
  2   Common Blunders      system_prompt   45 игр           ~6-8 часов
  │   (OPT-2)              ⚠️ РИСКОВАННЫЙ
  │
  3   Analysis Protocol    format_json_    45 игр           ~6-8 часов
  │   (OPT-3)              thinking
  │
  4   Endgame + Role       system_prompt   45 игр           ~6-8 часов
      (OPT-4 + OPT-5A)     + prompt_builder
─────────────────────────────────────────────────────────────────────────
ИТОГО:                                    225 игр           ~30-40 часов
```

**Правила перехода между фазами:**

1. **Go:** blunder_rate не вырос > 2 п.п., first_attempt_rate ≥ 0.99 → переходим к следующей фазе
2. **No-Go (мягкий):** Метрики не улучшились, но и не ухудшились → оставляем изменение, идём дальше
3. **No-Go (жёсткий):** blunder_rate вырос > 2 п.п. ИЛИ first_attempt_rate < 0.99 → ОТКАТ и анализ причин
4. **Rollback:** `git revert` конкретного коммита фазы, повторный прогон 15 игр для подтверждения

---

## 5. Сводная таблица целевых метрик

Кумулятивные ожидаемые изменения после всех 5 оптимизаций:

| Метрика | Baseline | После OPT-0..5 | Δ | Уверенность |
|---------|----------|----------------|---|-------------|
| **blunder_rate** | 0.281 | ≤ 0.210 | -7 п.п. | Средняя |
| **brilliant_rate** | 0.251 | ≥ 0.300 | +5 п.п. | Средняя |
| **threat_addressed_rate** | 0.932 | ≥ 0.960 | +3 п.п. | Высокая |
| **rank_1_rate** | 0.238 | ≥ 0.290 | +5 п.п. | Средняя |
| **top3_rate** | 0.542 | ≥ 0.600 | +6 п.п. | Средняя |
| **median_rating_gap** | 30 cp | ≤ 20 cp | -10 cp | Низкая |
| **avg_tokens_per_move** | 2325 | ≤ 2800 | +475 (+20%) | Высокая |
| **avg_cost_per_move** | $0.0030 | ≤ $0.0035 | +$0.0005 | Высокая |
| **first_attempt_rate** | 0.997 | ≥ 0.995 | -0.002 | Высокая |

**Уровни уверенности:**
- **Высокая** — механический эффект (токены, стоимость) или малый ожидаемый сдвиг
- **Средняя** — эффект зависит от того, как модели интерпретируют инструкции
- **Низкая** — зависит от кумуляции нескольких изменений

---

## 6. Инфраструктурные требования

Для полноценного измерения OPT-4 и OPT-5 необходимо расширить `aggregator.py`:

### 6.1 Сегментация по фазе игры

```python
# В aggregator.py: разбить метрики на 3 фазы
PHASE_BINS = {
    'opening':    lambda gp: gp >= 0.8,
    'middlegame': lambda gp: 0.3 < gp < 0.8,
    'endgame':    lambda gp: gp <= 0.3,
}
```

Метрики `blunder_rate`, `brilliant_rate`, `rank_1_rate` вычисляются отдельно для каждой фазы.

### 6.2 Сегментация по роли

```python
# В aggregator.py: разбить метрики по smartbot_player_role
ROLE_BINS = ['LEADER', 'MIDDLE', 'UNDERDOG']
```

### 6.3 Подсчёт фигур в prompt_builder.py (для OPT-5 шаг B)

Добавить парсинг Board-секции из серверного стейта и вставку строки:
```
Material balance: White 8 pcs (M+T+2D+2N+2P), Black 5 pcs (T+D+3P), Red 6 pcs (M+2N+3P) — you are WINNING.
```

---

## 7. Чек-лист перед каждой фазой

- [ ] Зафиксировать текущие метрики: `python -m trace_analyzer.metrics --smartbot`
- [ ] Сохранить snapshot: `cp logs/evaluations/model_rankings.json logs/evaluations/model_rankings_phase_N.json`
- [ ] Git commit текущего состояния промптов
- [ ] Внести одно (!) изменение
- [ ] Прогнать 45 игр (3 модели × 15 игр)
- [ ] Пересчитать метрики: `python -m trace_analyzer.metrics --smartbot`
- [ ] Сравнить с предыдущей фазой по таблице целевых метрик
- [ ] Решение: Go / No-Go(мягкий) / No-Go(жёсткий)
- [ ] Обновить таблицу результатов в этом документе (секция 8)

---

## 8. Результаты (заполняется по мере выполнения)

| Фаза | Оптимизация | blunder_rate | brilliant_rate | top3_rate | median_gap | tokens/ход | Решение |
|------|-------------|-------------|----------------|-----------|------------|------------|---------|
| Baseline | — | 0.281 | 0.251 | 0.542 | 30 cp | 2325 | — |
| OPT-0 | Piece Values | — | — | — | — | — | *ожидает тестов* |
| OPT-1 | Chat Diplomacy | — | — | — | — | — | — |
| OPT-2 | Common Blunders | — | — | — | — | — | — |
| OPT-3 | Analysis Protocol | — | — | — | — | — | — |
| OPT-4+5 | Endgame + Role | — | — | — | — | — | — |
