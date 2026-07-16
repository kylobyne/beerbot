<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>

<h1>🍺 Beer Bot — Telegram бот с рейтингом выпитого пива</h1>

<p>Telegram-бот для групповых чатов, который позволяет пользователям виртуально «пить пиво», получать место в рейтинге и покупать дополнительные попытки через Telegram Stars.</p>

<p>
    <span class="badge badge-python">Python 3.8+</span>
    <span class="badge badge-aiogram">aiogram 3.x</span>
    <span class="badge badge-license">MIT License</span>
</p>

<hr>

<h2>📋 Возможности</h2>

<h3>🍺 Обычное питьё</h3>

<p>Команда:</p>

<pre><code>/beer</code></pre>

<p>После команды пользователь получает случайное количество виртуального пива (от 0.1 до 5.0 литров).</p>

<p><strong>Особенности:</strong></p>
<ul>
    <li>работает только в групповых чатах;</li>
    <li>действует кулдаун между обычными попытками (1 час);</li>
    <li>выпитые литры добавляются в рейтинг текущего чата;</li>
    <li>время последнего питья сохраняется в базе.</li>
</ul>

<hr>

<h3>⭐ Дополнительные попытки</h3>

<p>Команда:</p>

<pre><code>/buy</code></pre>

<p>Открывает меню покупки дополнительных попыток за Telegram Stars.</p>

<p><strong>Доступные товары</strong> (настраиваются в <code>config.py</code>):</p>

<pre><code>BUY_OPTIONS = {
    "5": {"attempts": 5, "stars": 15},
    "10": {"attempts": 10, "stars": 20},
    "15": {"attempts": 15, "stars": 25}
}</code></pre>

<p><strong>После успешной оплаты:</strong></p>
<ul>
    <li>пользователю начисляются дополнительные попытки;</li>
    <li>попытки сохраняются глобально для всех чатов;</li>
    <li>используется база <code>payd_attemps.sqlite3</code> - общая для всех чатов.</li>
</ul>

<hr>

<h2>🎮 Логика дополнительных попыток</h2>

<p>Когда пользователь использует <code>/beer</code>, бот проверяет:</p>

<ol>
    <li><strong>Есть ли обычная доступная попытка?</strong>
        <ul>
            <li>Если да → выпивает и обновляет <code>last_drink</code></li>
        </ul>
    </li>
    <li><strong>Если действует кулдаун:</strong>
        <ul>
            <li>Проверяются купленные попытки</li>
            <li>Если они есть → одна попытка списывается</li>
            <li>Литры добавляются в рейтинг текущего чата</li>
            <li>Время обычного питья (<code>last_drink</code>) <strong>НЕ</strong> изменяется</li>
        </ul>
    </li>
</ol>

<p><strong>Результат:</strong></p>
<ul>
    <li>Купленные попытки позволяют пить вне кулдауна</li>
    <li>Рейтинг чата продолжает обновляться</li>
    <li>Невозможно сбить обычный таймер</li>
</ul>

<hr>

<h2>📊 Статистика</h2>

<p>Команда:</p>

<pre><code>/stats</code></pre>

<p>Показывает рейтинг пользователей в текущем чате.</p>

<p><strong>Возможности:</strong></p>
<ul>
    <li>сортировка по количеству литров (по убыванию);</li>
    <li>постраничный вывод (20 записей на страницу);</li>
    <li>inline-кнопки навигации ◀️ ▶️;</li>
    <li>автоматическая фильтрация покинувших чат пользователей;</li>
    <li>топ-3 с медальками 🥇🥈🥉.</li>
</ul>

<hr>

<h2>🎁 Промокоды</h2>

<p><strong>Для пользователей:</strong></p>

<pre><code>/promo КОД</code></pre>

<p>Активирует промокод и начисляет награду.</p>

<p><strong>Для администраторов:</strong></p>

<pre><code>/admin</code></pre>

<p>Открывает админ-панель для управления промокодами.</p>

<p><strong>Возможности админ-панели:</strong></p>
<ul>
    <li>Создание промокодов (пошаговый мастер)</li>
    <li>Настройка существующих промокодов</li>
    <li>Удаление промокодов (с двойным подтверждением)</li>
</ul>

<p><strong>Типы наград:</strong></p>
<ul>
    <li>Пиво (литры)</li>
    <li>Дополнительные попытки</li>
</ul>

<p><strong>Ограничения промокодов:</strong></p>
<ul>
    <li>⏰ Временные (дата или длительность: <code>2h</code>, <code>3h</code>, <code>2h5s</code>)</li>
    <li>🔢 Лимит активаций</li>
    <li>👥 Привязка к конкретным пользователям</li>
</ul>

<hr>

<h2>📁 Команды бота</h2>

<table>
    <thead>
        <tr>
            <th>Команда</th>
            <th>Описание</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><code>/start</code></td>
            <td>Информация о боте и справка</td>
        </tr>
        <tr>
            <td><code>/beer</code></td>
            <td>Выпить виртуальное пиво</td>
        </tr>
        <tr>
            <td><code>/buy</code></td>
            <td>Купить дополнительные попытки</td>
        </tr>
        <tr>
            <td><code>/stats</code></td>
            <td>Показать рейтинг</td>
        </tr>
        <tr>
            <td><code>/promo КОД</code></td>
            <td>Активировать промокод</td>
        </tr>
        <tr>
            <td><code>/admin</code></td>
            <td>Админ-панель (только для админов)</td>
        </tr>
    </tbody>
</table>

<hr>

<h2>📁 Структура проекта</h2>

<pre><code>beer/
│
├── bot.py                    # Запуск бота и фоновые задачи
├── config.py                 # Все настройки
├── database.py               # Работа с SQLite3
├── messages.py               # Все текстовые сообщения
│
├── handlers/
│   ├── admin.py              # Админ-панель
│   ├── beer.py               # Команда /beer
│   ├── buy.py                # Покупки Telegram Stars
│   ├── Middleware.py         # Анти-флуд
│   ├── promo.py              # Команда /promo
│   ├── start.py              # Команда /start
│   └── stats.py              # Команда /stats
│
├── sqlite3/
│   ├── chat_&lt;id&gt;.sqlite3     # Базы отдельных чатов
│   ├── payd_attemps.sqlite3  # Общая база платных попыток
│   └── promo.sqlite3         # База промокодов
│
├── .venv/                    # Виртуальное окружение
├── .env                      # Переменные окружения
├── requirements.txt          # Зависимости
├── start.bat                 # Запуск на Windows
└── README.md</code></pre>

<hr>

<h2>🗄️ Базы данных</h2>

<h3>База чата (<code>chat_&lt;chat_id&gt;.sqlite3</code>)</h3>

<p>Каждый чат имеет свою SQLite базу для изоляции данных.</p>

<pre><code>CREATE TABLE drinkers (
    user_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    total_liters REAL NOT NULL DEFAULT 0,
    last_drink INTEGER NOT NULL DEFAULT 0
);</code></pre>

<p><strong>Поля:</strong></p>
<ul>
    <li><code>user_id</code> - ID пользователя Telegram</li>
    <li><code>name</code> - Имя пользователя</li>
    <li><code>total_liters</code> - Всего выпито литров</li>
    <li><code>last_drink</code> - Время последнего выпивания (timestamp)</li>
</ul>

<hr>

<h3>Общая база платных попыток (<code>payd_attemps.sqlite3</code>)</h3>

<p>Используется для хранения купленных попыток. Одна база для всех чатов.</p>

<pre><code>-- Платные попытки пользователей
CREATE TABLE paid_attempts (
    user_id INTEGER PRIMARY KEY,
    attempts INTEGER NOT NULL DEFAULT 0
);

-- Инвойсы для отслеживания платежей
CREATE TABLE invoices (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'paid')),
    created_at INTEGER NOT NULL
);</code></pre>

<p><strong>Особенности:</strong></p>
<ul>
    <li>одна база для всех чатов;</li>
    <li>попытки привязаны к Telegram <code>user_id</code>;</li>
    <li>пользователь может использовать их в любом чате;</li>
    <li>защита от дублирования платежей.</li>
</ul>

<hr>

<h3>База промокодов (<code>promo.sqlite3</code>)</h3>

<p>Полноценная система управления промокодами.</p>

<pre><code>CREATE TABLE promocodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    reward_type TEXT,
    reward_amount INTEGER DEFAULT 0,
    time_limited INTEGER DEFAULT 0,
    expires_at TEXT,
    duration TEXT,
    activation_limited INTEGER DEFAULT 0,
    max_activations INTEGER,
    used_count INTEGER DEFAULT 0,
    bind_users TEXT,
    created_by INTEGER,
    created_at TEXT,
    updated_at TEXT,
    active INTEGER DEFAULT 1
);

CREATE TABLE promo_uses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    promo_id INTEGER,
    user_id INTEGER,
    used_at TEXT
);</code></pre>

<hr>

<h2>⚙️ Установка и запуск</h2>

<h3>1. Клонирование репозитория</h3>

<pre><code>git clone https://github.com/yourusername/beer-bot.git
cd beer-bot</code></pre>

<h3>2. Создание и активация виртуального окружения</h3>

<p><strong>Windows:</strong></p>
<pre><code>python -m venv .venv
.venv\Scripts\activate</code></pre>

<p><strong>macOS/Linux:</strong></p>
<pre><code>python3 -m venv .venv
source .venv/bin/activate</code></pre>

<h3>3. Установка зависимостей</h3>

<pre><code>pip install -r requirements.txt</code></pre>

<h3>4. Настройка окружения</h3>

<p>Создайте файл <code>.env</code> в корне проекта:</p>

<pre><code>BOT_TOKEN=ваш_токен_бота</code></pre>

<h3>5. Запуск бота</h3>

<pre><code>python bot.py</code></pre>

<p>Или используйте <code>start.bat</code> (Windows):</p>

<pre><code>start.bat</code></pre>

<hr>

<h2>🔧 Настройка товаров</h2>

<p>Все товары находятся в <code>config.py</code>:</p>

<pre><code>BUY_OPTIONS = {
    "5": {"attempts": 5, "stars": 15},
    "10": {"attempts": 10, "stars": 20},
    "15": {"attempts": 15, "stars": 25}
}</code></pre>

<p>Чтобы добавить новый пакет, достаточно добавить новый элемент:</p>

<pre><code>"25": {
    "attempts": 25,
    "stars": 100
}</code></pre>

<p>После этого бот автоматически:</p>
<ul>
    <li>создаст новую кнопку в <code>/buy</code>;</li>
    <li>создаст invoice Telegram Stars;</li>
    <li>обработает покупку;</li>
    <li>выдаст нужное количество попыток.</li>
</ul>

<hr>

<h2>🛡️ Безопасность покупок</h2>

<p>Попытки начисляются только после получения <code>successful_payment</code> от Telegram.</p>

<p><strong>Защита от дублирования:</strong></p>
<ul>
    <li>Инвойс имеет статус <code>pending</code> → <code>paid</code></li>
    <li>Один инвойс нельзя оплатить дважды</li>
    <li>Проверка срока действия (10 минут)</li>
    <li>Идемпотентность операций</li>
</ul>

<p><strong>Анти-флуд:</strong></p>
<ul>
    <li>5 секунд между покупками</li>
    <li>3 секунды между перелистыванием страниц</li>
    <li>1 час между бесплатными выпиваниями</li>
</ul>

<hr>

<h2>🔄 Фоновые задачи</h2>

<p>Бот автоматически очищает просроченные инвойсы:</p>

<pre><code>async def periodic_db_cleaner():
    while True:
        delete_old_pending_invoices()
        await asyncio.sleep(DB_CLEAN_INTERVAL)</code></pre>

<ul>
    <li><strong>Интервал</strong>: раз в час</li>
    <li><strong>Действие</strong>: удаление инвойсов со статусом <code>pending</code> старше 30 минут</li>
</ul>

<hr>

<h2>📦 Зависимости</h2>

<pre><code>aiogram>=3.0,&lt;4.0        # Фреймворк для Telegram ботов
python-dotenv>=1.0,&lt;2.0  # Загрузка переменных окружения</code></pre>

<p><strong>Встроенные модули Python:</strong></p>
<ul>
    <li><code>sqlite3</code> - работа с базами данных</li>
    <li><code>datetime</code> - работа с датами</li>
    <li><code>random</code> - генерация случайных чисел</li>
    <li><code>time</code> - работа с таймстемпами</li>
    <li><code>json</code> - работа с JSON</li>
    <li><code>uuid</code> - генерация уникальных ID</li>
    <li><code>re</code> - регулярные выражения</li>
    <li><code>html</code> - эскейпинг HTML</li>
    <li><code>math</code> - математические операции</li>
    <li><code>asyncio</code> - асинхронность</li>
</ul>

<hr>

<h2>🐛 Отладка и логирование</h2>

<pre><code>logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)</code></pre>

<hr>

<h2>🤝 Внесение вклада</h2>

<ol>
    <li>Форкните репозиторий</li>
    <li>Создайте ветку (<code>git checkout -b feature/amazing-feature</code>)</li>
    <li>Зафиксируйте изменения (<code>git commit -m 'Add feature'</code>)</li>
    <li>Отправьте изменения (<code>git push origin feature/amazing-feature</code>)</li>
    <li>Откройте Pull Request</li>
</ol>

<hr>

<h2>📄 Лицензия</h2>

<p>MIT License</p>

<hr>

<h2>💬 Поддержка</h2>

<p>По всем вопросам обращайтесь в <a href="https://t.me/kylobyne">Telegram</a> или создавайте Issue в репозитории.</p>

<hr>

<h2>🌟 Благодарности</h2>

<ul>
    <li><a href="https://docs.aiogram.dev/">aiogram</a> - за отличный фреймворк</li>
    <li>Telegram - за поддержку Telegram Stars и инвойсов</li>
    <li>Всех участников и пользователей бота 🍻</li>
</ul>

<hr>

<div class="center">
    <sub>Сделано с ❤️ и 🍺</sub>
</div>

</body>
</html>