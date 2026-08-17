# Contributing

感谢你改进 PM3 中文助手。提交贡献即表示你同意遵守
[行为准则](CODE_OF_CONDUCT.md)，并按本仓库的 MIT 许可证提供你的原创贡献。

## 开始之前

- 安全漏洞和危险操作绕过请按 [安全政策](SECURITY.md) 私下报告。
- 仅在自有或明确授权的硬件和卡片上测试；写入测试使用可丢弃介质。
- 不要提交真实卡片 dump、密钥、串口日志、工作区、签名证书或账号信息。
- 不要提交从未知来源复制的图标、截图、固件、字典或代码。

这些要求用于保护参与者和项目，不改变 MIT 许可证授予的商业使用权。

## 环境准备

初始化锁定子模块：

```bash
git submodule update --init --recursive
```

推荐使用 Python 3.12、Node.js 24、pnpm 11.19 和带 `rustfmt` 的稳定 Rust。
在虚拟环境中安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
make bootstrap
```

主客户端从源码运行：

```bash
python pm3-qml-client/main.py
```

## 修改与检查

尽量让每个 PR 只解决一个明确问题。修改后运行：

```bash
make check
```

如果完整环境暂不可用，至少运行与你改动相关的目标，并在 PR 中说明未运行项：

- `make python-check`
- `make frontend-check`
- `make rust-check`
- `make release-audit`

硬件行为不能由 CI 证明。需要实机验证时，请记录设备类别、固件族、操作系统和
脱敏结果，不要上传 UID、密钥或原始 dump。

## 安全边界

- 新命令默认应被拒绝，只有经过审计的只读命令才进入常规白名单。
- 写卡、改 UID、模拟、原始访问、固件和脚本能力必须经过后端授权；前端提示
  不能代替后端校验。
- 写入流程必须保留预检、完整备份、最小变更、完整读回校验和失败恢复语义。
- 不要用“命令有输出”或进程退出码单独代表业务成功。

## 许可证与来源

- 新增原创代码采用根级 MIT 许可证。
- 修改 Proxmark3 子模块或本地补丁时，保留 GPL 和文件级版权声明。
- 第三方材料必须记录上游 URL、固定 revision、许可证、必要归属和内容哈希。
- 不要把 `node_modules`、wheel、crate cache 或未审计二进制提交进仓库。
- 项目当前只发布源码。不要在 PR 或 issue 中附带未经完整许可复核、签名和公证
  的 DMG、app bundle 或 ZIP。

## PR 清单

- [ ] 改动目的和安全影响已说明。
- [ ] 测试已运行，未运行项已说明。
- [ ] 没有绝对个人路径、秘密、卡片数据或本地生成物。
- [ ] 新增第三方材料的来源与许可证已记录。
- [ ] 用户文档和错误提示已同步更新。
