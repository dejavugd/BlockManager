# BlockManager - Application Blocker 🛡️

<div align="center">
  <img src="https://img.shields.io/badge/Version-1.0.0-blue" alt="Version">
  <img src="https://img.shields.io/badge/Platform-Windows-success" alt="Platform">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/Status-PreRelease-orange" alt="Status">
</div>

**BlockManager** is a lightweight and secure Windows application control tool. The project is designed to manage application execution with two operational modes:

<div align="center">
  <table>
    <tr>
      <th>🔴 Blacklist</th>
      <th>🟢 Whitelist</th>
    </tr>
    <tr>
      <td>Block only specified applications</td>
      <td>Allow only specified applications</td>
    </tr>
  </table>
</div>

---

## 🌟 Features

- 📋 Application list management
- ⚙️ Blocking mode configuration (Blacklist/Whitelist)
- 👥 User exceptions
- 🔄 Auto-start services
- 🌐 Server connectivity
- 🚀 Low resource consumption

---

## 🛠️ Installation

<details>
<summary><b>🔧 (Manual Installation)</b></summary>

1. Download the [latest release archive](https://github.com/dejavugd/BlockManager/releases)
2. Extract to `%ProgramFiles%/BlockManager`
3. Run **BlockManager.exe**
4. Create application list (drag and drop .exe files)
5. Select blocking mode
6. Configure user exceptions
7. Apply settings

</details>

---

## ⚠️ Important Warning

<div class="warning" style="padding: 10px; border-left: 4px solid #ffc107; margin: 10px 0;">
⚠️ When using Whitelist mode, ensure you include all system files, otherwise the system may become unstable!
</div>

---

## 🆘 Emergency Disable

> taskkill /IM blocker.exe /f

---

## 🌐 Server Configuration

> First install the [server component](https://github.com/dejavugd/BlockManagerServer/releases)

1. After installing [BlockManager](#setting)
2. Navigate to "Server Settings" tab
3. Enter IP/DNS or use "Network Scan"
4. Click "Test Connection"
5. Configure blocking mode
6. Set user exceptions
7. Select configuration file (in {Filename}.json format)

---

## 📸 Screenshots

| Main Interface | Server Settings |
|-------------------|-------------------|
| ![Main Screen](./img/HOME.png) | ![Server](./img/SERVER.png) |

---

## 📝 Logging

All activities are logged to:  
`%ProgramFiles%/BlockManager/logs`

---

## 👨‍💻 Author

<div align="left">
  <a href="https://github.com/dejavugd">
    <img src="https://img.shields.io/badge/GitHub-dejavugd-blue?style=for-the-badge&logo=github" alt="GitHub">
  </a>
  <br>
  <a href="https://yoomoney.ru/to/4100115868712253">
    <img src="https://img.shields.io/badge/Support-Project-orange?style=for-the-badge" alt="Donate">
  </a>
</div>

---

## 📜 License

This project is licensed under the **MIT License**.  
Free for personal and commercial use.