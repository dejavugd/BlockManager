import time
import json
import os
import sys
import threading
import win32serviceutil
import win32ts
import win32profile
import win32service
import win32event
import pythoncom
import servicemanager
import socket
import ctypes
import logging
import logging.handlers
from datetime import datetime
import traceback
import requests

def setup_logging():
    """Настройка системы логирования"""
    if ctypes.windll.shell32.IsUserAnAdmin():
        log_dir = os.path.join(os.getenv("ProgramFiles"), "BlockManager", "logs")
    else:
        log_dir = os.path.join(os.path.expanduser("~"), 'AppData', 'Roaming', "BlockManager", "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    logger = logging.getLogger('BlockManagerChecker')
    logger.setLevel(logging.DEBUG)
    
    # Лог-файл с ротацией по дням
    log_file = os.path.join(log_dir, f"BlockManager_Checker_{datetime.now().strftime('%Y%m%d')}.log")

    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file, when='midnight', backupCount=7, encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    
    # Формат логов
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    
    # Также дублируем логи в консоль при запуске вручную
    if len(sys.argv) > 1:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger

# Инициализация логгера
logger = setup_logging()

class BlockManagerChecker(win32serviceutil.ServiceFramework):
    _svc_name_ = "BlockManagerChecker"
    _svc_display_name_ = "Block Manager Checker"
    _svc_description_ = "Updates the configuration file from the server"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.stop_event = threading.Event()
        self.blocker = None
        logger.info("Service initialized")

    def SvcStop(self):
        """Остановка сервиса"""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        logger.info("Service stop requested")
        self.stop_event.set()
        win32event.SetEvent(self.hWaitStop)
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)
        logger.info("Service stopped successfully")

    def SvcDoRun(self):
        """Основной метод работы сервиса"""
        pythoncom.CoInitialize()
        try:
            logger.info(f"Starting {self._svc_display_name_}")
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, '')
            )
            self.blocker = CheckJson(self.stop_event)
            self.blocker.run()
        except Exception as e:
            logger.critical(f"Service failed: {str(e)}\n{traceback.format_exc()}")
            raise
        finally:
            pythoncom.CoUninitialize()

class CheckJson:
    def __init__(self, stop_event):
        self.stop_event = stop_event
        self.config_path = os.path.join(os.getenv("ProgramFiles"), "BlockManager", "config.json")
        self.user_check_interval = 10  # Проверять активного пользователя каждые 10 секунд
        self.last_user_check = 0
        self.current_user_appdata = None
        self.lock = threading.Lock()
        self.load_config()
        self.last_update = 0
        self.update_interval = 5  # Интервал обновления в секундах
        logger.info("CheckJson initialized")

    def get_active_user_appdata(self):
        """Получаем AppData активного пользователя"""
        try:
            session_id = win32ts.WTSGetActiveConsoleSessionId()
            if session_id == 0xFFFFFFFF:
                logger.warning("No active console session found")
                return None
                
            user_token = win32ts.WTSQueryUserToken(session_id)
            env = win32profile.CreateEnvironmentBlock(user_token, False)
            return env['APPDATA']
        except Exception as e:
            logger.error(f"Error getting user AppData: {e}")
            return None

    def update_user_path(self):
        """Обновляем путь к AppData текущего пользователя"""
        current_time = time.time()
        if current_time - self.last_user_check < self.user_check_interval:
            return False
            
        new_appdata = self.get_active_user_appdata()
        if new_appdata is None:
            # Используем fallback путь
            new_appdata = os.path.join(os.path.expanduser("~"), 'AppData', 'Roaming')
            logger.warning(f"Using fallback AppData path: {new_appdata}")
            
        if new_appdata != self.current_user_appdata:
            self.current_user_appdata = new_appdata
            self.local_path = os.path.join(new_appdata, 'BlockManager', 'local.json')
            os.makedirs(os.path.dirname(self.local_path), exist_ok=True)
            logger.info(f"Updated user path to: {self.local_path}")
            self.last_user_check = current_time
            return True
            
        self.last_user_check = current_time
        return False

    def load_config(self):
        """Загрузка основного конфига"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.host = config.get('host', 'site.dejavu')
                self.json_file = config.get('json', '312.json')
                logger.info(f"Loaded config - host: {self.host}, json: {self.json_file}")
            
            # Инициализируем путь для текущего пользователя
            self.update_user_path()
        except Exception as e:
            logger.error(f"Config load error: {str(e)}\n{traceback.format_exc()}")
            raise

    def fetch_remote_list(self):
        """Загрузка списка программ с сервера"""
        current_time = time.time()
        if current_time - self.last_update < self.update_interval:
            logger.debug("Too soon for next update, skipping")
            return False
                
        url = f"http://{self.host}:8083/get_json_file?json={self.json_file}"
        logger.info(f"Checking server: {url}")
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # Сначала сохраняем во временный файл
            data = response.json()

            # Изменяем ключ на local_list_program
            if 'app_list' in data:
                data['local_list_program'] = data.pop('app_list')
            
            with open(self.local_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f'Путь к папке: {self.local_path}')

            reload_interval = data.get('reload', None)
            if reload_interval and (reload_interval != self.update_interval):
                self.update_interval = reload_interval
                logger.info(f"Update interval changed to {reload_interval} seconds")
            
            self.last_update = current_time
            logger.info("Remote list updated successfully")
            return True
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Server unavailable: {str(e)}")
        except json.JSONDecodeError:
            logger.error("Invalid JSON response from server")
        except Exception as e:
            logger.error(f"Remote fetch error: {str(e)}\n{traceback.format_exc()}")
            
        return False
    
    def load_local_list(self):
        """Загрузка локального списка программ"""
        try:
            if os.path.exists(self.local_path):
                with open(self.local_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.debug(f"Loaded local data: {len(data.get('local_list_program', []))} items")
                    return data.get('local_list_program', [])
            logger.debug("Local file not found, returning empty list")
            return []
        except Exception as e:
            logger.error(f"Local list load error: {str(e)}\n{traceback.format_exc()}")
            return []

    def run(self):
        """Основной цикл работы"""
        try:
            logger.info(f"Starting main loop with update interval: {self.update_interval} seconds")
            
            while not self.stop_event.is_set():
                start_time = time.time()
                
                # Обновляем путь к пользовательскому AppData при необходимости
                self.update_user_path()
                
                # Пытаемся получить обновленный список с сервера
                if not self.fetch_remote_list():
                    logger.debug("Using cached local list")
                
                # Загружаем актуальный список
                self.block_list = self.load_local_list()
                logger.info(f"Current block list contains {len(self.block_list)} applications")
                
                # Рассчитываем время до следующего обновления
                elapsed = time.time() - start_time
                sleep_time = max(0, min(self.update_interval, self.user_check_interval) - elapsed)
                
                # Ожидаем с возможностью прерывания
                self.stop_event.wait(sleep_time)
                
        except KeyboardInterrupt:
            logger.info("Service stopped by user")
        except Exception as e:
            logger.critical(f"Service crash: {str(e)}\n{traceback.format_exc()}")
            raise
        finally:
            logger.info("Service main loop ended")

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(BlockManagerChecker)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(BlockManagerChecker)