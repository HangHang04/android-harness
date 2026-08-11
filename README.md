# Android Harness

让 Agent 直接操作 Android 真机的小工具。

Android Harness 通过 Android 自带的 ADB 和 UI Automator，让 Codex 这类 Agent 可以读取当前屏幕、找按钮、点击、滑动、截图、打开应用，也可以直接用 PowerShell 手动控制。

项目受到 [ShawnPana/phone-harness](https://github.com/ShawnPana/phone-harness) 启发。Android Harness 是独立的 Android/ADB 实现，不需要 root、scrcpy、Appium，也不需要在手机里常驻一个服务。

## 最省事的用法：直接让 Agent 帮你装

如果你本来就是想让 Codex / Agent 操作手机，其实不用先把这一整页命令都看完。

把仓库链接发给支持本地 Skill 的 Agent，然后直接告诉它：

```text
请把 https://github.com/HangHang04/android-harness 安装成一个本地 Skill。
能自动完成的电脑端配置请直接帮我完成；需要我在手机上打开开发者选项、USB 调试、确认授权或无线配对时再告诉我。
安装好以后先运行 doctor 检查连接，确认正常后再使用这个 Skill 操作我的手机。
```

Agent 可以帮你处理仓库下载、Python 包安装、Skill 安装和连接检查。你通常只需要在它提示时完成手机上必须由本人确认的操作，比如：

- 打开开发者选项和 USB / 无线调试；
- 确认电脑的 RSA 调试授权；
- 无线调试时查看并输入一次性配对码；
- 解锁手机，或确认涉及账号、支付、权限等敏感操作。

> Agent 无法替你点击手机上的系统授权弹窗，也不会绕过锁屏或身份验证。这些步骤本来就应该由你自己确认。

安装完成后，可以直接这样说：

```text
用 android-harness 看看我的手机有没有连接好。
```

```text
打开手机设置，告诉我现在这个页面有什么。
```

```text
帮我找到开发者选项里的无线调试，但先不要修改任何开关。
```

如果这样已经能用，后面的内容可以等遇到问题再看。

## 它大概是怎么工作的？

整个过程其实就三件事：

```mermaid
flowchart LR
    A["电脑能通过 ADB 看到手机"] --> B["Android Harness 读取 / 操作界面"]
    B --> C["Agent 用 Skill 自己观察、操作、再检查"]
```

也就是说：**先让 ADB 连上手机，后面就可以把大部分事情交给 Agent。**

## 环境要求

目前主要面向：

- Windows 10 / 11；
- Python 3.11 或更高版本；
- Android SDK Platform Tools（里面有 `adb.exe`）；
- Android 11 / API 30 或更高版本的真机；
- 推荐 PowerShell 7（`pwsh.exe`）。

如果你不确定这些有没有装，可以先让 Agent 检查，不必自己一个个找。

## 想自己安装的话

如果不想让 Agent 自动配置，也可以手动安装。

在 PowerShell 中执行：

```powershell
git clone 'https://github.com/HangHang04/android-harness.git'
Set-Location -LiteralPath '.\android-harness'
py -3 -m pip install --user .
```

然后把项目自带的 Skill 安装到本地：

```powershell
py -3 -m android_harness.cli --json skill --install
```

安装后新建一个 Codex 任务，让 Skill 列表刷新。

如果只是开发 / 测试这个仓库，也可以不安装到用户目录，直接在仓库根目录运行：

```powershell
.\android-harness.ps1 --json doctor
```

如果 pip 提示 `Scripts` 目录不在 `PATH`，一般可以先忽略。本文的命令都可以通过 `py -3 -m android_harness.cli` 运行。

## 手机怎么连？

支持两种方式：

- **USB 数据线**：最直观，能正常识别时优先推荐；
- **无线调试**：USB 一直抽风时很好用，电脑只有有线网络也可以开 Windows 热点给手机连接。

不知道选哪个的话，先试 USB；如果 `adb devices -l` 一直看不到手机，再换无线。

### 方法 A：USB

手机上先做这些：

1. 打开“设置 > 关于本机”；
2. 连续点击“版本号”约 7 次，开启开发者模式；
3. 打开“开发者选项 > USB 调试”；
4. 手机保持解锁，重新插拔数据线；
5. 如果出现“是否允许 USB 调试”的 RSA 指纹弹窗，确认允许。

然后在电脑检查：

```powershell
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb devices -l
```

看到类似下面这种状态，就说明 ADB 已经连上：

```text
XXXXXXXX    device
```

常见结果：

| 看到的状态 | 是什么意思 | 怎么办 |
| --- | --- | --- |
| `device` | 已连接，可以用了 | 运行 `doctor` |
| `unauthorized` | 线是通的，但手机还没授权 | 解锁手机，确认 RSA 弹窗 |
| `offline` | 设备看到了，但 ADB 会话异常 | 重新插拔或重启 ADB |
| 什么设备都没有 | Windows 连 ADB 设备都没识别出来 | 换数据线 / USB 口，或直接试无线调试 |

重启 ADB：

```powershell
& $adb kill-server
& $adb start-server
& $adb devices -l
```

#### 一个很容易误会的地方

<p align="center">
  <img src="docs/images/default-usb-configuration-zh.jpg" alt="手机默认 USB 配置选择了传输文件或 Android Auto" width="360">
</p>

手机里的“默认 USB 配置 / 传输文件 / Android Auto”只是 USB 用途设置，**不等于 ADB 已经授权成功**。

所以如果一直没有 RSA 调试弹窗，不要只反复切这个选项。先看 `adb devices -l` 到底有没有设备。

如果 Windows 设备管理器出现“设备描述符请求失败”或错误代码 43，通常说明问题甚至还没走到 ADB 授权这一步。优先试：

1. 换一条确认可以传数据的数据线；
2. 直连电脑 USB 口，不走扩展坞；
3. 换另一个 USB 口；
4. 手机保持解锁后重新插拔；
5. 还是不行就直接用下面的无线方案。

### 方法 B：电脑热点 + 无线调试

如果 USB 怎么都识别不了，可以让 Windows 开热点，再让手机通过无线 ADB 连接。

电脑只有网线也没关系：Windows 可以把以太网共享成 Wi-Fi 热点。

先做这些：

1. Windows 打开“设置 > 网络和 Internet > 移动热点”；
2. 把 Internet 连接共享出去；
3. 手机连接电脑创建的 Wi-Fi；
4. 手机打开“开发者选项 > 无线调试”；
5. 点“使用配对码配对设备”。

手机会显示 IP、配对端口和六位配对码。

配对码只在本机终端里输入，**不要把它写进截图、Issue、日志或公开仓库。**

#### 如果手机显示的 IP 很奇怪

有些手机会把 VPN、游戏加速器或虚拟网卡的 IP 显示在无线调试页面上。

例如手机显示 `172.x.x.x`，但 Windows 热点实际是 `192.168.x.x`，这时直接照抄就可能配对失败。

可以先让 Agent 帮你判断；也可以自己在 PowerShell 看热点网卡和邻居：

```powershell
Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object InterfaceAlias -Match 'Local Area Connection|Wi-Fi Direct|移动热点' |
    Select-Object InterfaceAlias, IPAddress, PrefixLength

Get-NetNeighbor -AddressFamily IPv4 |
    Where-Object State -NotIn 'Unreachable', 'Incomplete' |
    Select-Object InterfaceAlias, IPAddress, State
```

手机真正的 Wi-Fi IP 应该和电脑热点网关处于同一子网。Windows 热点常见是 `192.168.137.x`，但不要死记这个数字，以你自己的电脑为准。

#### 配对

```powershell
$phoneIp = 'PHONE_WIFI_IP'
$pairingPort = 'CURRENT_PAIRING_PORT'

Test-NetConnection -ComputerName $phoneIp -Port $pairingPort
& $adb pair "${phoneIp}:${pairingPort}"
```

看到：

```text
Enter pairing code:
```

再输入手机当前显示的六位配对码。

成功后会看到类似：

```text
Successfully paired to PHONE_WIFI_IP:PAIRING_PORT
```

然后检查设备：

```powershell
& $adb mdns services
& $adb devices -l
```

如果已经配对成功，但 `adb devices` 还是空的，可以试：

```powershell
& $adb kill-server
& $adb start-server
& $adb mdns services
& $adb devices -l
```

还不行的话，在手机“无线调试”主页面查看**调试连接端口**，再执行：

```powershell
$debugPort = 'CURRENT_DEBUG_PORT'
& $adb connect "${phoneIp}:${debugPort}"
& $adb devices -l
```

注意：**配对端口和日常连接端口不是同一个东西。** 这是无线调试里最容易踩的坑之一。

#### 无线调试常见问题

| 现象 | 常见原因 | 可以怎么处理 |
| --- | --- | --- |
| `protocol fault (couldn't read status message)` | IP 指到了 VPN / 虚拟网卡，或者端口已经过期 | 检查热点子网，重新打开配对弹窗 |
| 已显示 Successfully paired，但设备列表为空 | 把配对端口当成了连接端口，或 mDNS 没发现服务 | 运行 `adb mdns services`，必要时手动 `adb connect` |
| `Test-NetConnection` 失败 | 手机和电脑不在同一局域网，或端口已经变了 | 确认手机连着电脑热点，再生成一次配对信息 |
| 用一会儿就断 | 热点 / 无线调试关闭、省电策略或 ADB 重启 | 保持热点和无线调试开启，再检查设备列表 |

## 怎么知道已经配置好了？

不管 USB 还是无线，最后运行：

```powershell
$env:PYTHONUTF8 = '1'
py -3 -m android_harness.cli --json doctor
```

最主要看两件事：

- `adb devices -l` 里的设备状态是 `device`；
- `doctor` 顶层返回 `"ok": true`，必需检查都通过。

`unicode-companion` 没安装也不影响截图、读界面和点击。它只是中文、emoji 等 Unicode 输入的可选组件。

如果你是让 Agent 配置的，直接让它运行 `doctor` 并解释没通过的项目就行，不需要自己读 JSON。

## 配好以后怎么用？

### 推荐：直接和 Agent 说人话

安装 Skill 后，新建一个任务，然后描述你想做什么：

```text
用 android-harness 检查手机连接。
```

```text
打开设置，截个图并告诉我现在有哪些选项。
```

```text
向上滚动，找到“无线调试”，先不要点进去。
```

```text
帮我看看当前 App 为什么卡在这个页面，只观察和截图，不要修改任何东西。
```

Skill 会尽量按照“先看清楚 → 再操作 → 操作后再确认”的方式工作。

遇到多个同名按钮、身份验证、发送消息、购买、删除、安装应用、修改权限或系统设置等情况时，应该先停下来让用户确认，而不是盲点。

### 想自己控制：PowerShell

如果你想自己玩命令，也可以直接用 CLI：

```powershell
$env:PYTHONUTF8 = '1'

# 看屏幕信息
py -3 -m android_harness.cli --json screen-info

# 截图
py -3 -m android_harness.cli screenshot -o '.\phone-screen.png'

# 读取当前页面的文字、资源 ID 和坐标
py -3 -m android_harness.cli --json ui

# 点击唯一匹配的文字
py -3 -m android_harness.cli --json tap-text '设置'

# 滑动 / Home / 打开设置
py -3 -m android_harness.cli --json swipe up
py -3 -m android_harness.cli --json key home
py -3 -m android_harness.cli --json open-app com.android.settings
```

在仓库根目录也可以用短启动脚本：

```powershell
.\android-harness.ps1 --json ui
.\android-harness.ps1 --json tap-text '设置'
```

多个设备同时在线时需要指定设备：

```powershell
py -3 -m android_harness.cli --serial 'DEVICE_SERIAL' --json doctor
```

ASCII 文本可以通过标准输入发送：

```powershell
'hello from Android Harness' |
    py -3 -m android_harness.cli --json type --stdin
```

ADB 原生输入对 Unicode 支持有限。中文、emoji 和其他 Unicode 文本需要可选 companion IME；项目不会为了“看起来成功”而偷偷丢字。

## 能做什么

- 检查 ADB、授权状态、Android 版本、锁屏状态、截图和 UI 读取能力；
- 获取当前屏幕截图；
- 读取可访问的文字、内容描述、资源 ID、坐标和交互状态；
- 按文字或坐标点击；
- 长按、滑动、滚动、按系统按键、打开应用；
- 操作后重新观察页面，确认刚才的动作有没有真的生效；
- 运行显式的 Python 工作流；
- 可选支持中文、emoji 和其他 Unicode 输入。

## 做不到 / 不应该自动做的事

- 不能替你批准 RSA 授权、解锁手机或绕过身份验证；
- 多台设备同时在线时不会偷偷猜该操作哪一台；
- DRM / 安全页面可能是黑屏或没有可读 UI，这种情况不应该盲点；
- Canvas、游戏以及没有无障碍标签的图标，可能需要结合截图判断；
- 不支持多点触控、相机 / 生物识别确认、远程解锁和无人值守重连；
- 默认不应该把配对码、验证码、私人消息或账户截图写进日志或公开仓库。

## 开发与测试

电脑端没有第三方运行时依赖。标准库测试：

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
py -3 -m unittest discover -s tests -v
py -3 -m compileall -q src tests
```

如果安装了可选开发依赖：

```powershell
py -3 -m pytest
py -3 -m ruff check .
```

可选 Unicode companion 位于 `companion\`，使用单独的 Gradle、JDK 17 和 Android SDK 工具链。

## 许可证

[MIT License](LICENSE)

## 致谢

Android Harness 的灵感来自 [ShawnPana/phone-harness](https://github.com/ShawnPana/phone-harness)，特别是它轻量、面向 Agent 的“观察、操作、验证”工作流。

本仓库是独立的 Android/ADB 实现，感谢 ShawnPana 公开分享原项目和设计思路。
