BOTNAME = "Пивной бот"
HELP = (
    '<tg-emoji emoji-id="5402227731972771532">🍺</tg-emoji> <b>Привет! Я ' + BOTNAME + '.</b>\n\n'
    "Команды:\n"
    "/beer — выпить пиво (раз в час).\n"
    "/stats — показать топ алкоголиков этого чата.\n"
    "/buy - купить дополнительные попытки."
)
START_PRIVATE = (
    '<tg-emoji emoji-id="5402227731972771532">🍺</tg-emoji> <b>Привет! Я ' + BOTNAME + '.</b>\n\n'
    "Бот работает только в группах!"
)
PRIVATE_DISABLED = '<tg-emoji emoji-id="5420323339723881652">⚠️</tg-emoji><i> Эта команда недоступна в личных сообщениях. </i>'
DRINK_NEXT = (
    '<i>{name}, ты выпил(а) {liters} л. пива <tg-emoji emoji-id="5264737672684907396">🍻</tg-emoji>. Всего выпито - {total_liters} л.</i>'
    "\n"
    "\n"
    "Следующая попытка через час"
)
COOLDOWN_EARLY = (
    '<i>{name}, повтори через {minutes} мин. {seconds} сек. Выпито всего - {total_liters} л.</i>\n\n'
    'Дополнительные попытки - /buy'
)
EMPTY_LEADERBOARD = '<tg-emoji emoji-id="5264737672684907396">🍻</tg-emoji> Пока никто в этом чате не пил пиво. Используйте /beer первым!'
LEADERBOARD_TITLE = '<b><i><tg-emoji emoji-id="5409008750893734809">🏆</tg-emoji> Топ игроков чата</i></b> (стр. {page}/{pages}):\n'
LEADERBOARD_ROW = "{number}. <i>{name} — <b>{liters} л.</b></i>"
TEXT_INFO = "\n\n<i>Чтобы попасть в этот список, начните игру с помощью команды /beer</i>"
INVALID_PAGE = "Не удалось открыть страницу топа."
PAGINATION_COOLDOWN = "Пожалуйста, подождите {seconds} сек."
TOO_FAST = "Не так быстро!"
RANK_EMOJIS = {
    1: '<tg-emoji emoji-id="5440539497383087970">🥇</tg-emoji>',
    2: '<tg-emoji emoji-id="5447203607294265305">🥈</tg-emoji>',
    3: '<tg-emoji emoji-id="5453902265922376865">🥉</tg-emoji>'
}
BUY_SUCCESS = (
    '<tg-emoji emoji-id="5285000061372091901">✅</tg-emoji> <b>Отлично! Оплата прошла успешно!!</b>(+{attempts})\n\n'
    "{name}, приятной игры!"
)
BUY_MENU = (
    '<tg-emoji emoji-id="5402227731972771532">🍺</tg-emoji> {name}, здесь вы можете приобрести дополнительные игровые попытки (/beer)\n\n'
    "Выберите кол-во попыток:"
)
ADMIN_PANEL = '<tg-emoji emoji-id="5282884789978828715">⚜️</tg-emoji><b> Админ-панель</b>\n\nЗдесь вы можете создать промокод, перенастроить его и удалить'
ADMIN_NO_ACCESS = "Нет доступа"
PROMPT_BEER_AMOUNT = "Введите количество литров пива\n(целое или дробное число, до 2 знаков после точки):"
PROMPT_ATTEMPTS_AMOUNT = "Введите количество дополнительных попыток\n(целое число):"
VALIDATE_NAME_EMPTY = "Название не может быть пустым"
VALIDATE_NAME_TOO_LONG = "Название не должно превышать 16 символов"
VALIDATE_NAME_INVALID_CHARS = "Название должно содержать только латинские буквы и цифры"
VALIDATE_REWARD_EMPTY = "Введите количество"
VALIDATE_BEER_POSITIVE = "Количество пива должно быть положительным числом"
VALIDATE_BEER_DECIMALS = "Допускается не более двух знаков после точки"
VALIDATE_ATTEMPTS_INTEGER = "Количество попыток должно быть целым числом"
VALIDATE_ATTEMPTS_POSITIVE = "Количество попыток должно быть положительным числом"
VALIDATE_REWARD_UNKNOWN = "Неизвестный тип награды"
VALIDATE_REWARD_NUMBER = "Введите корректное число"
VALIDATE_TIME_EMPTY = "Введите дату или длительность"
VALIDATE_TIME_INVALID_DATE = "Некорректная дата"
VALIDATE_TIME_INVALID_FORMAT = "Неверный формат. Используйте ДД.ММ.ГГ или 2h, 3h, 2h5s"
VALIDATE_ACTIVATIONS_EMPTY = "Введите количество активаций"
VALIDATE_ACTIVATIONS_POSITIVE = "Количество активаций должно быть положительным числом"
SAVE_ERROR_EMPTY_FIELDS = "Заполните все обязательные поля"
SAVE_ERROR_DUPLICATE = "Промокод с таким названием уже существует"
UNKNOWN_CALLBACK = "Действие не распознано. Попробуйте снова."
PROMO_ENTER_NAME = "Напишите название промокода на английском без пробелов"
PROMO_REWARD = "Что выдает промокод"
PROMO_TIME_LIMIT = "Этот промокод будет ограничен по времени?"
PROMO_TIME_INPUT = (
    "До какой даты будет доступен промокод\n"
    "или сколько времени он будет действовать\n\n"
    "Формат:\n"
    "ДД.ММ.ГГ\n"
    "или:\n"
    "2h\n"
    "3h\n"
    "2h5s"
)
PROMO_ACTIVATION_LIMIT = "Этот промокод будет ограничен по активациям?"
PROMO_ACTIVATION_AMOUNT = "Введите максимальное количество активаций"
PROMO_BIND_USER = "Привязать к пользователю?"
PROMO_BIND_USER_INPUT = "Введите Telegram user_id пользователей через запятую\nНапример: 123456, 789012"
PROMO_FINAL = '<tg-emoji emoji-id="5255806717689631058">⚜️</tg-emoji><b> Вы создаете промокод - {name}</b>\n\nПроверьте настройки перед сохранением'
PROMO_SAVED = "Промокод успешно создан!"
PROMO_UPDATED = "Настройки промокода успешно изменены!"
PROMO_CANCELLED = "Создание промокода отменено"
PROMO_NAME_SPACE_ERROR = "Название промокода не должно содержать пробелы"
PROMO_NAME_INVALID_ERROR = "Название промокода должно содержать только английские буквы и цифры"
PROMO_NUMBER_ERROR = "Введите целое число"
PROMO_USER_ID_ERROR = "Введите корректный Telegram user_id"
PROMO_SETTINGS_SELECT = "Выберите промокод для настройки"
PROMO_EDIT_TITLE = '<tg-emoji emoji-id="5255806717689631058">⚜️</tg-emoji><b> Вы настраиваете промокод - "{name}"</b>\n\nВыберите параметр для изменения'
PROMO_NO_FOUND = "Промокоды не найдены"
PROMO_DELETE_SELECT = "Выберите промокод для удаления"
PROMO_DELETE_CONFIRM = "Вы уверены что хотите удалить промокод {name}?"
PROMO_DELETE_SECOND_CONFIRM = "Вы точно УВЕРЕНЫ?"
PROMO_DELETED = "Промокод успешно удален"
PROMO_DELETE_CANCELLED = "Удаление промокода отменено"

PROMO_ALREADY_USED = '<tg-emoji emoji-id="5420323339723881652">⚠️</tg-emoji><i> Вы уже активировали этот промокод....</i>'
PROMO_NOT_VALID = '<tg-emoji emoji-id="5420323339723881652">⚠️</tg-emoji><i> Промокод больше не действителен</i>'
PROMO_USER_ONLY = '<tg-emoji emoji-id="5420323339723881652">⚠️</tg-emoji><i> Этот промокод доступен только другому пользователю</i>'
PROMO_ACTIVATED = '<tg-emoji emoji-id="5235711785482341993">🎉</tg-emoji><b> Промокод успешно активирован!</b>'

PROMO_PAGE = "{current}/{total}"
REWARD_BEER = "Пиво"
REWARD_ATTEMPTS = "Доп. попытки"
VALIDATE_TIME_PAST_DATE = "Дата не может быть раньше сегодняшнего дня"
PROMO_USAGE = '<tg-emoji emoji-id="5420323339723881652">⚠️</tg-emoji> <b>Вы не указали промокод!</b>\n\n>Используйте: /promo ПРОМОКОД'
PROMO_NOT_FOUND = '<tg-emoji emoji-id="5420323339723881652">⚠️</tg-emoji><i> Промокод не найден</i>'