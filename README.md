# 🍺 Beer Bot - Telegram Бот для Выпивания

> Telegram бот для соревнований по выпиванию пива с поддержкой платных попыток и промокодов

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-green.svg)](https://docs.aiogram.dev/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📋 Описание

**Beer Bot** - это игровой Telegram бот, который позволяет участникам групп соревноваться в количестве выпитого пива. Каждый час участники могут "выпить" случайное количество пива (от 0.1 до 5.0 литров) и соревноваться в таблице лидеров.

### 🎯 Основные возможности

- 🍺 **Выпивание пива** - случайное количество от 0.1 до 5.0 литров раз в час
- 🏆 **Таблица лидеров** - рейтинг самых "пьющих" участников с пагинацией
- ⭐ **Платные попытки** - покупка дополнительных попыток за Telegram Stars
- 🎁 **Промокоды** - гибкая система промокодов с различными наградами
- 👑 **Админ-панель** - управление промокодами через интерфейс бота
- 🛡️ **Защита от флуда** - кулдауны на команды и кнопки

---

## 🚀 Основные функции

### Для пользователей

| Команда | Описание |
|---------|----------|
| `/start` | Приветственное сообщение и справка |
| `/beer` | Выпить пиво (раз в час) |
| `/stats` | Показать таблицу лидеров |
| `/buy` | Купить дополнительные попытки за Telegram Stars |
| `/promo КОД` | Активировать промокод |

### Для администраторов

| Команда | Описание |
|---------|----------|
| `/admin` | Открыть админ-панель |

#### Админ-панель включает:
- **Создание промокодов** - пошаговый мастер с настройкой награды, времени действия, лимитов
- **Настройка промокодов** - редактирование существующих промокодов
- **Удаление промокодов** - с двойным подтверждением

---

## 📁 Архитектура проекта
project-root/
├── handlers/
│ ├── init.py
│ ├── admin.py # Админ-панель и управление промокодами
│ ├── beer.py # Основная механика выпивания
│ ├── buy.py # Покупка попыток через Telegram Stars
│ ├── Middleware.py # Анти-флуд для кнопок
│ ├── promo.py # Активация промокодов
│ ├── start.py # Приветствие и справка
│ └── stats.py # Таблица лидеров с пагинацией
│
├── sqlite3/
│ ├── chat_*.sqlite3 # Базы данных для каждого чата
│ ├── payd_attemps.sqlite3 # Платные попытки и инвойсы
│ └── promo.sqlite3 # Промокоды
│
├── .venv/ # Виртуальное окружение
├── bot.py # Точка входа в приложение
├── config.py # Конфигурация и настройки
├── database.py # Работа с SQLite3 базами данных
├── messages.py # Все текстовые сообщения
├── .env # Переменные окружения (токен)
├── requirements.txt # Зависимости
├── start.bat # Запуск на Windows
└── .gitignore # Игнорируемые файлы


### Назначение файлов

| Файл | Назначение |
|------|------------|
| `bot.py` | Точка входа, запуск бота и фоновых задач |
| `config.py` | Все настройки: токен, товары, кулдауны, админы |
| `database.py` | Работа с SQLite3: CRUD операции для всех БД |
| `messages.py` | Все текстовые сообщения для пользователей |
| `handlers/admin.py` | Админ-панель и управление промокодами |
| `handlers/beer.py` | Механика выпивания (бесплатно/платно) |
| `handlers/buy.py` | Покупка попыток через Telegram Stars |
| `handlers/Middleware.py` | Анти-флуд для кнопок (кулдауны) |
| `handlers/promo.py` | Активация промокодов пользователями |
| `handlers/start.py` | Приветствие и справка |
| `handlers/stats.py` | Таблица лидеров с пагинацией |

---

## 🗄️ Структура баз данных

### 1. База чата (`chat_{id}.sqlite3`)

Хранит статистику выпивания для каждого чата отдельно.

```sql
CREATE TABLE drinkers (
    user_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    total_liters REAL NOT NULL DEFAULT 0,
    last_drink INTEGER NOT NULL DEFAULT 0
);

Поля:

user_id - ID пользователя Telegram

name - Имя пользователя

total_liters - Всего выпито литров

last_drink - Время последнего выпивания (timestamp)

2. База платежей (payd_attemps.sqlite3)
Управляет платными попытками и защищает от дублирования платежей.
-- Платные попытки пользователей
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
);
-- Платные попытки пользователей
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
);
Таблица paid_attempts:

user_id - ID пользователя

attempts - Количество доступных платных попыток

Таблица invoices:

id - Уникальный ID инвойса (UUID)

user_id - ID пользователя

status - Статус: pending (ожидает оплаты) или paid (оплачен)

created_at - Время создания (timestamp)

3. База промокодов (promo.sqlite3)
Полноценная система управления промокодами.
CREATE TABLE promocodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    reward_type TEXT,         -- 'beer' или 'attempts'
    reward_amount INTEGER DEFAULT 0,
    time_limited INTEGER DEFAULT 0,
    expires_at TEXT,
    duration TEXT,
    activation_limited INTEGER DEFAULT 0,
    max_activations INTEGER,
    used_count INTEGER DEFAULT 0,
    bind_users TEXT,          -- ID пользователей через запятую
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
);

Таблица promocodes:

code - Название промокода (уникальное)

reward_type - Тип награды: beer (пиво) или attempts (попытки)

reward_amount - Количество награды

time_limited - Ограничение по времени (0/1)

expires_at - Дата истечения (формат: ДД.ММ.ГГГГ ЧЧ:ММ)

duration - Длительность действия (формат: 2h, 3h, 2h5s)

activation_limited - Ограничение по активациям (0/1)

max_activations - Максимальное количество активаций

used_count - Сколько раз уже активирован

bind_users - Привязанные пользователи (ID через запятую)

created_by - ID создавшего админа

created_at - Дата создания

updated_at - Дата обновления

active - Активен ли промокод (0/1)

Таблица promo_uses:

promo_id - ID промокода

user_id - ID активировавшего пользователя

used_at - Дата активации

⚙️ Установка и запуск
1. Клонирование репозитория
git clone https://github.com/yourusername/beer-bot.git
cd beer-bot

2. Создание и активация виртуального окружения
Windows:
python -m venv .venv
.venv\Scripts\activate

macOS/Linux:
python3 -m venv .venv
source .venv/bin/activate
3. Установка зависимостей
pip install -r requirements.txt
4. Настройка окружения
Создайте файл .env в корне проекта:
BOT_TOKEN=ваш_токен_бота
5. Запуск бота
python bot.py
Или используйте start.bat (Windows):
start.bat
🔧 Конфигурация (config.py)
Основные настройки бота с пояснениями:
# Товары для покупки
BUY_OPTIONS = {
    "5": {"attempts": 5, "stars": 15},    # 5 попыток за 15 звезд
    "10": {"attempts": 10, "stars": 20},   # 10 попыток за 20 звезд
    "15": {"attempts": 15, "stars": 25}    # 15 попыток за 25 звезд
}

# Администраторы (список Telegram ID)
admins = [
    123456789,  # Замените на свой ID
    987654321   # Можно добавить несколько админов
]

# Настройки кулдаунов
COOLDOWN_SECONDS = 3600          # 1 час между бесплатными выпиваниями
COOLDOWN_TIME = 5                # 5 секунд между покупками
PAGINATION_COOLDOWN_SECONDS = 3  # 3 секунды между перелистыванием топа

# Настройки инвойсов
INVOICE_LIFETIME = 600           # 10 минут на оплату
INVOICE_CLEAN_THRESHOLD = 1800   # 30 минут до очистки
DB_CLEAN_INTERVAL = 3600         # Очистка БД раз в час

# Пагинация
ROWS_PER_PAGE = 20               # Записей на страницу в таблице лидеров
PROMOS_PER_PAGE = 10             # Промокодов на страницу в админ-панели

# Разрешенные статусы пользователей в чате
ALLOWED_STATUSES = ["creator", "administrator", "member", "restricted"]
🎮 Механика игры
Бесплатные попытки
Каждый пользователь может использовать /beer раз в час

Случайное количество пива: 0.1 - 5.0 литров (с шагом 0.1)

Обновляется общая статистика и время последнего выпивания

Платные попытки
Можно купить через /buy за Telegram Stars

Три тарифа: 5, 10 или 15 попыток

Платные попытки НЕ обновляют таймер кулдауна

Можно использовать сразу после бесплатной попытки

Стоимость: от 15 до 25 звезд

Система промокодов
Награда: пиво (литры) или дополнительные попытки

Ограничения:

⏰ Временные (дата или длительность: 2h, 3h, 2h5s)

🔢 Лимит активаций

👥 Привязка к конкретным пользователям

Автоматическая деактивация после исчерпания

Защита от повторного использования одним пользователем

🛡️ Безопасность и защита
Анти-флуд (Middleware)
5 секунд между нажатиями кнопок покупки (привязка к user_id)

3 секунды между перелистыванием страниц таблицы лидеров (привязка к chat_id)

1 час между бесплатными выпиваниями (проверка в БД)

Платежи
Защита от дублирования через статус инвойса (pending → paid)

Проверка срока действия инвойса (10 минут)

Идемпотентность операций - один инвойс нельзя оплатить дважды

PreCheckoutQuery проверка перед оплатой

Данные
Отдельные БД для каждого чата (изоляция данных)

Фильтрация покинувших чат пользователей при просмотре статистики

Автоматическая очистка просроченных инвойсов (раз в час)

HTML-эскейпинг имен пользователей (защита от XSS)

📦 Зависимости
aiogram>=3.0,<4.0        # Фреймворк для Telegram ботов
python-dotenv>=1.0,<2.0  # Загрузка переменных окружения
Все остальное - встроенные модули Python:

sqlite3 - работа с базами данных

datetime - работа с датами

random - генерация случайных чисел

time - работа с таймстемпами

json - работа с JSON

uuid - генерация уникальных ID

re - регулярные выражения

html - эскейпинг HTML

math - математические операции

asyncio - асинхронность

🔄 Фоновые задачи
Бот выполняет фоновую задачу для автоматической очистки базы данных:
async def periodic_db_cleaner():
    """Фоновое задание для очистки просроченных инвойсов"""
    while True:
        delete_old_pending_invoices()
        await asyncio.sleep(DB_CLEAN_INTERVAL)
        Интервал: раз в час (настраивается в config.py)

Действие: удаление инвойсов со статусом pending, созданных более 30 минут назад

Запуск: автоматически при старте бота

🐛 Отладка и логирование
Бот использует встроенное логирование Python:
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
Для подавления избыточных логов aiogram:
logging.getLogger("aiogram.event").setLevel(logging.WARNING)
Уровни логирования:

INFO - основная информация

WARNING - предупреждения

ERROR - ошибки
🤝 Внесение вклада
Форкните репозиторий

Создайте ветку для новой функции (git checkout -b feature/amazing-feature)

Зафиксируйте изменения (git commit -m 'Add amazing feature')

Отправьте изменения в ветку (git push origin feature/amazing-feature)

Откройте Pull Request

📄 Лицензия
Этот проект распространяется под лицензией MIT. Подробнее см. в файле LICENSE.

💬 Поддержка
По всем вопросам обращайтесь в Telegram или создавайте Issue в репозитории.

🌟 Благодарности
aiogram - за отличный фреймворк

Telegram - за поддержку Telegram Stars и инвойсов

Всех участников и пользователей бота 🍻

<div align="center"> <sub>Сделано с ❤️ и 🍺</sub> </div> ```