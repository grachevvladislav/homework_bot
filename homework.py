import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import HttpNotFound, NoTokenException

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s, %(levelname)s, %(message)s'
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 60
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправка сообщения в Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception:
        logging.error(f'Сбой при отправке сообщения в Telegram "{message}"')
    else:
        logging.info(f'Сообщение отправлено в Telegram "{message}"')


def get_api_answer(current_timestamp):
    """Получения ответа от Я.Практикума."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
    homework_statuses = requests.get(ENDPOINT,
                                     headers=headers,
                                     params=params
                                     )
    if homework_statuses.status_code != HTTPStatus.OK:
        logging.error('Я.Практикум не доступен!')
        raise HttpNotFound('Я.Практикум не доступен!')
    else:
        json_answer = homework_statuses.json()
    return json_answer


def check_response(response):
    """Проверка ответа Api Я.Практикума."""
    if not isinstance(response, dict):
        logging.error('Тип данных не dict')
        raise TypeError('Тип данных не dict')
    if 'homeworks' not in response:
        logging.error('Отсутствие ключа "homeworks" в ответе API')
        raise KeyError('Отсутствие ключа "homeworks" в ответе API')
    if not isinstance(response['homeworks'], list):
        logging.error('Под ключом "homeworks" в ответе API не список')
        raise KeyError('Под ключом "homeworks" в ответе API не список')
    return response['homeworks']


def parse_status(homework):
    """Парсинг словаря 'homeworks' из ответа Api Я.Практикума."""
    for key_name in ['lesson_name', 'status']:
        if key_name not in homework:
            logging.error(f'Отсутствие ключа {key_name} в ответе API')
            raise KeyError(f'Отсутствие ключа {key_name} в ответе API')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        logging.error('Недокументированный статус домашней работы')
        raise KeyError('Недокументированный статус домашней работы')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка наличия переменных окружения."""
    for a in ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']:
        if eval(a) is None:
            logging.critical(f'Нет обязательной переменной окружения: {a}')
            return False
    return True


def main():
    """Основная логика работы бота."""

    if check_tokens() is False:
        raise NoTokenException('Недоступны необходимые переменные!')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = int(time.time())
            homeworks = check_response(response)
            for homework in homeworks:
                text = parse_status(homework)
                send_message(bot, text)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
