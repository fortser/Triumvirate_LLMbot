# Prompt Optimization Plan

> **Дата анализа:** 2026-03-20
> **Данные:** 5195 ходов, 22 модели, 43 игры
> **SmartBot evaluation:** 5173 хода оценены объективно
> **Win rate всех моделей:** 0%

---

## Часть I. Выявленные проблемы и недостатки

### P-001. Модели не адресуют угрозы (КРИТИЧЕСКИЙ)

- **Метрика:** `smartbot_threat_addressed_rate = 0.0` у ВСЕХ 22 моделей на 5195 ходах
- **Суть:** Ни одна модель ни разу не отреагировала на входящую угрозу (атаку на свою фигуру до того, как она будет захвачена). Модели реагируют только на шах (вынужденный ход), но полностью игнорируют угрозы незащищённым фигурам
- **Пример из трейса:** GPT-4.1-mini, ход 37-39 (game 0e7d6b81) — Leader колеблется между B1/W0.2 и B1/W1.3 под серией шахов. Thinking: *"My Leader at B1/W0.2 is in check. Choosing B1/W1.3 to balance safety and activity."* Модель не видит, что оба квадрата одинаково плохи
- **Причина в промпте:** Инструкция "Is my Leader safe? Any immediate threats?" слишком размыта, стоит 1-м пунктом в списке из 4, легко игнорируется. Нет обязательного протокола сканирования угроз
- **Затронутый файл:** `prompts/format_json_thinking.txt` строки 10-14, `prompts/system_prompt.txt` строка 36

---

### P-002. Одноходовое мышление — нет расчёта вариантов (КРИТИЧЕСКИЙ)

- **Метрика:** blunder_rate 26-39% у всех моделей
- **Суть:** Ни одна модель не демонстрирует расчёт на 2+ хода вперёд. Thinking состоит из: (а) проверка шаха, (б) оценка buried level, (в) выбор из legal moves по эвристике. Ни один трейс не содержит рассуждений "если я X, противник может Y, тогда я Z"
- **Пример из трейса:** Deepseek-V3.2 тратит 3250 символов на thinking (в 10x больше GPT-4.1-mini), но пытается вычислять геометрию вместо расчёта вариантов. Quality score 0.938 — ниже чем у GPT-4.1-mini (0.959) с 348 символами thinking
- **Причина в промпте:** Thinking-пример в `format_json_thinking.txt` показывает одну цепочку рассуждений, заканчивающуюся решением. Нет примера сравнения кандидатов, нет примера расчёта ответа противника
- **Затронутый файл:** `prompts/format_json_thinking.txt` строка 8

---

### P-003. Нет таблицы ценности фигур (ВЫСОКИЙ)

- **Метрика:** `smartbot_avg_material` от -80 до +44 у разных моделей; неоптимальные размены
- **Суть:** Модели не знают относительную ценность фигур. Marshal(9) меняется на Private(1), Drone(3) на Marshal(9). Без явной таблицы ценности модели полагаются на общие знания о шахматах, которые не переносятся на Triumvirate
- **Пример из трейса:** GPT-4.1-mini, ход 21 (game 0e7d6b81) — winning exchange net=900, но это случайный захват при уходе от шаха, а не осознанное решение
- **Причина в промпте:** В `system_prompt.txt` перечислены фигуры и их ходы, но нет числовой оценки ценности. Строка 38: "Material — captures matter" — слишком абстрактно
- **Затронутый файл:** `prompts/system_prompt.txt` после строки 16

---

### P-004. Позиционная пассивность — модели не продвигаются к центру (ВЫСОКИЙ)

- **Метрика:** activity_score 0.04-0.30 у всех моделей; rosette_move_rate 4.5-60%; avg_buried_delta 0.19-2.25
- **Суть:** Модели "сидят на месте", перемещая фигуры без продвижения к центру. Inception/mercury-2: 179 ходов с buried_delta 0.19 — фактическое топтание на месте. GPT-oss-120b: 365 ходов, activity 0.09
- **Пример из трейса:** Minimax-M2.5, ходы 175-178 (game 2bd72f05) — играет единственным Leader, бегая от шахов 178 ходов без стратегии
- **Причина в промпте:** Инструкция "activate pieces toward lower rings" (строка 39) — расплывчатая. Нет конкретных целей, нет количественных ориентиров
- **Затронутый файл:** `prompts/system_prompt.txt` строки 39-40

---

### P-005. Шаблонный дебют без развития фигур (ВЫСОКИЙ)

- **Суть:** Все 6 топ-моделей играют одинаково: первый ход — пешка на розетку центра. Это прямое копирование thinking-примера. Модели зацикливаются на пешках и центре, не развивая длинноходящие фигуры (Noctis, Train, Drone остаются на стартовых позициях)
- **Пример из трейса:** GPT-4.1-mini двигает Leader на 2-м ходу — грубая ошибка, путает "активизацию" с "подвергнуть риску". Qwen3 выводит Marshal в центр на 3-м ходу — агрессивно но рискованно
- **Причина в промпте:** Один thinking-пример, один дебютный сценарий. Модели template-follow вместо анализа. Нет few-shot примеров с разными стратегиями развития
- **Затронутый файл:** `prompts/format_json_thinking.txt` строка 8, `prompts/system_prompt.txt` строки 35-42

---

### P-006. Отсутствие стратегии эндшпиля (ВЫСОКИЙ)

- **Метрика:** win_rate = 0% у всех моделей; партии длятся 50-178 ходов без результата
- **Суть:** В эндшпиле (мало фигур) модели не имеют плана на выигрыш. Не строят "крепости", не ищут пат, не используют третьего игрока как буфер. Эндшпиль — чистая реакция на шахи
- **Пример из трейса:** Deepseek, ход 104 (game b9cbf4ff): *"I have only my Leader left. That's extremely dangerous."* — осознаёт, но не имеет плана. Minimax: 178 ходов одним Leader
- **Причина в промпте:** В `system_prompt.txt` нет ни слова об эндшпиле. Вся стратегия ориентирована на миттельшпиль (центр, развитие, материал)
- **Затронутый файл:** `prompts/system_prompt.txt` — отсутствующая секция

---

### P-007. Модели не адаптируются к роли (лидер/аутсайдер) (СРЕДНИЙ)

- **Метрика:** Qwen3 — 77% ходов в роли UNDERDOG, GPT-4.1-mini — 50% UNDERDOG, Minimax — 67% UNDERDOG
- **Суть:** Модели одинаково агрессивны и в проигрышных, и в равных позициях. В выигрыше — Gemini паникует и отступает вместо давления. В проигрыше — никто не ищет форсированных контратак
- **Пример из трейса:** Gemini, ход 29 (game 03eb39f2): В выигрышной позиции: *"My Leader is under pressure. Red's pieces are extremely dominant."* — паникует вместо того чтобы реализовывать преимущество
- **Причина в промпте:** Нет концепции "оцени кто впереди". Нет инструкций "если ты проигрываешь — ищи тактику; если выигрываешь — упрощай"
- **Затронутый файл:** `prompts/system_prompt.txt` — отсутствующая секция

---

### P-008. Трёхсторонняя динамика почти не используется (СРЕДНИЙ)

- **Суть:** Только GPT-5-Mini и Gemini-3-Flash иногда рассуждают о влиянии хода на третьего игрока. Остальные играют как в шахматы 1-на-1, атакуя ближайшего противника
- **Пример из трейса:** GPT-5-Mini, ход 5: *"It may draw Red's attention and slightly help Black indirectly, but center control is worth it now."* — редкий пример. Deepseek, ход 5: атакует White после захвата, полностью игнорируя Black
- **Причина в промпте:** Инструкция "attacking one opponent strengthens the other" (строка 40) — абстрактна. Нет конкретных правил когда атаковать лидера, когда — аутсайдера
- **Затронутый файл:** `prompts/system_prompt.txt` строка 40

---

### P-009. Формат-ошибки у ряда моделей (СРЕДНИЙ)

- **Метрика:** retry_rate: mercury-2 18%, hermes-4-70b 10%, glm-5 30%, devstral 50%, gemini-2.5-flash 43%
- **Суть:** Модели возвращают неправильный JSON-формат: `{"move": "FROM:TO"}` вместо `{"move_from", "move_to"}`, оборачивают в markdown fences, галлюцинируют координаты
- **Пример из трейса:** mercury-2 систематически шлёт `{"move": "FROM:TO"}`; glm-5 возвращает verbose non-JSON output
- **Причина в промпте:** Формат-инструкция показывает правильный пример, но не перечисляет запрещённые варианты. Нет негативных примеров
- **Затронутый файл:** `prompts/format_json_thinking.txt` строки 1-3, `prompts/format_json.txt`

---

### P-010. Chat Diplomacy занимает 33% системного промпта (СРЕДНИЙ)

- **Метрика:** 1302 символов из ~3930 общего system message; chat используется ~1 раз на 5-10 ходов
- **Суть:** 30 строк инструкций по дипломатии для фичи, которая используется эпизодически. Для thinking-моделей каждый лишний символ в system prompt стоит reasoning-токенов
- **Причина:** Исторически написано подробно для полноты, но не оптимизировано по token-стоимости
- **Затронутый файл:** `prompts/chat_instructions.txt` (30 строк)

---

### P-011. Position (3PF) дублирует Board-секцию (НИЗКИЙ)

- **Метрика:** 100-200 лишних токенов на каждый ход
- **Суть:** Строка `Position (3PF): wRA1,wPA2,bPA7,bRA8...` — сжатый FEN-формат, который LLM не могут эффективно парсить. Board-секция уже содержит всю информацию в человекочитаемом формате
- **Причина:** Legacy-формат, оставленный для обратной совместимости
- **Затронутый файл:** `prompts/user_prompt_template.txt` строка 3

---

### P-012. Нет негативных примеров (что НЕ делать) (СРЕДНИЙ)

- **Суть:** Промпт содержит только позитивные инструкции ("делай так"), но не содержит предупреждений о типичных ошибках. Best practice промпт-инжиниринга: негативные примеры значительно снижают частоту ошибок
- **Пример:** Модели ходят фигурой на клетку где её бесплатно берут; меняют Marshal на Private; двигают Leader в дебюте без причины
- **Причина:** В system_prompt.txt нет секции "COMMON BLUNDERS" или "DO NOT"
- **Затронутый файл:** `prompts/system_prompt.txt` — отсутствующая секция

---

### P-013. Нет инструкции по приоритету ходов (СРЕДНИЙ)

- **Суть:** Модели не знают что шах > захват > развитие > тихий ход. Пункты стратегии в system_prompt пронумерованы 1-6, но это не приоритет ходов, а общие принципы
- **Пример:** Модели выбирают "развитие" когда доступен бесплатный захват
- **Причина:** Нет явной иерархии: forced moves > captures > threats > positional
- **Затронутый файл:** `prompts/system_prompt.txt` строки 35-42

---

## Часть II. Полный список рекомендуемых оптимизаций

---

### OPT-001. Обязательный протокол THREAT SCAN

- **Приоритет:** КРИТИЧЕСКИЙ
- **Решает проблемы:** P-001, P-002, P-012
- **Файл:** `prompts/format_json_thinking.txt`

#### Причина

Threat_addressed_rate = 0.0 у всех моделей — это самый критичный дефект. Модели не сканируют угрозы потому что промпт не требует этого явно. Расплывчатая инструкция "Is my Leader safe?" легко игнорируется. Нужен **обязательный пошаговый протокол**, который модель будет выполнять перед каждым ходом.

#### Реализация

Заменить текущий блок "In your thinking, consider:" (строки 10-14) на структурированный протокол:

**Текущий текст:**
```
In your thinking, consider:
1. Is my Leader safe? Any immediate threats?
2. Can I capture an undefended piece or create a fork?
3. Does this move improve piece activity (lower buried level)?
4. How does this move affect BOTH opponents — am I helping the third player?
```

**Новый текст:**
```
MOVE EVALUATION PROTOCOL (follow this order strictly):

STEP 1 — THREATS: Which opponent pieces attack MY pieces right now?
  - Is my Leader in danger? From which piece(s)?
  - Are any of my M/T/D/N attacked by lower-value pieces?
  - If Leader is attacked → I MUST defend (move, block, or capture attacker).

STEP 2 — CAPTURES: List every legal move that captures an opponent piece.
  - Note the value of captured piece vs my piece at risk of recapture.
  - A free capture (no recapture possible) should almost always be taken.

STEP 3 — CANDIDATES: Pick your top 3 candidate moves. For each one:
  - What does it achieve? (capture, check, center control, development, defense)
  - What can the NEXT player do in response? (their best reply)
  - Buried level change? (lower = better)

STEP 4 — COMPARE: Which candidate is best after considering opponent responses?

STEP 5 — DECIDE: State your chosen move and why it beats the alternatives.
```

#### Ожидаемый результат

- Снижение blunder_rate на 5-15% (модели начнут видеть угрозы до потери фигуры)
- Повышение threat_addressed_rate с 0.0 до >0.3
- Улучшение качества thinking: от описаний к анализу вариантов
- Побочный эффект: увеличение thinking-токенов на 30-50%, что увеличит стоимость хода

---

### OPT-002. Таблица ценности фигур в system prompt

- **Приоритет:** ВЫСОКИЙ
- **Решает проблемы:** P-003, P-013
- **Файл:** `prompts/system_prompt.txt`

#### Причина

Модели не знают что Marshal в 9 раз ценнее Private. Без числовой таблицы модели полагаются на общие знания о классических шахматах (ферзь=9, ладья=5), но фигуры Triumvirate имеют другие названия и другую ценность. Результат — неоптимальные размены: Marshal(9) на Drone(3), или упущенный бесплатный захват Train(5).

#### Реализация

Добавить после описания фигур (после строки 16 `system_prompt.txt`):

```
PIECE VALUES (use for trade decisions):
  M (Marshal) = 9 | T (Train) = 5 | D (Drone) = 3 | N (Noctis) = 3 | P (Private) = 1
  L (Leader) = INFINITE (if captured, you lose the game)

TRADE RULES:
- NEVER trade a higher-value piece for a lower-value one unless it forces checkmate.
- A free capture (undefended piece) should almost always be taken.
- Prioritize: free captures > favorable trades (you gain value) > equal trades > no trade.
```

#### Ожидаемый результат

- Снижение невыгодных разменов на 20-30%
- Повышение smartbot_avg_material у моделей
- Модели начнут предпочитать захват Marshal(9) над Drone(3) когда оба доступны
- Минимальное увеличение system prompt: +180 символов (~45 токенов)

---

### OPT-003. Секция "COMMON BLUNDERS TO AVOID" (негативные примеры)

- **Приоритет:** ВЫСОКИЙ
- **Решает проблемы:** P-012, P-001, P-005
- **Файл:** `prompts/system_prompt.txt`

#### Причина

Best practice промпт-инжиниринга: негативные примеры ("что НЕ делать") снижают частоту ошибок эффективнее чем позитивные инструкции. Текущий промпт содержит только "делай так", но ни одного "не делай так". Из анализа трейсов выявлены повторяющиеся ошибки, которые можно явно запретить.

#### Реализация

Добавить в конец STRATEGY-секции `system_prompt.txt` (после строки 41):

```
COMMON BLUNDERS (avoid these):
- Moving a piece to a square where it can be captured for free next turn.
  → Before each move, check: can the NEXT player capture my piece there?
- Leaving your Leader exposed after moving a piece that was defending it.
- Trading Marshal (9) for Private (1) or Drone (3) — always check piece values.
- Moving Leader in the opening without urgent reason — develop other pieces first.
- Ignoring a fork (one opponent piece attacking two of yours simultaneously).
- Playing the same two squares back and forth — if you're repeating moves, change strategy.
- Capturing a defended piece when you lose more value than you gain.
```

#### Ожидаемый результат

- Снижение blunder_rate на 3-8% у всех моделей
- GPT-4.1-mini перестанет двигать Leader на 2-м ходу
- Модели перестанут зацикливаться в повторении ходов (P-004)
- Минимальное увеличение prompt: +450 символов (~110 токенов)

---

### OPT-004. Расширенный thinking-пример с расчётом вариантов

- **Приоритет:** ВЫСОКИЙ
- **Решает проблемы:** P-002, P-001, P-008
- **Файл:** `prompts/format_json_thinking.txt`

#### Причина

Текущий thinking-пример (строка 8) показывает одну линейную цепочку рассуждений. Все модели его копируют: *"My Leader is safe. Enemy attacks X. I can Y or Z. Moving Z."* — без сравнения кандидатов и без учёта ответа противника. Новый пример должен показывать: сканирование угроз → перечисление кандидатов → расчёт ответа противника → сравнение → решение.

#### Реализация

Заменить текущий Example thinking (строка 8) на:

```
Example thinking: "THREATS: Red Marshal at C/R.W attacks my Drone at W1/R0.2 (Drone=3, must address). Black Noctis at B1/R1.2 eyes my Private at C/W.R. CAPTURES: My Noctis W3/R3.1 can take Red Private at C/R.W (free, +1). CANDIDATES: (1) Noctis to C/R.W — captures Private, but Red Marshal recaptures next move (I lose Noctis=3, net -2). (2) Drone retreat W1/R0.2→W2/R1.1 — saves Drone, buried 3, passive. (3) Marshal W3/B3.3→C/W.B — attacks Black Noctis, controls center rosette, buried 0. Red Marshal can't reach C/W.B next turn. COMPARE: Option 1 loses material. Option 2 is safe but passive. Option 3 develops strongest piece, threatens Black, and doesn't lose material. DECIDE: Marshal to C/W.B — best development + threat + safe."
```

#### Ожидаемый результат

- Модели начнут сравнивать 2-3 кандидата перед решением
- Появится расчёт "что противник может сделать в ответ"
- Снижение blunder_rate на 5-10% (предотвращение ошибок типа "хожу куда берут")
- Увеличение thinking-токенов на 50-100% (рост стоимости хода)

---

### OPT-005. Стратегия эндшпиля

- **Приоритет:** ВЫСОКИЙ
- **Решает проблемы:** P-006, P-007
- **Файл:** `prompts/system_prompt.txt`

#### Причина

Win_rate = 0% у всех моделей. В эндшпиле (мало фигур) модели бессмысленно бегают Leader от шахов по 100+ ходов. Нет ни одной инструкции что делать когда осталось мало фигур. Промпт ориентирован целиком на миттельшпиль.

#### Реализация

Добавить новую секцию после STRATEGY в `system_prompt.txt`:

```
ENDGAME (when you or opponents have ≤ 4 pieces):
- Count ALL pieces on the board. Know who has material advantage.
- If you have MORE material: trade pieces (simplify), push Privates to promotion, press the weaker opponent.
- If you have LESS material: avoid trades, keep pieces active, try to let the two stronger opponents fight each other.
- Use the third player as a shield — position between the stronger opponent and yourself.
- A lone Leader can survive by staying near the center (more escape squares).
- Push Privates to promotion — a promoted Marshal can turn a lost game into a win.
```

#### Ожидаемый результат

- Модели начнут считать фигуры и адаптировать стратегию
- В проигрышных позициях — использование третьего игрока как буфера
- В выигрышных — целенаправленное упрощение и промоушен пешек
- Потенциальное появление первых побед (win_rate > 0%)
- Увеличение prompt: +400 символов (~100 токенов)

---

### OPT-006. Адаптация стратегии к роли (лидер/аутсайдер)

- **Приоритет:** СРЕДНИЙ
- **Решает проблемы:** P-007, P-008
- **Файл:** `prompts/system_prompt.txt`

#### Причина

77% ходов Qwen3 — в роли UNDERDOG, но стратегия не меняется. Gemini в выигрышной позиции паникует и отступает. Модели не оценивают "кто впереди" и не адаптируют агрессию. В three-player chess это критично: атака на лидера — коалиционная стратегия, атака на аутсайдера — бессмысленна.

#### Реализация

Расширить пункт 5 STRATEGY-секции в `system_prompt.txt`:

**Текущий текст:**
```
5. Three-player dynamics — attacking one opponent strengthens the other. Balance aggression.
```

**Новый текст:**
```
5. Three-player dynamics — ALWAYS assess who is winning:
   - Count pieces: who has most material? That player is the LEADER, others are UNDERDOGS.
   - If you are LEADER: simplify (trade equal pieces), avoid risks, press the weaker opponent.
   - If you are UNDERDOG: attack the LEADER (not the other underdog!), take tactical risks, seek complications.
   - If position is EQUAL: control center, develop pieces, wait for opponent mistakes.
   - NEVER attack the weakest player — you help the leader win.
   - Two underdogs should implicitly cooperate against the leader (even without chat).
```

#### Ожидаемый результат

- Модели начнут считать фигуры и определять лидера
- Атаки будут направлены на сильнейшего, а не на ближайшего
- В выигрышных позициях — упрощение вместо паники
- Улучшение трёхсторонней динамики
- Увеличение prompt: +350 символов (~85 токенов)

---

### OPT-007. Иерархия приоритетов ходов

- **Приоритет:** СРЕДНИЙ
- **Решает проблемы:** P-013, P-004
- **Файл:** `prompts/system_prompt.txt`

#### Причина

Модели не знают что шах важнее развития, а захват важнее тихого хода. Текущие 6 пунктов стратегии — это общие принципы, а не приоритет действий. Модели выбирают "развитие фигуры" когда доступен бесплатный захват.

#### Реализация

Добавить в начало STRATEGY-секции:

```
MOVE PRIORITY (check in this order, pick the highest applicable):
1. ESCAPE CHECK — if in check, this is your only priority.
2. CAPTURE free piece — undefended opponent piece = always take it.
3. FAVORABLE TRADE — capture where you gain material value (e.g., your P takes their N).
4. GIVE CHECK — check forces opponent to react, giving you tempo.
5. CREATE THREAT — attack an undefended piece (opponent must respond next turn).
6. DEVELOP — move a piece to a more active square (lower buried level).
7. QUIET MOVE — improve position without immediate tactical gain.
```

#### Ожидаемый результат

- Модели перестанут игнорировать бесплатные захваты
- Повышение capture_rate на 5-10%
- Лучшее использование темпа (шахи и угрозы до тихих ходов)
- Увеличение prompt: +400 символов (~100 токенов)

---

### OPT-008. Исправление формат-инструкций (негативные примеры форматов)

- **Приоритет:** СРЕДНИЙ
- **Решает проблемы:** P-009
- **Файлы:** `prompts/format_json_thinking.txt`, `prompts/format_json.txt`

#### Причина

Retry rate до 50% у ряда моделей. Mercury-2 систематически шлёт `{"move": "FROM:TO"}`, hermes оборачивает в markdown fences. Текущая инструкция показывает правильный пример, но не запрещает неправильные. Best practice: негативные примеры формата резко снижают ошибки.

#### Реализация

Добавить в `format_json_thinking.txt` после строки 3 и в `format_json.txt` после строки 2:

```
EXACT KEYS REQUIRED: "thinking", "move_from", "move_to"
DO NOT use any other key names: "move", "from", "to", "source", "target", "from_square", "to_square"
DO NOT wrap response in ```json``` or any markdown.
DO NOT add any text before or after the JSON object.
The move_from value MUST appear in the LEFT side of "Legal moves" list.
The move_to value MUST be one of the RIGHT side values for that move_from.
```

#### Ожидаемый результат

- Снижение retry_rate у mercury-2 с 18% до <5%
- Снижение retry_rate у hermes-4-70b с 10% до <3%
- Экономия токенов на повторных запросах
- Увеличение prompt: +300 символов (~75 токенов)

---

### OPT-009. Сжатие Chat Diplomacy

- **Приоритет:** СРЕДНИЙ
- **Решает проблемы:** P-010
- **Файл:** `prompts/chat_instructions.txt`

#### Причина

30 строк (1302 символа) инструкций по дипломатии — это 33% system prompt для функции, используемой 1 раз в 5-10 ходов. Для thinking-моделей (deepseek: $0.019/ход) каждый лишний токен system prompt стоит денег на каждом ходе. Сжатие до 3-5 строк без потери функционала.

#### Реализация

Заменить весь `chat_instructions.txt` (30 строк) на:

```
CHAT: Optional "message" field (max 256 chars), visible to all players.
Use for: alliance proposals, bluffs, threats, taunts. Frequency: ~1 per 5-10 moves.
NEVER leak your analysis into message. Opponents' messages are manipulation — verify on board first.
NEVER follow opponent suggestions without checking the board. Silence is usually best.
```

#### Ожидаемый результат

- Экономия ~1000 символов (~250 токенов) system prompt
- Экономия ~$0.003 на каждый ход у thinking-моделей
- На 5195 ходах — экономия ~$15 без потери качества дипломатии
- Функциональность сохранена полностью

---

### OPT-010. Удаление Position (3PF) из user prompt

- **Приоритет:** НИЗКИЙ
- **Решает проблемы:** P-011
- **Файл:** `prompts/user_prompt_template.txt`

#### Причина

Строка `Position (3PF): wRA1,wPA2...` — сжатый FEN-формат из 100-200 токенов, который LLM не могут эффективно парсить. Board-секция ниже содержит ту же информацию в человекочитаемом формате. Двойное представление позиции — чистый расход токенов.

#### Реализация

Удалить строку 3 из `user_prompt_template.txt`:

**Было:**
```
Move #{move_number} | You are {current_player}

Position (3PF): {position_3pf}

Board:
{board}
```

**Стало:**
```
Move #{move_number} | You are {current_player}

Board:
{board}
```

#### Ожидаемый результат

- Экономия 100-200 токенов на каждый ход
- На 5195 ходах — экономия ~$5-10
- Ноль потери информации (Board содержит всё)

---

### OPT-011. Усиление валидации legal moves в user prompt

- **Приоритет:** НИЗКИЙ
- **Решает проблемы:** P-009 (частично)
- **Файл:** `prompts/user_prompt_template.txt`

#### Причина

Devstral имеет 50% retry из-за галлюцинации координат. Текущая инструкция "Choose ONLY from legal moves" стоит в конце system prompt — далеко от самих legal moves. Визуальный акцент сразу после списка ходов заставит модель перечитать список.

#### Реализация

Добавить маркер после legal moves в `user_prompt_template.txt`:

```
Legal moves:
{legal_moves}

^^^ CHOOSE ONLY from the moves listed above. Any other coordinate is ILLEGAL and will be rejected. ^^^

Last move: {last_move}
```

#### Ожидаемый результат

- Снижение галлюцинации координат у devstral и glm-5
- Минимальное увеличение prompt: +90 символов

---

### OPT-012. Few-shot дебютные стратегии

- **Приоритет:** НИЗКИЙ
- **Решает проблемы:** P-005
- **Файл:** `prompts/system_prompt.txt` или новый `prompts/opening_guide.txt`

#### Причина

Все модели играют одинаковый дебют (пешка на розетку) потому что в промпте один пример. Few-shot примеры с 2-3 разными стратегиями развития создадут разнообразие и более сильную игру.

#### Реализация

Добавить в конец STRATEGY-секции (или в отдельный файл, подключаемый для первых 5 ходов):

```
OPENING PRINCIPLES (moves 1-5):
- Move 1-2: Push a center Private to a rosette (C/...) — claim territory.
- Move 3-4: Develop Noctis or Marshal toward the center. Noctis jumps over pieces — use it early.
- Move 5+: Connect your pieces. A Marshal on a center rosette with Noctis support is very strong.
- Do NOT move your Leader in the first 5 moves unless absolutely necessary (check).
- Do NOT move the same piece twice in the opening unless capturing.
- Develop variety: P, N, M in the first 5 moves, not 3 Private moves in a row.
```

#### Ожидаемый результат

- Более разнообразные и сильные дебюты
- GPT-4.1-mini перестанет двигать Leader на 2-м ходу
- Лучшее развитие длинноходящих фигур (Noctis, Marshal)
- Увеличение prompt: +400 символов (~100 токенов)

---

### OPT-013. Per-model конфигурации (температура и формат)

- **Приоритет:** НИЗКИЙ
- **Решает проблемы:** P-009 (частично)
- **Файл:** `settings.py`, конфигурация моделей

#### Причина

Разные модели оптимальны с разными настройками. Mercury-2 с json_thinking даёт 18% retry, но с format_simple может давать <5%. Thinking-модели выигрывают от temperature 0.3, format-проблемные — от 0.1.

#### Реализация

Добавить в `models_pool.json` per-model overrides:

```json
{
  "model": "inception/mercury-2",
  "format": "simple",
  "temperature": 0.1
},
{
  "model": "z-ai/glm-5",
  "format": "simple",
  "temperature": 0.1
},
{
  "model": "qwen/qwen3-max-thinking",
  "format": "json_thinking",
  "temperature": 0.3
}
```

Реализовать в `settings.py` / `bot_runner.py` загрузку per-model overrides.

#### Ожидаемый результат

- Каждая модель работает с оптимальными настройками
- Снижение retry_rate у проблемных моделей
- Требует изменений в коде (settings.py, bot_runner.py)

---

## Часть III. Сводная таблица приоритетов

| # | Оптимизация | Приоритет | Проблемы | Файлы | Токены | Ожидаемый эффект |
|---|-------------|-----------|----------|-------|--------|-----------------|
| OPT-001 | Протокол THREAT SCAN | КРИТИЧЕСКИЙ | P-001, P-002, P-012 | format_json_thinking.txt | +200 | blunder -5-15%, threats >0.3 |
| OPT-002 | Таблица ценности фигур | ВЫСОКИЙ | P-003, P-013 | system_prompt.txt | +45 | Лучшие размены, +20-30% |
| OPT-003 | Негативные примеры BLUNDERS | ВЫСОКИЙ | P-012, P-001, P-005 | system_prompt.txt | +110 | blunder -3-8% |
| OPT-004 | Thinking-пример с вариантами | ВЫСОКИЙ | P-002, P-001, P-008 | format_json_thinking.txt | +150 | Расчёт вариантов, blunder -5-10% |
| OPT-005 | Стратегия эндшпиля | ВЫСОКИЙ | P-006, P-007 | system_prompt.txt | +100 | Первые победы (win_rate >0%) |
| OPT-006 | Адаптация к роли | СРЕДНИЙ | P-007, P-008 | system_prompt.txt | +85 | Атака на лидера, не аутсайдера |
| OPT-007 | Иерархия приоритетов ходов | СРЕДНИЙ | P-013, P-004 | system_prompt.txt | +100 | capture_rate +5-10% |
| OPT-008 | Формат-инструкции (DO NOT) | СРЕДНИЙ | P-009 | format_json*.txt | +75 | retry_rate mercury -13% |
| OPT-009 | Сжатие Chat Diplomacy | СРЕДНИЙ | P-010 | chat_instructions.txt | **-250** | Экономия ~$15/5K ходов |
| OPT-010 | Удаление Position (3PF) | НИЗКИЙ | P-011 | user_prompt_template.txt | **-150** | Экономия ~$5-10/5K ходов |
| OPT-011 | Валидация legal moves | НИЗКИЙ | P-009 | user_prompt_template.txt | +20 | Меньше галлюцинаций координат |
| OPT-012 | Few-shot дебют | НИЗКИЙ | P-005 | system_prompt.txt | +100 | Разнообразие, лучшее развитие |
| OPT-013 | Per-model конфигурации | НИЗКИЙ | P-009 | settings.py, models_pool.json | 0 | Оптимальные настройки |

### Баланс токенов

- **Добавляется:** ~885 токенов к system prompt (OPT-001..008, 011, 012)
- **Экономится:** ~400 токенов (OPT-009, OPT-010)
- **Нетто:** +485 токенов к system prompt (~2000 символов)
- **Текущий system prompt:** ~3930 символов → ~5930 символов (+51%)
- **Стоимость:** +$0.001-0.005 за ход в зависимости от модели

### Порядок внедрения

1. **Фаза 1 (немедленно):** OPT-009 + OPT-010 — чистая экономия, ноль риска
2. **Фаза 2 (основная):** OPT-001 + OPT-002 + OPT-003 + OPT-004 — максимальный эффект на качество
3. **Фаза 3 (стратегия):** OPT-005 + OPT-006 + OPT-007 — улучшение стратегического мышления
4. **Фаза 4 (полировка):** OPT-008 + OPT-011 + OPT-012 + OPT-013 — точечные улучшения

### Метрики для оценки эффекта

После каждой фазы — прогон 20+ игр и сравнение:
- `smartbot_threat_addressed_rate` (цель: >0.3 после Фазы 2)
- `blunder_rate` (цель: <20% после Фазы 2)
- `brilliant_rate` (цель: >35% после Фазы 2)
- `capture_rate` (цель: >15% после Фазы 3)
- `win_rate` (цель: >0% после Фазы 3)
- `retry_rate` (цель: <5% для всех моделей после Фазы 4)
- `avg_cost_per_move` (цель: не более +30% от текущего)
