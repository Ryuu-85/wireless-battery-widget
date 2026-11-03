# Wireless Battery Widget

一个 Windows 桌面悬浮小组件，集中查看无线鼠标、键盘、耳机和手柄的电量。支持拖动、置顶、自定义背景、低电量提醒和开机自启动。

## 支持的电量来源

- Windows 蓝牙电量和 BLE Battery Service；XInput 兼容手柄。
- Logitech G HUB 本地接口和 Razer Synapse 日志。
- ATK/VXE V75X：通过 ATK HUB 页面读取。
- SteelSeries Arctis 7（2019）：通过 HID 读取；其他型号可尝试 Windows 蓝牙或 SteelSeries GG 日志。

实际显示取决于设备、连接方式及厂商软件是否提供电量；不可读取时可能显示 `--`。XInput 对部分手柄只提供粗略电量等级。

## 运行

1. 在 Windows 上安装 Python（包括 Tkinter）。可选安装 Pillow 以使用背景图片：`python -m pip install Pillow`。
2. 根据设备安装并运行相应的厂商软件。ATK HUB 功能还需要 Node.js。
3. 双击 `run_wireless_battery_widget.bat`。左键拖动窗口，右键打开刷新、通知、置顶、自启动及背景设置。

首次运行时会生成 `wireless_battery_widget_config.json`。ATK HUB 后台功能可通过右键菜单安装计划任务，可能需要管理员权限。

面板还可显示 Codex 使用额度和 DeepSeek 余额；后者可使用本机 DSH 凭据或 `DEEPSEEK_API_KEY`。凭据由程序在本机读取，不包含在本仓库中。

## 文件

- `wireless_battery_widget.py`：主程序。
- `low_battery_notify.ps1`：Windows 静音低电量通知。
- `atk_v75x_battery_probe.js` 和 ATK PowerShell 脚本：ATK HUB 读取及窗口管理。
- `wireless_battery_widget_steelseries.py`：兼容原有 SteelSeries 启动方式的同一版本。

设备支持情况依赖其具体型号和连接协议；厂商接口或日志格式变化也可能导致读取失效。
