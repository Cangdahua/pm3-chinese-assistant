# PM3 中文助手

PM3 中文助手是面向 PM3 Easy / Proxmark3 的中文桌面客户端。项目把设备状态、
卡片识别、数据预览和高风险操作保护整理成普通用户更容易理解的工作流。

## 项目状态：源码优先

本仓库以可审查、可复现的源码为第一交付物：

- 主客户端位于 `pm3-qml-client/`，采用 PySide6 Essentials、Qt Quick/QML 和
  Python；绑定运行时同时使用锁定的 shiboken6。
- 根目录的 React/Vite 与 `src-tauri/` 是只读诊断原型，不是主客户端的替代品。
- 当前不提供官方 DMG、ZIP 或其他预编译安装包。未经完整第三方许可证复核、
  Developer ID 签名和 Apple 公证的本地构建，不应被转发或标记为官方版本。
- 后续只有在精确依赖清单、LGPL/GPL 对应源码义务、签名和公证均完成后，才会
  考虑发布二进制。

## 安全与授权使用

PM3 是双用途硬件。请只操作你拥有的设备和卡片，或已获得所有者明确授权的
测试目标，并遵守所在地法律、合同和访问控制规则。不要把真实卡片数据、密钥、
串口日志或个人工作区提交到公开 issue、PR 或仓库。

这些是操作安全和合规提醒，不修改 [MIT 许可证](LICENSE)，也不对许可证授予的
商业使用权增加用途限制。

## 从源码运行

建议使用 macOS、Python 3.12 和 Xcode Command Line Tools。首次检出后初始化锁定
的兼容客户端：

```bash
git submodule update --init --recursive
tools/bootstrap_compat_client.sh
```

创建独立 Python 环境并启动主客户端：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r pm3-qml-client/requirements.txt
python pm3-qml-client/main.py
```

兼容客户端固定到已记录的上游 commit 和本地补丁。构建来源、哈希与重建说明见
[兼容客户端来源说明](docs/COMPAT_CLIENT_PROVENANCE.md)。

## 主要能力

- 显示串口、通信、设备与固件状态。
- 高频、低频与常见 MIFARE 卡片识别。
- 以独立工作区保存当前卡、待写目标、写后校验和写前备份。
- 导入和导出 BIN、DUMP、MFD、EML、JSON、TXT 等 PM3 相关格式。
- 将来源密钥、扫描结果和手动密钥分仓保存，并区分待验证与已验证状态。
- 写入前进行能力预检、完整读取、容量检查和备份；写入后完整读回校验。
- 对写卡、改 UID、模拟、原始访问、固件操作、未知命令和未审计脚本实行后端
  默认拒绝策略，不能从高级命令行绕过。

运行数据保存在用户的应用支持目录中，不应写回源码树。

## 开发与验证

安装开发依赖并运行与 CI 相同的检查：

```bash
make bootstrap
make check
```

检查包含 Python 安全回归、实验前端 lint/build、Rust fmt/test/check、发布数据
审计和兼容客户端 provenance 校验。更细的环境说明见
[开发指南](docs/DEVELOPMENT.md)。

硬件测试不属于自动化 CI。涉及写入的验证只能在已授权、可丢弃的测试介质上，
并应遵循 [发布清单](docs/RELEASE_CHECKLIST.md)。

## 仓库结构

- `pm3-qml-client/`：当前主客户端。
- `compat-clients/iceman-ice_v3.1.0/`：锁定的 GPL Proxmark3 子模块。
- `packaging/compat/`：兼容补丁和可复现运行时锁。
- `tools/`：来源验证、安全审计和本地构建工具。
- `src/`、`src-tauri/`：实验性 React/Tauri 诊断原型。
- `docs/`：开发、来源和发布检查文档。

## 贡献与安全报告

提交补丁前请阅读 [贡献指南](CONTRIBUTING.md) 和
[行为准则](CODE_OF_CONDUCT.md)。安全漏洞、危险操作绕过或敏感数据泄露请按
[安全政策](SECURITY.md) 私下报告，不要先公开利用细节。

## 许可证

原创代码和文档采用 MIT 许可证：
`Copyright (c) 2026 PM3 Chinese Assistant contributors`。

Proxmark3、PySide6 Essentials/Qt、shiboken6、Python、pyserial、npm/Cargo
依赖和其他第三方材料保留各自许可证。详情见
[第三方说明](THIRD_PARTY_NOTICES.md) 与
[`LICENSES/`](LICENSES/)。项目图标 `public/app-icon.svg` 是原创项目资产，
`src-tauri/icons/` 中的栅格与平台图标由它生成，均随原创项目材料采用 MIT 许可。
