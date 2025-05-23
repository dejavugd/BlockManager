# BlockManager - Блокировщик программного обеспечения 🛡️

<div align="center">
  <img src="https://img.shields.io/badge/Version-0.1-blue" alt="Version">
  <img src="https://img.shields.io/badge/Platform-Windows-success" alt="Platform">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/Status-PreRelease-orange" alt="Status">
</div>

**BlockManager** - это легкая и безопасная программа для контроля запускаемого ПО в Windows. Проект создан для управления запуском приложений с двумя режимами работы:

<div align="center">
  <table>
    <tr>
      <th>🔴 Blacklist</th>
      <th>🟢 Whitelist</th>
    </tr>
    <tr>
      <td>Блокировка приложений из списка</td>
      <td>Блокировка всех приложений, кроме указанных</td>
    </tr>
  </table>
</div>

---

## 🌟 Возможности

- 📋 Создание списка программ
- ⚙️ Настройка метода блокировки (Blacklist/Whitelist)
- 👥 Исключения для пользователей
- 🔄 Автозапуск служб
- 🌐 Подключение к серверу
- 🚀 Низкое потребление ресурсов

---

## 🛠️ Установка

<details>
<summary><b>🔧 (Ручная установка)</b></summary>

1. Скачайте [последнюю версию архива](https://github.com/dejavugd/BlockManager/releases)
2. Распакуйте в `%ProgramFiles%/BlockManager`
3. Запустите **BlockManager.exe**
4. Создайте список программ (перетаскиванием .exe)
5. Выберите метод блокировки
6. Укажите исключения
7. Примените настройки

</details>

---

## ⚠️ Важное предупреждение

<div class="warning" style="padding: 10px; border-left: 4px solid #ffc107; margin: 10px 0;">
⚠️ При использовании Whitelist обязательно добавьте системные файлы, иначе система может стать нестабильной!
</div>

---

## 🆘 Экстренное отключение

> taskkill /IM blocker.exe /f
---

## 🌐 Настройка сервера

> Перед настройкой установите [серверную часть](https://github.com/dejavugd/BlockManagerServer/releases) на сервер

1. После установки ПО [BlockManager](#setting)
2. Перейдите на вкладку "Настройки сервера"
3. Укажите IP/DNS или используйте "Сканирование сети"
4. Нажмите кнопку "Проверить"
5. Настройте метод блокировки
6. Укажите исключения для пользователей
7. Выберите файл конфигурации (в формате {Имя_файла}.json)

---
## 📸 Скриншоты
<details>
<summary><b>v0.1</b></summary>


| Главный интерфейс | Настройки сервера |
|-------------------|-------------------|
| ![Главный экран](./img/HOME.png) | ![Сервер](./img/SERVER.png) |
</details>

---

## 📝 Логирование

Все действия записываются в:  
`%ProgramFiles%/BlockManager/logs`

---

## 👨‍💻 Автор

<div align="left">
  <a href="https://github.com/dejavugd">
    <img src="https://img.shields.io/badge/GitHub-dejavugd-blue?style=for-the-badge&logo=github" alt="GitHub">
  </a>
  <br>
  <a href="https://yoomoney.ru/to/4100115868712253">
    <img src="https://img.shields.io/badge/Поддержать-проект-orange?style=for-the-badge" alt="Donate">
  </a>
</div>

---

## 📜 Лицензия

Этот проект распространяется под лицензией **MIT**.  
Свободен для личного и коммерческого использования.
