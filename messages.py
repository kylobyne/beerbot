HELP = (
    '<tg-emoji emoji-id="5402227731972771532">🍺</tg-emoji> <b>Привет! Я Пивной бот.</b>\n\n'
    "\n"
    "Команды:\n"
    "/beer — выпить пиво (раз в час).\n"
    "/stats — показать топ алкоголиков этого чата."
)

# Текст приветствия при `/start` в личных сообщениях — замените на свой
START_PRIVATE = (
    '<tg-emoji emoji-id="5402227731972771532">🍺</tg-emoji> <b>Привет! Я Пивной бот.</b>\n\n'
    "Бот работает только в группах!"
)

# Сообщение при попытке использовать некоторые команды в личных сообщениях
PRIVATE_DISABLED = '<tg-emoji emoji-id="5420323339723881652">⚠️</tg-emoji><i> Эта команда недоступна в личных сообщениях. </i>'

DRINK_NEXT = (
    '<i>{name}, ты выпил(а) {liters} л. пива <tg-emoji emoji-id="5264737672684907396">🍻</tg-emoji>. Всего выпито - {total_liters} л.</i>'
    "\n"
    "\n"
    "Следующая попытка через час"
)

COOLDOWN_EARLY = '<i>{name}, повтори через {minutes} мин. {seconds} сек. Выпито всего - {total_liters} л.</i>'

EMPTY_LEADERBOARD = '<tg-emoji emoji-id="5264737672684907396">🍻</tg-emoji> Пока никто в этом чате не пил пиво. Используйте /beer первым!'

LEADERBOARD_TITLE = '<b><i><tg-emoji emoji-id="5409008750893734809">🏆</tg-emoji> Топ игроков чата — страница</i></b> ({page}/{pages}):\n'
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
