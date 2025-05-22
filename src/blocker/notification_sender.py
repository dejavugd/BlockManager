import sys
import os
import ctypes
import logging
from argparse import ArgumentParser
from datetime import datetime

def setup_logging():
    """Настройка системы логирования"""
    if ctypes.windll.shell32.IsUserAnAdmin():
        log_dir = os.path.join(os.getenv("ProgramFiles"), "BlockManager", "logs")
    else:
        log_dir = os.path.join(os.path.expanduser("~"), 'AppData', 'Roaming', "BlockManager", "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    logger = logging.getLogger('NotificationSender')
    logger.setLevel(logging.DEBUG)
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    file_handler = logging.FileHandler(
        os.path.join(log_dir, f"notifications_{datetime.now().strftime('%Y%m%d')}.log"),
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

def show_notification(process_name):
    """Показать уведомление через WinAPI"""
    try:
        ctypes.windll.user32.MessageBoxW(
            0,
            f"Приложение заблокировано администратором:\n{process_name}",
            "BlockManager",
            0x40  # MB_ICONINFORMATION
        )
    except Exception as e:
        raise Exception(f"Ошибка уведомления: {str(e)}")

if __name__ == "__main__":
    logger = setup_logging()
    try:
        parser = ArgumentParser()
        parser.add_argument('-name', required=True, help='Имя процесса')
        args = parser.parse_args()
        
        logger.info(f"Попытка показать уведомление для: {args.name}")
        show_notification(args.name)
        logger.info("Уведомление успешно отправлено")
    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        sys.exit(1)