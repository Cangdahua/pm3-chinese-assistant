# PM3 中文助手 QML 客户端

这里是项目当前的主客户端：Qt Quick/QML 负责界面，Python 负责设备通信、命令
授权、数据工作区和写入事务。应用通过独立进程调用锁定的 PM3 Easy 兼容客户端。

## 源码优先状态

当前支持方式是从源码运行。本项目暂不发布官方 DMG、ZIP 或其他预编译安装包；
未经完整第三方许可证复核、Developer ID 签名与 Apple 公证的本地构建，不应被
转发或标记为官方版本。

## 安全与授权使用

请只操作你拥有或已获明确授权测试的设备和卡片，并遵守适用法律、合同与访问
控制规则。写入测试应使用可丢弃介质。不要向公开 issue 或 PR 上传真实 UID、
密钥、卡片 dump、串口日志或个人工作区。

这些安全提醒不修改根级 MIT 许可证，也不限制该许可证授予的商业使用权。

## 准备与运行

在项目根目录初始化并构建锁定的兼容客户端：

```bash
git submodule update --init --recursive
tools/bootstrap_compat_client.sh
```

使用 Python 3.12 虚拟环境安装运行依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r pm3-qml-client/requirements.txt
python pm3-qml-client/main.py
```

兼容客户端的上游 commit、补丁和哈希记录在
`docs/COMPAT_CLIENT_PROVENANCE.md` 与 `packaging/compat/runtime-lock.json`。

## 界面与工作流

- 13.56 MHz 工作台：识别卡片、默认密钥扫描、继续解析、读取整卡、校验数据、
  确认写卡，并提供可编辑密钥矩阵。
- 低频卡：LF search、HID、EM410x、Indala 与 T55xx 等诊断入口。
- 特殊卡：NTAG/Ultralight、NDEF、MIFARE Plus 只读识别、iCLASS、LEGIC、TNP3。
- 高频分析：通信记录、采样、dump 与 emulator 相关入口。
- 数据处理：导入、区块预览、导出、保存、打开工作区和受保护写入。
- 软件设置：串口、固件、兼容协议、外观和危险操作能力开关。
- 高级命令：仍经过 Python 后端授权，不能绕过危险操作保护。

界面提供跟随系统、白天和黑夜三种外观。窗口按业务内容计算自然尺寸，放大时
保持工作台比例并同步缩放内容。

## 数据与独立工作区

导入入口只接受 PM3/卡片相关格式：

- `dumpdata.bin`、`dumpkeys.bin`
- MIFARE Classic `.dump`、`.bin`、`.mfd`
- PM3 `.eml`
- NTAG/特殊卡 `.json`
- 密钥字典 `.dic`

导出支持 BIN、DUMP、MFD、EML、JSON 和 TXT。来源密钥、扫描结果和手动密钥
分别保存；从外部数据提取的密钥先标记为待验证，只有通过认证或用户明确保存后
才视为已知。

运行数据位于当前用户的应用支持目录。当前卡、待写目标、写后校验和写前备份
彼此隔离，不会写回源码目录。

## 写入安全模型

- 未解锁危险能力时，写卡、改 UID、模拟、原始访问、固件、未知命令和未审计
  脚本都由后端拒绝。
- 智能写入先进行无写入能力探测、完整读取、容量与 UID/BCC 检查和写前备份。
- 只写入确有差异的数据块；任何预检失败都必须在发送块数据前停止。
- 写入完成后读取整卡并逐字节校验，不能只凭退出码或输出文本报告成功。
- 事务状态支持在意外退出后识别中断并按差异恢复。

MIFARE Plus 当前只执行安全识别并解析可用的 UID、SAK 和安全级别线索，不调用
未审计脚本，也不发送认证、proximity、personalization、raw 或写入命令。

## 验证

从项目根目录运行：

```bash
make python-check
make release-audit
```

自动化检查不会向真实 PM3 设备发送命令。实机测试是独立、显式的步骤；相关
结果必须脱敏，写入路径只能使用已授权且可丢弃的测试介质。

## 关键文件

- `main.py`：后端、串口、命令授权、数据导入和写入事务。
- `Main.qml`：原生界面与交互状态。
- `requirements.txt`：固定的 Python 运行依赖。
- `tests/test_magic_write.py`：写入安全和数据处理回归测试。
- `../compat-clients/iceman-ice_v3.1.0/`：锁定的 GPL 兼容客户端子模块。

原创客户端代码采用根级 MIT 许可证。兼容客户端、PySide6 Essentials/Qt、
shiboken6、Python、pyserial 和数据来源保留各自许可证；参见根目录
`THIRD_PARTY_NOTICES.md` 与 `LICENSES/`。
