import logging
import os
import time
from http import HTTPStatus

import requests
from telegram import Bot, TelegramError
from dotenv import load_dotenv
from json.decoder import JSONDecodeError

import exceptions

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s, %(levelname)s, %(message)s'
)

logger = logging.getLogger(__name__)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

LAST_ERROR_MESSAGE = ''
RETRY_TIME = 600
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
    except TelegramError:
        logger.error(f'Сбой при отправке сообщения в Telegram "{message}"')
    else:
        logger.info(f'Сообщение отправлено в Telegram "{message}"')


def get_api_answer(current_timestamp):
    """Получения ответа от Я.Практикума."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
    try:
        homework_statuses = requests.get(ENDPOINT, headers=headers,
                                         params=params, timeout=5
                                         )
        if homework_statuses.status_code != HTTPStatus.OK:
            raise exceptions.StatusCodeError
        json_answer = homework_statuses.json()
    except requests.Timeout:
        logger.error('Timeout Я.Практикум!')
        raise exceptions.HttpTimeOut('Timeout Я.Практикум!')
    except requests.ConnectionError:
        logger.error('Я.Практикум не доступен!')
        raise exceptions.HttpNotFound('Я.Практикум не доступен!')
    except exceptions.StatusCodeError:
        logger.error('Я.Практикум не доступен!')
        raise exceptions.HttpNotFound('Я.Практикум не доступен!')
    except JSONDecodeError:
        logger.error('Ошибка преобразования JSON!')
        raise ValueError('Ошибка преобразования JSON!')
    return json_answer


def check_response(response):
    """Проверка ответа Api Я.Практикума."""
    if not isinstance(response, dict):
        logger.error('Тип данных не dict')
        raise TypeError('Тип данных не dict')
    if 'homeworks' not in response:
        logger.error('Отсутствие ключа "homeworks" в ответе API')
        raise KeyError('Отсутствие ключа "homeworks" в ответе API')
    if not isinstance(response['homeworks'], list):
        logger.error('Под ключом "homeworks" в ответе API не список')
        raise KeyError('Под ключом "homeworks" в ответе API не список')
    return response['homeworks']


def parse_status(homework):
    """Парсинг словаря 'homeworks' из ответа Api Я.Практикума."""
    for key_name in ['lesson_name', 'status']:
        if key_name not in homework:
            logger.error(f'Отсутствие ключа {key_name} в ответе API')
            raise KeyError(f'Отсутствие ключа {key_name} в ответе API')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        logger.error('Недокументированный статус домашней работы')
        raise KeyError('Недокументированный статус домашней работы')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка наличия переменных окружения."""
    for env_var in ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']:
        if eval(env_var) is None:
            logger.critical(f'Нет обязательной переменной окружения:'
                            f' {env_var}')
            return False
    return True


def main():
    """Основная логика работы бота."""
    global LAST_ERROR_MESSAGE
    if not check_tokens():
        raise exceptions.NoTokenException('Недоступны необходимые переменные!')
    inst_bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = int(time.time())
            homeworks = check_response(response)
            for homework in homeworks:
                text = parse_status(homework)
                send_message(inst_bot, text)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if LAST_ERROR_MESSAGE != message:
                send_message(inst_bot, message)
            LAST_ERROR_MESSAGE = message
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
