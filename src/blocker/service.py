import time
import wmi
import json
import os
import sys
import threading
import win32serviceutil
import win32service
import win32event
import win32ts
import win32profile
import pythoncom
import servicemanager
import socket
import ctypes
import logging
import logging.handlers
from datetime import datetime
import traceback

def setup_logging():
    """Настройка системы логирования"""
    if ctypes.windll.shell32.IsUserAnAdmin():
        log_dir = os.path.join(os.getenv("ProgramFiles"), "BlockManager", "logs")
    else:
        log_dir = os.path.join(os.path.expanduser("~"), 'AppData', 'Roaming', "BlockManager", "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    logger = logging.getLogger('BlockManager')
    logger.setLevel(logging.DEBUG)
    
    # Лог-файл с ротацией по дням
    log_file = os.path.join(log_dir, f"BlockManager_{datetime.now().strftime('%Y%m%d')}.log")

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

class BlockManagerService(win32serviceutil.ServiceFramework):
    _svc_name_ = "BlockManagerService"
    _svc_display_name_ = "Block Manager Service"
    _svc_description_ = "Manages application blocking based on policies"


    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.running = False
        self.blocker = None
        logger.info("Service initialized")

    def SvcStop(self):
        """Остановка сервиса"""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        logger.info("Service stop requested")
        self.running = False
        if self.blocker:
            self.blocker.stop()
        win32event.SetEvent(self.hWaitStop)
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)
        logger.info("Service stopped successfully")

    def SvcDoRun(self):
        """Основной метод работы сервиса"""
        pythoncom.CoInitialize()  # Инициализация COM для главного потока
        try:
            logger.info(f"Starting {self._svc_display_name_}")
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, '')
            )
            self.running = True
            self.main()
        except Exception as e:
            logger.critical(f"Service failed to start: {str(e)}\n{traceback.format_exc()}")
            raise
        finally:
            pythoncom.CoUninitialize()

    def main(self):
        """Запуск основного функционала"""
        try:
            self.blocker = ProcessBlocker()
            self.blocker.run()
        except Exception as e:
            logger.critical(f"Main service error: {str(e)}\n{traceback.format_exc()}")
            raise


class ProcessBlocker:
    """Класс для блокировки процессов"""
    def __init__(self):
        self.skip_app = ['notification.exe', 'updater.exe', 'blocker.exe', 'uninstaller.exe', 'blockmanager.exe', 'server_response.exe']
        self.running = False
        self.block_mode = None
        self.excluded_users = []
        self.host = None
        self.block_list = []
        self.lock = threading.Lock()
        self.config_path = os.path.join(os.getenv("ProgramFiles"), "BlockManager", "config.json")
        self.static_path = os.path.join(os.getenv("ProgramFiles"), "BlockManager", "static")
        self.exe_path = os.path.join(os.getenv("ProgramFiles"), "BlockManager", "notification.exe")
        self.last_config_check = 0
        self.config_check_interval = 5
        
        # Получаем путь к AppData текущего активного пользователя
        appdata_dir = self.get_user_appdata_path()
        if not appdata_dir:
            # Fallback для случаев, когда не удалось получить путь
            appdata_dir = os.path.join(os.path.expanduser("~"), 'AppData', 'Roaming')
            logger.warning(f"Using fallback AppData path: {appdata_dir}")
        
        self.local_list_path = os.path.join(appdata_dir, "BlockManager", "local.json")
        logger.info(f"User local config path: {self.local_list_path}")
        
        # Инициализируем WMI с правильной COM-инициализацией
        self._init_wmi()
    
    def _init_wmi(self):
        """Потокобезопасная инициализация WMI"""
        pythoncom.CoInitialize()
        try:
            self.c = wmi.WMI()
            self.process_watcher = None
        except Exception as e:
            pythoncom.CoUninitialize()
            raise
    
    def __del__(self):
        """Очистка COM"""
        if hasattr(self, 'c'):
            pythoncom.CoUninitialize()
    
    def show_block_notification(self, process_name):
        """Показ уведомления через отдельный процесс"""
        try:
            cmd = f'"{self.exe_path}" -name="{process_name}"'
            self.run_as_user(cmd)
        except Exception as e:
            logger.error(f"Ошибка показа уведомления: {str(e)}")
            logger.warning(f"Application blocked: {process_name}")

    def run_as_user(self, executable_path):
        import win32process
        import win32con
        import win32api
        """Запускаем программу в сессии пользователя с видимым GUI"""
        try:
            # Находим активную пользовательскую сессию
            session_id = None
            for session in win32ts.WTSEnumerateSessions(win32ts.WTS_CURRENT_SERVER_HANDLE):
                if session['State'] == win32ts.WTSActive and session['SessionId'] != 0:
                    session_id = session['SessionId']
                    break
            
            if session_id is None:
                raise Exception("Активная пользовательская сессия не найдена")

            # Получаем токен пользователя
            h_token = win32ts.WTSQueryUserToken(session_id)
            
            # Создаем окружение пользователя
            env = win32profile.CreateEnvironmentBlock(h_token, False)
            
            # Параметры запуска
            startup_info = win32process.STARTUPINFO()
            startup_info.lpDesktop = "winsta0\\default"  # Для отображения GUI
            
            # Запускаем процесс
            win32process.CreateProcessAsUser(
                h_token,
                None,
                executable_path,
                None,
                None,
                False,
                win32con.NORMAL_PRIORITY_CLASS,
                env,
                None,
                startup_info
            )
            
            win32api.CloseHandle(h_token)
            return True
            
        except Exception as e:
            servicemanager.LogErrorMsg(f"Ошибка запуска от пользователя: {str(e)}")
            return False

    def get_user_appdata_path(self):
        try:
            # Получаем SID активного пользователя консоли
            session_id = win32ts.WTSGetActiveConsoleSessionId()
            user_token = win32ts.WTSQueryUserToken(session_id)
            
            # Получаем переменные среды пользователя
            env = win32profile.CreateEnvironmentBlock(user_token, False)
            return env['APPDATA']
        except Exception as e:
            logger.error(f"Error getting user AppData: {e}")
            return None

    def load_configs(self):
        """Загрузка конфигурационных файлов"""
        try:
            current_time = time.time()
            if current_time - self.last_config_check < self.config_check_interval:
                return
                
            self.last_config_check = current_time
            logger.debug(f"Loading config from {self.config_path}")
            
            # Загрузка глобального конфига
            if not os.path.exists(self.config_path):
                raise FileNotFoundError(f"Config file not found: {self.config_path}")
                
            with open(self.config_path, "r", encoding="utf-8") as file:
                config = json.load(file)
                with self.lock:
                    self.block_mode = config.get("block_mode", "Blacklist")
                    self.excluded_users = [user.lower() for user in config.get("excluded_users", [])]
                    self.host = config.get("host", "")
            
            logger.info(f"Config loaded: mode={self.block_mode}, excluded_users={self.excluded_users}")

            # Загрузка локального списка программ
            logger.info(f"Loading local config from: {self.local_list_path}")
            os.makedirs(os.path.dirname(self.local_list_path), exist_ok=True)

            # Получаем путь к AppData текущего активного пользователя
            appdata_dir = self.get_user_appdata_path()
            if not appdata_dir:
                # Fallback для случаев, когда не удалось получить путь
                appdata_dir = os.path.join(os.path.expanduser("~"), 'AppData', 'Roaming')
                logger.warning(f"Using fallback AppData path: {appdata_dir}")
            
            self.local_list_path = os.path.join(appdata_dir, "BlockManager", "local.json")
            logger.info(f"User local config path: {self.local_list_path}")

            if os.path.exists(self.local_list_path):
                with open(self.local_list_path, "r", encoding="utf-8") as file:
                    local_config = json.load(file)
                    with self.lock:
                        raw_list = local_config.get("local_list_program", [])
                        self.block_list = []
                        for item in raw_list:
                            if isinstance(item, dict):
                                if 'name' in item:
                                    self.block_list.append(item['name'].lower())
                                elif 'path' in item:
                                    self.block_list.append(os.path.basename(item['path']).lower())
                            else:
                                self.block_list.append(str(item).lower())
            else:
                logger.info("Local config file not found, using empty list")
            
            logger.info(f"Current block list: {self.block_list}")

        except json.JSONDecodeError as je:
            logger.error(f"Invalid JSON in config file: {str(je)}\n{traceback.format_exc()}")
            raise
        except PermissionError as pe:
            logger.error(f"Permission denied accessing config files: {str(pe)}\n{traceback.format_exc()}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error loading configs: {str(e)}\n{traceback.format_exc()}")
            raise

    def reload_configs(self):
        """Поток для периодической перезагрузки конфигов"""
        pythoncom.CoInitialize()
        try:
            while self.running:
                time.sleep(self.config_check_interval)
                try:
                    self.load_configs()
                except Exception as e:
                    logger.error(f"Error reloading config: {str(e)}")
        finally:
            pythoncom.CoUninitialize()

    def block_process(self, event):
        """Обработка нового процесса с COM-инициализацией"""
        pythoncom.CoInitialize()
        try:
            process_name = event.Name.lower()

            # Получаем путь к AppData текущего активного пользователя
            appdata_dir = self.get_user_appdata_path()
            if not appdata_dir:
                # Fallback для случаев, когда не удалось получить путь
                appdata_dir = os.path.join(os.path.expanduser("~"), 'AppData', 'Roaming')
                logger.warning(f"Using fallback AppData path: {appdata_dir}")
            
            if appdata_dir.split('\\')[-3] in self.excluded_users:
                return

            if process_name in self.skip_app:
                return
            
            try:
                process_user = event.GetOwner()[0].lower() if event.GetOwner() else ""
            except Exception as e:
                process_user = ""
                logger.warning(f"Could not get process owner for {process_name}: {str(e)}")
            
            # Проверяем, является ли пользователь исключенным
            with self.lock:
                if process_user in self.excluded_users:
                    logger.debug(f"Skipping process {process_name} for excluded user {process_user}")
                    return
                
                if self.block_mode.lower() == 'blacklist':
                    if process_name in self.block_list:
                        self.terminate_process(event.ProcessId, process_name=process_name)
                elif self.block_mode.lower() == 'whitelist':
                    if process_name not in self.block_list:
                        self.terminate_process(event.ProcessId, process_name=process_name)
                
        except Exception as e:
            logger.error(f"Error processing event: {str(e)}")
        finally:
            pythoncom.CoUninitialize()

    def terminate_process(self, process_id, process_name):
        """Завершение процесса"""
        try:
            logger.debug(f"Attempting to terminate {process_name} (PID: {process_id})")
            process_list = self.c.Win32_Process(ProcessId=process_id)
            if process_list:
                process_list[0].Terminate()
                logger.info(f"Successfully blocked process: {process_name} (PID: {process_id})")
                threading.Thread(target=self.show_block_message, args=(process_name,)).start()
            else:
                logger.warning(f"Process {process_name} (PID: {process_id}) not found")
        except Exception as e:
            logger.error(f"Error terminating process {process_name}: {str(e)}\n{traceback.format_exc()}")

    def show_block_message(self, name):
        """Показ сообщения о блокировке"""
        try:
            logger.debug(f"Showing block message for {name}")
            self.show_block_notification(name)
        except Exception as e:
            logger.error(f"Error showing message box: {str(e)}\n{traceback.format_exc()}")

    def stop(self):
        """Остановка мониторинга"""
        self.running = False
        if self.process_watcher:
            self.process_watcher = None
        logger.info("Process monitoring stopped")

    def run(self):
        """Основной цикл мониторинга"""
        # Запускаем поток для обновления конфигурации
        config_thread = threading.Thread(target=self.reload_configs, daemon=True)
        config_thread.start()
        
        pythoncom.CoInitialize()
        try:
            self.load_configs()
            self.running = True
            self.process_watcher = self.c.Win32_Process.watch_for('creation')
            
            while self.running:
                try:
                    # Проверяем конфиг перед обработкой каждого события
                    if time.time() - self.last_config_check >= self.config_check_interval:
                        self.load_configs()
                    
                    event = self.process_watcher()
                    self.block_process(event)
                except wmi.x_wmi_timed_out:
                    continue
                except Exception as e:
                    logger.error(f"Monitoring error: {str(e)}")
        finally:
            pythoncom.CoUninitialize()

if __name__ == '__main__':
    try:
        logger.info("Service starting...")
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(BlockManagerService)
        servicemanager.StartServiceCtrlDispatcher()
    except Exception as e:
        logger.critical(f"Service startup failed: {str(e)}\n{traceback.format_exc()}")
        raise