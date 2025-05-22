from typing import Tuple
import customtkinter as ctk
from PIL import Image
import pkg_resources
import os, pywinstyles, threading, json
import tkinter as tk
import win32net
from win32com import client
from tkinter import messagebox
import ctypes
import win32serviceutil
import win32service
import sys, logging
import logging.handlers
from TkinterDnD import DND_FILES, DnDWrapper, _require
import subprocess
from datetime import datetime

# Мои библиотеки
from .imager import invert_image
from .web import HttpJsonFetcher

# Глобальные переменные
SYSTEM_ACCOUNTS = {
    'Administrator': 'Администратор',
    'Guest': 'Гость',
    'DefaultAccount': 'Учетная запись по умолчанию',
    'WDAGUtilityAccount': 'Учетная запись WDAG',
    'Администратор': 'Администратор',
    'Гость': 'Гость',
}


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

class BlockManagerGUI(ctk.CTk, DnDWrapper):
    def __init__(self, fg_color: str | Tuple[str, str] | None = None, **kwargs):
        super().__init__(fg_color, **kwargs)

        # Иницилизация logger
        self.logger = setup_logging()
        
        # DnD
        self.TkdndVersion = _require(self)
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', lambda e: self._get_path(event=e))

        # Быстрый доступ к файлам
        self.static_folder = pkg_resources.resource_filename(__name__, f'static')

        # Главные параметры
        self.center_height = (self.winfo_screenheight() // 2) - (720 // 2)
        self.center_width = (self.winfo_screenwidth() // 2) - (1280 // 2)
        self.title('BlockManager')
        self.geometry('1280x720+{}+{}'.format(self.center_width, self.center_height))
        self.resizable(False, False)
        self.iconbitmap(f'{self.static_folder}\\icon\\favicon.ico')

        # Загрузка GUI
        self.loading_frame = None
        self.loading_angle = 0
        self.loading_animation_id = None

        # tooltip
        self.tooltip_window = None

        # Combobox
        self.combobox_window = None

        # Инициализация путей
        self.config_path = os.path.join(os.environ['ProgramFiles'], 'BlockManager', 'config.json')
        self.local_admin_path = os.path.join(os.environ['ProgramFiles'], 'BlockManager', 'local.json')
        self.local_path = os.path.join(self.get_appdata_path(), 'local.json')
        self.main_dir = os.path.join(os.path.dirname(sys.executable))

        # Переменные
        self.block_mode = "Блокировка отключена"
        self.excluded_users = []
        self.local_list_program = []
        self.server_status = False
        self.host = ''
        # Загрузка настроек
        self.load_settings()

        # Меню
        self.menu_frame = ctk.CTkFrame(self, corner_radius=0, width=340, fg_color='#121212')
        self.menu_frame.pack(side='left', fill='y', expand=True, anchor='w')
        self.menu_frame.pack_propagate(False)

        favicon_data = Image.open(f'{self.static_folder}\\icon\\favicon.ico')
        favicon = ctk.CTkImage(favicon_data, size=(35, 35))
        self.app_name = ctk.CTkLabel(self.menu_frame, text='BlockManager', compound='left', font=('Arial', 22), text_color='#D9B6E0', padx=5, image=favicon)
        self.app_name.pack(anchor=tk.CENTER, pady=(20, 10))

        ## Панель пользователя
        self.frame = ctk.CTkFrame(self.menu_frame, corner_radius=0, height=50, fg_color='#1E1E2F')
        self.frame.pack(fill='x', anchor='w', pady=(10, 10), padx=(10, 10))
        self.frame.pack_propagate(False)

        user_data = Image.open(f'{self.static_folder}\\png\\user.png')
        user_image = ctk.CTkImage(user_data, size=(25, 25))
        # self.user = ctk.CTkLabel(self.frame, text='', compound='left', image=user_image, font=('Arial', 18), text_color='#D9B6E0', padx=5)
        # self.user.pack(side='left', pady=(10, 10), padx=10)
 
        self.name = ctk.CTkLabel(self.frame, text="Anonymaus", compound='left', width=360, font=('Arial', 18), text_color='#D9B6E0', padx=10, image=user_image, pady=10, justify='left', anchor='w')
        self.name.pack(side='right', pady=(10, 10), padx=5)
 
        # self.name = ctk.CTkLabel(self.frame, text="Anonymaus", compound='left', font=('Arial', 18), text_color='#D9B6E0')
        # self.name.pack(side='right', pady=(10, 10), padx=10)

        ## Элементы меню
        self._create_menu_items(self.menu_frame)

        # Основной фрейм
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, width=940, fg_color='#1A1A2E')
        self.main_frame.pack(side='right', fill='both', expand=True)
        self.main_frame.pack_propagate(False)

        self._block_ui()

    # def test(self, host="site.dejavu"):
    #     fetcher = HttpJsonFetcher(base_url=f"http://{host}:8083")
    #     data = fetcher.get_json_list()
    #     if data:
    #         self.block_apply()
    #         print("Получены данные:", data)
    #     else:
    #         print("Не удалось получить данные")

    def is_admin(self):
        """Проверяет, запущена ли программа с правами администратора"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    def load_settings(self):
        """Загрузка настроек из файлов"""
        try:
            # Загрузка config.json
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.block_mode = config.get('block_mode', 'Блокировка отключена')
                    self.excluded_users = config.get('excluded_users', [])
            
            # Загрузка local.json
            if os.path.exists(self.local_path):
                with open(self.local_path, 'r', encoding='utf-8') as f:
                    local = json.load(f)
                    self.local_list_program = local.get('local_list_program', [])
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка загрузки настроек: {str(e)}")

    def save_config(self, c=None):
        """Сохранение системных настроек (только для администратора)"""
        if not self.is_admin():
            messagebox.showerror("Ошибка", "Требуются права администратора!")
            return False
        
        try:
            if isinstance(self.server_entry, ctk.CTkEntry):
                self.server_host = self.server_entry.get()
            else:
                self.server_host = None
        except:
            self.server_host = None
            
        config = {
            'host': self.server_host,
            'config': c,
            'block_mode': self.block_mode,
            'excluded_users': self.excluded_users
        }
        
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
            return True
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка сохранения конфига: {str(e)}")
            return False

    def save_local(self):
        """Сохранение пользовательских настроек"""
        local = {
            'local_list_program': self.local_list_program
        }
        print("admin")
        print(self.local_path)
        if ctypes.windll.shell32.IsUserAnAdmin():
            try:
                with open(self.local_admin_path, 'w', encoding='utf-8') as f:
                    json.dump(local, f, indent=4)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Ошибка сохранения списка: {str(e)}")
                return False
        print("appdata")
        try:
            print(self.local_path)
            with open(self.local_path, 'w', encoding='utf-8') as f:
                json.dump(local, f, indent=4)
            return True
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка сохранения списка: {str(e)}")
            return False

    # Созданиие меню 
    def _create_menu_items(self, frame):
        # Блокировка приложений
        block_data = Image.open(f'{self.static_folder}\\png\\block.png')
        block = ctk.CTkImage(block_data, size=(25, 25))
        self.block_menu = ctk.CTkLabel(frame, text="Контроль приложений", compound='left', width=360, font=('Arial', 18), text_color='#D9B6E0', padx=10, image=block, fg_color='#1E1E2F', corner_radius=5, pady=10, justify='left', anchor='w')
        self.block_menu.pack(anchor='w', padx=10, pady=(20, 5))
        self.block_menu.bind('<Button-1>', self._block_ui)
        self._add_tooltip(self.block_menu, text="Управление блокировкой приложений")

        # Твики системы
        twiks_data = Image.open(f'{self.static_folder}\\png\\twiks.png')
        twiks = ctk.CTkImage(twiks_data, size=(25, 25))
        self.twiks_menu = ctk.CTkLabel(frame, text="Твики системы", compound='left', width=360, font=('Arial', 18), text_color='#D9B6E0', padx=10, image=twiks, fg_color='#1E1E2F', corner_radius=5, pady=10, justify='left', anchor='w')
        self.twiks_menu.pack(anchor='w', padx=10, pady=5)
        # self.twiks_menu.bind('<Button-1>', self.twiks_ui)
        # self._add_tooltip(self.twiks_menu, text="Системные твики и оптимизация")

        # Серверные настройки
        server_data = Image.open(f'{self.static_folder}\\png\\server.png')
        server = ctk.CTkImage(server_data, size=(25, 25))
        self.server_menu = ctk.CTkLabel(frame, text="Настройки сервера", compound='left', width=360, font=('Arial', 18), text_color='#D9B6E0', padx=10, image=server, fg_color='#1E1E2F', corner_radius=5, pady=10, justify='left', anchor='w')
        self.server_menu.pack(anchor='w', padx=10, pady=5)
        self.server_menu.bind('<Button-1>', self._server_ui)
        self._add_tooltip(self.server_menu, text="Управление серверными настройками")

        # Настройки
        setting_data = Image.open(f'{self.static_folder}\\png\\setting.png')
        setting = ctk.CTkImage(setting_data, size=(25, 25))
        self.setting_menu = ctk.CTkLabel(frame, text="Дополнительные функции", compound='left', width=360, font=('Arial', 18), text_color='#D9B6E0', padx=10, image=setting, fg_color='#1E1E2F', corner_radius=5, pady=10, justify='left', anchor='w')
        # self.setting_menu.pack(anchor='w', padx=10, pady=5)
        # self._add_tooltip(self.setting_menu, text="Настройка прокси, установка сертификатов")

        # Настройки
        exit_data = Image.open(f'{self.static_folder}\\png\\exit.png')
        exit = ctk.CTkImage(exit_data, size=(25, 25))
        self.exit_menu = ctk.CTkLabel(frame, text="Выход", compound='left', width=360, font=('Arial', 18), text_color='#D9B6E0', padx=10, image=exit, fg_color='#1E1E2F', corner_radius=5, pady=10, justify='left', anchor='w')
        self.exit_menu.pack(anchor='w', padx=10, pady=5)
        self.exit_menu.bind('<Button-1>', lambda e: sys.exit(0))
        self._add_tooltip(self.exit_menu, text="Закрыть программу")

        # Футер
        footer_frame = ctk.CTkFrame(frame, corner_radius=8, border_width=1, width=360, height=40, border_color="#5f4a63", fg_color="transparent")
        footer_frame.pack(side='bottom', pady=(0, 10), padx=10, anchor='w')
        footer_frame.pack_propagate(False)
        self.footer = ctk.CTkLabel(footer_frame, text="Разработал: DEJAVU", compound='left', font=('Arial', 11), text_color='#5f4a63')
        self.footer.pack(padx=12, pady=6)

    # Получения данных
    def get_appdata_path(self):
        appdata_dir = os.getenv('APPDATA')  # Получаем путь к AppData
        app_dir = os.path.join(appdata_dir, 'BlockManager')  # Создаем подпапку для приложения
        os.makedirs(app_dir, exist_ok=True)  # Создаем папку, если она не существует
        return app_dir
    
    def get_windows_users(self):
        try:
            users, _, _ = win32net.NetUserEnum(None, 0)
            return [user['name'] for user in users if user['name'] not in SYSTEM_ACCOUNTS]
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка получения пользователей: {e}")
            return []
        
    # Блокировка приложений UI
    def _block_ui(self, event=None):
        for widget in self.main_frame.winfo_children():
            try:
                widget.destroy()
            except:
                continue

        self.show_loading(self.main_frame)
        
        def load_content():
            import time
            time.sleep(1)
            
            self.server_status = False

            content_frame = ctk.CTkFrame(self.main_frame, corner_radius=8, fg_color='transparent', border_color="#5f4a63", border_width=1)
            content_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER, relwidth=0.9, relheight=0.9)

            # Левый контейнер
            left_container = ctk.CTkFrame(content_frame, fg_color='transparent')
            left_container.pack(side='left', fill='y', padx=10, pady=10)

            # Поиск и очистка
            search_frame = ctk.CTkFrame(left_container, fg_color='transparent')
            search_frame.pack(fill='x', pady=5)
            
            search_entry = ctk.CTkEntry(search_frame, border_color='#5f4a63', 
                                    fg_color='transparent', width=180, border_width=2)
            search_entry.pack(side='left', padx=5)

            clear_img = ctk.CTkImage(Image.open(f'{self.static_folder}\\png\\clear.png'), size=(25, 25))
            clear_btn = ctk.CTkLabel(search_frame, image=clear_img, text='')
            clear_btn.pack(side='right', padx=5)
            self._add_tooltip(clear_btn, text="Очистить список программ")

            reload_img = ctk.CTkImage(Image.open(f'{self.static_folder}\\png\\reload.png'), size=(25, 25))
            reload_btn = ctk.CTkLabel(search_frame, image=reload_img, text='')
            reload_btn.pack(side='right', padx=5)
            reload_btn.bind('<Button-1>', lambda e: self._update_program_list_display())  # Добавлено обновление по клику
            self._add_tooltip(reload_btn, text="Обновить список")

            # Список программ (изначально пустой)
            self.scrollable_frame = ctk.CTkScrollableFrame(left_container, label_text='Список программ', width=250, height=400, fg_color='#121212')
            self.scrollable_frame.pack(fill='both', expand=True, pady=5)
            
            # Инициализация пустого списка
            self._update_program_list_display()

            # Правый контейнер
            right_container = ctk.CTkFrame(content_frame, fg_color='transparent')
            right_container.pack(side='right', fill='both', expand=True, padx=10, pady=10)

            # Кнопки действий
            action_frame = ctk.CTkFrame(right_container, fg_color='transparent')
            action_frame.pack(fill='x', pady=10)
            
            import_img = ctk.CTkImage(Image.open(invert_image(f'{self.static_folder}\\png\\import.png')), size=(30, 30))
            import_btn = ctk.CTkLabel(action_frame, image=import_img, text='')
            import_btn.pack(side='left', padx=20)
            # import_btn.bind('<Button-1>', self.import_list)
            self._add_tooltip(import_btn, "Импортировать список программ")

            export_img = ctk.CTkImage(Image.open(invert_image(f'{self.static_folder}\\png\\export.png')), size=(30, 30))
            export_btn = ctk.CTkLabel(action_frame, image=export_img, text='')
            export_btn.pack(side='left', padx=20)
            # export_btn.bind('<Button-1>', self.export_list)
            self._add_tooltip(export_btn, "Экспортировать список программ")

            apply_img = ctk.CTkImage(Image.open(f'{self.static_folder}\\png\\apply.png'), size=(30, 30))
            apply_btn = ctk.CTkLabel(action_frame, image=apply_img, text='')
            apply_btn.pack(side='right', padx=20)
            apply_btn.bind('<Button-1>', lambda e: self.block_apply())
            self._add_tooltip(apply_btn, "Применить настройки")

            # Выбор режима блокировки
            block_list = ['Блокировка отключена', 'Blacklist', 'Whitelist']
            self.combobox_block = ctk.CTkButton(right_container, text=block_list[0], anchor='w', width=300, font=('Arial', 14), fg_color='#4a1aa2', hover_color='#6235ad')
            self.combobox_block.pack_propagate(0)
            self.combobox_block.pack(padx=0, pady=10, fill='x')
            self.combobox_block.bind('<Button-1>', lambda event, widget=self.combobox_block, text=block_list: self.show_combobox(widget=widget, event=event, text=text, y_plus=35, x_plus=0))
            self.combobox_block.configure(text=f'{self.block_mode}')

            combobox_select_data = ctk.CTkImage(Image.open(f'{self.static_folder}\\png\\down.png'), size=(15, 15))
            combobox_select = ctk.CTkLabel(self.combobox_block, text='', image=combobox_select_data, bg_color='#000001')
            combobox_select.pack(side='right', padx=(0, 10))
            pywinstyles.set_opacity(combobox_select, color='#000001')

            # Список пользователей
            self.scrollable_user = ctk.CTkScrollableFrame(right_container, label_text='Список пользователей', height=300, fg_color='#121212')
            self.scrollable_user.pack(fill='both', expand=True, pady=10)

            users = self.get_windows_users()
            self.user_checkboxes = []
            for user in users:
                var = ctk.BooleanVar(value=user in self.excluded_users)
                cb = ctk.CTkCheckBox(self.scrollable_user, text=user, variable=var, 
                                   text_color='white', font=('Arial', 14),
                                   command=lambda u=user, v=var: self.update_excluded_users(u, v))
                cb.pack(anchor='w', padx=10, pady=2)
                self.user_checkboxes.append((user, var))

            # Скрыть индикатор загрузки только после полной загрузки контента
            self.hide_loading()

        loading = threading.Thread(target=load_content, daemon=True)
        loading.start()

    def update_excluded_users(self, user, var):
        """Обновление списка исключенных пользователей"""
        if var.get():
            if user not in self.excluded_users:
                self.excluded_users.append(user)
        else:
            if user in self.excluded_users:
                self.excluded_users.remove(user)
        
        # Автосохранение настроек
        if self.is_admin():
            self.save_config()
        else:
            messagebox.showwarning("Предупреждение", "Изменения для системных настроек не сохранены!\nТребуются права администратора")

    def swap_text(self, widget, text):
        widget.configure(text=text)
        self.block_mode = text
        if self.combobox_window != None:
            self.combobox_window.destroy()
            self.combobox_window = None
        
        # Автосохранение настроек
        if self.is_admin():
            self.save_config()
        else:
            messagebox.showwarning("Предупреждение", "Изменения режима блокировки не сохранены!\nТребуются права администратора")

    # Блокировка приложений
    def block_apply(self, c=None):
        """Применение настроек блокировки и добавление в автозагрузку"""
        results = {
            'config': False,
            'local': False,
            'autostart': False,
            'server': False,
            'updater': False
        }
        messages = []

        try:
            status = self.save_config(c)
            results['config'] = status
            messages.append(f"Конфигурация: {'успешно сохранена' if status else 'ошибка сохранения'}")
        except Exception as e:
            messages.append(f"Конфигурация: ошибка ({str(e)})")

        try:
            status = self.save_local()
            results['local'] = status
            messages.append(f"Локальные настройки: {'успешно сохранены' if status else 'ошибка сохранения'}")
        except Exception as e:
            messages.append(f"Локальные настройки: ошибка ({str(e)})")

        # Добавляем сервис в автозагрузку
        try:
            status = self.add_to_autostart()
            results['autostart'] = status
            messages.append(f"Автозагрузка: {'успешно добавлена' if status else 'ошибка добавления'}")
        except Exception as e:
            messages.append(f"Автозагрузка: ошибка ({str(e)})")

        # Добавляем сервис в автозагрузку обращения к серверу
        if self.server_status:
            try:
                status = self.add_to_autostart_server()
                results['server'] = status
                messages.append(f"Серверная автозагрузка: {'успешно добавлена' if status else 'ошибка добавления'}")
            except Exception as e:
                messages.append(f"Серверная автозагрузка: ошибка ({str(e)})")
        else:
            messages.append("Серверная автозагрузка: отключена")

        # Формируем итоговое сообщение
        success_count = sum(results.values())
        total_operations = len(results)
        
        summary = (
            f"Выполнено операций: {success_count} из {total_operations}\n\n"
            "Детальный отчет:\n" + 
            "\n".join(f"• {msg}" for msg in messages) +
            "\n\nПрограмма готова к работе!"
        )

        if success_count == total_operations:
            title = "Все операции выполнены успешно!"
        elif success_count > total_operations / 2:
            title = "Большинство операций выполнено"
        else:
            title = "Выполнены не все операции"

        messagebox.showinfo(title, summary)

    def add_to_autostart(self):
        """Альтернативный способ через subprocess"""
        try:
            # Запускаем от имени администратора
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            # Проверяем существует ли сервис
            try:
                subprocess.run(['sc', 'query', 'BlockManagerService'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                # Если сервис существует, удаляем его
                subprocess.run(['sc', 'delete', 'BlockManagerService'], check=True, startupinfo=startupinfo)
                print("Сервис успешно удален.")
            except subprocess.CalledProcessError as e:
                print(f"Ошибка при удалении сервиса: {e}")

            exe_path = os.path.join(self.main_dir, "blocker.exe")
            # exe_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "blocker.exe"))
            if not os.path.exists(exe_path):
                print(f"Ошибка: Файл {exe_path} не найден")
                return False
            
            try:                
                subprocess.run(['sc', 'create', 'BlockManagerService', f'binPath="{exe_path}"', 'DisplayName="Block Manager Service"', 'start=auto', 'type=own'], shell=True)
                
                subprocess.run(['sc', 'start', 'BlockManagerService'], shell=True)

                print("Сервис успешно установлен")
                return True
                
            except Exception as e:
                print(f"Ошибка установки: {str(e)}")
                return False
        except Exception as e:
            print(f"Ошибка установки: {str(e)}")
            return False
        
    def add_to_autostart_server(self):
        """Альтернативный способ через subprocess"""
        try:
            # Запускаем от имени администратора
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            # Проверяем существует ли сервис
            try:
                subprocess.run(['sc', 'query', 'BlockManagerChecker'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                # Если сервис существует, удаляем его
                subprocess.run(['sc', 'delete', 'BlockManagerChecker'], check=True, startupinfo=startupinfo)
                print("Сервис успешно удален.")
            except subprocess.CalledProcessError as e:
                print(f"Ошибка при удалении сервиса: {e}")

            exe_path = os.path.join(self.main_dir, "server_response.exe")
            # exe_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "blocker.exe"))
            if not os.path.exists(exe_path):
                print(f"Ошибка: Файл {exe_path} не найден")
                return False
            
            try:                
                subprocess.run(['sc', 'create', 'BlockManagerChecker', f'binPath="{exe_path}"', 'DisplayName="Block Manager Checker"', 'start=auto', 'type=own'], shell=True)
                
                subprocess.run(['sc', 'start', 'BlockManagerChecker'], shell=True)

                print("Сервис успешно установлен")
                return True
                
            except Exception as e:
                print(f"Ошибка установки: {str(e)}")
                return False
        except Exception as e:
            print(f"Ошибка установки: {str(e)}")
            return False

    def _server_ui(self, event=None):
        for widget in self.main_frame.winfo_children():
            try:
                widget.destroy()
            except:
                continue
        
        self.show_loading(self.main_frame)
        
        def load_content():
            import time
            time.sleep(1)

            self.server_status = True
            
            content_frame = ctk.CTkFrame(self.main_frame, corner_radius=8, fg_color='transparent', border_color="#5f4a63", border_width=1)
            content_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER, relwidth=0.9, relheight=0.9)

            # Левый контейнер
            left_container = ctk.CTkFrame(content_frame, fg_color='transparent')
            left_container.pack(side='left', fill='y', padx=10, pady=10)

            # Заголовок и поле ввода сервера
            server_frame = ctk.CTkFrame(left_container, fg_color='transparent')
            server_frame.pack(fill='x', pady=5)
            
            server_label = ctk.CTkLabel(server_frame, text="Адрес сервера:", font=('Arial', 14), text_color='white')
            server_label.pack(anchor='w', pady=5)
            
            self.server_entry = ctk.CTkEntry(server_frame, border_color='#5f4a63', 
                                    fg_color='transparent', width=250, border_width=2,
                                    placeholder_text="example.com или 192.168.1.100")
            self.server_entry.pack(fill='x', pady=5)
            
            # Кнопки управления сервером
            button_frame = ctk.CTkFrame(left_container, fg_color='transparent')
            button_frame.pack(fill='x', pady=10)
            
            scan_btn = ctk.CTkButton(button_frame, text="Сканировать сеть", width=120,
                                command=self.scan_network, font=('Arial', 14), fg_color='#4a1aa2', hover_color='#6235ad')
            scan_btn.pack(side='left', padx=5)
            self._add_tooltip(scan_btn, "Сканировать локальную сеть для поиска сервера")
            
            test_btn = ctk.CTkButton(button_frame, text="Проверить", width=120,
                                command=self.test_server_connection, font=('Arial', 14), fg_color='#4a1aa2', hover_color='#6235ad')
            test_btn.pack(side='left', padx=5)
            self._add_tooltip(test_btn, "Проверить подключение к серверу")
            
            # Результаты сканирования
            scan_results_frame = ctk.CTkFrame(left_container, fg_color='transparent')
            scan_results_frame.pack(fill='both', expand=True, pady=10)
            
            self.scan_results = ctk.CTkScrollableFrame(scan_results_frame, label_text='Найденные серверы', 
                                                    height=200, fg_color='#121212')
            self.scan_results.pack(fill='both', expand=True)
            
            # Правый контейнер
            right_container = ctk.CTkFrame(content_frame, fg_color='transparent')
            right_container.pack(side='right', fill='both', expand=True, padx=10, pady=10)

            # Настройки сервера
            settings_frame = ctk.CTkFrame(right_container, fg_color='transparent')
            settings_frame.pack(fill='x', pady=10)
            
            # Выбор режима блокировки
            block_list = ['Блокировка отключена', 'Blacklist', 'Whitelist']
            self.combobox_block = ctk.CTkButton(settings_frame, text=block_list[0], anchor='w', width=300, font=('Arial', 14), fg_color='#4a1aa2', hover_color='#6235ad')
            self.combobox_block.pack_propagate(0)
            self.combobox_block.pack(padx=0, pady=10, fill='x')
            self.combobox_block.bind('<Button-1>', lambda event, widget=self.combobox_block, text=block_list: self.show_combobox(widget=widget, event=event, text=text, y_plus=35, x_plus=0))
            self.combobox_block.configure(text=f'{self.block_mode}')

            combobox_select_data = ctk.CTkImage(Image.open(f'{self.static_folder}\\png\\down.png'), size=(15, 15))
            combobox_select = ctk.CTkLabel(self.combobox_block, text='', image=combobox_select_data, bg_color='#000001')
            combobox_select.pack(side='right', padx=(0, 10))
            pywinstyles.set_opacity(combobox_select, color='#000001')
            
            # Список пользователей для исключения (такой же как в _block_ui)
            user_frame = ctk.CTkFrame(right_container, fg_color='transparent')
            user_frame.pack(fill='both', expand=True, pady=10)
            
            user_label = ctk.CTkLabel(user_frame, text="Исключить пользователей:", 
                                    font=('Arial', 14), text_color='white')
            user_label.pack(anchor='w', pady=(0, 5))
            
            # Создаем ScrollableFrame для чекбоксов пользователей
            self.user_scroll_frame = ctk.CTkScrollableFrame(user_frame, fg_color='#121212', height=150)
            self.user_scroll_frame.pack(fill='both', expand=True)
            
            # Добавляем чекбоксы пользователей
            users = self.get_windows_users()
            self.server_user_checkboxes = []
            
            for user in users:
                frame = ctk.CTkFrame(self.user_scroll_frame, fg_color='#121212', height=30)
                frame.pack(fill='x', pady=2)
                
                var = ctk.BooleanVar(value=user in self.excluded_users)
                cb = ctk.CTkCheckBox(frame, text=user, variable=var, 
                                text_color='white', font=('Arial', 12),
                                command=lambda u=user, v=var: self.update_excluded_users(u, v))
                cb.pack(side='left', padx=5, pady=2)
                
                self.server_user_checkboxes.append((user, var))
                
            # Список конфигураций с сервера
            config_frame = ctk.CTkFrame(right_container, fg_color='transparent')
            config_frame.pack(fill='both', expand=True, pady=(10, 0))
            
            config_label = ctk.CTkLabel(config_frame, text="Доступные конфигурации:", 
                                    font=('Arial', 14), text_color='white')
            config_label.pack(anchor='w', pady=(0, 5))
            
            self.config_list_frame = ctk.CTkScrollableFrame(config_frame, fg_color='#121212', height=150)
            self.config_list_frame.pack(fill='both', expand=True)
            
            # Загружаем текущие настройки если они есть
            if hasattr(self, 'server_host'):
                self.server_entry.insert(0, self.server_host)
                
            # Скрыть индикатор загрузки
            self.hide_loading()

        loading = threading.Thread(target=load_content, daemon=True)
        loading.start()

    def scan_network(self):
        """Сканирование локальной сети для поиска серверов"""
        import socket
        import ipaddress
        import concurrent.futures
        
        # Очищаем предыдущие результаты
        for widget in self.scan_results.winfo_children():
            widget.destroy()
            
        # Получаем текущий IP и подсеть
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            network = ipaddress.ip_network(f"{local_ip}/24", strict=False)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось определить сеть: {e}")
            return
        
        # Добавляем label с информацией о сканировании
        scanning_label = ctk.CTkLabel(self.scan_results, text=f"Сканирование {network}...", 
                                    text_color="yellow")
        scanning_label.pack(pady=5)
        
        def check_server(ip):
            """Проверяет доступность сервера на порту 8083"""
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    result = s.connect_ex((str(ip), 8083))
                    if result == 0:
                        return ip
            except:
                return None
        
        def scan_complete(future):
            """Обработка завершения сканирования"""
            scanning_label.destroy()
            
            found_servers = []
            for f in future:
                if f.result():
                    found_servers.append(f.result())
                    
            if not found_servers:
                no_servers_label = ctk.CTkLabel(self.scan_results, text="Серверы не найдены", 
                                            text_color="red")
                no_servers_label.pack(pady=5)
                return
                
            for server_ip in found_servers:
                server_btn = ctk.CTkButton(
                    self.scan_results, 
                    text=str(server_ip), font=('Arial', 14), fg_color='#4a1aa2', hover_color='#6235ad',
                    command=lambda ip=server_ip: [self.server_entry.delete(0, 'end'), self.server_entry.insert(0, str(ip))]
                )
                server_btn.pack(pady=2, padx=5, fill='x')
        
        # Запускаем сканирование в отдельном потоке
        def start_scan():
            with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
                futures = [executor.submit(check_server, ip) for ip in network.hosts()]
                self.after(100, lambda: scan_complete(futures))
                
        threading.Thread(target=start_scan, daemon=True).start()

    def test_server_connection(self):
        """Проверка подключения к серверу"""
        host = self.server_entry.get().strip()
        if not host:
            messagebox.showwarning("Предупреждение", "Введите адрес сервера")
            return
            
        try:
            fetcher = HttpJsonFetcher(base_url=f"http://{host}:8083")
            data = fetcher.get_json_list()
            if data:
                messagebox.showinfo("Успех", f"Сервер {host} доступен\nНайдено конфигураций: {len(data['files'])}")
                self.update_config_list(data)
            else:
                messagebox.showerror("Ошибка", "Не удалось получить данные с сервера")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка подключения: {str(e)}")

    def update_config_list(self, configs):
        """Обновление списка конфигураций с сервера"""
        for widget in self.config_list_frame.winfo_children():
            widget.destroy()
            
        if not configs:
            no_configs_label = ctk.CTkLabel(self.config_list_frame, text="Конфигурации не найдены", 
                                        text_color="red")
            no_configs_label.pack(pady=5)
            return
            
        for config in configs['files']:
            config_btn = ctk.CTkButton(self.config_list_frame, text=config, fg_color='#4a1aa2', hover_color='#6235ad',
                                    command=lambda c=config: self.block_apply(c))
            config_btn.pack(pady=2, padx=5, fill='x')

    def apply_server_config(self, config):
        """Применение конфигурации с сервера"""
        try:
            # Обновляем локальные настройки из конфига
            self.block_mode = config.get('block_mode', self.block_mode)
            self.excluded_users = config.get('excluded_users', self.excluded_users)
            
            # Обновляем UI
            if hasattr(self, 'combobox_block'):
                self.combobox_block.configure(text=self.block_mode)
                
            # Обновляем чекбоксы пользователей
            for user, var in getattr(self, 'server_user_checkboxes', []):
                var.set(user in self.excluded_users)
                
            messagebox.showinfo("Успех", "Конфигурация применена")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка применения конфигурации: {str(e)}")

    def toggle_server_mode(self):
        """Включение/выключение серверного режима"""
        self.server_status = self.server_mode_var.get()
        if self.server_status and not self.server_entry.get():
            messagebox.showwarning("Предупреждение", "Укажите адрес сервера перед включением режима")
            self.server_mode_var.set(False)
            self.server_status = False

    def apply_server_settings(self):
        """Применение всех серверных настроек"""
        self.server_host = self.server_entry.get().strip()
        self.server_status = self.server_mode_var.get()
        
        if self.server_status and not self.server_host:
            messagebox.showwarning("Предупреждение", "Укажите адрес сервера")
            return
            
        # Сохраняем настройки
        try:
            self.save_config()
            messagebox.showinfo("Успех", "Настройки сохранены")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка сохранения: {str(e)}")

    # Пример реализации одной из вспомогательных функций
    def show_loading(self, parent, text_load='Пожалуйста подождите идет загрузка...'):
        if self.loading_frame:
            self.loading_frame.destroy()
            self.loading_frame = None
        self.loading_frame = ctk.CTkFrame(parent, fg_color='#1A1A2E', corner_radius=15, border_width=0)
        self.loading_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER, relwidth=1, relheight=1)
        
        self.loading_canvas = tk.Canvas(self.loading_frame, bg='#1A1A2E', width=60, height=60)
        self.loading_canvas.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        loading_label = ctk.CTkLabel(self.loading_frame, text=text_load,  text_color='#D9B6E0', font=('Arial', 14))
        loading_label.place(relx=0.5, y=260, anchor=tk.CENTER)
        
        self.animate_loading()
        self.block_menu.unbind('<Button-1>')
        self.server_menu.unbind('<Button-1>')
        self.exit_menu.unbind('<Button-1>')

    def animate_loading(self):
        try:
            # Check if widgets still exist
            if not self.loading_frame or not self.loading_frame.winfo_exists():
                return
                
            if not self.loading_canvas or not self.loading_canvas.winfo_exists():
                return
                
            # Update animation
            self.loading_angle = (self.loading_angle + 24) % 360
            self.loading_canvas.delete("all")
            self.loading_canvas.create_arc(10, 10, 50, 50, 
                                        start=self.loading_angle, 
                                        extent=240, 
                                        style=tk.ARC, 
                                        outline='#D9B6E0', 
                                        width=3)
            
            # Schedule next frame only if still needed
            if self.loading_frame and self.loading_frame.winfo_exists():
                self.loading_animation_id = self.loading_canvas.after(50, self.animate_loading)
                
        except Exception as e:
            self.logger.error(f"Animation error: {str(e)}")
            # Stop animation on error
            if hasattr(self, 'loading_animation_id'):
                self.loading_canvas.after_cancel(self.loading_animation_id)

    def hide_loading(self):
        try:
            # Cancel any pending animation
            if hasattr(self, 'loading_animation_id') and self.loading_animation_id:
                self.loading_canvas.after_cancel(self.loading_animation_id)
                
            # Safely destroy widgets
            if self.loading_frame and self.loading_frame.winfo_exists():
                self.loading_frame.destroy()
                
            self.loading_frame = None
            self.loading_animation_id = None
            
            # Restore menu bindings
            self.block_menu.bind('<Button-1>', self._block_ui)
            self.exit_menu.bind('<Button-1>', lambda e: sys.exit(0))
            self.server_menu.bind('<Button-1>', self._server_ui)
            
        except Exception as e:
            self.logger.error(f"Error hiding loading: {str(e)}")

    # Функции для работы с tooltip
    def _show_tooltip(self, event, widget, text, x_plus=20, y_plus=40):    
        # Удаляем предыдущий tooltip если есть
        if self.tooltip_window != None:
            self.tooltip_window.destroy()
            self.tooltip_window = None
        
        # Создаем новое окно
        self.tooltip_window = ctk.CTkToplevel(widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{widget.winfo_rootx()+x_plus}+{widget.winfo_rooty()+y_plus}")
        self.tooltip_window.attributes('-alpha', 0.0)  # Начальная прозрачность
        self.tooltip_window.attributes('-topmost', True)
        
        # Создаем содержимое
        frame = ctk.CTkFrame(self.tooltip_window, fg_color='#2A2A2A', border_color='#404040', border_width=1, corner_radius=4)
        frame.pack()
        
        label = ctk.CTkLabel(frame, text=text, padx=10, pady=5, font=('Arial', 12), fg_color='transparent', text_color='white')
        label.pack()

        # Анимация появления
        self.tooltip_alpha = 0.0
        def animate():
            if self.tooltip_window and self.tooltip_alpha < 1.0:
                self.tooltip_alpha = min(self.tooltip_alpha + 0.075, 1.0)
                self.tooltip_window.attributes('-alpha', self.tooltip_alpha)
                self.tooltip_window.after(10, animate)
        
        animate()  # Запускаем анимацию

    def _hide_tooltip(self, event):
        if self.tooltip_window != None:
            self.tooltip_window.destroy()
            self.tooltip_window = None

    def _add_tooltip(self, widget, text):
        widget.bind('<Enter>', lambda e: self._show_tooltip(e, widget, text))
        widget.bind('<Leave>', self._hide_tooltip)

    # Показать выбор combobox
    def show_combobox(self, widget, event, text, x_plus=20, y_plus=40):
        if self.combobox_window != None:
            self.combobox_window.destroy()
            self.combobox_window = None
        else:
            width = widget.cget('width')
            height = widget.cget('height')

            x = widget.winfo_rootx() + x_plus
            y = widget.winfo_rooty() + y_plus

            self.combobox_window = ctk.CTkToplevel(widget)
            self.combobox_window.wm_overrideredirect(True)
            self.combobox_window.wm_geometry(f"{width}x100+{x}+{y}")
            self.combobox_window.attributes('-topmost', True)
            frame = ctk.CTkScrollableFrame(self.combobox_window, orientation="vertical", fg_color='#290d5e', width=width-23, height=60, border_color='white', border_width=1)
            frame.pack(expand=False)
            i = 0
            for texts in text:
                label = ctk.CTkLabel(frame, text=texts, text_color='white', width=width-23, justify='left', anchor='w', padx=5, corner_radius=5)  # Измените цвет текста для теста
                label.grid(row=i, column=0)
                # label.bind('<Enter>', lambda event, widget=label, mode=0: color_swap(event=event, widget=widget, mode=mode))
                # label.bind('<Leave>', lambda event, widget=label, mode=1: color_swap(event=event, widget=widget, mode=mode))
                label.bind('<Button-1>', lambda event, widget=widget, text=texts: self.swap_text(widget=widget, text=text))
                i += 1

    # Сменить текст у combobox
    def swap_text(self, widget, text):
        widget.configure(text=text)
        self.block_mode = text
        if self.combobox_window != None:
            self.combobox_window.destroy()
            self.combobox_window = None

    def _update_program_list(self):
        """Обновление списка программ"""
        self._update_program_list_display()
        self.save_local()  # Сохраняем изменения
        messagebox.showinfo("Успех", "Список программ обновлен и сохранен")

    def _update_program_list_display(self):
        """Обновляет отображение списка программ в интерфейсе"""
        # Очистка текущего списка
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # Добавление новых элементов
        for name in self.local_list_program:
            label = ctk.CTkLabel(self.scrollable_frame, 
                            text = str(name.get('name') if isinstance(name, dict) else str(name)),
                            text_color="white")
            label.pack(padx=5, pady=3, anchor="w")
            label.bind("<Button-1>", lambda e, n=name: self.delete_file_from_list(n))

    def delete_file_from_list(self, name=None):
        print(name)
        if name:
            if name in self.local_list_program:
                self.local_list_program.remove(name)  # Удаляем элемент
                messagebox.showinfo("Успех", "\nНажмите 'Обновить список' для отображения изменений")

    def _get_path(self, event):
        # Проверка доступности scrollable_frame
        if not self.scrollable_frame or not self.scrollable_frame.winfo_exists():
            messagebox.showwarning("Ошибка", "Список программ недоступен")
            return

        # Получение и нормализация путей
        dropped_files = [f.strip() for f in event.data.strip('{}').split('} {')]
        
        # Сбор существующих имен программ
        existing_labels = {
            widget.cget("text") 
            for widget in self.scrollable_frame.winfo_children() 
            if isinstance(widget, ctk.CTkLabel)
        }

        new_files = set()

        # Обработка каждого переданного пути
        for path in dropped_files:
            path = path.strip()
            try:
                if os.path.isfile(path):
                    # Обработка файлов .exe и .lnk
                    file_name = self._process_file(path)
                    if file_name and file_name not in existing_labels:
                        new_files.add(file_name)
                        
                elif os.path.isdir(path):
                    # Обработка директории
                    new_files.update(self._process_directory(path, existing_labels))
                    
            except Exception as e:
                print(f"Ошибка обработки элемента {path}: {e}")

        # Проверка наличия новых файлов
        if not new_files:
            messagebox.showinfo("Информация", "Новых .exe файлов не обнаружено или они уже есть в списке")
            return

        # Обновление данных (но не интерфейса)
        self.local_list_program = sorted(set(self.local_list_program) | new_files)
        new_additions = len(new_files)
        
        # Показать уведомление
        msg = (f"Добавлено новых .exe: {new_additions}" 
            if new_additions > 1 
            else "Добавлен новый .exe: 1")
        messagebox.showinfo("Успех", msg + "\nНажмите 'Обновить список' для отображения изменений")

    # Получение пути с .ink
    def get_target_path(sefl, lnk_path):
        shell = client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(lnk_path)
        return shortcut.Targetpath

    def _process_file(self, path):
        """Обработка отдельных файлов, возвращает имя exe-файла или None"""
        if path.lower().endswith(".exe"):
            return os.path.basename(path)
        
        if path.lower().endswith(".lnk"):
            try:
                target = self.get_target_path(path)
                if target and target.lower().endswith(".exe"):
                    return os.path.basename(target)
            except Exception as e:
                print(f"Ошибка обработки ярлыка {path}: {e}")
        
        return None

    def _process_directory(self, path, existing_labels):
        """Рекурсивный поиск exe-файлов в директории"""
        found_files = set()
        try:
            for root, _, files in os.walk(path):
                for file in files:
                    if file.lower().endswith(".exe") and file not in existing_labels:
                        found_files.add(file)
        except Exception as e:
            print(f"Ошибка обработки директории {path}: {e}")
        
        return found_files
