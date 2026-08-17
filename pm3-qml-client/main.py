from __future__ import annotations

import glob
import ctypes
import json
import os
import re
import shutil
import signal
import sqlite3
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import hashlib
from pathlib import Path
from urllib.parse import unquote, urlparse

import serial
from PySide6.QtCore import QObject, Property, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine


APP_NAME = "PM3 中文助手"
APP_VERSION = "0.3.1"
APP_BUILD = "2026.08.17-safety-v3"
SOURCE_ROOT = Path(__file__).resolve().parents[1]
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", SOURCE_ROOT))
IS_BUNDLED_APP = bool(getattr(sys, "frozen", False))
APP_SUPPORT_ROOT = Path.home() / "Library/Application Support/PM3 Chinese Assistant"
ROOT = APP_SUPPORT_ROOT if IS_BUNDLED_APP else SOURCE_ROOT
BUNDLED_QML_FILE = RESOURCE_ROOT / "pm3-qml-client/Main.qml"
BUNDLED_COMPAT_CLIENT_DIR = RESOURCE_ROOT / "compat-clients/iceman-ice_v3.1.0/client"
BUNDLED_KEY_LIBRARY_DB = RESOURCE_ROOT / "pm3-qml-client/data/key_library.sqlite"
COMPAT_CLIENT = ROOT / "compat-clients/iceman-ice_v3.1.0/client/proxmark3"
KEY_STATUS_FILE = COMPAT_CLIENT.parent / "dumpkeys-status.json"
KEY_LIBRARY_DB = APP_SUPPORT_ROOT / "key_library.sqlite"
LEGACY_USER_KEY_LIBRARY_DB = APP_SUPPORT_ROOT / "pm3-qml-client/data/key_library.sqlite"
INTEGRITY_ROOT = RESOURCE_ROOT if IS_BUNDLED_APP else ROOT
INTEGRITY_MANIFEST = INTEGRITY_ROOT / "pm3-qml-client/data/integrity_manifest.json"
WORKSPACE_ROOT = Path(os.environ.get("PM3_WORKSPACE_ROOT", APP_SUPPORT_ROOT / "workspace-v2"))
WORKSPACE_READ_DATA = WORKSPACE_ROOT / "read/current_card.bin"
WORKSPACE_PENDING_DATA = WORKSPACE_ROOT / "write/target.bin"
WORKSPACE_VERIFY_DATA = WORKSPACE_ROOT / "verify/readback.bin"
WORKSPACE_STATE_FILE = WORKSPACE_ROOT / "workspace.json"
WORKSPACE_TRANSACTION_FILE = WORKSPACE_ROOT / "transaction.json"
WORKSPACE_BACKUP_DIR = WORKSPACE_ROOT / "backups"
WORKSPACE_KEY_DIR = WORKSPACE_ROOT / "keys"
WORKSPACE_ANALYSIS_DIR = WORKSPACE_ROOT / "analysis"
LEGACY_PACKET_SIZE = 544
CMD_VERSION = 0x0107

RUNTIME_SENSITIVE_NAMES = {
    ".history",
    "proxmark3.log",
    "dumpdata.bin",
    "dumpkeys.bin",
    "dumpkeys-status.json",
    "nonces.bin",
    "trace.bin",
    "selected_data.eml",
    "selected_data_magic_target.bin",
    "selected_data_smart_target.bin",
    "pending_write_data.bin",
}

COMMAND_CAPABILITY_READ_ONLY = "read_only"
COMMAND_CAPABILITY_CARD_MUTATION = "card_mutation"
COMMAND_CAPABILITY_EMULATION = "emulation"
COMMAND_CAPABILITY_RAW = "raw_device_access"
COMMAND_CAPABILITY_FIRMWARE = "firmware_management"
COMMAND_CAPABILITY_DANGEROUS_SCRIPT = "dangerous_script"
COMMAND_CAPABILITY_SCRIPT = "script"
COMMAND_CAPABILITY_RESTRICTED = "restricted"

# Authorization is intentionally based on this positive list.  Anything that is
# not proven to be a read-only operation is restricted by default, including new
# commands introduced by a future PM3 client.
READ_ONLY_WORKFLOW_COMMANDS = frozenset(
    {
        "workflow mifare_classic_autopwn",
        "workflow mifare_classic_local_dict",
        "workflow mifare_default_key_scan",
        "workflow mifare_classic_nested_missing",
        "workflow mifare_classic_hardnested_missing",
        "workflow mifare_nonce_collect",
        "workflow mifare_mfkeys_recover",
        "workflow mifare_nonce_assist",
        "workflow mifare_plus_inspect",
    }
)

READ_ONLY_EXACT_COMMANDS = frozenset(
    {
        ("help",),
        ("quit",),
        ("hw",),
        ("hf",),
        ("lf",),
        ("hf", "14a"),
        ("hf", "15"),
        ("hf", "iclass"),
        ("hf", "mf"),
        ("hf", "mfu"),
        ("lf", "em"),
        ("lf", "hid"),
        ("lf", "indala"),
        ("lf", "t55xx"),
        ("lf", "t55xx", "config"),
        ("script",),
        ("script", "list"),
    }
)

READ_ONLY_COMMAND_PREFIXES = (
    ("hw", "version"),
    ("hw", "status"),
    ("hw", "ping"),
    ("hw", "tune"),
    ("hf", "search"),
    ("hf", "list"),
    ("hf", "14a", "reader"),
    ("hf", "15", "reader"),
    ("hf", "15", "info"),
    ("hf", "15", "dump"),
    ("hf", "15", "read"),
    ("hf", "iclass", "reader"),
    ("hf", "iclass", "dump"),
    ("hf", "mf", "chk"),
    ("hf", "mf", "dump"),
    ("hf", "mf", "hardnested"),
    ("hf", "mf", "ice"),
    ("hf", "mf", "mifare"),
    ("hf", "mf", "nested"),
    ("hf", "mf", "rdbl"),
    ("hf", "mf", "rdsc"),
    ("lf", "search"),
    ("lf", "em", "410x_read"),
    ("lf", "hid", "read"),
    ("lf", "indala", "read"),
    ("lf", "t55xx", "detect"),
    ("lf", "t55xx", "dump"),
    ("lf", "t55xx", "info"),
    ("lf", "t55xx", "read"),
)

AUDITED_READ_ONLY_SCRIPTS = {
    "emul2dump": (1497, "88085d17ac7241b11d62ff62e69df8555f92ff53d3960e7f33c6a518649324ae"),
    "emul2html": (1676, "737b2464bbfd816ac3c7240e43bb1300c045d98a40288de5148988d553eb791f"),
    "htmldump": (1660, "799af1cee0735b6b1dc1642f68d4ecc676623870ad94e8e05b1228f68ee84b90"),
    "ndef_dump": (7084, "886ed08741e925133bae1eb5735a8fd9396d7e3b6c9e61cb7c1245712accaab5"),
    "parameters": (1267, "1f556b7d40c4e7e21f6d3a9f94fde2573b843d7ec2b096d4e7aa054dc9dba44c"),
    "tracetest": (2335, "ef92864a92f5c3cd887475dcaff20acbaad528f29f307c062646d8f6e40a38ad"),
}

DANGEROUS_SCRIPT_NAMES = frozenset(
    {
        "14araw",
        "brutesim",
        "didump",
        "dumptoemul",
        "lf_bulk_program",
        "remagic",
        "test_t55x7_ask",
        "test_t55x7_bi",
        "test_t55x7_fsk",
        "test_t55x7_psk",
        "tnp3clone",
        "tnp3dump",
        "tnp3sim",
    }
)

CARD_MUTATION_OPERATION_TOKENS = frozenset(
    {
        "clone",
        "cload",
        "cset",
        "csetblk",
        "csetuid",
        "cwipe",
        "format",
        "lock",
        "personalize",
        "restore",
        "setuid",
        "unlock",
        "wipe",
        "wrbl",
        "write",
        "writeblk",
    }
)

EMULATION_OPERATION_TOKENS = frozenset(
    {
        "eload",
        "emulate",
        "eset",
        "sim",
        "simulate",
    }
)

# These legacy MIFARE commands are normally read-only, but selected one-letter
# options transfer data or recovered keys into the PM3 emulator memory.
EMULATOR_MUTATING_OPTIONS = {
    ("hf", "mf", "chk"): frozenset({"t"}),
    ("hf", "mf", "nested"): frozenset({"t"}),
    ("hf", "mf", "csave"): frozenset({"e"}),
}

FIRMWARE_COMMAND_PREFIXES = (
    ("flash",),
    ("bootloader",),
    ("bootrom",),
    ("hw", "bootloader"),
    ("hw", "flash"),
    ("hw", "fpga"),
)


def ensure_runtime_assets() -> None:
    APP_SUPPORT_ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        APP_SUPPORT_ROOT.chmod(0o700)
    except OSError:
        pass

    if IS_BUNDLED_APP and BUNDLED_COMPAT_CLIENT_DIR.exists():
        COMPAT_CLIENT.parent.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(BUNDLED_COMPAT_CLIENT_DIR, COMPAT_CLIENT.parent, dirs_exist_ok=True)
    if COMPAT_CLIENT.exists():
        COMPAT_CLIENT.chmod(COMPAT_CLIENT.stat().st_mode | 0o111)

    if not KEY_LIBRARY_DB.exists():
        seed = LEGACY_USER_KEY_LIBRARY_DB if LEGACY_USER_KEY_LIBRARY_DB.exists() else BUNDLED_KEY_LIBRARY_DB
        KEY_LIBRARY_DB.parent.mkdir(parents=True, exist_ok=True)
        if seed.exists() and seed.resolve() != KEY_LIBRARY_DB.resolve():
            shutil.copy2(seed, KEY_LIBRARY_DB)
    if KEY_LIBRARY_DB.exists():
        try:
            KEY_LIBRARY_DB.chmod(0o600)
        except OSError:
            pass


class CommandCancelled(RuntimeError):
    pass


class CommandExecutionError(RuntimeError):
    pass


class CommandTimedOut(CommandExecutionError):
    pass

PUBLIC_KEY_SOURCE = "compat-clients/iceman-ice_v3.1.0/client/default_keys.dic"
PUBLIC_KEY_NOTE = "locked submodule deterministic seed"


OUTPUT_TRANSLATIONS = (
    ("Usage:", "用法："),
    ("usage:", "用法："),
    ("options:", "选项："),
    ("Options:", "选项："),
    ("samples:", "示例："),
    ("Samples:", "示例："),
    ("Examples:", "示例："),
    ("examples:", "示例："),
    ("Commands:", "命令："),
    ("commands:", "命令："),
    ("Example usage", "示例用法"),
    ("Arguments:", "参数："),
    ("Output files from this operation:", "本次操作会生成这些文件："),
    ("This is a script which automates cracking and dumping mifare classic cards.", "这是用于自动分析并读取 Mifare Classic 授权测试卡片的脚本。"),
    ("Waiting for card or press any key to stop", "正在等待放卡；按任意键可停止。"),
    ("Card found, commencing crack on UID", "已发现卡片，开始对这个 UID 做密钥分析："),
    ("Found valid key:", "发现有效密钥："),
    ("Card found, darkside attack useless PRNG hardend on UID", "已发现卡片，但随机数较强，Darkside 方法不适用。UID："),
    ("Button pressed. Aborted.", "已按下按钮，操作中止。"),
    ("Aborted by user", "用户已中止。"),
    ("Aborted via keyboard.", "已通过键盘中止。"),
    ("Card is not vulnerable to Darkside attack", "这张卡不适合 Darkside 攻击"),
    ("doesn't send NACK on authentication requests", "认证请求时没有返回 NACK"),
    ("its random number generator is not predictable", "随机数生成器不可预测"),
    ("debug logging on", "打开调试日志"),
    ("emulator file", "模拟器文件"),
    ("html file containing card data", "包含卡片数据的 HTML 文件"),
    ("keys are dumped here", "密钥会保存在这里"),
    ("card data in binary form", "二进制形式的卡片数据"),
    ("This file is volatile", "这个文件会被其它命令覆盖"),
    ("as other commands overwrite it sometimes", "因为其它命令有时会覆盖它"),
    ("available commands", "可用命令"),
    ("Syntax error", "语法错误"),
    ("Invalid command", "命令格式不正确"),
    ("Invalid option", "选项不正确"),
    ("No tag found", "没有发现卡片"),
    ("No card found", "没有发现卡片"),
    ("No tag is found", "没有发现卡片"),
    ("Waiting for card", "正在等待放卡"),
    ("Press pm3-button to abort", "按 PM3 按钮可中止"),
    ("aborted via keyboard!", "已通过键盘中止。"),
    ("aborted", "已中止"),
    ("Authentication failed. Card timeout.", "认证失败：卡片超时。"),
    ("Auth error", "认证错误"),
    ("WRITE BLOCK FINISHED", "写块完成"),
    ("READ BLOCK FINISHED", "读块完成"),
    ("Successfully read block", "成功读取块"),
    ("of sector", "所属扇区"),
    ("Dumping all blocks to file...", "正在把整卡数据保存到文件..."),
    ("Dumped", "已转储"),
    ("Done", "完成"),
    ("done", "完成"),
    ("success", "成功"),
    ("Success", "成功"),
    ("failed", "失败"),
    ("Failed", "失败"),
    ("Reading", "正在读取"),
    ("reading", "正在读取"),
    ("Writing", "正在写入"),
    ("writing", "正在写入"),
    ("Dumping", "正在转储"),
    ("saving", "正在保存"),
    ("Saved", "已保存"),
    ("loaded", "已载入"),
    ("Loaded", "已载入"),
    ("not found", "未找到"),
    ("timeout", "超时"),
    ("Timeout", "超时"),
    ("key file", "密钥文件"),
    ("dictionary", "字典"),
    ("sector", "扇区"),
    ("Sector", "扇区"),
    ("blocks", "块"),
    ("block", "块"),
    ("Block", "块"),
    ("this help", "显示这段帮助"),
    ("all sectors based on card memory, other values then below defaults to 1k", "按卡片容量扫描全部扇区；其它值默认按 1K 处理"),
    ("write keys to binary file", "把找到的密钥写入二进制文件"),
    ("write keys to emulator memory", "把找到的密钥写入模拟器内存"),
    ("target block", "目标块"),
    ("target all blocks", "目标全部块"),
    ("all keys", "A/B 所有密钥"),
    ("write to emul", "写入模拟器内存"),
    ("write to file", "写入文件"),
    ("to file", "到文件"),
    ("Key A", "A 密钥"),
    ("Key B", "B 密钥"),
    ("block number", "块号"),
    ("card memory", "卡片容量"),
    ("key type", "密钥类型"),
    ("12 hex symbols", "12 位十六进制"),
    ("binary file", "二进制文件"),
    ("emulator memory", "模拟器内存"),
    ("bytes", "字节"),
    ("Ping successful", "通信测试成功"),
    ("Memory", "内存"),
    ("BIGBUF_SIZE", "大缓冲区大小"),
    ("Available memory", "可用内存"),
    ("Tracing", "采样记录"),
    ("tracing", "记录开关"),
    ("traceLen", "记录长度"),
    ("Currently loaded FPGA image", "当前加载的 FPGA 镜像"),
    ("Smart card module (ISO 7816)", "智能卡模块（ISO 7816）"),
    ("version", "版本"),
    ("FAILED", "失败"),
    ("LF Sampling config", "低频采样配置"),
    ("USB Speed", "USB 速度"),
    ("Sending USB packets to client", "正在向客户端发送 USB 数据包"),
    ("Time elapsed", "耗时"),
    ("Bytes transferred", "已传输字节"),
    ("USB Transfer Speed PM3 -> Client", "PM3 到客户端传输速度"),
    ("Various", "其它信息"),
    ("ERROR: cannot communicate with the Proxmark3", "错误：无法与 Proxmark3 通信"),
    ("cannot communicate with the Proxmark3", "无法与 Proxmark3 通信"),
    ("Tag Information", "卡片信息"),
    ("Valid ISO14443-A Tag Found - Quiting Search", "已发现有效的 ISO14443-A 卡，停止搜索。"),
    ("Valid ISO14443-A Tag Found - Quitting Search", "已发现有效的 ISO14443-A 卡，停止搜索。"),
    ("proprietary non iso14443-4 card found, RATS not supported", "发现非 ISO14443-4 的私有协议卡，RATS 不支持。"),
    ("halt error. response len:", "停止卡片通信时返回异常，响应长度："),
    ("No chinese magic backdoor command detected", "没有检测到国产魔术卡后门指令。"),
    ("Answers to chinese magic backdoor commands", "国产魔术卡后门指令回应"),
    ("Answers to magic commands", "魔术卡指令回应"),
    ("Prng detection", "随机数检测"),
    ("Static nonce", "固定随机数"),
    ("weak prng", "弱随机数"),
    ("Strong PRNG", "强随机数"),
    ("Valid ISO14443-A tag found", "已发现有效的 ISO14443-A 卡"),
    ("Card doesn't support standard iso14443-3 anticollision", "卡片不支持标准 ISO14443-3 防冲突流程"),
    ("RATS not supported", "不支持 RATS"),
    ("MIFARE Classic", "MIFARE Classic"),
    ("MIFARE CLASSIC", "MIFARE Classic"),
    ("Plus 2k SL1", "MIFARE Plus 2K 安全等级 SL1"),
    ("1k Ev1", "1K EV1"),
    ("NDEF Message", "NDEF 信息"),
    ("Tag Signature", "卡片签名"),
    ("Tag Version", "卡片版本"),
    ("Tag Configuration", "卡片配置"),
    ("Found a default password", "发现默认密码"),
    ("Measuring antenna characteristics, please wait...", "正在检测天线，请稍等..."),
    ("# Your LF antenna is unusable.", "低频天线不可用或没有检测到有效低频天线。"),
    ("# Your HF antenna is unusable.", "高频天线不可用或没有检测到有效高频天线。"),
    ("iso14443a card select failed", "没有选中 13.56MHz 高频卡"),
    ("Can't select card", "没有选中卡片"),
    ("No response from tag", "卡片没有回应"),
    ("Could not read file dumpdata.eml", "没有找到模拟器数据文件 dumpdata.eml"),
    ("Could not detect modulation automatically.", "无法自动检测低频调制方式。"),
    ("Try setting it manually with 'lf t55xx config'", "可在低频 T55xx 配置里手动设置。"),
    ("Wrote a HTML dump to the file", "已导出 HTML 报告文件"),
    ("No known/supported 13.56 MHz tags found", "没有发现已支持的 13.56MHz 高频卡"),
    ("no known/supported 13.56 MHz tags found", "没有发现已支持的 13.56MHz 高频卡"),
    ("timeout while waiting for reply.", "等待设备回复超时。"),
    ("unknown command::", "未知命令："),
    ("No data found", "没有读取到数据"),
    ("Could not find file dumpkeys.bin", "没有找到密钥文件 dumpkeys.bin"),
    ("Could not find file dumpdata.bin", "没有找到数据文件 dumpdata.bin"),
    ("Restoring dumpdata.bin to card", "正在把 dumpdata.bin 写入卡片"),
    ("Writing to block", "正在写入块"),
    ("Command execute timeout", "命令执行超时"),
    ("Collecting", "正在采集"),
    ("nonces", "随机数"),
    ("Total nonces", "已采集随机数"),
    ("time:", "耗时："),
    ("Testing block", "正在测试块"),
    ("keytype", "密钥类型"),
    ("Found tag", "发现卡片"),
    ("mfkeys - Total execution time:", "MFKeys 总耗时："),
)

OUTPUT_VALUE_TRANSLATIONS = {
    "YES": "是",
    "NO": "否",
    "WEAK": "弱，说明这张卡的随机数较弱，可继续做密钥分析",
    "STRONG": "强，常规旧方法不一定有效",
    "UNKNOWN": "未知",
    "true": "是",
    "false": "否",
}

COMMAND_HELP_TRANSLATIONS = {
    "help": "显示帮助",
    "dbg": "设置默认调试模式",
    "rdbl": "读取 Mifare Classic 指定块",
    "rdsc": "读取 Mifare Classic 指定扇区",
    "dump": "把 Mifare Classic 卡片转储为二进制文件",
    "restore": "把 Mifare Classic 二进制文件写入空白卡",
    "wrbl": "写入 Mifare Classic 指定块",
    "chk": "检查/扫描密钥",
    "mifare": "Darkside 攻击，读取校验错误信息",
    "nested": "Nested 攻击，测试嵌套认证",
    "hardnested": "针对加固 Mifare 卡的 Hardnested 攻击",
    "keybrute": "多扇区 Nested 恢复密钥的第二阶段",
    "sniff": "嗅探卡片和读卡器通信",
    "sim": "模拟 Mifare 卡片",
    "eclr": "清除模拟器内存块",
    "eget": "读取模拟器内存块",
    "eset": "设置模拟器内存块",
    "eload": "从文件加载模拟器转储",
    "esave": "把模拟器转储保存到文件",
    "ecfill": "根据模拟器里的密钥填充模拟器内存",
    "ekeyprn": "打印模拟器内存中的密钥",
    "csetuid": "设置国产魔术卡 UID",
    "csetblk": "写入国产魔术卡指定块",
    "cgetblk": "读取国产魔术卡指定块",
    "cgetsc": "读取国产魔术卡指定扇区",
    "cload": "把转储写入国产魔术卡",
    "csave": "把国产魔术卡数据保存到文件或模拟器",
    "decrypt": "解密嗅探或 trace 数据，参数为 [nt] [ar_enc] [at_enc] [data]",
    "setmod": "设置 Mifare Classic EV1 负载调制强度",
    "ice": "采集 Mifare Classic nonce 到文件",
}


def decode_process(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("gb18030", errors="replace")


def clean_legacy_output(text: str, command: str) -> str:
    ignored = {
        command.strip(),
        "quit",
        "pm3 -->",
    }
    cleaned: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line in ignored:
            continue
        if line.startswith("Num of args:") or line.startswith("using 'scripting' commands file"):
            continue
        if line.startswith("#db#"):
            line = line[4:].strip()
        cleaned.append(line)
    localized = add_usage_guidance(command, localize_output("\n".join(cleaned).strip()))
    if command.strip().lower() == "hf search" and "没有发现已支持的 13.56MHz 高频卡" in localized:
        localized = "\n".join(
            line
            for line in localized.splitlines()
            if "等待设备回复超时" not in line and "未知命令： 0x03bc" not in line
        ).strip()
    return localized


def localize_output(text: str) -> str:
    localized = "\n".join(localize_output_line(line) for line in text.splitlines())
    for source, target in OUTPUT_TRANSLATIONS:
        localized = localized.replace(source, target)
    return localized


def add_usage_guidance(command: str, text: str) -> str:
    if "用法：" not in text and not looks_like_command_help(text):
        return text
    command_hint = command.strip()
    hints = {
        "hf mf chk": "默认密钥扫描需要指定卡容量和要扫描的密钥类型，例如 1K 卡常用：hf mf chk *1 ? d。",
        "hf mf nested": "知一密求全密需要先知道至少一个扇区密钥，再指定块号、密钥类型和密钥。",
        "hf mf hardnested": "Hardnested 需要卡片在天线上，并通常要先有一个已知密钥。",
        "hf mf darkside": "PRNG/暗面分析需要卡片在天线上，并且只适用于随机数较弱的部分 Mifare Classic 卡。",
        "hf mf mifare": "Darkside 弱随机数分析默认尝试 0 块 Key A，只适用于部分弱随机数 Mifare Classic 卡。",
        "hf mf ice": "随机数采集需要 Mifare Classic 卡片稳定贴在高频天线上，采集结果会保存为 nonces.bin。",
        "hf mf autopwn": "一键解析需要 Mifare Classic 卡片在天线上，程序会尝试自动扫描密钥并保存转储。",
        "hf mf restore": "整卡写入需要先导入 dumpdata.bin 和 dumpkeys.bin，并打开「允许危险操作」。",
        "hf mf csetuid": "改 UID 需要可改 UID/CUID/FUID/UFUID 类型卡，并且需要明确目标 UID。",
        "hf mf cwipe": "初始化/擦卡是危险操作，需要确认卡类型并打开「允许危险操作」。",
        "hf mf dump": "保存卡片数据需要卡片在天线上，并通常需要已知密钥或先完成密钥扫描。",
        "hf mf sim": "Mifare 模拟需要先准备模拟器数据。",
        "hf 14a sim": "14A 模拟需要指定模拟参数或准备好的数据。",
        "hf mfu dump": "NTAG/Ultralight 转储需要卡片在天线上，并确认卡片不是 Mifare Classic。",
        "hf mfu info": "NTAG/Ultralight 识别需要卡片在天线上。",
        "hf iclass reader": "iCLASS 搜索需要 iCLASS 卡片在高频天线上。",
        "lf hid read": "HID 低频读取需要把低频卡放在低频天线上。",
        "lf indala read": "Indala 低频读取需要把低频卡放在低频天线上。",
        "lf em 410x_read": "EM410x 读取需要把 125K 低频卡放在低频天线上。",
        "lf em 410xsim": "EM410x 模拟需要指定要模拟的卡号或先准备模拟数据。",
        "lf hid sim": "HID 模拟需要指定要模拟的 HID 卡号。",
        "lf t55xx detect": "T55xx 检测需要把 T55xx 卡放在低频天线上。",
        "lf t55xx config": "T55xx 配置需要先检测卡片调制参数，必要时手动指定。",
        "lf t55xx dump": "T55xx 转储需要卡片在低频天线上，并且参数识别正确。",
        "lf t55xx write": "T55xx 写入需要指定块号和数据，属于危险操作。",
        "script run mfkeys": "MFKeys 脚本会调用默认密钥库逐扇区测试；图形客户端优先使用内置扫描流程，避免脚本交互卡住。",
    }
    hint = next((message for prefix, message in hints.items() if command_hint.startswith(prefix)), "")
    if not hint:
        hint = "底层返回的是命令用法，说明这个功能还需要更多参数、卡片上下文或数据文件。"
    return f"这个功能还需要补充信息。\n{hint}\n\n{text}"


def looks_like_command_help(text: str) -> bool:
    hits = 0
    for line in text.splitlines():
        command = line.split(maxsplit=1)[0] if line.split() else ""
        if command in COMMAND_HELP_TRANSLATIONS:
            hits += 1
    return hits >= 5


def localize_output_line(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return line

    ok_match = re.match(r"^isOk\s*:\s*([0-9A-Fa-f]{2})$", stripped)
    if ok_match:
        code = ok_match.group(1).upper()
        result = "成功" if code != "00" else "失败"
        return f"执行结果：{result}（{code}）"

    usage_line = localize_usage_line(stripped)
    if usage_line:
        return usage_line

    normalized = re.sub(r"\s+", " ", stripped)
    colon_match = re.match(r"^([A-Za-z][A-Za-z0-9_ /().-]*?)\s*:\s*(.*)$", normalized)
    if colon_match:
        key = colon_match.group(1).strip()
        value = colon_match.group(2).strip()
        translated_value = OUTPUT_VALUE_TRANSLATIONS.get(value, value)
        key_map = {
            "UID": "卡片 UID",
            "ATQA": "ATQA 防冲突参数",
            "SAK": "SAK 选择应答",
            "TYPE": "卡片类型",
            "Prng detection": "随机数检测",
            "Static nonce": "固定随机数",
            "Answers to magic commands (GEN 1a)": "魔术卡指令回应（GEN 1a）",
            "Answers to magic commands": "魔术卡指令回应",
            "Answers to chinese magic backdoor commands": "国产魔术卡后门指令回应",
            "Card memory": "卡片容量",
            "Block count": "块数量",
            "File size": "文件大小",
            "Password": "密码",
            "Pack": "PACK 校验值",
        }
        if key in key_map:
            return f"{key_map[key]}：{translated_value}"

    if normalized.startswith("UID "):
        return "卡片 UID：" + normalized[4:].strip()
    if normalized.startswith("ATQA "):
        return "ATQA 防冲突参数：" + normalized[5:].strip()
    if normalized.startswith("SAK "):
        return "SAK 选择应答：" + normalized[4:].strip()
    if normalized.startswith("TYPE "):
        return "卡片类型：" + normalized[5:].strip()
    return line


def localize_usage_line(line: str) -> str:
    normalized = line.strip()
    if normalized.lower().startswith("usage:"):
        body = normalized.split(":", 1)[1].strip()
        body = localize_usage_placeholders(body)
        return f"用法：{body}"
    if normalized.lower() == "options:":
        return "选项："
    if normalized.lower() in {"samples:", "examples:"}:
        return "示例："

    command_match = re.match(r"^([a-z][a-z0-9_-]*)\s{2,}(.+)$", normalized)
    if command_match and command_match.group(1) in COMMAND_HELP_TRANSLATIONS:
        return f"{command_match.group(1)}    {COMMAND_HELP_TRANSLATIONS[command_match.group(1)]}"

    option_match = re.match(r"^([*a-zA-Z0-9?|-]+(?:\s+-\s+[A-Za-z0-9(). ]+)?)\s{2,}(.+)$", normalized)
    if option_match:
        option = option_match.group(1).strip()
        desc = localize_usage_description(option_match.group(2).strip())
        return f"{option}    {desc}"

    sample_match = re.match(r"^(hf\s+.+?)\s+--\s+(.+)$", normalized)
    if sample_match:
        command = localize_usage_placeholders(sample_match.group(1).strip())
        desc = localize_usage_description(sample_match.group(2).strip())
        return f"{command}    -- {desc}"

    if normalized.startswith("hf ") or normalized.startswith("lf ") or normalized.startswith("hw "):
        return localize_usage_placeholders(normalized)
    return ""


def localize_usage_placeholders(text: str) -> str:
    replacements = (
        ("<block number>|<*card memory>", "<块号>|<*卡片容量>"),
        ("<key type (A/B/?)>", "<密钥类型（A/B/?）>"),
        ("[<key (12 hex symbols)>]", "[<密钥（12 位十六进制）>]"),
        ("[<dic (*.dic)>]", "[<字典文件 (*.dic)>]"),
        ("MINI(320 bytes)", "MINI（320 字节）"),
        ("(320 bytes)", "（320 字节）"),
    )
    localized = text
    for source, target in replacements:
        localized = localized.replace(source, target)
    return localized


def localize_usage_description(text: str) -> str:
    replacements = (
        ("this help", "显示这段帮助"),
        ("all sectors based on card memory, other values then below defaults to 1k", "按卡片容量扫描全部扇区；其它值默认按 1K 处理"),
        ("write keys to binary file", "把找到的密钥写入二进制文件"),
        ("write keys to emulator memory", "把找到的密钥写入模拟器内存"),
        ("target block", "目标块"),
        ("target all blocks", "目标全部块"),
        ("all keys", "A/B 所有密钥"),
        ("write to emul", "写入模拟器内存"),
        ("write to file", "写入文件"),
        ("Key A", "A 密钥"),
        ("Key B", "B 密钥"),
        ("MINI(320 bytes)", "MINI（320 字节）"),
    )
    localized = text
    for source, target in replacements:
        localized = localized.replace(source, target)
    return localized


def apply_macos_window_style(window: object) -> None:
    # Use the normal macOS titlebar for reliable native dragging.
    return
    if sys.platform != "darwin":
        return

    try:
        objc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.A.dylib")
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.sel_registerName.restype = ctypes.c_void_p

        def selector(name: str) -> ctypes.c_void_p:
            return ctypes.c_void_p(objc.sel_registerName(name.encode("utf-8")))

        def msg_id(receiver: int, name: str) -> int:
            objc.objc_msgSend.restype = ctypes.c_void_p
            objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            return int(objc.objc_msgSend(ctypes.c_void_p(receiver), selector(name)) or 0)

        def msg_ulong(receiver: int, name: str) -> int:
            objc.objc_msgSend.restype = ctypes.c_ulong
            objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            return int(objc.objc_msgSend(ctypes.c_void_p(receiver), selector(name)))

        def send_bool(receiver: int, name: str, value: bool) -> None:
            objc.objc_msgSend.restype = None
            objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool]
            objc.objc_msgSend(ctypes.c_void_p(receiver), selector(name), ctypes.c_bool(value))

        def send_long(receiver: int, name: str, value: int) -> None:
            objc.objc_msgSend.restype = None
            objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]
            objc.objc_msgSend(ctypes.c_void_p(receiver), selector(name), ctypes.c_long(value))

        def send_ulong(receiver: int, name: str, value: int) -> None:
            objc.objc_msgSend.restype = None
            objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
            objc.objc_msgSend(ctypes.c_void_p(receiver), selector(name), ctypes.c_ulong(value))

        native_view = int(window.winId())
        native_window = msg_id(native_view, "window")
        if not native_window:
            return

        full_size_content_view = 1 << 15
        hidden_title = 1
        style_mask = msg_ulong(native_window, "styleMask")
        send_ulong(native_window, "setStyleMask:", style_mask | full_size_content_view)
        send_bool(native_window, "setTitlebarAppearsTransparent:", True)
        send_long(native_window, "setTitleVisibility:", hidden_title)
        send_bool(native_window, "setMovableByWindowBackground:", False)
    except Exception:
        # If the private macOS bridge fails, keep the normal native titlebar.
        return


class Backend(QObject):
    portsChanged = Signal()
    selectedPortChanged = Signal()
    logTextChanged = Signal()
    statusTextChanged = Signal()
    deviceTextChanged = Signal()
    firmwareTextChanged = Signal()
    integrityTextChanged = Signal()
    dictionaryTextChanged = Signal()
    keyLibraryTextChanged = Signal()
    scriptTextChanged = Signal()
    selectedDataFileChanged = Signal()
    cardReadDataTextChanged = Signal()
    cardReadBlocksChanged = Signal()
    selectedCardReadBlockChanged = Signal()
    dataWorkspaceTextChanged = Signal()
    dataBlocksChanged = Signal()
    selectedDataBlockChanged = Signal()
    keyMatrixChanged = Signal()
    writePlanTextChanged = Signal()
    cardCapabilityTextChanged = Signal()
    writeTransactionTextChanged = Signal()
    busyChanged = Signal()
    lastCommandChanged = Signal()
    progressTextChanged = Signal()

    commandFinished = Signal(str, str, bool, str)

    def __init__(self) -> None:
        super().__init__()
        self._ensure_workspace_layout()
        self._migrate_legacy_workspace()
        self._workspace_state = self._read_json_file(WORKSPACE_STATE_FILE)
        self._write_transaction = self._read_json_file(WORKSPACE_TRANSACTION_FILE)
        if self._write_transaction.get("status") in {"preflight", "backing_up", "writing", "verifying"}:
            self._write_transaction["status"] = "interrupted"
            self._write_transaction["detail"] = "检测到上次操作没有正常结束；重新执行智能写入会按差异继续。"
            self._write_json_file(WORKSPACE_TRANSACTION_FILE, self._write_transaction)
        self._card_capability = dict(self._workspace_state.get("last_card") or {})
        self._card_capability_text = self._format_card_capability_text(self._card_capability)
        self._write_transaction_text = self._format_transaction_text(self._write_transaction)
        self._ports: list[str] = []
        self._selected_port = ""
        self._log_text = "PM3 Native 已准备好。先点「读取设备版本」。"
        self._status_text = "待检测"
        self._device_text = "未连接"
        self._firmware_text = "未知"
        self._integrity_text = self._verify_integrity_manifest()
        self._ensure_key_library_db()
        self._key_library_text = self._build_key_library_summary()
        self._dictionary_text = self._build_dictionary_summary()
        self._script_text = self._build_script_summary()
        self._selected_data_file = ""
        self._card_read_file = ""
        self._card_read_data_text = "还没有读取卡片数据"
        self._card_read_blocks = self._empty_data_blocks()
        self._selected_card_read_block_index = 0
        self._data_workspace_text = "未导入待写入数据"
        self._data_blocks = self._empty_data_blocks()
        self._selected_data_block_index = 0
        self._key_matrix = self._read_workspace_key_matrix()
        self._write_plan_text = "还没有可写入的数据"
        self._prepared_write_command = ""
        self._pending_data_file = ""
        self._busy = False
        self._cancel_requested = False
        self._current_process: subprocess.Popen[bytes] | None = None
        self._process_lock = threading.Lock()
        self._last_command = "等待操作"
        self._progress_text = ""
        self._command_started_at = 0.0
        self.commandFinished.connect(self._handle_command_finished)
        if any(
            row.get("knownA") or row.get("knownB") or row.get("candidateA") or row.get("candidateB")
            for row in self._key_matrix
        ):
            self._activate_runtime_keys(self._key_matrix)
        self._secure_runtime_artifacts()
        self.refreshPorts()
        self._load_existing_workspace_snapshot()
        self._sync_selected_data_block()

    @Property("QVariantList", notify=portsChanged)
    def ports(self) -> list[str]:
        return self._ports

    @Property(str, notify=selectedPortChanged)
    def selectedPort(self) -> str:
        return self._selected_port

    @selectedPort.setter
    def selectedPort(self, value: str) -> None:
        if self._selected_port == value:
            return
        self._selected_port = value
        self.selectedPortChanged.emit()

    @Property(str, notify=logTextChanged)
    def logText(self) -> str:
        return self._log_text

    @Property(str, notify=statusTextChanged)
    def statusText(self) -> str:
        return self._status_text

    @Property(str, notify=deviceTextChanged)
    def deviceText(self) -> str:
        return self._device_text

    @Property(str, notify=firmwareTextChanged)
    def firmwareText(self) -> str:
        return self._firmware_text

    @Property(str, notify=integrityTextChanged)
    def integrityText(self) -> str:
        return self._integrity_text

    @Property(str, constant=True)
    def appVersion(self) -> str:
        return APP_VERSION

    @Property(str, constant=True)
    def appBuild(self) -> str:
        return APP_BUILD

    @Property(str, notify=dictionaryTextChanged)
    def dictionaryText(self) -> str:
        return self._dictionary_text

    @Property(str, notify=keyLibraryTextChanged)
    def keyLibraryText(self) -> str:
        return self._key_library_text

    @Property(str, notify=scriptTextChanged)
    def scriptText(self) -> str:
        return self._script_text

    @Property(str, notify=selectedDataFileChanged)
    def selectedDataFile(self) -> str:
        return self._selected_data_file

    @Property(str, notify=cardReadDataTextChanged)
    def cardReadDataText(self) -> str:
        return self._card_read_data_text

    @Property("QVariantList", notify=cardReadBlocksChanged)
    def cardReadBlocks(self) -> list[dict[str, object]]:
        return self._card_read_blocks

    @Property(int, notify=selectedCardReadBlockChanged)
    def selectedCardReadBlockIndex(self) -> int:
        return self._selected_card_read_block_index

    @Property(str, notify=selectedCardReadBlockChanged)
    def selectedCardReadBlockLabel(self) -> str:
        row = self._selected_card_read_block_row()
        return str(row.get("label", "--"))

    @Property(str, notify=selectedCardReadBlockChanged)
    def selectedCardReadBlockValue(self) -> str:
        row = self._selected_card_read_block_row()
        return str(row.get("value", "--"))

    @Property(bool, notify=selectedCardReadBlockChanged)
    def selectedCardReadBlockIsTrailer(self) -> bool:
        return bool(self._selected_card_read_block_row().get("trailer"))

    @Property(str, notify=dataWorkspaceTextChanged)
    def dataWorkspaceText(self) -> str:
        return self._data_workspace_text

    @Property("QVariantList", notify=dataBlocksChanged)
    def dataBlocks(self) -> list[dict[str, object]]:
        return self._data_blocks

    @Property(int, notify=selectedDataBlockChanged)
    def selectedDataBlockIndex(self) -> int:
        return self._selected_data_block_index

    @Property(str, notify=selectedDataBlockChanged)
    def selectedDataBlockLabel(self) -> str:
        row = self._selected_data_block_row()
        return str(row.get("label", "--"))

    @Property(str, notify=selectedDataBlockChanged)
    def selectedDataBlockValue(self) -> str:
        row = self._selected_data_block_row()
        return str(row.get("value", "--"))

    @Property(bool, notify=selectedDataBlockChanged)
    def selectedDataBlockIsTrailer(self) -> bool:
        return bool(self._selected_data_block_row().get("trailer"))

    @Property("QVariantList", notify=keyMatrixChanged)
    def keyMatrix(self) -> list[dict[str, object]]:
        return self._key_matrix

    @Property(str, notify=writePlanTextChanged)
    def writePlanText(self) -> str:
        return self._write_plan_text

    @Property(str, notify=cardCapabilityTextChanged)
    def cardCapabilityText(self) -> str:
        return self._card_capability_text

    @Property(str, notify=writeTransactionTextChanged)
    def writeTransactionText(self) -> str:
        return self._write_transaction_text

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @Property(str, notify=lastCommandChanged)
    def lastCommand(self) -> str:
        return self._last_command

    @Property(str, notify=progressTextChanged)
    def progressText(self) -> str:
        return self._progress_text

    @Slot()
    def refreshPorts(self) -> None:
        ports = sorted(glob.glob("/dev/cu.*"))
        ports.sort(key=lambda item: (0 if "usbmodem" in item.lower() else 1, item))
        self._ports = ports
        if not self._selected_port and ports:
            self._selected_port = ports[0]
            self.selectedPortChanged.emit()
        self._device_text = "已发现串口" if ports else "未发现设备"
        self.portsChanged.emit()
        self.deviceTextChanged.emit()

    @Slot(str, str)
    def runScript(self, label: str, script_name: str) -> None:
        name = script_name.strip()
        if not name:
            return
        if name.endswith(".lua"):
            name = name[:-4]
        self.runCommand(label, f"script run {name}")

    @Slot(str, str)
    def showNotice(self, label: str, message: str) -> None:
        self._last_command = label
        self.lastCommandChanged.emit()
        self._append_log(f"{label}\n{message}")

    @Slot()
    def clearLog(self) -> None:
        self._log_text = "PM3 Native 已准备好。先点「读取设备版本」。"
        self.logTextChanged.emit()

    @Slot()
    def chooseDataFile(self) -> None:
        script = (
            'set chosenFile to choose file with prompt "请选择 IC 卡 / PM3 数据文件，例如 dumpdata.bin、dumpkeys.bin、.dump、.eml、.mfd、.json、.dic"\n'
            "POSIX path of chosenFile"
        )
        try:
            proc = subprocess.run(
                ["osascript", "-e", script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
                check=False,
            )
        except Exception as error:  # noqa: BLE001
            self._append_log(f"选择数据文件失败：{error}")
            return
        if proc.returncode != 0:
            return
        self.setDataFile(proc.stdout.strip())

    @Slot(str)
    def setDataFile(self, value: str) -> None:
        path = self._normalize_local_path(value)
        if not path.exists():
            self._append_log(f"没有找到数据文件：{path}")
            return
        if not self._is_supported_card_file(path):
            self._append_log(
                "这个文件不像 IC 卡 / PM3 数据文件，已拒绝导入。\n"
                "目前支持：dumpdata.bin、dumpkeys.bin、Mifare/NTAG 的 .dump、.bin、.eml、.mfd、.json、.dic。"
            )
            return
        previous_file = self._selected_data_file
        previous_text = self._data_workspace_text
        self._selected_data_file = str(path)
        self._data_workspace_text = f"已选择：{path.name}"
        self.selectedDataFileChanged.emit()
        self.dataWorkspaceTextChanged.emit()
        self._append_log(f"已选择数据文件：{path}\n正在自动载入并生成预览。")
        if not self.loadSelectedDataToWorkspace():
            self._selected_data_file = previous_file
            self._data_workspace_text = previous_text
            self.selectedDataFileChanged.emit()
            self.dataWorkspaceTextChanged.emit()

    @Slot(result=bool)
    def loadSelectedDataToWorkspace(self) -> bool:
        if not self._selected_data_file:
            self._append_log("请先选择数据文件。")
            return False
        path = Path(self._selected_data_file)
        if not path.exists():
            self._append_log(f"数据文件不存在：{path}")
            return False

        try:
            command, note, blocks = self._prepare_data_file(path)
        except Exception as error:  # noqa: BLE001
            self._append_log(f"载入数据失败：{error}")
            return False

        self._prepared_write_command = command
        self._pending_data_file = str(WORKSPACE_PENDING_DATA) if WORKSPACE_PENDING_DATA.exists() else ""
        self._data_workspace_text = note
        self._data_blocks = blocks or self._empty_data_blocks()
        self._key_matrix = self._read_workspace_key_matrix()
        self._sync_selected_data_block()
        self._write_plan_text = (
            self._pending_write_plan(WORKSPACE_PENDING_DATA.read_bytes())
            if WORKSPACE_PENDING_DATA.exists()
            else self._friendly_write_plan(command)
        )
        self.dataWorkspaceTextChanged.emit()
        self.dataBlocksChanged.emit()
        self.selectedDataBlockChanged.emit()
        self.keyMatrixChanged.emit()
        self.writePlanTextChanged.emit()
        self._persist_workspace_state()
        self._append_log(f"数据已载入工作区。\n{note}\n{self._write_plan_text}")
        return True

    @Slot(int)
    def selectDataBlock(self, index: int) -> None:
        if index < 0 or index >= len(self._data_blocks):
            return
        self._selected_data_block_index = index
        self.selectedDataBlockChanged.emit()

    @Slot(int)
    def selectCardReadBlock(self, index: int) -> None:
        if index < 0 or index >= len(self._card_read_blocks):
            return
        self._selected_card_read_block_index = index
        self.selectedCardReadBlockChanged.emit()

    @Slot()
    def copyCardReadToPendingWrite(self) -> None:
        data = self._blocks_to_bytes(self._card_read_blocks)
        if not data:
            self._append_log("复制失败：左侧还没有读到完整卡片数据。")
            return
        pending_path = WORKSPACE_PENDING_DATA
        try:
            pending_path.write_bytes(data)
        except OSError as error:
            self._append_log(f"复制失败：无法写入待写入缓存。\n{error}")
            return
        self._pending_data_file = str(pending_path)
        self._selected_data_file = "来自左侧读卡数据"
        source_matrix = self._matrix_from_dump_bytes(data, trusted=True)
        if source_matrix:
            self._save_key_store("source", source_matrix, "复制自左侧读卡数据")
            self._activate_runtime_keys()
        self._data_blocks = [dict(row) for row in self._card_read_blocks]
        self._sync_selected_data_block()
        block_count = len([row for row in self._data_blocks if row.get("value") != "--"])
        self._data_workspace_text = f"待写入：来自左侧读卡数据（{block_count} 块）"
        if any(row.get("knownA") or row.get("knownB") for row in self._read_workspace_key_matrix()):
            self._prepared_write_command = self._restore_command_for_dump(pending_path)
            self._write_plan_text = self._pending_write_plan(data)
        else:
            self._prepared_write_command = ""
            self._write_plan_text = "仅预览：还缺 dumpkeys.bin"
        self.selectedDataFileChanged.emit()
        self.dataBlocksChanged.emit()
        self.selectedDataBlockChanged.emit()
        self.dataWorkspaceTextChanged.emit()
        self.writePlanTextChanged.emit()
        self._persist_workspace_state()
        self._append_log("已把左侧读卡数据复制到右侧待写入区。")

    @Slot(str)
    def exportCardReadData(self, format_name: str) -> None:
        key = self._normalize_export_format(format_name)
        if not key:
            self._append_log("导出失败：请选择有效的数据格式。")
            return
        data = self._blocks_to_bytes(self._card_read_blocks)
        if not data:
            self._append_log("导出失败：左侧还没有读到完整卡片数据。")
            return
        target = self._choose_export_path(key)
        if target is None:
            return
        try:
            self._write_export_file(key, target, data, "左侧读卡数据")
        except Exception as error:  # noqa: BLE001
            self._append_log(f"导出失败：{error}")
            return
        self._append_log(f"导出成功：{target}\n格式：{key.upper()}\n来源：左侧读卡数据")

    @Slot()
    def clearCardReadData(self) -> None:
        for path in (WORKSPACE_READ_DATA, COMPAT_CLIENT.parent / "dumpdata.bin"):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass
        self._card_read_file = ""
        self._card_read_data_text = "已清空读卡数据"
        self._card_read_blocks = self._empty_data_blocks()
        self._selected_card_read_block_index = 0
        self.cardReadDataTextChanged.emit()
        self.cardReadBlocksChanged.emit()
        self.selectedCardReadBlockChanged.emit()
        self._persist_workspace_state()
        self._append_log("左侧读卡数据已清空。")

    @Slot()
    def clearPendingWriteData(self) -> None:
        self._selected_data_file = ""
        self._pending_data_file = ""
        self._data_workspace_text = "未导入待写入数据"
        self._data_blocks = self._empty_data_blocks()
        self._selected_data_block_index = 0
        self._prepared_write_command = ""
        self._write_plan_text = "还没有可写入的数据"
        self._discard_pending_write_target(clear_source=True)
        self._key_matrix = self._read_workspace_key_matrix()
        self._activate_runtime_keys(self._key_matrix)
        self.keyMatrixChanged.emit()
        self.selectedDataFileChanged.emit()
        self.dataWorkspaceTextChanged.emit()
        self.dataBlocksChanged.emit()
        self.selectedDataBlockChanged.emit()
        self.writePlanTextChanged.emit()
        self._persist_workspace_state()
        self._append_log("右侧待写入数据已清空。")

    def _discard_pending_write_target(self, clear_source: bool) -> None:
        paths = [WORKSPACE_PENDING_DATA, WORKSPACE_VERIFY_DATA]
        if clear_source:
            paths.append(self._key_store_path("source"))
        paths.extend(
            (
                COMPAT_CLIENT.parent / "selected_data.eml",
                COMPAT_CLIENT.parent / "selected_data_magic_target.bin",
                COMPAT_CLIENT.parent / "selected_data_smart_target.bin",
                COMPAT_CLIENT.parent / "pending_write_data.bin",
            )
        )
        for path in paths:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass

    @Slot(str, bool)
    def saveSelectedDataBlock(self, value: str, allow_trailer: bool) -> None:
        row = self._selected_data_block_row()
        if row.get("value") == "--":
            self._append_log("保存块失败：当前没有可编辑的卡片数据。")
            return
        if row.get("trailer") and not allow_trailer:
            self._append_log(
                "已阻止修改密钥尾块。\n"
                "尾块包含 Key A、权限控制位、Key B，误改可能导致卡读写失败。"
            )
            return

        compact = "".join(ch for ch in value.upper() if ch in "0123456789ABCDEF")
        if len(compact) != 32:
            self._append_log("保存块失败：每个块必须正好是 16 字节，也就是 32 位十六进制。")
            return

        data_path = self._current_editable_data_path()
        if data_path is None:
            self._append_log("保存块失败：右侧没有可编辑的待写入数据。请先导入整卡数据，或从左侧复制到待写入区。")
            return

        block_index = self._selected_data_block_index
        data = bytearray(data_path.read_bytes())
        start = block_index * 16
        end = start + 16
        if end > len(data):
            self._append_log("保存块失败：当前块超出文件范围。")
            return

        old_value = bytes(data[start:end]).hex(" ").upper()
        new_bytes = bytes.fromhex(compact)
        new_value = new_bytes.hex(" ").upper()
        if old_value == new_value:
            self._append_log(f"块 {row.get('label')} 没有变化，不需要保存。")
            return

        backup_path = self._backup_data_file(data_path)
        data[start:end] = new_bytes
        data_path.write_bytes(data)
        source_matrix = self._matrix_from_dump_bytes(bytes(data))
        if source_matrix:
            self._save_key_store("source", source_matrix, "编辑后的待写入数据")
            self._activate_runtime_keys()
        self._data_blocks = self._preview_blocks(data_path)
        self._sync_selected_data_block()
        self._data_workspace_text = f"已修改：块 {row.get('label')}，原文件已备份"
        self._prepared_write_command = self._restore_command_for_dump(data_path)
        self._write_plan_text = self._pending_write_plan(bytes(data))
        if block_index == 0:
            self._write_plan_text += "｜块 00 已修改，将由智能预检选择写法"
        self.dataBlocksChanged.emit()
        self.selectedDataBlockChanged.emit()
        self.dataWorkspaceTextChanged.emit()
        self.writePlanTextChanged.emit()
        self._persist_workspace_state()
        self._append_log(
            f"块 {row.get('label')} 已保存到工作区。\n"
            f"原值：{old_value}\n"
            f"新值：{new_value}\n"
            f"备份：{backup_path}"
            + (
                "\n提醒：块 00 是 UID/厂商块。普通 IC 写入会保留目标卡原 UID，只有匹配的可改 UID 卡型才能写入。"
                if block_index == 0
                else ""
            )
        )

    @Slot()
    def loadWorkspaceKeys(self) -> None:
        self._key_matrix = self._read_workspace_key_matrix()
        self.keyMatrixChanged.emit()
        known = sum(1 for row in self._key_matrix if row["knownA"] or row["knownB"])
        candidates = sum(
            1
            for row in self._key_matrix
            if (row.get("candidateA") and not row.get("knownA"))
            or (row.get("candidateB") and not row.get("knownB"))
        )
        self._append_log(f"密钥矩阵已载入：已验证 {known} 个扇区，另有 {candidates} 个扇区包含待验证候选密钥。")

    @Slot(str)
    def addPersonalKey(self, value: str) -> None:
        key = self._normalize_key_text(value)
        if not key:
            self._append_log("加入我的密钥库失败：密钥必须是 12 位十六进制，例如 FFFFFFFFFFFF。")
            return
        inserted, existing = self._add_keys_to_library([key], "personal", "手动添加", "用户手动加入")
        self._refresh_library_summaries()
        if inserted:
            self._append_log(f"已加入我的密钥库：{key}")
        else:
            self._append_log(f"我的密钥库里已经有这个密钥：{key}（重复 {existing} 条）")

    @Slot()
    def saveCurrentKeysToPersonalLibrary(self) -> None:
        keys: list[str] = []
        for row in self._key_matrix:
            for key_field, known_field in (("keyA", "knownA"), ("keyB", "knownB")):
                key = self._normalize_key_text(str(row.get(key_field, "")))
                if key and row.get(known_field):
                    keys.append(key)
        if not keys:
            self._append_log("当前密钥矩阵里还没有可保存的已知密钥。")
            return
        inserted, existing = self._add_keys_to_library(keys, "personal", "当前密钥矩阵", "从已解析卡片密钥保存")
        self._refresh_library_summaries()
        self._append_log(f"已保存当前密钥到我的密钥库：新增 {inserted} 条，已有 {existing} 条。")

    @Slot()
    def openKeyLibraryFolder(self) -> None:
        try:
            KEY_LIBRARY_DB.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["open", str(KEY_LIBRARY_DB.parent)], check=False)
            self._append_log(f"已打开本地密钥库目录：{KEY_LIBRARY_DB.parent}")
        except OSError as error:
            self._append_log(f"打开本地密钥库目录失败：{error}")

    @Slot()
    def verifyWorkspaceData(self) -> None:
        read_blocks = [row for row in self._card_read_blocks if row.get("value") and row.get("value") != "--"]
        visible_blocks = [row for row in self._data_blocks if row.get("value") and row.get("value") != "--"]
        known_key_sectors = sum(1 for row in self._key_matrix if row["knownA"] or row["knownB"])
        total_key_sectors = len(self._key_matrix)
        trailer_blocks = sum(1 for row in visible_blocks if row.get("trailer"))
        lines = ["工作区校验结果："]
        lines.append(f"左侧读卡数据：{'已读取' if read_blocks else '还没有读取'}")
        if read_blocks:
            lines.append(f"左侧已显示 {len(read_blocks)} 个块。")
        lines.append(f"右侧待写入数据：{'已准备' if visible_blocks else '还没有导入'}")
        if visible_blocks:
            lines.append(f"已预览 {len(visible_blocks)} 个块，其中 {trailer_blocks} 个是扇区尾块。")
        lines.append(f"密钥矩阵：已验证 {known_key_sectors}/{total_key_sectors} 个扇区。")
        if self._prepared_write_command:
            lines.append(f"写卡计划：已准备，可执行 {self._prepared_write_command}")
        else:
            lines.append("写卡计划：还不完整，需要先导入数据，或把左侧读卡数据复制到右侧。")
        if known_key_sectors < total_key_sectors:
            lines.append("建议：先执行「默认密钥扫描」或「一键解析」，尽量补齐全卡密钥。")
        if not visible_blocks:
            lines.append("建议：右侧导入已有 .dump/.bin/.mfd 数据，或点左侧「复制到待写入」。")
        self._append_log("\n".join(lines))

    @Slot(str)
    def exportWorkspaceData(self, format_name: str) -> None:
        key = self._normalize_export_format(format_name)
        if not key:
            self._append_log("导出失败：请选择有效的数据格式。")
            return

        try:
            data, source, partial = self._current_card_data_bytes()
        except ValueError as error:
            self._append_log(f"导出失败：{error}")
            return

        target = self._choose_export_path(key)
        if target is None:
            return

        try:
            self._write_export_file(key, target, data, source)
        except Exception as error:  # noqa: BLE001
            self._append_log(f"导出失败：{error}")
            return

        note = "注意：当前只导出了界面里已预览的数据块。" if partial else "已导出完整工作区数据。"
        self._append_log(f"导出成功：{target}\n格式：{key.upper()}\n来源：{source}\n{note}")

    @Slot()
    def saveKeyMatrix(self) -> None:
        try:
            self._save_key_store("manual", self._key_matrix, "用户在密钥矩阵中保存")
            self._activate_runtime_keys(self._key_matrix)
        except ValueError:
            self._append_log("保存密钥失败：Key A / Key B 必须是 12 位十六进制。")
            return
        self._append_log(f"密钥已保存到独立的手动密钥仓库：{self._key_store_path('manual')}")

    @Slot(bool)
    def clearKeyMatrix(self, confirmed: bool) -> None:
        if not confirmed:
            self._append_log("清空密钥会删除来源、扫描和手动密钥。请先打开右上角「允许危险操作」。")
            return
        backup_dir = WORKSPACE_BACKUP_DIR / f"keys_{time.strftime('%Y%m%d_%H%M%S')}"
        copied = False
        for name in ("source", "scanned", "manual"):
            source = self._key_store_path(name)
            if source.exists():
                backup_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, backup_dir / source.name)
                copied = True
        for name in ("source", "scanned", "manual"):
            try:
                self._key_store_path(name).unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass
        self._key_matrix = self._empty_key_matrix()
        self._activate_runtime_keys(self._key_matrix)
        self.keyMatrixChanged.emit()
        note = f"；原密钥已备份到 {backup_dir}" if copied else ""
        self._append_log(f"密钥矩阵已清空{note}。")

    @Slot(int, str, str)
    def setSectorKeys(self, sector: int, key_a: str, key_b: str) -> None:
        if sector < 0 or sector >= len(self._key_matrix):
            self._append_log("设置密钥失败：扇区编号不正确。")
            return
        key_a = self._normalize_key_text(key_a)
        key_b = self._normalize_key_text(key_b)
        if not key_a or not key_b:
            self._append_log("设置密钥失败：Key A 和 Key B 都必须是 12 位十六进制。")
            return
        manual = self._load_key_store("manual")
        if len(manual) < len(self._key_matrix):
            manual.extend(self._empty_key_matrix(len(self._key_matrix))[len(manual):])
        row = dict(manual[sector])
        row["keyA"] = key_a
        row["keyB"] = key_b
        row["knownA"] = True
        row["knownB"] = True
        row["candidateA"] = True
        row["candidateB"] = True
        manual[sector] = row
        self._save_key_store("manual", manual, "用户手动填写")
        self._key_matrix = self._read_workspace_key_matrix()
        self._activate_runtime_keys(self._key_matrix)
        self.keyMatrixChanged.emit()
        self._append_log(f"已更新扇区 {sector:02d} 的 Key A / Key B。")

    @Slot(str, str, str)
    def readMifareSector(self, sector_text: str, key_type: str, key_text: str) -> None:
        parsed = self._validate_manual_sector_inputs(sector_text, key_type, key_text)
        if parsed is None:
            return
        sector, normalized_type, key = parsed
        self.runCommand(
            f"读取扇区 {sector:02d}",
            f"hf mf rdsc {sector} {normalized_type} {key}",
        )

    @Slot(str, str, str, str)
    def readMifareBlock(self, sector_text: str, block_text: str, key_type: str, key_text: str) -> None:
        parsed = self._validate_manual_block_inputs(sector_text, block_text, key_type, key_text)
        if parsed is None:
            return
        sector, block_in_sector, absolute_block, normalized_type, key = parsed
        self.runCommand(
            f"读取扇区 {sector:02d} 的块 {block_in_sector}",
            f"hf mf rdbl {absolute_block} {normalized_type} {key}",
        )

    @Slot(bool, str, str, str, str, str)
    def writeMifareBlock(
        self,
        confirmed: bool,
        sector_text: str,
        block_text: str,
        key_type: str,
        key_text: str,
        data_text: str,
    ) -> None:
        parsed = self._validate_manual_block_inputs(sector_text, block_text, key_type, key_text)
        data = self._normalize_block_text(data_text)
        if parsed is None:
            return
        if not data:
            self._append_log("写块失败：块数据必须正好是 16 字节，也就是 32 位十六进制。")
            return
        sector, block_in_sector, absolute_block, normalized_type, key = parsed
        self.runAuthorizedCommand(
            f"写入扇区 {sector:02d} 的块 {block_in_sector}",
            f"hf mf wrbl {absolute_block} {normalized_type} {key} {data}",
            confirmed,
        )

    @Slot(bool, str, str, str, str, str, str, str)
    def writeMifareSector(
        self,
        confirmed: bool,
        sector_text: str,
        key_type: str,
        key_text: str,
        block0: str,
        block1: str,
        block2: str,
        block3: str,
    ) -> None:
        parsed = self._validate_manual_sector_inputs(sector_text, key_type, key_text)
        if parsed is None:
            return
        sector, normalized_type, key = parsed
        if sector >= 32:
            self._append_log("写扇区失败：32-39 扇区各有 16 个块，请改用高级单块操作，不能按四块扇区写入。")
            return
        blocks = [self._normalize_block_text(value) for value in (block0, block1, block2, block3)]
        if any(not value for value in blocks):
            self._append_log("写扇区失败：块0到块3都必须填写完整的 16 字节数据。")
            return
        command = " ".join(
            ["workflow", "mifare_manual_write_sector", str(sector), normalized_type, key, *blocks]
        )
        self.runAuthorizedCommand(f"写入扇区 {sector:02d}", command, confirmed)

    def _validate_manual_sector_inputs(
        self,
        sector_text: str,
        key_type: str,
        key_text: str,
    ) -> tuple[int, str, str] | None:
        try:
            sector = int(sector_text.strip(), 10)
        except ValueError:
            self._append_log("扇区编号不正确：请输入 0 到 39 的十进制数字。")
            return None
        if sector < 0 or sector > 39:
            self._append_log("扇区编号不正确：Mifare Classic 扇区范围是 0 到 39。")
            return None
        normalized_type = key_type.strip().upper()
        if normalized_type not in {"A", "B"}:
            self._append_log("密钥类型不正确：只能选择 Key A 或 Key B。")
            return None
        key = self._normalize_key_text(key_text)
        if not key:
            self._append_log("密钥格式不正确：必须是 12 位十六进制。")
            return None
        return sector, normalized_type, key

    def _validate_manual_block_inputs(
        self,
        sector_text: str,
        block_text: str,
        key_type: str,
        key_text: str,
    ) -> tuple[int, int, int, str, str] | None:
        parsed = self._validate_manual_sector_inputs(sector_text, key_type, key_text)
        if parsed is None:
            return None
        sector, normalized_type, key = parsed
        try:
            block_in_sector = int(block_text.strip(), 10)
        except ValueError:
            self._append_log("块编号不正确：请输入扇区内的十进制块号。")
            return None
        block_limit = self._blocks_per_sector(sector)
        if block_in_sector < 0 or block_in_sector >= block_limit:
            self._append_log(f"块编号不正确：扇区 {sector:02d} 的块范围是 0 到 {block_limit - 1}。")
            return None
        absolute_block = self._first_block_of_sector(sector) + block_in_sector
        return sector, block_in_sector, absolute_block, normalized_type, key

    @staticmethod
    def _normalize_block_text(value: str) -> str:
        compact = "".join(ch for ch in value.upper() if ch in "0123456789ABCDEF")
        return compact if len(compact) == 32 else ""

    @Slot(bool)
    def writeSelectedDataToCard(self, confirmed: bool) -> None:
        if not confirmed:
            self._append_log("写入卡片属于危险操作。请先打开右上角「允许危险操作」。")
            return
        if not WORKSPACE_PENDING_DATA.exists() and self._selected_data_file and Path(self._selected_data_file).exists():
            self.loadSelectedDataToWorkspace()
        if not WORKSPACE_PENDING_DATA.exists():
            self._append_log("写入失败：右侧还没有完整的待写入数据。")
            return
        self.runAuthorizedCommand("智能写入待写数据", "workflow mifare_auto_write_card", True)

    @Slot(bool)
    def writeSelectedDataToMagicCard(self, confirmed: bool) -> None:
        if not confirmed:
            self._append_log("写入魔术卡属于危险操作。请先打开右上角「允许危险操作」。")
            return
        if not self._prepare_magic_write_files():
            return
        self.runAuthorizedCommand("写整卡到魔术卡", "workflow mifare_magic_write_card", True)

    @Slot(bool)
    def rescueMagicCard(self, confirmed: bool) -> None:
        if not confirmed:
            self._append_log("坏卡救援会改写魔术卡 0 块。请先打开右上角「允许危险操作」。")
            return
        self.runAuthorizedCommand("魔术卡救援", "workflow mifare_magic_rescue", True)

    @Slot(bool, str)
    def restoreMagicCardUid(self, confirmed: bool, uid_text: str) -> None:
        if not confirmed:
            self._append_log("恢复 UID 属于危险操作。请先打开右上角「允许危险操作」。")
            return
        uid = self._normalize_uid_text(uid_text)
        if not uid:
            self._append_log("恢复 UID 失败：请输入 8 位十六进制 UID，例如 9D7456AA。")
            return
        self.runAuthorizedCommand("恢复魔术卡 UID", f"workflow mifare_magic_restore_uid {uid}", True)

    @Slot(bool, str)
    def resetMagicCardToBlank(self, confirmed: bool, uid_text: str) -> None:
        if not confirmed:
            self._append_log("初始化空白卡会清空整卡数据并恢复默认密钥。请先打开右上角「允许危险操作」。")
            return
        uid = self._normalize_uid_text(uid_text)
        if not uid:
            self._append_log("初始化失败：请输入要保留的 8 位十六进制 UID，例如 9D7456AA。")
            return
        self.runAuthorizedCommand("初始化为空白卡", f"workflow mifare_magic_blank_reset {uid}", True)

    @Slot(bool, str)
    def oneClickResetMagicCard(self, confirmed: bool, uid_text: str) -> None:
        if not confirmed:
            self._append_log("一键重置会救援并清空魔术卡。请先打开右上角「允许危险操作」。")
            return
        uid = self._normalize_uid_text(uid_text)
        if not uid:
            self._append_log("一键重置失败：请输入要保留的 8 位十六进制 UID，例如 9D7456AA。")
            return
        self.runAuthorizedCommand("一键重置", f"workflow mifare_magic_one_click_reset {uid}", True)

    @Slot()
    def openWorkspaceFolder(self) -> None:
        try:
            subprocess.run(["open", str(WORKSPACE_ROOT)], check=False)
        except OSError as error:
            self._append_log(f"打开工作区失败：{error}")

    @Slot(str, str, bool)
    def runPreset(self, label: str, command: str, danger: bool = False) -> None:
        if danger:
            self._append_log(f"危险操作已准备：{label}\n底层命令：{command}\n请先打开右上角「允许危险操作」开关再执行。")
            self._last_command = f"需要确认：{label}"
            self.lastCommandChanged.emit()
            return
        self.runCommand(label, command)

    @Slot(str, str)
    def runCommand(self, label: str, command: str) -> None:
        self._start_command(label, command, authorized=False)

    @Slot(str, str, bool)
    def runAuthorizedCommand(self, label: str, command: str, authorized: bool) -> None:
        self._start_command(label, command, authorized=authorized)

    def _start_command(self, label: str, command: str, authorized: bool) -> None:
        if self._busy:
            return
        if self._command_has_forbidden_control(command):
            self._append_log(
                "命令已拒绝：每次只能执行一条 PM3 命令，不能包含分号、换行或控制字符。"
            )
            return
        command = command.strip()
        if not command:
            return
        if self._command_requires_authorization(command) and not authorized:
            self._append_log(
                f"危险操作已锁定：{label}\n"
                "请先打开右上角「允许危险操作」，再重新执行。"
            )
            self._last_command = f"需要确认：{label}"
            self.lastCommandChanged.emit()
            return
        if (
            IS_BUNDLED_APP
            and self._integrity_text != "完整性正常"
        ):
            self._append_log(
                "设备命令已阻止：客户端核心文件未通过完整性检查。\n"
                f"当前状态：{self._integrity_text}"
            )
            return
        if not self._selected_port:
            self._append_log("还没有选择 PM3 串口。")
            return

        self._busy = True
        self._cancel_requested = False
        self._progress_text = ""
        self._status_text = f"正在执行：{label}"
        self._last_command = label
        self.busyChanged.emit()
        self.statusTextChanged.emit()
        self.lastCommandChanged.emit()
        self.progressTextChanged.emit()
        self._command_started_at = time.time()
        self._append_log(f"准备执行：{label}\n实际执行：{self._display_command(command)}")

        worker = threading.Thread(target=self._run_command_worker, args=(label, command), daemon=True)
        worker.start()

    @staticmethod
    def _command_has_forbidden_control(command: str) -> bool:
        return any(
            character == ";"
            or (
                character != "\t"
                and unicodedata.category(character) in {"Cc", "Cf", "Zl", "Zp"}
            )
            for character in command
        )

    @staticmethod
    def _command_tokens(command: str) -> tuple[str, ...]:
        if Backend._command_has_forbidden_control(command):
            return ()
        return tuple(command.casefold().split())

    @staticmethod
    def _matches_audited_read_only_script(script_name: str) -> bool:
        expected = AUDITED_READ_ONLY_SCRIPTS.get(script_name)
        if expected is None:
            return False
        expected_size, expected_digest = expected
        script_path = COMPAT_CLIENT.parent / "scripts" / f"{script_name}.lua"
        try:
            with script_path.open("rb") as handle:
                payload = handle.read(expected_size + 1)
        except OSError:
            return False
        return len(payload) == expected_size and hashlib.sha256(payload).hexdigest() == expected_digest

    @staticmethod
    def _classify_command_capability(command: str) -> str:
        """Classify one PM3 command; only proven read-only commands are exempt."""
        tokens = Backend._command_tokens(command)
        if not tokens:
            return COMMAND_CAPABILITY_RESTRICTED

        normalized = " ".join(tokens)
        if normalized in READ_ONLY_WORKFLOW_COMMANDS:
            return COMMAND_CAPABILITY_READ_ONLY
        if tokens[0] == "workflow":
            return COMMAND_CAPABILITY_CARD_MUTATION

        if tokens[:2] == ("script", "run"):
            script_name = tokens[2].removesuffix(".lua") if len(tokens) >= 3 else ""
            if len(tokens) == 3 and Backend._matches_audited_read_only_script(script_name):
                # These bundled scripts were reviewed to contain only card reads,
                # trace analysis, or local dump conversion.  Arguments are not
                # exempt because several scripts accept arbitrary output paths;
                # the digest check also fails closed if a script is replaced.
                return COMMAND_CAPABILITY_READ_ONLY
            if script_name in DANGEROUS_SCRIPT_NAMES:
                return COMMAND_CAPABILITY_DANGEROUS_SCRIPT
            # Lua can issue arbitrary PM3 commands.  Even currently benign or
            # unknown scripts therefore require the same explicit authorization.
            return COMMAND_CAPABILITY_SCRIPT

        if any(tokens[: len(prefix)] == prefix for prefix in FIRMWARE_COMMAND_PREFIXES):
            return COMMAND_CAPABILITY_FIRMWARE
        if "raw" in tokens:
            return COMMAND_CAPABILITY_RAW
        for prefix, options in EMULATOR_MUTATING_OPTIONS.items():
            if tokens[: len(prefix)] == prefix and any(
                token in options for token in tokens[len(prefix):]
            ):
                return COMMAND_CAPABILITY_EMULATION
        if tokens[:3] in {("lf", "t55xx", "read"), ("lf", "t55xx", "detect")} and any(
            token in {"p", "o"} for token in tokens[3:]
        ):
            return COMMAND_CAPABILITY_CARD_MUTATION
        if tokens[:3] == ("lf", "t55xx", "dump") and any(
            token != "h" for token in tokens[3:]
        ):
            return COMMAND_CAPABILITY_CARD_MUTATION
        if tokens[:3] == ("hf", "mfu", "dump"):
            return COMMAND_CAPABILITY_CARD_MUTATION
        if tokens[:3] in {("hf", "mfu", "info"), ("hf", "mfu", "rdbl")} and any(
            token in {"k", "l"} for token in tokens[3:]
        ):
            return COMMAND_CAPABILITY_CARD_MUTATION
        if any(token in EMULATION_OPERATION_TOKENS or token.endswith("sim") for token in tokens):
            return COMMAND_CAPABILITY_EMULATION
        if any(token in CARD_MUTATION_OPERATION_TOKENS for token in tokens):
            return COMMAND_CAPABILITY_CARD_MUTATION

        if tokens in READ_ONLY_EXACT_COMMANDS:
            return COMMAND_CAPABILITY_READ_ONLY
        if tokens[:3] == ("hf", "mfu", "info") and tokens[3:] in {(), ("h",)}:
            return COMMAND_CAPABILITY_READ_ONLY
        if tokens[:3] == ("hf", "mfu", "rdbl"):
            arguments = tokens[3:]
            if arguments == ("h",) or (
                len(arguments) == 2
                and arguments[0] == "b"
                and arguments[1].isdecimal()
            ):
                return COMMAND_CAPABILITY_READ_ONLY
        if any(tokens[: len(prefix)] == prefix for prefix in READ_ONLY_COMMAND_PREFIXES):
            return COMMAND_CAPABILITY_READ_ONLY

        # Unknown commands are deliberately restricted.  This makes the policy
        # fail closed when the bundled PM3 client gains a new mutating command.
        return COMMAND_CAPABILITY_RESTRICTED

    @staticmethod
    def _command_requires_authorization(command: str) -> bool:
        return Backend._classify_command_capability(command) != COMMAND_CAPABILITY_READ_ONLY

    @Slot()
    def stopCurrentCommand(self) -> None:
        if not self._busy:
            self._append_log("当前没有正在执行的操作。")
            return

        self._cancel_requested = True
        self._progress_text = ""
        self._status_text = "正在终止"
        self.statusTextChanged.emit()
        self.progressTextChanged.emit()
        self._append_log("已请求终止当前操作，正在让 PM3 内核停止。")

        with self._process_lock:
            proc = self._current_process
        if proc is None or proc.poll() is not None:
            return

        threading.Thread(target=self._terminate_process, args=(proc,), daemon=True).start()

    @Slot()
    def shutdown(self) -> None:
        self._cancel_requested = True
        with self._process_lock:
            proc = self._current_process
        self._terminate_process(proc)
        self._cleanup_runtime_artifacts(include_keys=True)

    @staticmethod
    def _secure_runtime_artifacts() -> None:
        for name in RUNTIME_SENSITIVE_NAMES:
            path = COMPAT_CLIENT.parent / name
            if path.exists():
                try:
                    path.chmod(0o600)
                except OSError:
                    pass

    @staticmethod
    def _cleanup_runtime_artifacts(include_keys: bool = False) -> None:
        names = set(RUNTIME_SENSITIVE_NAMES)
        if not include_keys:
            names.discard("dumpkeys.bin")
            names.discard("dumpkeys-status.json")
        for name in names:
            try:
                (COMPAT_CLIENT.parent / name).unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass
        for pattern in ("pm3_localdict_*.dic", "pm3_my_key_library.dic"):
            for path in COMPAT_CLIENT.parent.glob(pattern):
                try:
                    path.unlink()
                except OSError:
                    pass

    def _run_command_worker(self, label: str, command: str) -> None:
        write_workflow = self._is_write_workflow_command(command)
        try:
            if command == "hw version":
                output = self._read_legacy_version()
            elif command == "workflow mifare_classic_autopwn":
                output = self._run_mifare_classic_workflow()
            elif command == "workflow mifare_classic_local_dict":
                output = self._run_local_dictionary_workflow()
            elif command == "workflow mifare_default_key_scan":
                output = self._run_default_key_scan_workflow()
            elif command == "workflow mifare_classic_nested_missing":
                output = self._run_nested_missing_workflow()
            elif command == "workflow mifare_classic_hardnested_missing":
                output = self._run_hardnested_missing_workflow()
            elif command == "workflow mifare_nonce_collect":
                output = self._run_nonce_collect_workflow()
            elif command == "workflow mifare_mfkeys_recover":
                output = self._run_mfkeys_recover_workflow()
            elif command == "workflow mifare_nonce_assist":
                output = self._run_nonce_assist_workflow()
            elif command == "workflow mifare_plus_inspect":
                output = self._run_mifare_plus_inspect_workflow()
            elif command == "workflow mifare_auto_write_card":
                output = self._run_auto_write_workflow()
            elif command == "workflow mifare_magic_write_card":
                output = self._run_magic_write_workflow()
            elif command == "workflow mifare_smart_write_card":
                output = self._run_smart_write_workflow()
            elif command == "workflow mifare_magic_rescue":
                output = self._run_magic_rescue_workflow()
            elif command.startswith("workflow mifare_magic_restore_uid "):
                output = self._run_magic_restore_uid_workflow(command.rsplit(" ", 1)[-1])
            elif command.startswith("workflow mifare_magic_blank_reset "):
                output = self._run_magic_blank_reset_workflow(command.rsplit(" ", 1)[-1])
            elif command.startswith("workflow mifare_magic_one_click_reset "):
                output = self._run_magic_one_click_reset_workflow(command.rsplit(" ", 1)[-1])
            elif command.startswith("workflow mifare_manual_write_sector "):
                output = self._run_manual_sector_write_workflow(command)
            else:
                output = self._run_compat_client(command)
            ok = bool(output.strip()) and not self._output_indicates_failure(output)
            if write_workflow:
                verified = "【结果：成功】" in output
                if verified:
                    self._update_write_transaction("completed", "读回数据与冻结目标完全一致。", verified=True)
                elif "【结果：部分完成】" in output:
                    self._update_write_transaction("failed", "普通数据已写入，但块 00/UID 与目标不同。", verified=False)
                elif not ok:
                    self._update_write_transaction("failed", "写入流程没有通过完整校验。", verified=False)
        except CommandCancelled:
            self._close_raw_field()
            self._update_write_transaction("cancelled", "用户终止了当前操作；再次智能写入会重新比较差异。")
            output = "操作已由用户终止。"
            ok = False
        except Exception as error:  # noqa: BLE001
            output = str(error)
            ok = False
            if write_workflow:
                self._update_write_transaction(
                    "failed",
                    f"写入流程异常停止：{error}",
                    verified=False,
                )
        self.commandFinished.emit(label, output, ok, command)

    @staticmethod
    def _is_write_workflow_command(command: str) -> bool:
        return command in {
            "workflow mifare_auto_write_card",
            "workflow mifare_magic_write_card",
            "workflow mifare_smart_write_card",
            "workflow mifare_magic_rescue",
        } or command.startswith(
            (
                "workflow mifare_magic_restore_uid ",
                "workflow mifare_magic_blank_reset ",
                "workflow mifare_magic_one_click_reset ",
                "workflow mifare_manual_write_sector ",
            )
        )

    @staticmethod
    def _output_indicates_failure(output: str) -> bool:
        markers = (
            "【结果：失败】",
            "流程停止：",
            "这个功能还需要补充信息。",
            "用法：",
            "命令执行超过",
            "执行结果：失败",
            "未知命令：",
            "认证失败",
            "认证错误",
            "写块错误",
            "读取块错误",
            "ERROR:",
            "[!!]",
        )
        return any(marker in output for marker in markers)

    @Slot(str, str, bool, str)
    def _handle_command_finished(self, label: str, output: str, ok: bool, command: str) -> None:
        was_cancelled = "用户终止" in output
        self._busy = False
        self._cancel_requested = False
        self._progress_text = ""
        self._status_text = "完成" if ok else "已终止" if was_cancelled else "失败"
        key_rows = {} if command == "workflow mifare_classic_local_dict" else self._extract_key_scan_rows(output) if ok else {}
        if key_rows:
            self._write_key_status_rows(key_rows)
        if ok and label == "读取设备版本":
            first = next((line.strip() for line in output.splitlines() if line.strip()), "已通信")
            self._device_text = first[:80]
            self._firmware_text = self._extract_firmware_text(output)
            self.deviceTextChanged.emit()
            self.firmwareTextChanged.emit()
        if ok and command.strip().lower() == "hf search":
            self._mark_card_identified_only(output)
            self._set_card_capability(self._classify_card_capability(output))
        if ok and (
            command in {
                "workflow mifare_classic_autopwn",
                "workflow mifare_classic_local_dict",
                "workflow mifare_default_key_scan",
                "workflow mifare_classic_nested_missing",
                "workflow mifare_classic_hardnested_missing",
                "workflow mifare_nonce_collect",
                "workflow mifare_mfkeys_recover",
                "workflow mifare_nonce_assist",
                "workflow mifare_auto_write_card",
                "workflow mifare_smart_write_card",
                "workflow mifare_magic_write_card",
                "workflow mifare_magic_blank_reset",
            }
            or command.startswith("workflow mifare_magic_blank_reset")
            or command.startswith("workflow mifare_magic_one_click_reset")
            or command.startswith("hf mf chk")
            or command.startswith("hf mf dump")
            or command.startswith("hf mf nested")
            or command.startswith("hf mf hardnested")
        ):
            self._refresh_workspace_from_pm3_files(command)
        if command in {"workflow mifare_auto_write_card", "workflow mifare_smart_write_card", "workflow mifare_magic_write_card"}:
            self._update_write_plan_from_result(output)
        if key_rows:
            self._apply_key_scan_rows(key_rows)
        self.busyChanged.emit()
        self.statusTextChanged.emit()
        self.progressTextChanged.emit()
        finished_text = "执行完成" if ok else "执行已终止" if was_cancelled else "执行失败"
        self._append_log(finished_text + f"：{label}\n{output}")
        self._cleanup_runtime_artifacts(include_keys=False)

    def _update_write_plan_from_result(self, output: str) -> None:
        summary = self._write_result_summary(output)
        if summary and summary != self._write_plan_text:
            self._write_plan_text = summary
            self.writePlanTextChanged.emit()

    @staticmethod
    def _write_result_summary(output: str) -> str:
        if "【结果：成功】" in output and "64/64" in output:
            return "写入结果：64/64 块已读回校验，目标完全一致"
        if "【结果：部分完成】" in output:
            return "写入结果：普通数据已完成，但 UID/厂商块与目标不同"
        if "唯一未改变的是块 00" in output or "仅 UID 未修改" in output:
            counts = re.search(r"其余\s+(\d+)/(\d+)\s+个块", output)
            count_text = f"{counts.group(1)}/{counts.group(2)} 块一致；" if counts else ""
            return f"写入结果：{count_text}仅 UID/厂商块 00 未修改"
        if "64/64" in output and "完全一致" in output:
            return "写入结果：64/64 块完全一致"
        if "wupC1 error" in output or "GEN1A 后门未打开" in output:
            return "写入结果：GEN1A 后门未打开；块 00 / UID 未修改"
        mismatch = re.search(r"(?:仍有|共)\s*(\d+)\s*个块(?:和待写入数据)?不一致", output)
        if mismatch:
            return f"写入结果：仍有 {mismatch.group(1)} 个块不一致，请查看执行记录"
        return ""

    def _append_log(self, text: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self._log_text = f"{self._log_text}\n\n[{stamp}] {text}".strip()
        lines = self._log_text.splitlines()
        if len(lines) > 900:
            self._log_text = "\n".join(lines[-900:])
        self.logTextChanged.emit()

    @staticmethod
    def _terminal_progress_bar(current: int, total: int, width: int = 18) -> str:
        total = max(1, total)
        current = max(0, min(current, total))
        filled = round(width * current / total)
        percent = round(current * 100 / total)
        return f"[{'█' * filled}{'░' * (width - filled)}] {percent:>3}%"

    def _emit_task_progress(self, task: str, current: int, total: int, detail: str = "") -> None:
        line = f"{task} {self._terminal_progress_bar(current, total)}"
        if detail:
            line = f"{line}  {detail}"
        self._progress_text = line
        self.progressTextChanged.emit()

    def _read_legacy_version(self) -> str:
        packet = struct.pack("<Q", CMD_VERSION) + bytes(LEGACY_PACKET_SIZE - 8)
        with serial.Serial(self._selected_port, baudrate=9600, timeout=0, write_timeout=2) as port:
            port.reset_input_buffer()
            port.reset_output_buffer()
            port.write(packet)
            data = bytearray()
            deadline = time.time() + 4
            last_data = time.time()
            while time.time() < deadline:
                if self._cancel_requested:
                    raise CommandCancelled()
                chunk = port.read(4096)
                if chunk:
                    data.extend(chunk)
                    last_data = time.time()
                elif data and time.time() - last_data > 0.6:
                    break
                else:
                    time.sleep(0.04)

        if not data:
            raise RuntimeError("设备没有回应。")
        payload = bytes(data[16:]).rstrip(b"\x00")
        text = payload.decode("gb18030", errors="replace").strip()
        return f"{localize_output(text)}\n\n兼容模式：PM3 Easy / 兼容短帧协议\n原始回包：{len(data)} 字节"

    @staticmethod
    def _display_command(command: str) -> str:
        if command == "workflow mifare_classic_autopwn":
            return "内置流程：Mifare Classic 一键解析"
        if command == "workflow mifare_classic_local_dict":
            return "内置流程：本地撞库"
        if command == "workflow mifare_default_key_scan":
            return "内置流程：按卡片容量扫描默认密钥"
        if command == "workflow mifare_classic_nested_missing":
            return "内置流程：继续破解缺失扇区（Nested）"
        if command == "workflow mifare_classic_hardnested_missing":
            return "内置流程：强力破解缺失扇区（Hardnested）"
        if command == "workflow mifare_nonce_collect":
            return "内置流程：采集随机数"
        if command == "workflow mifare_mfkeys_recover":
            return "内置流程：MFKeys 默认库恢复"
        if command == "workflow mifare_nonce_assist":
            return "内置流程：辅助分析一键流程"
        if command == "workflow mifare_plus_inspect":
            return "内置流程：MIFARE Plus 只读识别"
        if command == "workflow mifare_magic_write_card":
            return "内置流程：魔术卡后门整卡写入并校验"
        if command == "workflow mifare_smart_write_card":
            return "内置流程：普通 IC 智能写卡并校验"
        if command == "workflow mifare_magic_rescue":
            return "内置流程：魔术卡坏卡救援"
        if command.startswith("workflow mifare_magic_restore_uid "):
            return "内置流程：恢复魔术卡 UID"
        if command.startswith("workflow mifare_magic_blank_reset "):
            return "内置流程：初始化为空白卡"
        if command.startswith("workflow mifare_magic_one_click_reset "):
            return "内置流程：一键重置魔术卡"
        return command

    def _run_mifare_plus_inspect_workflow(self) -> str:
        command = "hf search"
        search_output = self._run_compat_client(command)
        assessment = self._classify_mifare_plus_search_output(search_output)
        sections = [f"【1 只读搜索】\n实际执行：{command}\n{search_output}"]
        safety_note = (
            "安全边界：本流程只执行 hf search；未调用 mifarePlus.lua，也未发送 raw、认证、"
            "proximity、personalization 或任何写入命令。"
        )

        kind = str(assessment["kind"])
        if kind == "no_card":
            sections.append(
                "【2 MIFARE Plus 判断】\n"
                "【结果：失败】\n"
                "流程停止：没有识别到卡片。请把卡片稳定放在高频天线上再试。\n"
                + safety_note
            )
            return "\n\n".join(sections)

        uid = str(assessment["uid_display"] or "未从搜索输出提取")
        sak = str(assessment["sak"] or "未提供")
        card_type = str(assessment["card_type"] or "搜索输出未提供明确类型")
        if kind == "not_plus":
            sections.append(
                "【2 MIFARE Plus 判断】\n"
                "【结果：失败】\n"
                "流程停止：已识别到卡片，但现有搜索结果没有 MIFARE Plus 类型线索。\n"
                f"UID：{uid}\nSAK：{sak}\n卡片类型：{card_type}\n"
                + safety_note
            )
            return "\n\n".join(sections)

        certainty = "候选类型" if kind == "possible_plus" else "已识别"
        caution = (
            "搜索类型同时列出 Classic/DESFire/JCOP 等候选，因此只能确认“可能是 Plus”，不能据此认证卡型。"
            if kind == "possible_plus"
            else "搜索输出明确包含 MIFARE Plus；本流程仍不进行密钥认证。"
        )
        sections.append(
            "【2 MIFARE Plus 判断】\n"
            "【结果：成功】\n"
            f"判断：{certainty} MIFARE Plus。\n"
            f"UID：{uid}\nSAK：{sak}\n卡片类型：{card_type}\n"
            f"可能安全级别：{assessment['security_level']}\n"
            f"判断说明：{caution}\n"
            "能力限制：SL3/AES 深度认证与数据访问仍因当前固件能力未开放。\n"
            + safety_note
        )
        return "\n\n".join(sections)

    @staticmethod
    def _classify_mifare_plus_search_output(search_output: str) -> dict[str, str]:
        uid = Backend._extract_uid_from_search_output(search_output)
        sak = Backend._extract_sak_from_search_output(search_output)
        card_type = Backend._extract_card_type_from_search_output(search_output)
        uid_display = " ".join(uid[index:index + 2] for index in range(0, len(uid), 2)) if uid else ""
        if Backend._output_has_no_card(search_output):
            return {
                "kind": "no_card",
                "uid": uid,
                "uid_display": uid_display,
                "sak": sak,
                "card_type": card_type,
                "security_level": "未确认",
            }

        plus_line = next(
            (
                line.strip()
                for line in search_output.splitlines()
                if "mifare plus" in line.casefold()
                or re.search(r"\bplus\s+(?:2k|4k|sl\s*[0-3])\b", line, re.IGNORECASE)
            ),
            "",
        )
        if not plus_line:
            return {
                "kind": "not_plus",
                "uid": uid,
                "uid_display": uid_display,
                "sak": sak,
                "card_type": card_type,
                "security_level": "未确认",
            }

        lower_line = plus_line.casefold()
        ambiguous_markers = ("|", "classic", "desfire", "jcop")
        kind = "possible_plus" if any(marker in lower_line for marker in ambiguous_markers) else "plus"
        level_match = re.search(r"\bSL\s*([0-3])\b", plus_line, re.IGNORECASE)
        if not level_match:
            level_match = re.search(r"安全等级\s*(?:SL\s*)?([0-3])", plus_line, re.IGNORECASE)
        if level_match:
            level = f"SL{level_match.group(1)}（搜索类型明确标注，未做密钥认证）"
        else:
            sak_hints = {"08": "SL1", "18": "SL1", "10": "SL2", "11": "SL2", "20": "SL3"}
            hint = sak_hints.get(sak)
            level = (
                f"{hint} 候选（仅依据兼容内核的 SAK 类型表，未做密钥认证）"
                if hint
                else "未确认（搜索输出未标注，不能仅凭现有信息推断）"
            )
        return {
            "kind": kind,
            "uid": uid,
            "uid_display": uid_display,
            "sak": sak,
            "card_type": card_type or plus_line,
            "security_level": level,
        }

    def _run_default_key_scan_workflow(self) -> str:
        search_output = self._run_compat_client("hf search")
        sections = [f"【1 识别卡片】\n{search_output}"]
        if self._output_has_no_card(search_output):
            sections.append("流程停止：没有识别到卡片。")
            return "\n\n".join(sections)
        if not self._output_is_mifare_classic(search_output):
            sections.append("流程停止：当前卡片不是支持默认密钥扫描的 Mifare Classic。")
            return "\n\n".join(sections)
        memory_arg = self._card_memory_arg_from_search_output(search_output)
        command = f"hf mf chk *{memory_arg} ? d"
        output = self._run_compat_client(command)
        sections.append(f"【2 默认密钥扫描】\n卡片容量参数：*{memory_arg}\n实际执行：{command}\n{output}")
        return "\n\n".join(sections)

    def _run_mifare_classic_workflow(self) -> str:
        sections: list[str] = [
            "内置一键解析流程已启动。",
            "流程：识别卡片 → 默认密钥扫描 → 读取整卡 → 刷新工作区。",
            "说明：不再调用会误判按键中止的 mifare_autopwn.lua。",
        ]

        search_output = self._run_compat_client("hf search")
        sections.append(f"【1 识别卡片】\n{search_output}")
        if any(text in search_output for text in ("没有发现", "没有选中", "卡片没有回应")):
            sections.append("流程已停止：没有识别到可继续解析的高频卡。请把卡贴近天线后再试。")
            return "\n\n".join(sections)
        if "Mifare Classic" not in search_output and "MIFARE Classic" not in search_output:
            sections.append("流程已停止：当前识别结果不像 Mifare Classic。请改用对应卡型页面处理。")
            return "\n\n".join(sections)

        memory_arg = self._card_memory_arg_from_search_output(search_output)
        key_output = self._run_compat_client(f"hf mf chk *{memory_arg} ? d")
        sections.append(f"【2 默认密钥扫描】\n{key_output}")

        dump_output = self._run_compat_client("hf mf dump")
        sections.append(f"【3 读取整卡】\n{dump_output}")
        sections.append(
            "流程结束：如果读取整卡成功，工作区会自动刷新卡片数据和密钥矩阵。\n"
            "如果仍然缺密钥，请继续使用 Nested / Hardnested，或在密钥矩阵里手动补充已知 Key A / Key B。"
        )
        return "\n\n".join(sections)

    def _run_local_dictionary_workflow(self) -> str:
        sections: list[str] = [
            "本地撞库已启动。",
            "流程：识别卡片 → 优先匹配 UID 专属字典 → 继续尝试本机默认库/扩展库 → 刷新密钥矩阵。",
            "说明：这是离线功能，只使用本机随包字典，不会联网；它只读卡和试密钥，不会写卡。",
        ]

        self._emit_task_progress("本地撞库", 0, 5, "准备识别卡片")
        search_output = self._run_compat_client("hf search")
        self._emit_task_progress("本地撞库", 1, 5, "卡片识别完成")
        sections.append(f"【1 识别卡片】\n{search_output}")
        if any(text in search_output for text in ("没有发现", "没有选中", "卡片没有回应")):
            self._emit_task_progress("本地撞库", 5, 5, "已停止：没有识别到卡片")
            sections.append("流程已停止：没有识别到可继续分析的高频卡。请把卡贴近天线后再试。")
            return "\n\n".join(sections)
        if "Mifare Classic" not in search_output and "MIFARE Classic" not in search_output:
            self._emit_task_progress("本地撞库", 5, 5, "已停止：不是 Mifare Classic")
            sections.append("流程已停止：本地撞库目前主要用于 Mifare Classic/S50/S70 这类 IC 卡。")
            return "\n\n".join(sections)

        uid = self._extract_uid_from_search_output(search_output)
        memory_arg = self._card_memory_arg_from_search_output(search_output)
        candidates = self._local_dictionary_candidates(uid)
        if not candidates:
            self._emit_task_progress("本地撞库", 5, 5, "已停止：没有可用字典")
            sections.append("流程已停止：没有找到可用的本地密钥字典。请先确认本地资源包里的 keys/default_keys 文件还在。")
            return "\n\n".join(sections)

        progress_total = len(candidates) + 4
        self._emit_task_progress("本地撞库", 2, progress_total, f"找到 {len(candidates)} 个本地字典")

        uid_text = uid or "未识别到 UID"
        sections.append(
            "【2 准备本地字典】\n"
            f"卡片 UID：{uid_text}\n"
            f"卡容量参数：*{memory_arg}（1 表示常见 S50/1K）\n"
            "将按“UID 专属库 → 临时库 → 扩展库 → 默认库”的顺序尝试。"
        )

        matrix = self._read_workspace_key_matrix()
        for index, (label, source_path) in enumerate(candidates, start=1):
            if not self._missing_key_targets(matrix):
                self._emit_task_progress("本地撞库", progress_total - 1, progress_total, "密钥已补齐，跳过剩余字典")
                sections.append("密钥已经没有缺口了，后面的字典不用再试。")
                break

            try:
                dictionary_name = self._prepare_dictionary_for_pm3(source_path, index)
            except OSError as error:
                self._emit_task_progress("本地撞库", 2 + index, progress_total, f"跳过 {label}")
                sections.append(f"【跳过 {label}】\n复制字典失败：{error}")
                continue

            line_count = self._count_nonempty_lines(source_path)
            command = f"hf mf chk *{memory_arg} ? d {dictionary_name}"
            self._emit_task_progress("本地撞库", 2 + index, progress_total, f"正在尝试：{label}（约 {line_count} 条）")
            sections.append(
                f"【{index + 2} {label}】\n"
                f"字典文件：{source_path.name}（约 {line_count} 条）\n"
                f"实际执行：{command}"
            )
            output = self._run_compat_client(command)
            sections.append(output)

            rows = self._extract_key_scan_rows(output)
            if rows:
                self._write_key_status_rows(rows)
            incoming = self._read_workspace_key_matrix()
            matrix = self._merge_key_matrices(matrix, incoming)
            self._key_matrix = matrix
            self._activate_runtime_keys(matrix)
            sections.append(self._key_progress_summary(matrix))

        self._key_matrix = matrix
        self._activate_runtime_keys(matrix)
        if not self._missing_key_targets(matrix):
            self._emit_task_progress("本地撞库", progress_total - 1, progress_total, "密钥已补齐，正在读取整卡")
            dump_output = self._run_compat_client("hf mf dump")
            self._emit_task_progress("本地撞库", progress_total, progress_total, "完成：整卡数据已读取")
            sections.append(f"【读取整卡】\n密钥已尽量补齐，开始读取整卡数据。\n{dump_output}")
        else:
            self._emit_task_progress("本地撞库", progress_total, progress_total, "完成：仍有密钥缺口")
            sections.append(
                "本地撞库结束：仍然有密钥缺口。\n"
                "下一步建议：先点「继续破解」做 Nested；如果还缺，再点「强力破解」做 Hardnested。"
            )
        return "\n\n".join(sections)

    @staticmethod
    def _ensure_workspace_layout() -> None:
        APP_SUPPORT_ROOT.mkdir(parents=True, exist_ok=True)
        try:
            APP_SUPPORT_ROOT.chmod(0o700)
        except OSError:
            pass
        for directory in (
            WORKSPACE_READ_DATA.parent,
            WORKSPACE_PENDING_DATA.parent,
            WORKSPACE_VERIFY_DATA.parent,
            WORKSPACE_BACKUP_DIR,
            WORKSPACE_KEY_DIR,
            WORKSPACE_ANALYSIS_DIR,
        ):
            directory.mkdir(parents=True, exist_ok=True)
            try:
                directory.chmod(0o700)
            except OSError:
                pass
        try:
            WORKSPACE_ROOT.chmod(0o700)
        except OSError:
            pass
        for path in WORKSPACE_ROOT.rglob("*"):
            try:
                path.chmod(0o700 if path.is_dir() else 0o600)
            except OSError:
                pass

    @staticmethod
    def _read_json_file(path: Path) -> dict[str, object]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _write_json_file(path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            temporary.chmod(0o600)
        except OSError:
            pass
        temporary.replace(path)
        try:
            path.chmod(0o600)
        except OSError:
            pass

    def _migrate_legacy_workspace(self) -> None:
        state = self._read_json_file(WORKSPACE_STATE_FILE)
        if state.get("storage_version") == 2:
            return

        legacy_data = COMPAT_CLIENT.parent / "dumpdata.bin"
        if legacy_data.exists() and not WORKSPACE_READ_DATA.exists():
            shutil.copy2(legacy_data, WORKSPACE_READ_DATA)

        candidates = [
            COMPAT_CLIENT.parent / "selected_data_magic_target.bin",
            COMPAT_CLIENT.parent / "selected_data_smart_target.bin",
            COMPAT_CLIENT.parent / "pending_write_data.bin",
        ]
        candidates = [path for path in candidates if path.exists() and path.stat().st_size in {320, 1024, 2048, 4096}]
        if candidates and not WORKSPACE_PENDING_DATA.exists():
            newest = max(candidates, key=lambda path: path.stat().st_mtime)
            shutil.copy2(newest, WORKSPACE_PENDING_DATA)
            state["pending_source"] = f"从旧工作区恢复：{newest.name}"

        if WORKSPACE_PENDING_DATA.exists():
            target_data = WORKSPACE_PENDING_DATA.read_bytes()
            source_matrix = self._matrix_from_dump_bytes(target_data)
            if source_matrix:
                self._save_key_store("source", source_matrix, "待写入数据的扇区尾块")
            if WORKSPACE_READ_DATA.exists() and WORKSPACE_READ_DATA.read_bytes() == target_data:
                shutil.copy2(WORKSPACE_READ_DATA, WORKSPACE_VERIFY_DATA)

        legacy_matrix = self._read_legacy_key_matrix()
        if any(row.get("knownA") or row.get("knownB") for row in legacy_matrix):
            self._save_key_store("scanned", legacy_matrix, "旧版工作区迁移")

        state.update(
            {
                "storage_version": 2,
                "migrated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        self._write_json_file(WORKSPACE_STATE_FILE, state)

    def _persist_workspace_state(self) -> None:
        state = dict(self._workspace_state)
        state.update(
            {
                "storage_version": 2,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "read_data": str(WORKSPACE_READ_DATA) if WORKSPACE_READ_DATA.exists() else "",
                "pending_data": str(WORKSPACE_PENDING_DATA) if WORKSPACE_PENDING_DATA.exists() else "",
                "verify_data": str(WORKSPACE_VERIFY_DATA) if WORKSPACE_VERIFY_DATA.exists() else "",
                "pending_source": self._selected_data_file,
                "last_card": self._card_capability,
            }
        )
        self._workspace_state = state
        self._write_json_file(WORKSPACE_STATE_FILE, state)

    @staticmethod
    def _pending_write_plan(data: bytes) -> str:
        if not data or len(data) % 16:
            return "待写入数据格式不完整"
        uid = data[:4].hex(" ").upper() if len(data) >= 4 else "未知"
        digest = hashlib.sha256(data).hexdigest()[:10].upper()
        return f"目标 {len(data) // 16} 块｜UID {uid}｜校验 {digest}｜等待智能预检"

    def _load_existing_workspace_snapshot(self) -> None:
        if WORKSPACE_READ_DATA.exists():
            self._set_card_read_snapshot(WORKSPACE_READ_DATA, "已恢复上次读卡数据")

        if WORKSPACE_PENDING_DATA.exists():
            data = WORKSPACE_PENDING_DATA.read_bytes()
            self._pending_data_file = str(WORKSPACE_PENDING_DATA)
            source = str(self._workspace_state.get("pending_source") or "")
            self._selected_data_file = source if source else str(WORKSPACE_PENDING_DATA)
            self._data_blocks = self._preview_blocks(WORKSPACE_PENDING_DATA)
            self._sync_selected_data_block()
            self._prepared_write_command = self._restore_command_for_dump(WORKSPACE_PENDING_DATA)
            self._data_workspace_text = f"已恢复待写入数据：{len(data) // 16} 块"
            self._write_plan_text = self._pending_write_plan(data)
        elif WORKSPACE_READ_DATA.exists():
            self._data_workspace_text = "未导入待写入数据"
            self._write_plan_text = "可点「复制到待写入」使用左侧读卡数据"

    def _selected_card_read_block_row(self) -> dict[str, object]:
        if not self._card_read_blocks:
            return {"label": "--", "value": "--", "trailer": False}
        index = max(0, min(self._selected_card_read_block_index, len(self._card_read_blocks) - 1))
        return self._card_read_blocks[index]

    def _sync_selected_card_read_block(self) -> None:
        if not self._card_read_blocks:
            self._selected_card_read_block_index = 0
            return
        self._selected_card_read_block_index = max(
            0,
            min(self._selected_card_read_block_index, len(self._card_read_blocks) - 1),
        )

    def _set_card_read_snapshot(self, data_path: Path, prefix: str = "已读取卡片数据") -> None:
        snapshot_path = data_path
        try:
            if data_path.resolve() != WORKSPACE_READ_DATA.resolve():
                WORKSPACE_READ_DATA.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(data_path, WORKSPACE_READ_DATA)
                snapshot_path = WORKSPACE_READ_DATA
        except OSError:
            snapshot_path = data_path
        self._card_read_file = str(snapshot_path)
        self._card_read_blocks = self._preview_blocks(snapshot_path)
        block_count = len([row for row in self._card_read_blocks if row.get("value") != "--"])
        self._sync_selected_card_read_block()
        self._card_read_data_text = f"{prefix}：{snapshot_path.name}（{block_count} 块）"
        self._persist_workspace_state()

    def _mark_card_identified_only(self, output: str) -> None:
        uid = self._extract_uid_from_search_output(output)
        card_type = self._extract_card_type_from_search_output(output)
        parts = []
        if uid:
            spaced_uid = " ".join(uid[index:index + 2] for index in range(0, len(uid), 2))
            parts.append(f"UID {spaced_uid}")
        if card_type:
            parts.append(card_type)
        summary = "；".join(parts) if parts else "已识别卡片"
        self._card_read_file = ""
        self._card_read_blocks = self._empty_data_blocks()
        self._selected_card_read_block_index = 0
        self._card_read_data_text = f"{summary}；还没有读出扇区数据"
        self.cardReadDataTextChanged.emit()
        self.cardReadBlocksChanged.emit()
        self.selectedCardReadBlockChanged.emit()

    def _selected_data_block_row(self) -> dict[str, object]:
        if not self._data_blocks:
            return {"label": "--", "value": "--", "trailer": False}
        index = max(0, min(self._selected_data_block_index, len(self._data_blocks) - 1))
        return self._data_blocks[index]

    def _sync_selected_data_block(self) -> None:
        if not self._data_blocks:
            self._selected_data_block_index = 0
            return
        self._selected_data_block_index = max(0, min(self._selected_data_block_index, len(self._data_blocks) - 1))

    def _current_editable_data_path(self) -> Path | None:
        if self._pending_data_file:
            pending = Path(self._pending_data_file)
            if pending.exists():
                return pending
        return None

    @staticmethod
    def _backup_data_file(path: Path) -> Path:
        backup_dir = path.parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        backup_path = backup_dir / f"{path.stem}_{time.strftime('%Y%m%d_%H%M%S')}{path.suffix or '.bin'}"
        shutil.copy2(path, backup_path)
        return backup_path

    def _run_nested_missing_workflow(self) -> str:
        sections: list[str] = [
            "继续破解缺失扇区已启动。",
            "流程：重新扫描默认密钥 → 找一个已知密钥 → 自动执行 Nested → 成功后尝试读取整卡。",
        ]

        initial_matrix = self._read_workspace_key_matrix()
        scan_memory = self._card_memory_arg_from_matrix(initial_matrix)
        scan_output = self._run_compat_client(f"hf mf chk *{scan_memory} ? d")
        sections.append(f"【1 确认当前密钥状态】\n{scan_output}")
        self._write_key_status_rows(self._extract_key_scan_rows(scan_output))

        matrix = self._read_workspace_key_matrix()
        known = self._known_key_candidates(matrix)
        missing = self._missing_key_targets(matrix)
        sections.append(self._key_progress_summary(matrix))

        if not known:
            sections.append(
                "流程停止：现在还没有任何一个可确认的已知密钥。\n"
                "建议：先确认卡片贴紧天线；如果默认密钥扫不到，可以尝试「强力破解缺失扇区」。"
            )
            return "\n\n".join(sections)
        if not missing:
            dump_output = self._run_compat_client("hf mf dump")
            sections.append(f"【2 密钥已足够，直接读取整卡】\n{dump_output}")
            return "\n\n".join(sections)

        source = known[0]
        memory_arg = self._card_memory_arg_from_matrix(matrix)
        nested_command = f"hf mf nested {memory_arg} {source['block']} {source['type']} {source['key']} d"
        sections.append(
            "【2 自动选择已知密钥】\n"
            f"使用扇区 {source['sector']:02d} 的 Key {source['type']} 作为起点。\n"
            f"目标：尝试补齐全卡缺失密钥。\n"
            f"实际执行：{nested_command}"
        )

        nested_output = self._run_compat_client(nested_command)
        sections.append(f"【3 Nested 继续破解】\n{nested_output}")
        self._write_key_status_rows(self._extract_key_scan_rows(nested_output))

        matrix = self._read_workspace_key_matrix()
        sections.append(self._key_progress_summary(matrix))
        if not self._missing_key_targets(matrix):
            dump_output = self._run_compat_client("hf mf dump")
            sections.append(f"【4 密钥已补齐，读取整卡】\n{dump_output}")
        else:
            sections.append(
                "Nested 后仍有缺失密钥。\n"
                "下一步：点「强力破解缺失扇区」，程序会自动选第一个缺失 Key 做 Hardnested。"
            )
        return "\n\n".join(sections)

    def _run_hardnested_missing_workflow(self) -> str:
        sections: list[str] = [
            "强力破解缺失扇区已启动。",
            "说明：Hardnested 可能比较慢；本客户端一次只处理一个缺失 Key，便于观察结果。",
        ]

        matrix = self._read_workspace_key_matrix()
        if not self._known_key_candidates(matrix) or not self._missing_key_targets(matrix):
            scan_memory = self._card_memory_arg_from_matrix(matrix)
            scan_output = self._run_compat_client(f"hf mf chk *{scan_memory} ? d")
            sections.append(f"【1 重新确认密钥状态】\n{scan_output}")
            self._write_key_status_rows(self._extract_key_scan_rows(scan_output))
            matrix = self._read_workspace_key_matrix()

        known = self._known_key_candidates(matrix)
        missing = self._missing_key_targets(matrix)
        sections.append(self._key_progress_summary(matrix))

        if not known:
            sections.append(
                "流程停止：Hardnested 也需要至少一个已知密钥作为起点。\n"
                "目前一个确认可用的 Key A / Key B 都没有。"
            )
            return "\n\n".join(sections)
        if not missing:
            sections.append("密钥已经没有缺口了，可以直接点「读取整卡」。")
            return "\n\n".join(sections)

        source = known[0]
        target = missing[0]
        hard_command = (
            f"hf mf hardnested {source['block']} {source['type']} {source['key']} "
            f"{target['block']} {target['type']}"
        )
        sections.append(
            "【2 自动选择目标】\n"
            f"已知起点：扇区 {source['sector']:02d} Key {source['type']}。\n"
            f"本次目标：扇区 {target['sector']:02d} Key {target['type']}。\n"
            f"实际执行：{hard_command}"
        )

        hard_output = self._run_compat_client(hard_command)
        sections.append(f"【3 Hardnested 强力破解】\n{hard_output}")

        found_key = self._extract_found_key_from_hardnested(hard_output)
        if found_key:
            self._set_workspace_key(target["sector"], target["type"], found_key)
            sections.append(
                "【4 已写入密钥矩阵】\n"
                f"找到扇区 {target['sector']:02d} 的 Key {target['type']}：{found_key}。\n"
                "可以继续点「强力破解缺失扇区」处理下一个缺口，或点「读取整卡」测试能否读出数据。"
            )
        else:
            sections.append(
                "【4 本次没有提取到新密钥】\n"
                "可能原因：卡片距离不稳、已知起点不适合、目标 Key 较难，或命令超时。\n"
                "可以保持卡片不动再试一次。"
            )
        return "\n\n".join(sections)

    def _run_nonce_collect_workflow(self) -> str:
        sections: list[str] = [
            "随机数采集已启动。",
            "用途：把 Mifare Classic 的随机数记录保存到本地 nonces.bin，后续可辅助 Hardnested 或其它分析。",
            "说明：这个流程只读和采集，不会写卡。",
        ]

        self._emit_task_progress("采集随机数", 0, 4, "准备识别卡片")
        search_output = self._run_compat_client("hf search")
        self._emit_task_progress("采集随机数", 1, 4, "卡片识别完成")
        sections.append(f"【1 识别卡片】\n{search_output}")
        if self._output_has_no_card(search_output):
            self._emit_task_progress("采集随机数", 4, 4, "已停止：没有识别到卡片")
            sections.append("流程已停止：没有识别到卡片。请把卡稳定贴在高频天线上再试。")
            return "\n\n".join(sections)
        if not self._output_is_mifare_classic(search_output):
            self._emit_task_progress("采集随机数", 4, 4, "已停止：不是 Mifare Classic")
            sections.append("流程已停止：随机数采集目前只面向 Mifare Classic / S50 / S70。")
            return "\n\n".join(sections)

        nonce_path = COMPAT_CLIENT.parent / "nonces.bin"
        try:
            nonce_path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass

        self._emit_task_progress("采集随机数", 2, 4, "正在采集 nonces.bin")
        collect_output = self._run_compat_client("hf mf ice 3000")
        sections.append(f"【2 采集随机数】\n{collect_output}")

        self._emit_task_progress("采集随机数", 3, 4, "正在读取高频记录")
        trace_output = self._run_compat_client("hf list")
        sections.append(f"【3 高频记录】\n{trace_output}")

        if nonce_path.exists() and nonce_path.stat().st_size > 0:
            archive_path = WORKSPACE_ANALYSIS_DIR / f"nonces_{time.strftime('%Y%m%d_%H%M%S')}.bin"
            shutil.copy2(nonce_path, archive_path)
            try:
                archive_path.chmod(0o600)
            except OSError:
                pass
            self._emit_task_progress("采集随机数", 4, 4, "完成：已生成 nonces.bin")
            sections.append(
                "采集完成：已经生成 nonces.bin。\n"
                f"文件位置：{archive_path}\n"
                "下一步：可以点「强力破解」或「辅助分析」，继续尝试补齐缺失密钥。"
            )
        else:
            self._emit_task_progress("采集随机数", 4, 4, "结束：没有生成有效随机数文件")
            sections.append(
                "采集结束：没有看到有效的 nonces.bin。\n"
                "常见原因：卡片距离不稳、卡片不是 Mifare Classic、设备等待超时，或当前卡不适合这种采集方式。"
            )
        return "\n\n".join(sections)

    def _run_mfkeys_recover_workflow(self) -> str:
        sections: list[str] = [
            "MFKeys 恢复已启动。",
            "实际做法：用 PM3 内置默认密钥库逐扇区测试，并把结果保存到 dumpkeys.bin 和密钥矩阵。",
            "说明：原 mfkeys.lua 会弹交互确认，图形客户端改用更稳定的内置扫描流程。",
        ]

        self._emit_task_progress("MFKeys恢复", 0, 4, "准备识别卡片")
        search_output = self._run_compat_client("hf search")
        self._emit_task_progress("MFKeys恢复", 1, 4, "卡片识别完成")
        sections.append(f"【1 识别卡片】\n{search_output}")
        if self._output_has_no_card(search_output):
            self._emit_task_progress("MFKeys恢复", 4, 4, "已停止：没有识别到卡片")
            sections.append("流程已停止：没有识别到卡片。请把卡贴近天线后再试。")
            return "\n\n".join(sections)
        if not self._output_is_mifare_classic(search_output):
            self._emit_task_progress("MFKeys恢复", 4, 4, "已停止：不是 Mifare Classic")
            sections.append("流程已停止：MFKeys 默认库恢复主要用于 Mifare Classic / S50 / S70。")
            return "\n\n".join(sections)

        memory_arg = self._card_memory_arg_from_search_output(search_output)
        scan_command = f"hf mf chk *{memory_arg} ? d"
        self._emit_task_progress("MFKeys恢复", 2, 4, "正在扫描默认密钥库")
        scan_output = self._run_compat_client(scan_command)
        sections.append(f"【2 默认库恢复】\n实际执行：{scan_command}\n{scan_output}")

        rows = self._extract_key_scan_rows(scan_output)
        if rows:
            self._write_key_status_rows(rows)
        matrix = self._read_workspace_key_matrix()
        self._key_matrix = matrix
        self._write_key_status_from_matrix()
        self._emit_task_progress("MFKeys恢复", 3, 4, "正在刷新密钥矩阵")
        sections.append(f"【3 密钥矩阵】\n{self._key_progress_summary(matrix)}")

        known = sum(1 for row in matrix for key in ("knownA", "knownB") if row.get(key))
        if known:
            self._emit_task_progress("MFKeys恢复", 4, 4, "完成：已写入密钥矩阵")
            sections.append("恢复完成：已经把能确认的 Key A / Key B 同步到密钥矩阵。")
        else:
            self._emit_task_progress("MFKeys恢复", 4, 4, "结束：没有恢复到密钥")
            sections.append(
                "本次没有恢复到可用密钥。\n"
                "下一步建议：先试「本地撞库」；如果有一个已知密钥，再试 Nested / Hardnested。"
            )
        return "\n\n".join(sections)

    def _run_nonce_assist_workflow(self) -> str:
        sections: list[str] = [
            "辅助分析一键流程已启动。",
            "流程：识别卡片 → 弱随机数分析 → 采集随机数 → 查看高频记录 → 默认库恢复 → 刷新密钥矩阵。",
            "说明：这个流程只读和分析，不会写卡。",
        ]

        self._emit_task_progress("辅助分析", 0, 6, "准备识别卡片")
        search_output = self._run_compat_client("hf search")
        self._emit_task_progress("辅助分析", 1, 6, "卡片识别完成")
        sections.append(f"【1 识别卡片】\n{search_output}")
        if self._output_has_no_card(search_output):
            self._emit_task_progress("辅助分析", 6, 6, "已停止：没有识别到卡片")
            sections.append("流程已停止：没有识别到卡片。请把卡稳定贴在天线上再试。")
            return "\n\n".join(sections)
        if not self._output_is_mifare_classic(search_output):
            self._emit_task_progress("辅助分析", 6, 6, "已停止：不是 Mifare Classic")
            sections.append("流程已停止：这个辅助流程目前面向 Mifare Classic / S50 / S70。")
            return "\n\n".join(sections)

        self._emit_task_progress("辅助分析", 2, 6, "正在做弱随机数分析")
        darkside_output = self._run_compat_client("hf mf mifare")
        sections.append(f"【2 弱随机数分析】\n{darkside_output}")
        darkside_key = self._extract_found_key_from_hardnested(darkside_output)
        if darkside_key:
            self._set_workspace_key(0, "A", darkside_key)
            sections.append(f"已把弱随机数分析得到的 0 扇区 Key A 写入密钥矩阵：{darkside_key}")

        self._emit_task_progress("辅助分析", 3, 6, "正在采集随机数")
        collect_output = self._run_compat_client("hf mf ice 3000")
        sections.append(f"【3 采集随机数】\n{collect_output}")
        nonce_path = COMPAT_CLIENT.parent / "nonces.bin"
        if nonce_path.exists() and nonce_path.stat().st_size > 0:
            archive_path = WORKSPACE_ANALYSIS_DIR / f"nonces_{time.strftime('%Y%m%d_%H%M%S')}.bin"
            shutil.copy2(nonce_path, archive_path)
            try:
                archive_path.chmod(0o600)
            except OSError:
                pass
            sections.append(f"随机数文件已保存到私有工作区：{archive_path}")

        self._emit_task_progress("辅助分析", 4, 6, "正在读取高频记录")
        trace_output = self._run_compat_client("hf list")
        sections.append(f"【4 高频记录】\n{trace_output}")

        memory_arg = self._card_memory_arg_from_search_output(search_output)
        scan_command = f"hf mf chk *{memory_arg} ? d"
        self._emit_task_progress("辅助分析", 5, 6, "正在用默认库恢复密钥")
        scan_output = self._run_compat_client(scan_command)
        sections.append(f"【5 默认库恢复】\n实际执行：{scan_command}\n{scan_output}")
        rows = self._extract_key_scan_rows(scan_output)
        if rows:
            self._write_key_status_rows(rows)

        matrix = self._read_workspace_key_matrix()
        self._key_matrix = matrix
        self._write_key_status_from_matrix()
        self._emit_task_progress("辅助分析", 6, 6, "完成：密钥矩阵已刷新")
        sections.append(f"【6 结果】\n{self._key_progress_summary(matrix)}")
        sections.append(
            "下一步：如果密钥还没补齐，回到「IC 破解流程」点「继续破解」或「强力破解」。"
        )
        return "\n\n".join(sections)

    @staticmethod
    def _format_card_capability_text(capability: dict[str, object]) -> str:
        kind = str(capability.get("kind") or "unknown")
        labels = {
            "none": "未检测到卡片",
            "ordinary_mfc": "普通 Mifare Classic，块 00 保留",
            "gen1a": "GEN1A，可使用原始后门写入",
            "rescue_gen1a": "GEN1A 救援中间状态，可继续恢复",
            "cuid_gen2": "CUID/Gen2，需要专用写入方式",
            "fuid_ufuid": "FUID/UFUID，需要专用写入方式",
            "unsupported": "当前不是可自动写入的 Mifare Classic",
            "unknown": "尚未执行卡片能力预检",
        }
        uid = str(capability.get("uid") or "")
        uid_text = f"｜UID {uid}" if uid else ""
        return f"能力：{labels.get(kind, labels['unknown'])}{uid_text}"

    @staticmethod
    def _format_transaction_text(transaction: dict[str, object]) -> str:
        status = str(transaction.get("status") or "idle")
        detail = str(transaction.get("detail") or "")
        labels = {
            "idle": "尚未开始写入任务",
            "preflight": "正在进行写入前检查",
            "backing_up": "正在读取并备份当前卡",
            "writing": "正在写入差异块",
            "verifying": "正在读回校验",
            "completed": "上次写入已完整校验",
            "failed": "上次写入未通过校验",
            "cancelled": "上次操作已终止",
            "interrupted": "检测到未完成操作，可按差异继续",
        }
        text = labels.get(status, labels["idle"])
        return f"任务：{text}" + (f"｜{detail}" if detail else "")

    def _classify_card_capability(self, output: str) -> dict[str, object]:
        uid = self._extract_uid_from_search_output(output)
        card_type = self._extract_card_type_from_search_output(output)
        compact = re.sub(r"\s+", "", output).lower()
        atqa_match = re.search(r"ATQA(?:\s*防冲突参数)?\s*[：:]\s*([0-9A-Fa-f ]{4,5})", output)
        atqa = re.sub(r"\s+", "", atqa_match.group(1)).upper() if atqa_match else ""
        sak = self._extract_sak_from_search_output(output)
        if self._output_has_no_card(output) or not uid:
            kind = "none"
        elif any(marker in compact for marker in ("cuid", "gen2")):
            kind = "cuid_gen2"
        elif any(marker in compact for marker in ("fuid", "ufuid")):
            kind = "fuid_ufuid"
        elif self._search_reports_gen1a(output):
            kind = "rescue_gen1a" if uid == "01020304" and atqa == "0002" and sak == "88" else "gen1a"
        elif self._output_is_mifare_classic(output):
            kind = "ordinary_mfc"
        else:
            kind = "unsupported"
        return {
            "kind": kind,
            "uid": " ".join(uid[index:index + 2] for index in range(0, len(uid), 2)) if uid else "",
            "uid_compact": uid,
            "atqa": atqa,
            "sak": sak,
            "card_type": card_type,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _set_card_capability(self, capability: dict[str, object]) -> None:
        self._card_capability = dict(capability)
        self._card_capability_text = self._format_card_capability_text(self._card_capability)
        self.cardCapabilityTextChanged.emit()
        self._persist_workspace_state()

    def _begin_write_transaction(self, operation: str, target: bytes) -> None:
        self._write_transaction = {
            "status": "preflight",
            "operation": operation,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "target_size": len(target),
            "target_blocks": len(target) // 16 if len(target) % 16 == 0 else 0,
            "target_sha256": hashlib.sha256(target).hexdigest(),
            "detail": "目标数据已冻结，正在识别卡片。",
        }
        self._write_json_file(WORKSPACE_TRANSACTION_FILE, self._write_transaction)
        self._write_transaction_text = self._format_transaction_text(self._write_transaction)
        self.writeTransactionTextChanged.emit()

    def _update_write_transaction(self, status: str, detail: str = "", **fields: object) -> None:
        if not self._write_transaction and status != "preflight":
            return
        self._write_transaction.update(fields)
        self._write_transaction["status"] = status
        self._write_transaction["detail"] = detail
        self._write_transaction["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._write_json_file(WORKSPACE_TRANSACTION_FILE, self._write_transaction)
        self._write_transaction_text = self._format_transaction_text(self._write_transaction)
        self.writeTransactionTextChanged.emit()

    def _probe_gen1a_write_path(self) -> tuple[bool, str]:
        outputs: list[str] = []
        try:
            wake = self._run_compat_client("hf 14a raw -p -a -b 7 40")
            outputs.append(f"40 唤醒：{wake}")
            unlock = self._run_compat_client("hf 14a raw -p -a 43")
            outputs.append(f"43 确认：{unlock}")
            return self._raw_magic_ack_received(wake) and self._raw_magic_ack_received(unlock), "\n".join(outputs)
        finally:
            self._close_raw_field()

    def _close_raw_field(self) -> None:
        try:
            self._run_compat_client("hf 14a raw -c -a 5000", ignore_cancel=True)
        except Exception:
            pass

    def _run_manual_sector_write_workflow(self, command: str) -> str:
        parts = command.split()
        if len(parts) != 9:
            return "【结果：失败】\n流程停止：手动扇区写入参数不完整。"
        try:
            sector = int(parts[2])
        except ValueError:
            return "【结果：失败】\n流程停止：扇区编号不正确。"
        key_type = parts[3].upper()
        key = self._normalize_key_text(parts[4])
        blocks = [self._normalize_block_text(value) for value in parts[5:9]]
        if sector < 0 or sector >= 32 or key_type not in {"A", "B"} or not key or any(not block for block in blocks):
            return "【结果：失败】\n流程停止：扇区、密钥或四个块的数据格式不正确。"

        sections = [
            f"扇区 {sector:02d} 精确写入已启动。",
            "流程：先读取确认认证可用，再依次写数据块，最后写密钥尾块。",
        ]
        read_output = self._run_compat_client(f"hf mf rdsc {sector} {key_type} {key}")
        sections.append(f"【1 写前读取】\n{read_output}")
        if self._output_indicates_failure(read_output):
            sections.append("【结果：失败】\n写前读取或认证没有通过，本次没有发送写块命令。")
            return "\n\n".join(sections)

        first_block = self._first_block_of_sector(sector)
        write_lines: list[str] = []
        for block_in_sector, data in enumerate(blocks):
            absolute_block = first_block + block_in_sector
            ok, line = self._write_block_with_fallback(absolute_block, bytes.fromhex(data), [(key_type, key)])
            write_lines.append(line)
            if not ok:
                sections.append("【2 逐块写入】\n" + "\n".join(write_lines))
                sections.append(
                    "【结果：失败】\n"
                    f"扇区内块 {block_in_sector} 没有确认写入成功，流程已停止，后续块没有继续写。"
                )
                return "\n\n".join(sections)

        sections.append("【2 逐块写入】\n" + "\n".join(write_lines))
        sections.append("【结果：成功】\n四个块均收到写入成功应答；建议立即重新读取该扇区确认内容。")
        return "\n\n".join(sections)

    def _run_auto_write_workflow(self) -> str:
        if not WORKSPACE_PENDING_DATA.exists():
            return "【结果：失败】\n流程停止：右侧还没有待写入数据。"
        target = WORKSPACE_PENDING_DATA.read_bytes()
        if self._mifare_sector_count_for_size(len(target)) == 0:
            return f"【结果：失败】\n流程停止：当前 {len(target)} 字节数据不是支持的 Mifare Classic 整卡格式。"

        self._begin_write_transaction("智能写入", target)
        search_output = self._run_compat_client("hf search")
        capability = self._classify_card_capability(search_output)
        self._set_card_capability(capability)
        sections = [f"【智能预检】\n{search_output}", self._card_capability_text]
        kind = str(capability.get("kind"))

        if kind in {"gen1a", "rescue_gen1a"}:
            probe_ok, probe_text = self._probe_gen1a_write_path()
            sections.append(f"【无写入能力探测】\n{probe_text}")
            if not probe_ok:
                self._update_write_transaction("failed", "识别为 GEN1A，但原始 40/43 通道没有通过探测。")
                sections.append("【结果：失败】\n没有发送任何块数据：GEN1A 原始写入通道未通过预检。")
                return "\n\n".join(sections)
            self._update_write_transaction("backing_up", "已选择 GEN1A 原始差异写入策略。", strategy="gen1a_raw")
            result = self._run_magic_write_workflow(search_output)
        elif kind == "ordinary_mfc":
            self._update_write_transaction("backing_up", "已选择普通 IC 密钥写入策略；块 00 将保留。", strategy="ordinary_mfc")
            result = self._run_smart_write_workflow()
        elif kind in {"cuid_gen2", "fuid_ufuid"}:
            self._update_write_transaction("failed", "已识别卡片类型，但当前自动路由没有启用对应的块 00 写法。")
            sections.append("【结果：失败】\n为避免选错协议，本次没有写卡；请在高级页面使用对应卡型工具。")
            return "\n\n".join(sections)
        else:
            self._update_write_transaction("failed", "卡片类型不支持自动写入或没有识别到卡片。")
            sections.append("【结果：失败】\n本次没有写卡：无法为当前卡片选择可靠的写入策略。")
            return "\n\n".join(sections)

        if "【结果：成功】" in result or "写入成功：读回数据和待写入数据完全一致" in result:
            self._update_write_transaction("completed", "读回数据与冻结目标完全一致。", verified=True)
        else:
            self._update_write_transaction("failed", "写入流程结束，但没有通过完整读回校验。", verified=False)
        sections.append(result)
        return "\n\n".join(sections)

    def _run_magic_write_workflow(self, preflight_search: str = "") -> str:
        sections: list[str] = [
            "魔术卡整卡写入已启动。",
            "这次会先读卡并备份，只写入不同的块，最后逐块读回校验。",
            "适用范围：确认支持 GEN1A 后门的 1K/S50 可写 UID 卡。",
        ]

        client_dir = COMPAT_CLIENT.parent
        target_bin = client_dir / "selected_data_magic_target.bin"
        # Always rebuild these files from the visible pending-write area so an edited
        # block can never be hidden behind an older selected_data cache.
        if not self._prepare_magic_write_files():
            return "【结果：失败】\n流程停止：还没有可写入的魔术卡整卡数据。"

        target = target_bin.read_bytes()
        if len(target) != 1024:
            return f"【结果：失败】\n流程停止：GEN1A 整卡写入需要 1024 字节，当前数据为 {len(target)} 字节。"
        if self._write_transaction.get("status") not in {"preflight", "backing_up", "writing", "verifying"}:
            self._begin_write_transaction("GEN1A 写入", target)
        if not self._mifare_4byte_uid_bcc_valid(target):
            self._update_write_transaction("failed", "块 00 的 UID 校验字节 BCC 不正确。", verified=False)
            return (
                "【结果：失败】\n"
                "流程停止：待写入数据的块 00 校验字节（BCC）与 UID 不匹配。\n"
                "请先修正 UID 或校验字节，避免写入后卡片无法正常被识别。"
            )

        self._emit_task_progress("魔术卡写入", 0, 4, "正在识别目标卡")
        search_output = preflight_search or self._run_compat_client("hf search")
        self._set_card_capability(self._classify_card_capability(search_output))
        sections.append(f"【1 目标卡检查】\n{search_output}")
        if self._output_has_no_card(search_output):
            self._emit_task_progress("魔术卡写入", 4, 4, "已停止：没有识别到目标卡")
            sections.append("【结果：失败】\n流程停止：没有识别到目标卡。请把卡稳定放在天线感应区后再试。")
            return "\n\n".join(sections)

        if not self._search_reports_gen1a(search_output):
            self._emit_task_progress("魔术卡写入", 4, 4, "已停止：没有确认 GEN1A")
            sections.append(
                "【结果：失败】\n"
                "识别结果没有确认 GEN1A 后门。为避免把普通卡或其他可改 UID 卡写坏，本次没有发送原始写入指令。"
            )
            return "\n\n".join(sections)

        if not preflight_search:
            probe_ok, probe_text = self._probe_gen1a_write_path()
            sections.append(f"【2 无写入能力探测】\n{probe_text}")
            if not probe_ok:
                sections.append("【结果：失败】\nGEN1A 原始写入通道没有通过 40/43 探测，本次没有发送块数据。")
                return "\n\n".join(sections)

        if not self._install_workspace_keys_from_dump(target):
            self._emit_task_progress("魔术卡写入", 4, 4, "已停止：无法准备密钥")
            sections.append("【结果：失败】\n无法从待写入镜像恢复扇区密钥，因此没有开始写卡。")
            return "\n\n".join(sections)

        self._emit_task_progress("魔术卡写入", 1, 4, "正在读取并备份当前卡")
        self._update_write_transaction("backing_up", "正在读取当前卡并制作写前备份。")
        read_output, current = self._read_card_dump(WORKSPACE_READ_DATA)
        if len(current) == len(target):
            backup_path = self._save_card_backup(current, "before_magic_write")
            diffs = self._card_byte_diffs(target, current)
            self._update_write_transaction(
                "writing",
                f"发现 {len(diffs)} 个不同块。",
                backup=str(backup_path),
                diff_blocks=[block for block, _expected, _actual in diffs],
            )
            sections.append(
                "【2 写前读取与备份】\n"
                f"{read_output}\n\n"
                f"已备份当前卡：{backup_path}\n"
                f"发现 {len(diffs)} 个不同块。"
            )
        else:
            sections.append(
                "【2 写前读取与备份】\n"
                f"{read_output}\n\n"
                "【结果：失败】\n"
                f"只读取到 {len(current)} / {len(target)} 字节，无法制作完整写前备份。\n"
                "安全策略已停止本次写入，没有发送任何块数据。"
            )
            self._update_write_transaction(
                "failed",
                "写前整卡读取不完整，已在发送块数据前停止。",
                diff_blocks=[],
                verified=False,
            )
            return "\n\n".join(sections)

        if diffs:
            block_numbers = [block for block, _expected, _actual in diffs]
            self._emit_task_progress("魔术卡写入", 2, 4, f"正在写入 {len(block_numbers)} 个不同块")
            write_lines, failed_blocks = self._write_magic_blocks_raw(
                target,
                block_numbers,
                "魔术卡写入",
            )
            sections.append("【3 原始后门写入】\n" + "\n".join(write_lines))
            if failed_blocks:
                self._install_workspace_keys_from_dump(target)
                self._emit_task_progress("魔术卡写入", 4, 4, "写入失败，已停止")
                sections.append(
                    "【结果：失败】\n"
                    f"块 {failed_blocks[0]:02d} 没有收到卡片的 0A 成功应答，流程已立即停止。\n"
                    "请保持卡片不动；不要连续重试，先查看上面的失败步骤。"
                )
                return "\n\n".join(sections)
        else:
            sections.append("【3 原始后门写入】\n当前卡已经和待写入数据一致，没有重复写入。")

        self._install_workspace_keys_from_dump(target)
        source_keys = self._load_key_store("source")
        if source_keys:
            self._activate_runtime_keys(source_keys)
        self._emit_task_progress("魔术卡写入", 3, 4, "正在整卡读回校验")
        self._update_write_transaction("verifying", "写入命令结束，正在读取独立校验副本。")
        verify_output, verify = self._read_card_dump(WORKSPACE_VERIFY_DATA)
        sections.append(f"【4 整卡读回】\n{verify_output}")
        if len(verify) != len(target):
            self._emit_task_progress("魔术卡写入", 4, 4, "校验失败：没有完整读回")
            sections.append(
                "【结果：失败】\n"
                f"写入命令已经结束，但只读回 {len(verify)} / {len(target)} 字节，不能判定成功。"
            )
            return "\n\n".join(sections)

        final_diffs = self._card_byte_diffs(target, verify)
        if final_diffs:
            self._emit_task_progress("魔术卡写入", 4, 4, "校验失败：仍有块不一致")
            preview = "\n".join(
                self._format_block_diff(block, expected, actual)
                for block, expected, actual in final_diffs[:12]
            )
            suffix = "\n..." if len(final_diffs) > 12 else ""
            sections.append(
                "【结果：失败】\n"
                f"读回后仍有 {len(final_diffs)} 个块不一致。\n"
                f"{preview}{suffix}\n"
                "软件不会把这种情况显示成成功。"
            )
            return "\n\n".join(sections)

        self._emit_task_progress("魔术卡写入", 4, 4, "完成：64/64 块一致")
        sections.append("【结果：成功】\n写入成功：64/64 个块均已读回，并与导入数据逐字节一致。")
        return "\n\n".join(sections)

    def _normal_dump_compare_text(self, target: bytes) -> str:
        output, actual = self._read_card_dump(WORKSPACE_VERIFY_DATA)
        if not actual:
            return (
                f"{output}\n\n"
                "普通读回也没有生成整卡数据。请确认卡片贴稳、密钥已经解析完整，或目标卡确实可读。"
            )
        if len(actual) != len(target):
            return (
                f"{output}\n\n"
                f"普通读回长度不一致：读回 {len(actual)} 字节，待写入 {len(target)} 字节。"
            )

        diffs = self._card_byte_diffs(target, actual)
        if not diffs:
            return f"{output}\n\n校验结果：当前卡内容已经和待写入数据完全一致。"

        if len(diffs) == 1 and diffs[0][0] == 0:
            return (
                f"{output}\n\n"
                + self._block_zero_write_diagnostic(diffs[0][1], diffs[0][2], len(target) // 16)
            )

        preview = "\n".join(self._format_block_diff(block, expected, actual_block) for block, expected, actual_block in diffs[:12])
        suffix = "\n..." if len(diffs) > 12 else ""
        return (
            f"{output}\n\n"
            f"校验结果：当前卡仍有 {len(diffs)} 个块和待写入数据不一致。\n"
            f"{preview}{suffix}"
        )

    def _run_magic_rescue_workflow(self) -> str:
        sections: list[str] = [
            "魔术卡坏卡救援已启动。",
            "用途：处理 0 块写坏、ATQA 变成 AA AA、读块全 AA、普通识别失败的 GEN1A 魔术卡。",
            "说明：这会把卡临时拉回 UID 01 02 03 04。救回来后请再点「恢复UID」或「默认初始化」。",
        ]
        rescue_block = bytes.fromhex("01020304049802000000000000001001")
        self._begin_write_transaction("GEN1A 坏卡救援", rescue_block)
        self._update_write_transaction("writing", "正在写入救援厂商块。", diff_blocks=[0])
        self._emit_task_progress("坏卡救援", 1, 2, "正在写入救援厂商块")
        ok, detail = self._write_magic_block_raw(0, rescue_block)
        sections.append(f"【1 救援写入】\n{detail}")
        if not ok:
            sections.append("【结果：失败】\n卡片没有完整回应 GEN1A 原始救援指令，本次救援已停止。")
            return "\n\n".join(sections)

        self._emit_task_progress("坏卡救援", 2, 2, "正在重新识别")
        search_output = self._run_compat_client("hf search")
        sections.append(f"【2 重新识别】\n{search_output}")
        uid = self._extract_uid_from_search_output(search_output)
        if uid == "01020304":
            sections.append(
                "【结果：成功】\n"
                "卡片已经恢复响应，当前 UID 为 01 02 03 04。这里只完成救援，还没有恢复原 UID 和整卡数据。"
            )
        else:
            sections.append(
                "【结果：失败】\n"
                "写入收到了应答，但重新识别没有得到预期 UID。请把卡拿开 3 秒再放回后重新识别。"
            )
        return "\n\n".join(sections)

    def _run_magic_restore_uid_workflow(self, uid: str) -> str:
        uid = self._normalize_uid_text(uid)
        if not uid:
            return "【结果：失败】\n流程停止：UID 必须是 8 位十六进制。"
        pretty_uid = " ".join(uid[index:index + 2] for index in range(0, len(uid), 2))
        sections = [
            "恢复魔术卡 UID 已启动。",
            f"目标 UID：{pretty_uid}",
            "使用 GEN1A 原始方式写块 00，避免旧内核 csetuid 的 wupC1 兼容问题。",
        ]
        loaded = self._blocks_to_bytes(self._data_blocks)
        if len(loaded) >= 16:
            block0 = bytearray(loaded[:16])
        else:
            block0 = bytearray.fromhex("00000000000804006263646566676869")
        uid_bytes = bytes.fromhex(uid)
        block0[:4] = uid_bytes
        block0[4] = uid_bytes[0] ^ uid_bytes[1] ^ uid_bytes[2] ^ uid_bytes[3]
        block0[5:8] = bytes.fromhex("080400")

        self._begin_write_transaction("恢复 UID", bytes(block0))
        self._update_write_transaction("writing", "正在写入 UID/厂商块。", diff_blocks=[0])
        self._emit_task_progress("恢复UID", 1, 2, "正在写入 UID/厂商块")
        ok, detail = self._write_magic_block_raw(0, bytes(block0))
        sections.append(f"【1 写入 UID/厂商块】\n{detail}")
        if not ok:
            sections.append("【结果：失败】\n块 00 没有完整收到 0A 应答，UID 未确认写入。")
            return "\n\n".join(sections)

        self._emit_task_progress("恢复UID", 2, 2, "正在重新识别")
        search_output = self._run_compat_client("hf search")
        sections.append(f"【2 重新识别】\n{search_output}")
        found_uid = self._extract_uid_from_search_output(search_output)
        if found_uid == uid:
            sections.append("【结果：成功】\nUID 已写入并通过重新识别确认。")
        else:
            sections.append(
                "【结果：失败】\n"
                "写入步骤收到应答，但重新识别的 UID 不一致，因此不判定成功。"
            )
        return "\n\n".join(sections)

    def _run_magic_blank_reset_workflow(self, uid: str) -> str:
        return self._run_magic_reset_target_workflow(uid, "空白初始化")

    def _run_magic_one_click_reset_workflow(self, uid: str) -> str:
        return self._run_magic_reset_target_workflow(uid, "一键重置")

    def _run_magic_reset_target_workflow(self, uid: str, task_label: str) -> str:
        uid = self._normalize_uid_text(uid)
        if not uid:
            return "【结果：失败】\n流程停止：UID 必须是 8 位十六进制。"

        client_dir = COMPAT_CLIENT.parent
        eml_path = client_dir / "pm3_blank_reset.eml"
        try:
            eml_text = self._blank_mifare_1k_eml(uid)
            eml_path.write_text(eml_text, encoding="ascii")
            target = bytes.fromhex("".join(eml_text.splitlines()))
        except OSError as error:
            return f"【结果：失败】\n流程停止：无法创建空白卡镜像。\n{error}"

        pretty_uid = " ".join(uid[index:index + 2] for index in range(0, len(uid), 2))
        sections: list[str] = [
            f"{task_label}已启动。",
            f"目标 UID：{pretty_uid}",
            "流程：识别/救援 → 备份当前卡 → 原始方式写入空白结构 → 恢复正确密钥 → 整卡读回。",
            "数据块清零，Key A / Key B 设为 FFFFFFFFFFFF，权限位设为 FF078069。",
        ]
        self._begin_write_transaction(task_label, target)

        self._emit_task_progress(task_label, 0, 4, "正在识别卡片")
        search_output = self._run_compat_client("hf search")
        sections.append(f"【1 卡片检查】\n{search_output}")
        reports_gen1a = self._search_reports_gen1a(search_output)
        if not reports_gen1a:
            rescue_block = bytes.fromhex("01020304049802000000000000001001")
            rescue_ok, rescue_detail = self._write_magic_block_raw(0, rescue_block)
            sections.append(f"【2 尝试救援】\n{rescue_detail}")
            if not rescue_ok:
                sections.append("【结果：失败】\n没有确认 GEN1A 后门，救援块也未收到完整应答；本次没有继续清空整卡。")
                return "\n\n".join(sections)
            search_output = self._run_compat_client("hf search")
            reports_gen1a = self._search_reports_gen1a(search_output)
            sections.append(f"【3 救援后识别】\n{search_output}")
            if not reports_gen1a:
                sections.append("【结果：失败】\n救援后仍未确认 GEN1A 后门，流程已停止。")
                return "\n\n".join(sections)

        loaded = self._blocks_to_bytes(self._data_blocks)
        if len(loaded) == 1024:
            self._install_workspace_keys_from_dump(loaded)
        self._emit_task_progress(task_label, 1, 4, "正在备份当前卡")
        backup_output, current = self._read_card_dump(WORKSPACE_READ_DATA)
        if len(current) == 1024:
            backup_path = self._save_card_backup(current, "before_blank_reset")
            sections.append(f"【2 写前备份】\n{backup_output}\n\n已备份当前卡：{backup_path}")
        else:
            sections.append(f"【2 写前备份】\n{backup_output}\n\n当前卡未能完整读出，因此没有生成整卡备份。")

        self._update_write_transaction(
            "writing",
            "正在按安全顺序写入 64 块空白结构。",
            backup=str(backup_path) if len(current) == 1024 else "",
            diff_blocks=list(range(64)),
        )
        self._emit_task_progress(task_label, 2, 4, "正在写入 64 块空白结构")
        write_lines, failed_blocks = self._write_magic_blocks_raw(target, list(range(64)), task_label)
        sections.append("【3 写入空白结构】\n" + "\n".join(write_lines))
        if failed_blocks:
            sections.append(
                "【结果：失败】\n"
                f"块 {failed_blocks[0]:02d} 未收到 0A 成功应答，流程已立即停止，未再覆盖后续块。"
            )
            return "\n\n".join(sections)

        self._install_workspace_keys_from_dump(target)
        source_keys = self._load_key_store("source")
        if source_keys:
            self._activate_runtime_keys(source_keys)
        self._update_write_transaction("verifying", "空白结构写入结束，正在整卡读回校验。")
        self._emit_task_progress(task_label, 3, 4, "正在整卡读回校验")
        verify_output, verify = self._read_card_dump(WORKSPACE_VERIFY_DATA)
        sections.append(f"【4 整卡读回】\n{verify_output}")
        diffs = self._card_byte_diffs(target, verify) if len(verify) == len(target) else []
        if len(verify) == len(target) and not diffs:
            self._emit_task_progress(task_label, 4, 4, "完成：64/64 块一致")
            sections.append("【结果：成功】\n初始化成功：64/64 块已读回一致，UID、空白数据、默认密钥和权限位均已确认。")
        else:
            self._emit_task_progress(task_label, 4, 4, "校验失败")
            detail = f"仍有 {len(diffs)} 个块不一致。" if diffs else f"只读回 {len(verify)} / {len(target)} 字节。"
            sections.append(f"【结果：失败】\n写入步骤结束，但整卡校验没有通过：{detail}")
        return "\n\n".join(sections)

    @staticmethod
    def _blank_reset_verified(key_output: str, dump_output: str) -> bool:
        return (
            key_output.lower().count("ffffffffffff") >= 32
            and ("Dumped 64 blocks" in dump_output or "已转储 64 块" in dump_output)
        )

    @staticmethod
    def _blank_mifare_1k_eml(uid: str) -> str:
        uid_bytes = bytes.fromhex(uid)
        bcc = 0
        for byte in uid_bytes:
            bcc ^= byte
        block0 = uid + f"{bcc:02X}" + "0804006263646566676869"
        data_block = "00" * 16
        trailer = "FFFFFFFFFFFF" + "FF078069" + "FFFFFFFFFFFF"
        lines: list[str] = []
        for block in range(64):
            if block == 0:
                lines.append(block0)
            elif block % 4 == 3:
                lines.append(trailer)
            else:
                lines.append(data_block)
        return "\n".join(lines) + "\n"

    @staticmethod
    def _mifare_4byte_uid_bcc_valid(data: bytes) -> bool:
        if len(data) < 5:
            return False
        bcc = data[0] ^ data[1] ^ data[2] ^ data[3]
        return data[4] == bcc

    @staticmethod
    def _magic_backdoor_write_failed(output: str) -> bool:
        lowered = output.lower()
        failure_markers = (
            "wupc1 error",
            "can't set magic card",
            "can't write block",
            "write block error",
            "cmd error",
            "isok:00",
            "执行结果：失败",
        )
        return any(marker in lowered for marker in failure_markers)

    @staticmethod
    def _search_reports_gen1a(output: str) -> bool:
        compact = re.sub(r"\s+", "", output).lower()
        return any(
            marker in compact
            for marker in (
                "answerstomagiccommands(gen1a):yes",
                "魔术卡指令回应（gen1a）：是",
                "魔术卡指令回应(gen1a):是",
            )
        )

    @staticmethod
    def _raw_magic_ack_received(output: str) -> bool:
        return bool(re.search(r"(?mi)^\s*0A\s*$", output))

    def _write_magic_block_raw(self, block: int, data: bytes) -> tuple[bool, str]:
        if block < 0 or block > 255 or len(data) != 16:
            return False, "块号或数据长度无效。"

        payload = data.hex(" ").upper()
        commands = [
            ("唤醒 GEN1A 后门", "hf 14a raw -p -a -b 7 40"),
            ("确认后门", "hf 14a raw -p -a 43"),
            ("选择目标块", f"hf 14a raw -c -p -a A0{block:02X}"),
            ("写入 16 字节", f"hf 14a raw -c -p -a {payload}"),
        ]
        details: list[str] = []
        failed_step = ""
        try:
            for label, command in commands:
                output = self._run_compat_client(command)
                details.append(f"{label}：{output or '<无返回>'}")
                if not self._raw_magic_ack_received(output):
                    failed_step = label
                    break
        finally:
            # remagic.lua uses this HALT command to close the field after a raw write.
            self._close_raw_field()

        if failed_step:
            return False, f"{failed_step}没有收到 0A 应答。\n" + "\n".join(details)
        return True, "四个写入步骤均收到 0A 应答。"

    def _write_magic_blocks_raw(
        self,
        target: bytes,
        blocks: list[int],
        task_label: str,
    ) -> tuple[list[str], list[int]]:
        block_count = len(target) // 16
        unique_blocks = sorted(
            {block for block in blocks if 0 <= block < block_count},
            key=lambda block: (
                2 if block == 0 else 1 if self._sector_block_for_block_index(block)[1]
                == self._blocks_per_sector(self._sector_block_for_block_index(block)[0]) - 1 else 0,
                block,
            ),
        )
        lines: list[str] = []
        failed: list[int] = []
        total = max(1, len(unique_blocks))
        for index, block in enumerate(unique_blocks, start=1):
            self._emit_task_progress(task_label, index, total, f"正在写块 {block:02d}")
            chunk = target[block * 16:(block + 1) * 16]
            ok, detail = self._write_magic_block_raw(block, chunk)
            if ok:
                lines.append(f"块 {block:02d}：写入成功，已收到 0A 应答。")
                continue
            lines.append(f"块 {block:02d}：写入失败。\n{detail}")
            failed.append(block)
            break
        return lines, failed

    def _install_workspace_keys_from_dump(self, data: bytes) -> bool:
        matrix = self._matrix_from_dump_bytes(data)
        if not matrix:
            return False
        try:
            self._save_key_store("source", matrix, "待写入整卡数据的扇区尾块")
            self._activate_runtime_keys()
        except OSError:
            return False
        self.keyMatrixChanged.emit()
        return True

    def _read_card_dump(self, destination: Path | None = None) -> tuple[str, bytes]:
        dump_path = COMPAT_CLIENT.parent / "dumpdata.bin"
        try:
            dump_path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass
        output = self._run_compat_client("hf mf dump")
        try:
            data = dump_path.read_bytes()
        except OSError:
            return output, b""
        if destination is not None and data:
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(destination.suffix + ".incoming")
            temporary.write_bytes(data)
            try:
                temporary.chmod(0o600)
            except OSError:
                pass
            temporary.replace(destination)
            self._persist_workspace_state()
        return output, data

    @staticmethod
    def _save_card_backup(data: bytes, prefix: str) -> Path:
        backup_dir = WORKSPACE_BACKUP_DIR
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        target = backup_dir / f"{prefix}_{stamp}.bin"
        target.write_bytes(data)
        keys_path = COMPAT_CLIENT.parent / "dumpkeys.bin"
        if keys_path.exists():
            shutil.copy2(keys_path, target.with_suffix(".keys.bin"))
        return target

    @staticmethod
    def _looks_like_repeated_block_dump(data: bytes) -> bool:
        if len(data) < 64 or len(data) % 16 != 0:
            return False
        first = data[:16]
        blocks = [data[index:index + 16] for index in range(0, min(len(data), 1024), 16)]
        repeated = sum(1 for block in blocks if block == first)
        return repeated >= max(8, len(blocks) - 1)

    def _run_smart_write_workflow(self) -> str:
        client_dir = COMPAT_CLIENT.parent
        keys_path = client_dir / "dumpkeys.bin"
        target_path = client_dir / "selected_data_smart_target.bin"

        if not WORKSPACE_PENDING_DATA.exists():
            return "流程停止：还没有待写入的整卡数据。请先导入数据，或从左侧复制到待写入区。"

        target = WORKSPACE_PENDING_DATA.read_bytes()
        if len(target) % 16 != 0:
            return "流程停止：待写入文件长度不是 16 字节块的整数倍，不能当作 Mifare Classic 整卡数据写入。"
        sector_count = self._mifare_sector_count_for_size(len(target))
        if not sector_count:
            return f"流程停止：当前只支持 MINI/1K/2K/4K 的 Mifare Classic 整卡数据，当前大小是 {len(target)} 字节。"

        self._install_workspace_keys_from_dump(target)
        if not keys_path.exists():
            return "流程停止：没有可供底层读取当前卡的密钥。"
        target_path.write_bytes(target)
        matrix = self._read_workspace_key_matrix()
        block_count = len(target) // 16
        sections: list[str] = [
            "普通 IC 智能写卡已启动。",
            "流程：先读当前卡 → 找出不同块 → 逐块写入 → Key A 不行自动试 Key B → 最后整卡校验。",
            "说明：普通 IC 模式只写普通数据块和密钥尾块，会保留目标卡原来的块 00 / UID。",
        ]

        if self._write_transaction.get("status") not in {"preflight", "backing_up", "writing", "verifying"}:
            self._begin_write_transaction("普通 IC 写入", target)

        self._emit_task_progress("智能写卡", 0, 5, "正在读取当前卡")
        self._update_write_transaction("backing_up", "正在读取当前卡并制作写前备份。")
        read_output, current = self._read_card_dump(WORKSPACE_READ_DATA)
        sections.append(f"【1 读取当前卡】\n{read_output}")
        if len(current) != len(target):
            self._update_write_transaction(
                "failed",
                "写前整卡读取长度与目标不一致，已在写入前停止。",
                verified=False,
            )
            sections.append(
                "【结果：失败】\n"
                f"写前只读取到 {len(current)} 字节，目标数据为 {len(target)} 字节。\n"
                "这可能是密钥不完整、卡片移动或目标卡容量不匹配；本次没有发送写块命令。"
            )
            return "\n\n".join(sections)

        backup_path = self._save_card_backup(current, "before_ordinary_write")
        sections.append(f"写前备份：{backup_path}")

        diffs = self._card_byte_diffs(target, current)

        if not diffs:
            self._emit_task_progress("智能写卡", 5, 5, "完成：当前卡已一致")
            WORKSPACE_VERIFY_DATA.write_bytes(current)
            sections.append(
                "【2 差异检查】\n当前卡已经和待写入数据完全一致，不需要再写。\n\n"
                f"【结果：成功】\n{block_count}/{block_count} 块一致。"
            )
            return "\n\n".join(sections)

        skipped: list[str] = []
        write_blocks: list[int] = []
        for block, _expected, _actual in diffs:
            sector, sector_block = self._sector_block_for_block_index(block)
            if block == 0:
                skipped.append("块 00 是 UID/厂商块，普通 IC 模式会按规则跳过，不会把它误报成密钥失败。")
                continue
            if sector_block == self._blocks_per_sector(sector) - 1:
                write_blocks.append(block)
            else:
                write_blocks.insert(0, block)

        # Keep data blocks first and sector trailers last; changing trailers too early can lock out later writes.
        write_blocks = sorted(
            set(write_blocks),
            key=lambda block: (
                self._sector_block_for_block_index(block)[1]
                == self._blocks_per_sector(self._sector_block_for_block_index(block)[0]) - 1,
                block,
            ),
        )

        self._emit_task_progress("智能写卡", 1, 5, f"发现 {len(diffs)} 个不同块")
        self._update_write_transaction(
            "writing",
            f"发现 {len(diffs)} 个不同块，普通模式准备写入 {len(write_blocks)} 个。",
            diff_blocks=[block for block, _expected, _actual in diffs],
        )
        sections.append(
            "【2 差异检查】\n"
            f"共发现 {len(diffs)} 个不同块；准备写入 {len(write_blocks)} 个块。"
            + ("\n" + "\n".join(skipped) if skipped else "")
        )

        write_lines: list[str] = []
        failed: list[str] = []
        total_steps = max(1, len(write_blocks))
        for index, block in enumerate(write_blocks, start=1):
            sector, sector_block = self._sector_block_for_block_index(block)
            chunk = target[block * 16:(block + 1) * 16]
            current_trailer = self._sector_trailer_bytes(current, sector)
            target_trailer = self._sector_trailer_bytes(target, sector)
            order = self._write_auth_order_for_block(current_trailer or target_trailer, sector_block)
            candidates = self._key_candidates_for_sector(sector, order, matrix, target, current)
            detail = f"正在写块 {block:02d}"
            self._emit_task_progress("智能写卡", index, total_steps + 2, detail)
            ok, line = self._write_block_with_fallback(block, chunk, candidates)
            write_lines.append(line)
            if not ok:
                failed.append(f"块 {block:02d}")

        sections.append("【3 逐块写入】\n" + ("\n".join(write_lines) if write_lines else "没有需要写入的普通数据块。"))
        if failed:
            sections.append(
                "提示：下面这些块没有写成功，通常是权限位不允许、密钥不对、卡片不是可写卡，或卡片离天线不稳定。\n"
                + "、".join(failed)
            )

        self._emit_task_progress("智能写卡", total_steps + 1, total_steps + 2, "正在整卡读回校验")
        source_keys = self._load_key_store("source")
        if source_keys:
            self._activate_runtime_keys(source_keys)
        self._update_write_transaction("verifying", "普通数据块写入结束，正在读取独立校验副本。")
        verify_output, verify = self._read_card_dump(WORKSPACE_VERIFY_DATA)
        sections.append(f"【4 整卡校验】\n{verify_output}")
        final_diffs = self._card_byte_diffs(target, verify) if len(verify) == len(target) else diffs

        if not final_diffs:
            self._emit_task_progress(
                "智能写卡",
                total_steps + 2,
                total_steps + 2,
                f"完成：{block_count}/{block_count} 一致",
            )
            sections.append("【结果：成功】\n写入成功：读回数据和待写入数据完全一致。")
        elif len(final_diffs) == 1 and final_diffs[0][0] == 0:
            self._emit_task_progress(
                "智能写卡",
                total_steps + 2,
                total_steps + 2,
                f"完成：{block_count - 1}/{block_count} 一致，仅 UID 未修改",
            )
            sections.append(
                "【结果：部分完成】\n"
                + self._block_zero_write_diagnostic(
                    final_diffs[0][1],
                    final_diffs[0][2],
                    block_count,
                )
            )
        else:
            self._emit_task_progress("智能写卡", total_steps + 2, total_steps + 2, "完成：仍有差异")
            preview = "\n".join(self._format_block_diff(block, expected, actual) for block, expected, actual in final_diffs[:12])
            suffix = "\n..." if len(final_diffs) > 12 else ""
            sections.append(
                "【结果：失败】\n"
                f"仍有 {len(final_diffs)} 个块不一致。\n"
                f"{preview}{suffix}\n"
                "这些差异包含普通数据块或密钥尾块，需要按失败块分别检查密钥、访问位、卡片位置和目标卡类型。"
            )

        return "\n\n".join(sections)

    def _write_block_with_fallback(self, block: int, data: bytes, candidates: list[tuple[str, str]]) -> tuple[bool, str]:
        attempts: list[str] = []
        payload = data.hex().upper()
        for key_type, key in candidates:
            output = self._run_compat_client(f"hf mf wrbl {block} {key_type} {key} {payload}")
            if self._write_block_succeeded(output):
                return True, f"块 {block:02d}：使用 Key {key_type} 写入成功。"
            attempts.append(f"Key {key_type}")
        tried = "、".join(attempts) if attempts else "没有可用密钥"
        return False, f"块 {block:02d}：写入失败，已尝试 {tried}。"

    @staticmethod
    def _write_block_succeeded(output: str) -> bool:
        return (
            "isOk:01" in output
            or "执行结果：成功（01）" in output
            or "执行结果: 成功(01)" in output
        ) and "写块错误" not in output and "Write block error" not in output

    def _key_candidates_for_sector(
        self,
        sector: int,
        key_order: list[str],
        matrix: list[dict[str, object]],
        target: bytes,
        current: bytes,
    ) -> list[tuple[str, str]]:
        candidates: list[tuple[str, str]] = []

        row = matrix[sector] if sector < len(matrix) else {}
        for key_type in key_order:
            key = self._normalize_key_text(str(row.get("keyA" if key_type == "A" else "keyB", "")))
            self._append_key_candidate(candidates, key_type, key)

        for blob in (current, target):
            trailer = self._sector_trailer_bytes(blob, sector)
            if not trailer:
                continue
            self._append_key_candidate(candidates, "A", trailer[:6].hex().upper())
            self._append_key_candidate(candidates, "B", trailer[10:16].hex().upper())

        for key_type in key_order:
            self._append_key_candidate(candidates, key_type, "FFFFFFFFFFFF")

        return candidates

    @staticmethod
    def _append_key_candidate(candidates: list[tuple[str, str]], key_type: str, key: str) -> None:
        compact = "".join(ch for ch in key.upper() if ch in "0123456789ABCDEF")
        item = (key_type, compact)
        if len(compact) == 12 and item not in candidates:
            candidates.append(item)

    def _write_auth_order_for_block(self, trailer: bytes, block_in_sector: int) -> list[str]:
        access = self._access_bits_for_trailer(trailer)
        bits = access.get(min(block_in_sector, 3))
        if bits in {(1, 0, 0), (1, 1, 0), (0, 1, 1)}:
            return ["B", "A"]
        return ["A", "B"]

    @staticmethod
    def _access_bits_for_trailer(trailer: bytes) -> dict[int, tuple[int, int, int]]:
        if len(trailer) != 16:
            return {}
        byte6, byte7, byte8 = trailer[6], trailer[7], trailer[8]
        c1 = (byte7 >> 4) & 0x0F
        nc1 = byte6 & 0x0F
        c2 = (byte6 >> 4) & 0x0F
        nc2 = byte8 & 0x0F
        c3 = (byte8 >> 4) & 0x0F
        nc3 = byte7 & 0x0F
        if ((~c1) & 0x0F) != nc1 or ((~c2) & 0x0F) != nc2 or ((~c3) & 0x0F) != nc3:
            return {}
        return {
            block: (
                1 if c1 & (1 << block) else 0,
                1 if c2 & (1 << block) else 0,
                1 if c3 & (1 << block) else 0,
            )
            for block in range(4)
        }

    def _sector_trailer_bytes(self, data: bytes, sector: int) -> bytes:
        if not data:
            return b""
        trailer_index = self._first_block_of_sector(sector) + self._blocks_per_sector(sector) - 1
        start = trailer_index * 16
        trailer = data[start:start + 16]
        return trailer if len(trailer) == 16 else b""

    @staticmethod
    def _card_byte_diffs(expected: bytes, actual: bytes) -> list[tuple[int, bytes, bytes]]:
        block_count = max(len(expected), len(actual)) // 16
        diffs: list[tuple[int, bytes, bytes]] = []
        for block in range(block_count):
            left = expected[block * 16:(block + 1) * 16]
            right = actual[block * 16:(block + 1) * 16]
            if left != right:
                diffs.append((block, left, right))
        return diffs

    @staticmethod
    def _block_zero_write_diagnostic(expected: bytes, actual: bytes, block_count: int) -> str:
        total = max(1, block_count)
        matching = max(0, total - 1)
        lines = [
            f"写入结果：其余 {matching}/{total} 个块已经写入并读回一致。",
            "唯一未改变的是块 00（UID/厂商块）。",
        ]
        if len(expected) >= 5 and len(actual) >= 5:
            expected_uid = expected[:4].hex(" ").upper()
            actual_uid = actual[:4].hex(" ").upper()
            lines.extend(
                (
                    f"待写入 UID：{expected_uid}（校验字节 {expected[4]:02X}）",
                    f"当前卡 UID：{actual_uid}（校验字节 {actual[4]:02X}）",
                )
            )
            if expected[5:] == actual[5:]:
                lines.append("块 00 中除 UID 和校验字节外，其余内容也完全一致。")
        else:
            lines.append(Backend._format_block_diff(0, expected, actual))
        lines.extend(
            (
                "原因：普通 MIFARE Classic 不能通过扇区密钥修改块 00。",
                "这不是解密失败，也不是其余卡片数据没有写入。",
                "下一步：先确认目标卡属于 GEN1A、CUID/Gen2 或其他可改 UID 类型，再选择对应写法；重复普通写入不会改变 UID。",
            )
        )
        return "\n".join(lines)

    @staticmethod
    def _format_block_diff(block: int, expected: bytes, actual: bytes) -> str:
        return f"块 {block:02d}：待写入={expected.hex(' ').upper() or '<空>'}；读回={actual.hex(' ').upper() or '<空>'}"

    def _refresh_workspace_from_pm3_files(self, command: str) -> None:
        client_dir = COMPAT_CLIENT.parent
        cutoff = max(0.0, self._command_started_at - 1.0)
        data_path = client_dir / "dumpdata.bin"
        keys_path = client_dir / "dumpkeys.bin"
        fresh_data = self._file_updated_after(data_path, cutoff)
        fresh_keys = self._file_updated_after(keys_path, cutoff)
        expected_data = command in {
            "workflow mifare_classic_autopwn",
            "workflow mifare_classic_local_dict",
            "workflow mifare_classic_nested_missing",
        } or command.startswith("hf mf dump")

        if fresh_data:
            self._set_card_read_snapshot(data_path, "已读取卡片数据")
            block_count = len([row for row in self._card_read_blocks if row.get("value") != "--"])
            self.cardReadDataTextChanged.emit()
            self.cardReadBlocksChanged.emit()
            self.selectedCardReadBlockChanged.emit()
        elif expected_data:
            self._card_read_data_text = "本次没有生成新的读卡数据"
            self._card_read_file = ""
            self._card_read_blocks = self._empty_data_blocks()
            self._selected_card_read_block_index = 0
            self.cardReadDataTextChanged.emit()
            self.cardReadBlocksChanged.emit()
            self.selectedCardReadBlockChanged.emit()

        if fresh_keys:
            self._key_matrix = self._read_workspace_key_matrix()
            self.keyMatrixChanged.emit()

        if fresh_data or fresh_keys or expected_data:
            if fresh_data:
                if self._pending_data_file and Path(self._pending_data_file).exists() and self._prepared_write_command:
                    self._write_plan_text = f"左侧已读取 {block_count} 块；右侧待写入数据仍保留"
                else:
                    self._prepared_write_command = ""
                    self._write_plan_text = f"左侧已读取 {block_count} 块；写卡前请先复制到右侧待写入区"
            elif fresh_keys:
                self._write_plan_text = "密钥已刷新；读卡数据会显示在左侧，待写入数据在右侧"
            elif expected_data:
                self._prepared_write_command = ""
                self._write_plan_text = "未读出整卡：请先补齐密钥后再读取整卡"
            self.writePlanTextChanged.emit()

    @staticmethod
    def _file_updated_after(path: Path, cutoff: float) -> bool:
        try:
            return path.exists() and path.stat().st_mtime >= cutoff
        except OSError:
            return False

    def _extract_key_scan_rows(self, text: str) -> dict[int, dict[str, object]]:
        rows: dict[int, dict[str, object]] = {}
        for line in text.splitlines():
            parts = [part.strip() for part in line.split("|")]
            if len(parts) < 6 or not parts[1].isdigit():
                continue
            key_a = self._normalize_key_text(parts[2])
            key_b = self._normalize_key_text(parts[4])
            if not key_a and not key_b:
                continue
            sector = int(parts[1])
            rows[sector] = {
                "sector": sector,
                "keyA": key_a or "FFFFFFFFFFFF",
                "keyB": key_b or "FFFFFFFFFFFF",
                "knownA": parts[3] == "1",
                "knownB": parts[5] == "1",
                "candidateA": bool(key_a),
                "candidateB": bool(key_b),
            }
        return rows

    def _write_key_status_rows(self, rows: dict[int, dict[str, object]]) -> None:
        if not rows:
            return
        payload = {
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "sectors": {
                str(sector): {
                    "knownA": bool(row.get("knownA")),
                    "knownB": bool(row.get("knownB")),
                }
                for sector, row in sorted(rows.items())
            },
        }
        try:
            KEY_STATUS_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            return
        if any("keyA" in row or "keyB" in row for row in rows.values()):
            self._record_scanned_key_rows(rows)

    def _record_scanned_key_rows(self, rows: dict[int, dict[str, object]]) -> None:
        if not rows:
            return
        sector_count = max(16, max(rows) + 1)
        scanned = self._load_key_store("scanned")
        if len(scanned) < sector_count:
            scanned.extend(self._empty_key_matrix(sector_count)[len(scanned):])
        for sector, row in rows.items():
            current = dict(scanned[sector])
            if row.get("knownA"):
                key_a = self._normalize_key_text(str(row.get("keyA", "")))
                if key_a:
                    current["keyA"] = key_a
                    current["knownA"] = True
                    current["candidateA"] = True
            if row.get("knownB"):
                key_b = self._normalize_key_text(str(row.get("keyB", "")))
                if key_b:
                    current["keyB"] = key_b
                    current["knownB"] = True
                    current["candidateB"] = True
            scanned[sector] = current
        self._save_key_store("scanned", scanned, "卡片扫描与分析结果")

    def _read_key_status_rows(self) -> dict[int, dict[str, bool]]:
        try:
            payload = json.loads(KEY_STATUS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        sectors = payload.get("sectors") if isinstance(payload, dict) else None
        if not isinstance(sectors, dict):
            return {}
        rows: dict[int, dict[str, bool]] = {}
        for raw_sector, raw_row in sectors.items():
            if not isinstance(raw_row, dict):
                continue
            try:
                sector = int(raw_sector)
            except ValueError:
                continue
            rows[sector] = {
                "knownA": bool(raw_row.get("knownA")),
                "knownB": bool(raw_row.get("knownB")),
            }
        return rows

    def _apply_key_scan_rows(self, rows: dict[int, dict[str, object]]) -> None:
        if rows:
            self._record_scanned_key_rows(rows)
            self._key_matrix = self._read_workspace_key_matrix()
            self._activate_runtime_keys(self._key_matrix)
            self.keyMatrixChanged.emit()

    def _write_key_status_from_matrix(self) -> None:
        rows = {
            int(row["sector"]): {
                "knownA": bool(row.get("knownA")),
                "knownB": bool(row.get("knownB")),
            }
            for row in self._key_matrix
        }
        self._write_key_status_rows(rows)

    @staticmethod
    def _write_key_matrix_file(matrix: list[dict[str, object]], target: Path) -> None:
        key_a = bytes.fromhex("".join(str(row["keyA"]) for row in matrix))
        key_b = bytes.fromhex("".join(str(row["keyB"]) for row in matrix))
        target.write_bytes(key_a + key_b)

    def _mark_all_workspace_keys_known(self, sector_count: int) -> None:
        rows = {sector: {"knownA": True, "knownB": True} for sector in range(sector_count)}
        self._write_key_status_rows(rows)

    def _ensure_key_library_db(self) -> None:
        KEY_LIBRARY_DB.parent.mkdir(parents=True, exist_ok=True)
        if not KEY_LIBRARY_DB.exists():
            seed = LEGACY_USER_KEY_LIBRARY_DB if LEGACY_USER_KEY_LIBRARY_DB.exists() else BUNDLED_KEY_LIBRARY_DB
            if seed.exists() and seed.resolve() != KEY_LIBRARY_DB.resolve():
                shutil.copy2(seed, KEY_LIBRARY_DB)
        with sqlite3.connect(KEY_LIBRARY_DB) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS key_library (
                    key TEXT PRIMARY KEY,
                    bucket TEXT NOT NULL,
                    sources TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_key_library_bucket ON key_library(bucket)")
            self._sync_public_key_seed(conn)
            conn.commit()
        try:
            KEY_LIBRARY_DB.chmod(0o600)
        except OSError:
            pass

    def _sync_public_key_seed(self, conn: sqlite3.Connection) -> None:
        seed_path = COMPAT_CLIENT.parent / "default_keys.dic"
        if not seed_path.is_file():
            raise RuntimeError(f"找不到锁定的默认密钥库：{seed_path}")

        keys = sorted(
            self._extract_keys_from_dictionary_text(
                seed_path.read_text(encoding="utf-8", errors="ignore")
            )
        )
        personal_keys = {
            str(row[0])
            for row in conn.execute(
                "SELECT key FROM key_library WHERE bucket = 'personal'"
            ).fetchall()
        }
        seeded_at = "deterministic-seed"
        expected = [
            (key, PUBLIC_KEY_SOURCE, PUBLIC_KEY_NOTE, seeded_at, seeded_at)
            for key in keys
            if key not in personal_keys
        ]
        current = conn.execute(
            """
            SELECT key, sources, note, created_at, updated_at
            FROM key_library
            WHERE bucket = 'public'
            ORDER BY key
            """
        ).fetchall()
        if current == expected:
            return

        conn.execute("DELETE FROM key_library WHERE bucket = 'public'")
        conn.executemany(
            """
            INSERT OR IGNORE INTO key_library
                (key, bucket, sources, note, created_at, updated_at)
            VALUES (?, 'public', ?, ?, ?, ?)
            """,
            expected,
        )

    @staticmethod
    def _extract_keys_from_dictionary_text(text: str) -> list[str]:
        keys: list[str] = []
        seen: set[str] = set()
        for raw_line in text.splitlines():
            line = raw_line
            for marker in ("#", "//", ";"):
                if marker in line:
                    line = line.split(marker, 1)[0]
            line = line.strip()
            if not line:
                continue

            matches = re.findall(r"(?<![0-9A-Fa-f])([0-9A-Fa-f]{12})(?![0-9A-Fa-f])", line)
            if not matches:
                compact = "".join(ch for ch in line.upper() if ch in "0123456789ABCDEF")
                matches = [compact] if len(compact) == 12 else []
            for raw_key in matches:
                key = raw_key.upper()
                if key not in seen:
                    seen.add(key)
                    keys.append(key)
        return keys

    def _add_keys_to_library(
        self,
        keys: list[str],
        bucket: str,
        source: str,
        note: str = "",
    ) -> tuple[int, int]:
        self._ensure_key_library_db()
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        inserted = 0
        existing = 0
        with sqlite3.connect(KEY_LIBRARY_DB) as conn:
            for raw_key in keys:
                key = self._normalize_key_text(raw_key)
                if not key:
                    continue
                row = conn.execute("SELECT bucket, sources FROM key_library WHERE key = ?", (key,)).fetchone()
                if row:
                    existing += 1
                    old_bucket, old_sources = row
                    sources = [item for item in str(old_sources).split("；") if item]
                    if source not in sources:
                        sources.append(source)
                    new_bucket = "personal" if old_bucket == "personal" or bucket == "personal" else bucket
                    conn.execute(
                        """
                        UPDATE key_library
                        SET bucket = ?, sources = ?, updated_at = ?
                        WHERE key = ?
                        """,
                        (new_bucket, "；".join(sources), now, key),
                    )
                    continue

                conn.execute(
                    """
                    INSERT INTO key_library (key, bucket, sources, note, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (key, bucket, source, note, now, now),
                )
                inserted += 1
            conn.commit()
        return inserted, existing

    def _key_library_counts(self) -> tuple[int, int]:
        self._ensure_key_library_db()
        with sqlite3.connect(KEY_LIBRARY_DB) as conn:
            public_count = conn.execute("SELECT COUNT(*) FROM key_library WHERE bucket = 'public'").fetchone()[0]
            personal_count = conn.execute("SELECT COUNT(*) FROM key_library WHERE bucket = 'personal'").fetchone()[0]
        return int(public_count), int(personal_count)

    def _library_keys(self, bucket: str) -> list[str]:
        self._ensure_key_library_db()
        with sqlite3.connect(KEY_LIBRARY_DB) as conn:
            rows = conn.execute(
                "SELECT key FROM key_library WHERE bucket = ? ORDER BY key",
                (bucket,),
            ).fetchall()
        return [str(row[0]) for row in rows]

    def _export_library_bucket_to_dic(self, bucket: str, filename: str) -> Path | None:
        keys = self._library_keys(bucket)
        if not keys:
            return None
        path = COMPAT_CLIENT.parent / filename
        path.write_text("\n".join(keys) + "\n", encoding="utf-8")
        return path

    def _build_key_library_summary(self) -> str:
        public_count, personal_count = self._key_library_counts()
        return f"公开默认库 {public_count} 条；我的密钥库 {personal_count} 条"

    def _refresh_library_summaries(self) -> None:
        self._key_library_text = self._build_key_library_summary()
        self._dictionary_text = self._build_dictionary_summary()
        self.keyLibraryTextChanged.emit()
        self.dictionaryTextChanged.emit()

    @staticmethod
    def _extract_uid_from_search_output(text: str) -> str:
        patterns = (
            r"卡片\s*UID\s*[:：]\s*([0-9A-Fa-f ]{8,})",
            r"\bUID\s*[:：]\s*([0-9A-Fa-f ]{8,})",
            r"\bUID\s+([0-9A-Fa-f ]{8,})",
        )
        for pattern in patterns:
            match = re.search(pattern, text)
            if not match:
                continue
            compact = "".join(ch for ch in match.group(1).upper() if ch in "0123456789ABCDEF")
            if len(compact) >= 8 and len(compact) % 2 == 0:
                return compact
        return ""

    @staticmethod
    def _extract_sak_from_search_output(text: str) -> str:
        match = re.search(
            r"\bSAK(?:\s*选择应答)?\s*[：:]\s*(?:0x)?([0-9A-Fa-f]{2})",
            text,
            re.IGNORECASE,
        )
        return match.group(1).upper() if match else ""

    @staticmethod
    def _extract_card_type_from_search_output(text: str) -> str:
        patterns = (
            r"卡片类型\s*[:：]\s*(.+)",
            r"\bTYPE\s*[:：]\s*(.+)",
        )
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()[:90]
        return ""

    @staticmethod
    def _card_memory_arg_from_search_output(text: str) -> int:
        lower = text.lower()
        if "mini" in lower:
            return 0
        if re.search(r"(mifare\s+classic|classic)\s*4k|\bs70\b", lower):
            return 4
        if re.search(r"(mifare\s+classic|classic)\s*1k|\bs50\b|1k\s*ev1", lower):
            return 1
        if re.search(r"(mifare\s+classic|classic)\s*2k", lower):
            return 2
        return 1

    @staticmethod
    def _output_has_no_card(text: str) -> bool:
        return any(
            marker in text
            for marker in (
                "没有发现",
                "没有选中",
                "卡片没有回应",
                "No tag found",
                "No card found",
                "No known/supported",
            )
        )

    @staticmethod
    def _output_is_mifare_classic(text: str) -> bool:
        lower = text.lower()
        return "mifare classic" in lower or "mifare plus 2k 安全等级 sl1" in lower or "s50" in lower or "s70" in lower

    def _local_dictionary_candidates(self, uid: str) -> list[tuple[str, Path]]:
        candidates: list[tuple[str, Path]] = []
        seen: set[Path] = set()

        def add(label: str, path: Path) -> None:
            if not path.exists() or not path.is_file():
                return
            resolved = path.resolve()
            if resolved in seen:
                return
            seen.add(resolved)
            candidates.append((label, path))

        def find_uid_dictionary(value: str) -> Path | None:
            keys_dir = COMPAT_CLIENT.parent / "keys"
            if not value or not keys_dir.exists():
                return None
            exact = keys_dir / f"{value}.dic"
            if exact.exists():
                return exact
            for path in keys_dir.glob("*.dic"):
                if path.stem.upper() == value:
                    return path
            return None

        uid_variants: list[tuple[str, str]] = []
        if uid:
            uid_variants.append((f"UID 专属库 {uid}", uid))
            bytes_list = [uid[index:index + 2] for index in range(0, len(uid), 2)]
            reversed_uid = "".join(reversed(bytes_list))
            if reversed_uid != uid:
                uid_variants.append((f"反向 UID 专属库 {reversed_uid}", reversed_uid))

        for label, value in uid_variants:
            path = find_uid_dictionary(value)
            if path:
                add(label, path)

        personal_path = self._export_library_bucket_to_dic("personal", "pm3_my_key_library.dic")
        if personal_path:
            add("我的密钥库", personal_path)

        add("IC 默认密钥库", COMPAT_CLIENT.parent / "default_keys.dic")

        public_path = self._export_library_bucket_to_dic("public", "pm3_public_key_library.dic")
        if public_path:
            add("公开默认库", public_path)
        return candidates

    @staticmethod
    def _prepare_dictionary_for_pm3(source_path: Path, index: int) -> str:
        safe_stem = re.sub(r"[^0-9A-Za-z_-]+", "_", source_path.stem).strip("_")[:28] or "dict"
        target = COMPAT_CLIENT.parent / f"pm3_localdict_{index:02d}_{safe_stem}.dic"
        shutil.copy2(source_path, target)
        return target.name

    def _merge_key_matrices(
        self,
        base: list[dict[str, object]],
        incoming: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        sector_count = max(16, len(base), len(incoming))
        merged = self._empty_key_matrix(sector_count)

        for sector in range(sector_count):
            if sector < len(base):
                merged[sector].update(base[sector])
            if sector >= len(incoming):
                continue

            incoming_row = incoming[sector]
            for key_field, known_field in (
                ("keyA", "knownA"),
                ("keyB", "knownB"),
            ):
                incoming_key = self._normalize_key_text(str(incoming_row.get(key_field, "")))
                incoming_known = bool(incoming_row.get(known_field))
                if incoming_known and incoming_key:
                    merged[sector][key_field] = incoming_key
                    merged[sector][known_field] = True
                    merged[sector]["candidate" + key_field[-1]] = True
                elif not merged[sector].get(known_field) and incoming_key:
                    merged[sector][key_field] = incoming_key
                    merged[sector]["candidate" + key_field[-1]] = bool(
                        incoming_row.get("candidate" + key_field[-1])
                    )
        return merged

    def _known_key_candidates(self, matrix: list[dict[str, object]]) -> list[dict[str, object]]:
        candidates: list[dict[str, object]] = []
        for row in matrix:
            sector = int(row["sector"])
            block = self._first_block_of_sector(sector)
            key_a = self._normalize_key_text(str(row.get("keyA", "")))
            key_b = self._normalize_key_text(str(row.get("keyB", "")))
            if row.get("knownA") and key_a:
                candidates.append({"sector": sector, "block": block, "type": "A", "key": key_a})
            if row.get("knownB") and key_b:
                candidates.append({"sector": sector, "block": block, "type": "B", "key": key_b})
        return candidates

    def _missing_key_targets(self, matrix: list[dict[str, object]]) -> list[dict[str, object]]:
        targets: list[dict[str, object]] = []
        for row in matrix:
            sector = int(row["sector"])
            block = self._first_block_of_sector(sector)
            if not row.get("knownA"):
                targets.append({"sector": sector, "block": block, "type": "A"})
            if not row.get("knownB"):
                targets.append({"sector": sector, "block": block, "type": "B"})
        return targets

    @staticmethod
    def _card_memory_arg_from_matrix(matrix: list[dict[str, object]]) -> int:
        sector_count = len(matrix)
        if sector_count <= 5:
            return 0
        if sector_count <= 16:
            return 1
        if sector_count <= 32:
            return 2
        return 4

    def _key_progress_summary(self, matrix: list[dict[str, object]]) -> str:
        known = sum(1 for row in matrix for key in ("knownA", "knownB") if row.get(key))
        candidates = sum(
            1
            for row in matrix
            for key_type in ("A", "B")
            if row.get(f"candidate{key_type}") and not row.get(f"known{key_type}")
        )
        total = len(matrix) * 2
        missing = self._missing_key_targets(matrix)
        if not missing:
            return f"密钥进度：已确认 {known}/{total}，没有缺失密钥。"
        preview = "、".join(f"{item['sector']:02d}{item['type']}" for item in missing[:10])
        suffix = "..." if len(missing) > 10 else ""
        candidate_text = f"；待验证候选 {candidates} 个" if candidates else ""
        return f"密钥进度：已确认 {known}/{total}{candidate_text}；缺失 {len(missing)} 个：{preview}{suffix}"

    @staticmethod
    def _extract_found_key_from_hardnested(text: str) -> str:
        patterns = (
            r"Found key\s*\[([0-9A-Fa-f]{12})\]",
            r"Found valid key[:\s]+([0-9A-Fa-f]{12})",
        )
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).upper()
        return ""

    def _set_workspace_key(self, sector: int, key_type: str, key: str) -> None:
        key = self._normalize_key_text(key)
        if not key:
            return
        matrix = self._load_key_store("scanned") or self._empty_key_matrix()
        if sector < 0 or sector >= len(matrix):
            return
        row = dict(matrix[sector])
        if key_type == "A":
            row["keyA"] = key
            row["knownA"] = True
            row["candidateA"] = True
        else:
            row["keyB"] = key
            row["knownB"] = True
            row["candidateB"] = True
        matrix[sector] = row
        self._save_key_store("scanned", matrix, "Nested/Hardnested 分析结果")
        self._key_matrix = self._read_workspace_key_matrix()
        self._activate_runtime_keys(self._key_matrix)
        self.keyMatrixChanged.emit()

    def _run_compat_client(self, command: str, ignore_cancel: bool = False) -> str:
        if self._cancel_requested and not ignore_cancel:
            raise CommandCancelled()
        if not COMPAT_CLIENT.exists():
            raise RuntimeError(f"找不到兼容内核：{COMPAT_CLIENT}")

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as handle:
            handle.write(f"{command}\nquit\n")
            script_path = handle.name
        try:
            env = os.environ.copy()
            env["PM3_LEGACY_BAUD"] = "9600"
            timeout = self._timeout_for_command(command)
            proc: subprocess.Popen[bytes] | None = None
            try:
                proc = subprocess.Popen(
                    [str(COMPAT_CLIENT), self._selected_port, script_path],
                    cwd=str(COMPAT_CLIENT.parent),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True,
                )
                with self._process_lock:
                    self._current_process = proc
                started_at = time.time()
                last_progress = -1
                while True:
                    if self._cancel_requested and not ignore_cancel:
                        self._terminate_process(proc)
                        raise CommandCancelled()
                    try:
                        stdout, stderr = proc.communicate(timeout=1)
                        break
                    except subprocess.TimeoutExpired:
                        elapsed = int(time.time() - started_at)
                        if elapsed >= timeout:
                            self._terminate_process(proc)
                            raise CommandTimedOut(
                                f"命令执行超过 {timeout} 秒，已自动停止。\n"
                                "常见原因：没有放卡、卡片距离不对、设备正在等待卡片回应，或这个命令本身需要更长时间。"
                            )
                        progress = min(timeout - 1, max(1, elapsed))
                        if progress != last_progress:
                            self._emit_task_progress(self._last_command, progress, timeout, "PM3 内核执行中")
                            last_progress = progress
            except subprocess.TimeoutExpired:
                self._terminate_process(proc)
                raise CommandTimedOut(
                    f"命令执行超过 {timeout} 秒，已自动停止。\n"
                    "常见原因：没有放卡、卡片距离不对、设备正在等待卡片回应，或这个命令本身需要更长时间。"
                )
            finally:
                with self._process_lock:
                    if self._current_process is proc:
                        self._current_process = None
            if self._cancel_requested and not ignore_cancel:
                raise CommandCancelled()
            text = clean_legacy_output(decode_process(stdout), command)
            err = localize_output(decode_process(stderr).strip())
            if err:
                text = f"{text}\n{err}".strip()
            if proc.returncode not in (0, None):
                detail = text or "底层客户端没有返回可读信息。"
                raise CommandExecutionError(f"{detail}\n底层客户端退出码：{proc.returncode}")
            return text or "命令已结束。"
        finally:
            try:
                os.unlink(script_path)
            except OSError:
                pass

    @staticmethod
    def _terminate_process(proc: subprocess.Popen[bytes] | None) -> None:
        if proc is None or proc.poll() is not None:
            return
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except Exception:  # noqa: BLE001
            try:
                proc.terminate()
            except Exception:
                pass
        try:
            proc.wait(timeout=2)
            return
        except Exception:
            pass
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:  # noqa: BLE001
            try:
                proc.kill()
            except Exception:
                pass

    @staticmethod
    def _timeout_for_command(command: str) -> int:
        normalized = command.strip().lower()
        quick_prefixes = ("hw ", "prefs ", "hf list")
        if normalized.startswith(quick_prefixes):
            return 8
        if normalized.startswith("hf mf chk") and ".dic" in normalized:
            return 180
        if normalized.startswith("hf mf ice"):
            return 60
        if normalized.startswith("hf mf mifare"):
            return 30
        if normalized.startswith("hf mf cload"):
            return 60
        if normalized.startswith("hf mf csave"):
            return 45
        if "mifare_autopwn" in normalized:
            return 35
        if "hardnested" in normalized:
            return 900
        if "nested" in normalized:
            return 45
        if any(token in normalized for token in ("autopwn", "darkside", "chk")):
            return 18
        if any(token in normalized for token in ("restore", "dump", "cload", "sim", "write", "cwipe", "csetuid")):
            return 18
        if normalized.startswith("script run mfkeys"):
            return 90
        if normalized.startswith("script run"):
            return 120
        return 12

    def _build_dictionary_summary(self) -> str:
        client_dir = COMPAT_CLIENT.parent
        named = [
            ("IC 默认密钥", client_dir / "default_keys.dic"),
            ("NTAG 默认密码", client_dir / "default_pwd.dic"),
        ]
        parts: list[str] = []
        for label, path in named:
            if path.exists():
                parts.append(f"{label} {self._count_nonempty_lines(path)} 条")
        try:
            public_count, personal_count = self._key_library_counts()
        except Exception:  # noqa: BLE001
            public_count, personal_count = 0, 0
        if public_count or personal_count:
            parts.append(f"公开默认库 {public_count} 条")
            parts.append(f"我的密钥库 {personal_count} 条")
        return "；".join(parts) if parts else "还没有找到本地字典库"

    def _build_script_summary(self) -> str:
        scripts_dir = COMPAT_CLIENT.parent / "scripts"
        scripts = sorted(path.name for path in scripts_dir.glob("*.lua")) if scripts_dir.exists() else []
        if not scripts:
            return "还没有找到本地脚本"
        names = "、".join(script[:-4] for script in scripts[:8])
        suffix = f" 等 {len(scripts)} 个" if len(scripts) > 8 else f" 共 {len(scripts)} 个"
        return names + suffix

    @staticmethod
    def _normalize_export_format(format_name: str) -> str:
        key = format_name.strip().lower().split()[0] if format_name.strip() else ""
        aliases = {
            "bin": "bin",
            "dump": "dump",
            "mfd": "mfd",
            "eml": "eml",
            "json": "json",
            "txt": "txt",
        }
        return aliases.get(key, "")

    def _current_card_data_bytes(self) -> tuple[bytes, str, bool]:
        if WORKSPACE_PENDING_DATA.exists():
            return WORKSPACE_PENDING_DATA.read_bytes(), "待写入工作区", False

        selected = Path(self._selected_data_file) if self._selected_data_file else None
        if (
            selected
            and selected.exists()
            and selected.name.lower() != "dumpkeys.bin"
            and selected.suffix.lower() in {".bin", ".dump", ".mfd"}
        ):
            return selected.read_bytes(), selected.name, False

        if WORKSPACE_READ_DATA.exists():
            return WORKSPACE_READ_DATA.read_bytes(), "当前卡读卡工作区", False

        if selected and selected.exists() and selected.suffix.lower() == ".eml":
            data = self._read_eml_bytes(selected)
            if data:
                return data, selected.name, False

        preview = self._data_blocks_to_bytes()
        if preview:
            return preview, "界面预览数据", True
        raise ValueError("当前还没有可导出的卡片数据。请先读取整卡或导入 .dump/.bin/.mfd/.eml 文件。")

    def _choose_export_path(self, key: str) -> Path | None:
        extension = {"bin": "bin", "dump": "dump", "mfd": "mfd", "eml": "eml", "json": "json", "txt": "txt"}[key]
        default_name = f"pm3_card_{time.strftime('%Y%m%d_%H%M%S')}.{extension}"
        script = (
            f'set exportPath to choose file name with prompt "请选择导出位置" '
            f'default name {json.dumps(default_name)} default location (path to downloads folder)\n'
            "POSIX path of exportPath"
        )
        try:
            proc = subprocess.run(
                ["osascript", "-e", script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
                check=False,
            )
        except Exception as error:  # noqa: BLE001
            self._append_log(f"打开导出保存窗口失败：{error}")
            return None
        if proc.returncode != 0:
            return None
        path = Path(proc.stdout.strip())
        if path.suffix.lower() != f".{extension}":
            path = path.with_suffix(f".{extension}")
        return path

    def _write_export_file(self, key: str, target: Path, data: bytes, source: str) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        if key in {"bin", "dump", "mfd"}:
            target.write_bytes(data)
            return
        if key == "eml":
            target.write_text(self._bytes_to_eml(data), encoding="utf-8")
            return
        if key == "json":
            target.write_text(
                json.dumps(self._bytes_to_export_json(data, source), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return
        if key == "txt":
            target.write_text(self._bytes_to_text_report(data, source), encoding="utf-8")
            return
        raise ValueError("不支持的导出格式。")

    @staticmethod
    def _bytes_to_eml(data: bytes) -> str:
        rows = [data[index:index + 16].hex().upper() for index in range(0, len(data), 16)]
        return "\n".join(rows) + ("\n" if rows else "")

    def _bytes_to_export_json(self, data: bytes, source: str) -> dict[str, object]:
        blocks = []
        for index in range(0, len(data), 16):
            chunk = data[index:index + 16]
            sector, block = self._sector_block_for_block_index(index // 16)
            blocks.append(
                {
                    "index": index // 16,
                    "sector": sector,
                    "block": block,
                    "data": chunk.hex(" ").upper(),
                    "trailer": block == self._blocks_per_sector(sector) - 1,
                }
            )
        return {
            "app": "PM3 中文助手",
            "format_version": 2,
            "source": source,
            "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "bytes": len(data),
            "blocks": blocks,
            "keys": self._matrix_from_dump_bytes(data, trusted=False),
        }

    def _bytes_to_text_report(self, data: bytes, source: str) -> str:
        lines = [
            "PM3 中文助手卡片数据导出",
            f"来源：{source}",
            f"导出时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"数据长度：{len(data)} 字节",
            "",
            "区/块        16字节数据",
        ]
        for index in range(0, len(data), 16):
            block_index = index // 16
            chunk = data[index:index + 16]
            sector, block = self._sector_block_for_block_index(block_index)
            trailer = "  密钥尾块" if block == self._blocks_per_sector(sector) - 1 else ""
            lines.append(f"{sector:02d}/{block}    {chunk.hex(' ').upper()}{trailer}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _read_eml_bytes(path: Path) -> bytes:
        chunks: list[bytes] = []
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for raw in handle:
                compact = "".join(ch for ch in raw.strip() if ch in "0123456789abcdefABCDEF")
                if len(compact) >= 32:
                    chunks.append(bytes.fromhex(compact[:32]))
        return b"".join(chunks)

    def _data_blocks_to_bytes(self) -> bytes:
        return self._blocks_to_bytes(self._data_blocks)

    @staticmethod
    def _blocks_to_bytes(blocks: list[dict[str, object]]) -> bytes:
        chunks: list[bytes] = []
        for row in blocks:
            value = str(row.get("value", ""))
            compact = "".join(ch for ch in value if ch in "0123456789abcdefABCDEF")
            if len(compact) == 32:
                chunks.append(bytes.fromhex(compact))
        return b"".join(chunks)

    def _prepare_magic_write_files(self) -> bool:
        data = self._blocks_to_bytes(self._data_blocks)
        if not data:
            self.loadSelectedDataToWorkspace()
            data = self._blocks_to_bytes(self._data_blocks)
        if not data:
            self._append_log("写入魔术卡失败：右侧还没有待写入数据。请先导入整卡数据，或从左侧复制到待写入区。")
            return False
        if len(data) != 1024:
            self._append_log(
                "写入魔术卡失败：当前兼容内核的魔术卡整卡写入只支持 1K/S50，也就是 64 块、1024 字节。\n"
                f"当前待写入数据大小：{len(data)} 字节。"
            )
            return False

        client_dir = COMPAT_CLIENT.parent
        eml_path = client_dir / "selected_data.eml"
        target_bin = client_dir / "selected_data_magic_target.bin"
        try:
            lines = [data[index:index + 16].hex().upper() for index in range(0, len(data), 16)]
            eml_path.write_text("\n".join(lines) + "\n", encoding="ascii")
            target_bin.write_bytes(data)
            WORKSPACE_PENDING_DATA.write_bytes(data)
        except OSError as error:
            self._append_log(f"写入魔术卡失败：无法准备 selected_data.eml。\n{error}")
            return False

        self._prepared_write_command = "hf mf cload selected_data"
        self._write_plan_text = self._friendly_write_plan(self._prepared_write_command)
        self.writePlanTextChanged.emit()
        return True

    @staticmethod
    def _compare_card_bytes(expected: bytes, actual: bytes) -> list[str]:
        block_count = max(len(expected), len(actual)) // 16
        lines: list[str] = []
        for block in range(block_count):
            left = expected[block * 16:(block + 1) * 16]
            right = actual[block * 16:(block + 1) * 16]
            if left == right:
                continue
            lines.append(
                f"块 {block:02d} 不一致：待写入={left.hex(' ').upper() or '<空>'}；读回={right.hex(' ').upper() or '<空>'}"
            )
        return lines

    def _prepare_data_file(self, path: Path) -> tuple[str, str, list[dict[str, object]]]:
        client_dir = COMPAT_CLIENT.parent
        suffix = path.suffix.lower()
        name = path.name.lower()

        if suffix == ".eml":
            data = self._read_eml_bytes(path)
            if len(data) not in {320, 1024, 2048, 4096}:
                raise ValueError("EML 文件没有包含完整的 Mifare Classic 卡片块。")
            self._discard_pending_write_target(clear_source=True)
            WORKSPACE_PENDING_DATA.write_bytes(data)
            (client_dir / "selected_data.eml").write_text(self._bytes_to_eml(data), encoding="ascii")
            matrix = self._matrix_from_dump_bytes(data)
            if matrix:
                self._save_key_store("source", matrix, f"导入文件：{path.name}")
                self._activate_runtime_keys()
            return (
                "hf mf cload selected_data",
                f"已把 {path.name} 载入独立待写区，共 {len(data) // 16} 块。",
                self._preview_blocks(WORKSPACE_PENDING_DATA),
            )

        if suffix == ".json":
            blocks = self._preview_json_blocks(path)
            if not any(row.get("value") not in {None, "", "--"} for row in blocks):
                raise ValueError("JSON 文件里没有找到可识别的卡片块数据。")
            target = client_dir / path.name
            shutil.copy2(path, target)
            self._discard_pending_write_target(clear_source=True)
            self._prepared_write_command = ""
            return "", f"JSON 卡片数据：{path.name}；已载入预览，暂不直接写回。", blocks

        if suffix == ".dic":
            target = client_dir / path.name
            shutil.copy2(path, target)
            self._discard_pending_write_target(clear_source=True)
            return "", f"密钥字典：{path.name}；可用于扫密钥，不是整卡数据。", self._preview_blocks(path)

        if suffix not in {".bin", ".mfd", ".dump"}:
            raise ValueError("暂不支持这个卡片文件格式。")

        if name == "dumpkeys.bin":
            sibling_data = path.with_name("dumpdata.bin")
            if sibling_data.exists():
                data = sibling_data.read_bytes()
                sector_count = self._mifare_sector_count_for_size(len(data))
                matrix = self._matrix_from_key_blob(path.read_bytes(), sector_count)
                if not matrix:
                    raise ValueError("dumpkeys.bin 的长度与同目录卡片数据不匹配。")
                self._discard_pending_write_target(clear_source=True)
                WORKSPACE_PENDING_DATA.write_bytes(data)
                self._save_key_store("source", matrix, f"导入密钥文件：{path.name}")
                self._activate_runtime_keys()
                command = self._restore_command_for_dump(WORKSPACE_PENDING_DATA)
                return command, "已分别载入卡片数据和来源密钥，可进行智能预检。", self._preview_blocks(WORKSPACE_PENDING_DATA)
            sector_count = len(path.read_bytes()) // 12
            matrix = self._matrix_from_key_blob(path.read_bytes(), sector_count)
            self._discard_pending_write_target(clear_source=True)
            if matrix:
                self._save_key_store("source", matrix, f"导入密钥文件：{path.name}")
                self._activate_runtime_keys()
            return "", "已载入来源密钥；还需要同目录的 dumpdata.bin 才能整卡写入。", self._empty_data_blocks()

        size = path.stat().st_size
        if size in {320, 1024, 2048, 4096}:
            data = path.read_bytes()
            self._discard_pending_write_target(clear_source=True)
            WORKSPACE_PENDING_DATA.write_bytes(data)
            sector_count = self._mifare_sector_count_for_size(size)
            sibling_keys = path.with_name("dumpkeys.bin")
            if sibling_keys.exists():
                matrix = self._matrix_from_key_blob(sibling_keys.read_bytes(), sector_count)
                source_note = "同目录 dumpkeys.bin"
            else:
                matrix = self._matrix_from_dump_bytes(data)
                source_note = "扇区尾块"
            if matrix:
                self._save_key_store("source", matrix, f"{path.name}：{source_note}")
                self._activate_runtime_keys()
            command = self._restore_command_for_dump(WORKSPACE_PENDING_DATA)
            return (
                command,
                f"已把 {path.name} 载入独立待写区，共 {size // 16} 块；密钥来自{source_note}。",
                self._preview_blocks(WORKSPACE_PENDING_DATA),
            )

        shutil.copy2(path, client_dir / path.name)
        self._discard_pending_write_target(clear_source=True)
        return "", "BIN 文件已复制到工作区，但大小不像 Mifare Classic dump，暂不能直接整卡写入。", self._preview_blocks(path)

    @staticmethod
    def _is_supported_card_file(path: Path) -> bool:
        suffix = path.suffix.lower()
        name = path.name.lower()
        if name in {"dumpdata.bin", "dumpkeys.bin"}:
            return True
        if suffix in {".eml", ".json", ".dic"}:
            return True
        if suffix in {".mfd", ".dump"}:
            try:
                return path.stat().st_size in {320, 1024, 2048, 4096}
            except OSError:
                return False
        if suffix == ".bin":
            try:
                size = path.stat().st_size
            except OSError:
                return False
            return size >= 16 and (size % 4 == 0 or size in {320, 1024, 2048, 4096})
        return False

    def _preview_blocks(self, path: Path) -> list[dict[str, object]]:
        suffix = path.suffix.lower()
        try:
            if suffix == ".eml":
                return self._preview_eml_blocks(path)
            if suffix in {".bin", ".mfd", ".dump"}:
                return self._preview_binary_blocks(path)
            if suffix == ".json":
                return self._preview_json_blocks(path)
        except Exception:
            return self._empty_data_blocks()
        return self._empty_data_blocks()

    @staticmethod
    def _preview_binary_blocks(path: Path) -> list[dict[str, object]]:
        data = path.read_bytes()
        block_count = len(data) // 16
        blocks: list[dict[str, object]] = []
        for index in range(block_count):
            chunk = data[index * 16:(index + 1) * 16]
            sector, block = Backend._sector_block_for_block_index(index)
            blocks.append(
                {
                    "label": f"{sector:02d}/{block}",
                    "value": chunk.hex(" ").upper() if len(chunk) == 16 else "--",
                    "trailer": block == Backend._blocks_per_sector(sector) - 1,
                }
            )
        return blocks

    @staticmethod
    def _preview_eml_blocks(path: Path) -> list[dict[str, object]]:
        rows: list[str] = []
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for raw in handle:
                compact = "".join(ch for ch in raw.strip() if ch in "0123456789abcdefABCDEF")
                if len(compact) >= 32:
                    rows.append(compact[:32].upper())
                if len(rows) >= 256:
                    break
        blocks: list[dict[str, object]] = []
        for index in range(max(len(rows), 64)):
            value = rows[index] if index < len(rows) else ""
            spaced = " ".join(value[i:i + 2] for i in range(0, len(value), 2)) if value else "--"
            sector, block = Backend._sector_block_for_block_index(index)
            blocks.append(
                {
                    "label": f"{sector:02d}/{block}",
                    "value": spaced,
                    "trailer": block == Backend._blocks_per_sector(sector) - 1,
                }
            )
        return blocks

    @staticmethod
    def _preview_json_blocks(path: Path) -> list[dict[str, object]]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            return Backend._empty_data_blocks()

        candidates: list[object] = []
        if isinstance(payload, dict):
            for key in ("blocks", "data", "pages", "dump"):
                value = payload.get(key)
                if isinstance(value, list):
                    candidates = value
                    break
        elif isinstance(payload, list):
            candidates = payload

        blocks: list[dict[str, object]] = []
        for index in range(max(len(candidates), 64)):
            item = candidates[index] if index < len(candidates) else ""
            if isinstance(item, dict):
                raw = str(item.get("data") or item.get("value") or item.get("bytes") or "")
            else:
                raw = str(item)
            compact = "".join(ch for ch in raw if ch in "0123456789abcdefABCDEF")[:32]
            spaced = " ".join(compact[i:i + 2] for i in range(0, len(compact), 2)).upper() if compact else "--"
            sector, block = Backend._sector_block_for_block_index(index)
            blocks.append(
                {
                    "label": f"{sector:02d}/{block}",
                    "value": spaced,
                    "trailer": block == Backend._blocks_per_sector(sector) - 1,
                }
            )
        return blocks

    @staticmethod
    def _empty_data_blocks() -> list[dict[str, object]]:
        return [{"label": f"{index // 4:02d}/{index % 4}", "value": "--", "trailer": index % 4 == 3} for index in range(16)]

    @staticmethod
    def _empty_key_matrix(sector_count: int = 16) -> list[dict[str, object]]:
        return [
            {
                "sector": index,
                "label": f"{index:02d}",
                "keyA": "FFFFFFFFFFFF",
                "keyB": "FFFFFFFFFFFF",
                "knownA": False,
                "knownB": False,
                "candidateA": False,
                "candidateB": False,
            }
            for index in range(sector_count)
        ]

    @staticmethod
    def _normalize_key_text(value: str) -> str:
        compact = "".join(ch for ch in value.upper() if ch in "0123456789ABCDEF")
        return compact if len(compact) == 12 else ""

    @staticmethod
    def _normalize_uid_text(value: str) -> str:
        compact = "".join(ch for ch in value.upper() if ch in "0123456789ABCDEF")
        return compact if len(compact) == 8 else ""

    def _verify_integrity_manifest(self) -> str:
        if not INTEGRITY_MANIFEST.exists():
            return "完整性校验未启用"
        try:
            manifest = json.loads(INTEGRITY_MANIFEST.read_text(encoding="utf-8"))
        except Exception as error:  # noqa: BLE001
            return f"完整性清单不可读：{error}"

        files = manifest.get("files", {})
        if not isinstance(files, dict) or not files:
            return "完整性清单为空"

        mismatches: list[str] = []
        missing: list[str] = []
        for relative_path, expected_hash in files.items():
            path = INTEGRITY_ROOT / str(relative_path)
            if not path.exists():
                missing.append(str(relative_path))
                continue
            actual_hash = self._sha256_file(path)
            if actual_hash != str(expected_hash).lower():
                mismatches.append(str(relative_path))
                continue
            if IS_BUNDLED_APP and str(relative_path).startswith("compat-clients/iceman-ice_v3.1.0/client/"):
                runtime_path = ROOT / str(relative_path)
                if not runtime_path.exists() or self._sha256_file(runtime_path) != str(expected_hash).lower():
                    mismatches.append(f"运行副本：{relative_path}")

        if missing or mismatches:
            details = []
            if missing:
                details.append(f"缺少 {len(missing)} 项")
            if mismatches:
                details.append(f"变更 {len(mismatches)} 项")
            return "完整性需确认：" + "，".join(details)
        return "完整性正常"

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _key_store_path(name: str) -> Path:
        return WORKSPACE_KEY_DIR / f"{name}.json"

    def _save_key_store(self, name: str, matrix: list[dict[str, object]], source: str) -> None:
        sectors: dict[str, object] = {}
        for row in matrix:
            sector = int(row.get("sector", 0))
            known_a = bool(row.get("knownA"))
            known_b = bool(row.get("knownB"))
            key_a = self._normalize_key_text(str(row.get("keyA", "")))
            key_b = self._normalize_key_text(str(row.get("keyB", "")))
            candidate_a = bool(row.get("candidateA")) and bool(key_a)
            candidate_b = bool(row.get("candidateB")) and bool(key_b)
            sectors[str(sector)] = {
                "keyA": key_a if known_a or candidate_a else None,
                "keyB": key_b if known_b or candidate_b else None,
                "knownA": known_a,
                "knownB": known_b,
                "candidateA": candidate_a or known_a,
                "candidateB": candidate_b or known_b,
            }
        self._write_json_file(
            self._key_store_path(name),
            {
                "storage_version": 2,
                "source": source,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "sectors": sectors,
            },
        )

    def _load_key_store(self, name: str) -> list[dict[str, object]]:
        payload = self._read_json_file(self._key_store_path(name))
        raw_sectors = payload.get("sectors")
        if not isinstance(raw_sectors, dict) or not raw_sectors:
            return []
        sector_numbers = [int(value) for value in raw_sectors if str(value).isdigit()]
        if not sector_numbers:
            return []
        matrix = self._empty_key_matrix(max(sector_numbers) + 1)
        for sector in sector_numbers:
            raw = raw_sectors.get(str(sector))
            if not isinstance(raw, dict):
                continue
            key_a = self._normalize_key_text(str(raw.get("keyA") or ""))
            key_b = self._normalize_key_text(str(raw.get("keyB") or ""))
            known_a = bool(raw.get("knownA")) and bool(key_a)
            known_b = bool(raw.get("knownB")) and bool(key_b)
            candidate_a = bool(raw.get("candidateA", bool(key_a))) and bool(key_a)
            candidate_b = bool(raw.get("candidateB", bool(key_b))) and bool(key_b)
            matrix[sector].update(
                {
                    "keyA": key_a if known_a or candidate_a else "FFFFFFFFFFFF",
                    "keyB": key_b if known_b or candidate_b else "FFFFFFFFFFFF",
                    "knownA": known_a,
                    "knownB": known_b,
                    "candidateA": candidate_a or known_a,
                    "candidateB": candidate_b or known_b,
                }
            )
        return matrix

    def _read_legacy_key_matrix(self) -> list[dict[str, object]]:
        path = COMPAT_CLIENT.parent / "dumpkeys.bin"
        if not path.exists():
            return self._empty_key_matrix()
        data = path.read_bytes()
        sector_count = min(40, len(data) // 12)
        if sector_count <= 0:
            return self._empty_key_matrix()
        key_a_blob = data[:sector_count * 6]
        key_b_blob = data[sector_count * 6:sector_count * 12]
        matrix = self._empty_key_matrix(sector_count)
        status_rows = self._read_key_status_rows()
        for sector in range(sector_count):
            key_a = key_a_blob[sector * 6:(sector + 1) * 6].hex().upper()
            key_b = key_b_blob[sector * 6:(sector + 1) * 6].hex().upper()
            status = status_rows.get(sector)
            known_a = bool(status["knownA"]) if status else key_a != "FFFFFFFFFFFF"
            known_b = bool(status["knownB"]) if status else key_b != "FFFFFFFFFFFF"
            matrix[sector] = {
                "sector": sector,
                "label": f"{sector:02d}",
                "keyA": key_a,
                "keyB": key_b,
                "knownA": known_a,
                "knownB": known_b,
                "candidateA": key_a != "FFFFFFFFFFFF" or known_a,
                "candidateB": key_b != "FFFFFFFFFFFF" or known_b,
            }
        return matrix

    def _read_workspace_key_matrix(self) -> list[dict[str, object]]:
        stores = [
            self._load_key_store("source"),
            self._load_key_store("scanned"),
            self._load_key_store("manual"),
        ]
        populated = [matrix for matrix in stores if matrix]
        if not populated:
            return self._read_legacy_key_matrix()

        sector_count = max(len(matrix) for matrix in populated)
        merged = self._empty_key_matrix(sector_count)
        for matrix in populated:
            for sector, row in enumerate(matrix):
                if sector >= sector_count:
                    break
                if row.get("knownA"):
                    merged[sector]["keyA"] = str(row["keyA"])
                    merged[sector]["knownA"] = True
                    merged[sector]["candidateA"] = True
                elif row.get("candidateA") and not merged[sector].get("knownA"):
                    merged[sector]["keyA"] = str(row["keyA"])
                    merged[sector]["candidateA"] = True
                if row.get("knownB"):
                    merged[sector]["keyB"] = str(row["keyB"])
                    merged[sector]["knownB"] = True
                    merged[sector]["candidateB"] = True
                elif row.get("candidateB") and not merged[sector].get("knownB"):
                    merged[sector]["keyB"] = str(row["keyB"])
                    merged[sector]["candidateB"] = True
        return merged

    @classmethod
    def _matrix_from_dump_bytes(cls, data: bytes, trusted: bool = False) -> list[dict[str, object]]:
        sector_count = cls._mifare_sector_count_for_size(len(data))
        if not sector_count:
            return []
        matrix = cls._empty_key_matrix(sector_count)
        for sector in range(sector_count):
            trailer_index = cls._first_block_of_sector(sector) + cls._blocks_per_sector(sector) - 1
            trailer = data[trailer_index * 16:(trailer_index + 1) * 16]
            if len(trailer) != 16:
                return []
            matrix[sector].update(
                {
                    "keyA": trailer[:6].hex().upper(),
                    "keyB": trailer[10:16].hex().upper(),
                    "knownA": trusted,
                    "knownB": trusted,
                    "candidateA": True,
                    "candidateB": True,
                }
            )
        return matrix

    @classmethod
    def _matrix_from_key_blob(
        cls,
        data: bytes,
        sector_count: int,
        trusted: bool = False,
    ) -> list[dict[str, object]]:
        if sector_count <= 0 or len(data) < sector_count * 12:
            return []
        matrix = cls._empty_key_matrix(sector_count)
        key_a_blob = data[:sector_count * 6]
        key_b_blob = data[sector_count * 6:sector_count * 12]
        for sector in range(sector_count):
            matrix[sector].update(
                {
                    "keyA": key_a_blob[sector * 6:(sector + 1) * 6].hex().upper(),
                    "keyB": key_b_blob[sector * 6:(sector + 1) * 6].hex().upper(),
                    "knownA": trusted,
                    "knownB": trusted,
                    "candidateA": True,
                    "candidateB": True,
                }
            )
        return matrix

    def _activate_runtime_keys(self, matrix: list[dict[str, object]] | None = None) -> None:
        active = matrix or self._read_workspace_key_matrix()
        self._write_key_matrix_file(active, COMPAT_CLIENT.parent / "dumpkeys.bin")
        self._key_matrix = active
        self._write_key_status_from_matrix()

    @staticmethod
    def _write_dumpkeys_from_dump(source: Path, target: Path) -> bool:
        payload = Backend._dumpkeys_bytes_from_dump(source.read_bytes())
        if payload is None:
            return False
        target.write_bytes(payload)
        return True

    @staticmethod
    def _dumpkeys_bytes_from_dump(data: bytes) -> bytes | None:
        sector_count = Backend._mifare_sector_count_for_size(len(data))
        if not sector_count:
            return None

        key_a: list[bytes] = []
        key_b: list[bytes] = []
        for sector in range(sector_count):
            trailer_index = Backend._first_block_of_sector(sector) + Backend._blocks_per_sector(sector) - 1
            trailer = data[trailer_index * 16:(trailer_index + 1) * 16]
            if len(trailer) != 16:
                return None
            key_a.append(trailer[:6])
            key_b.append(trailer[10:16])
        return b"".join(key_a + key_b)

    @staticmethod
    def _mifare_sector_count_for_size(size: int) -> int:
        return {320: 5, 1024: 16, 2048: 32, 4096: 40}.get(size, 0)

    @staticmethod
    def _first_block_of_sector(sector: int) -> int:
        return sector * 4 if sector < 32 else 128 + (sector - 32) * 16

    @staticmethod
    def _blocks_per_sector(sector: int) -> int:
        return 4 if sector < 32 else 16

    @staticmethod
    def _sector_block_for_block_index(block_index: int) -> tuple[int, int]:
        if block_index < 128:
            return block_index // 4, block_index % 4
        sector = 32 + (block_index - 128) // 16
        return sector, (block_index - 128) % 16

    @staticmethod
    def _restore_command_for_dump(path: Path) -> str:
        size = path.stat().st_size
        if size == 320:
            return "hf mf restore 0"
        if size == 2048:
            return "hf mf restore 2"
        if size == 4096:
            return "hf mf restore 4"
        return "hf mf restore"

    @staticmethod
    def _friendly_write_plan(command: str) -> str:
        if command.startswith("hf mf restore"):
            return "普通 IC 模式：可写普通数据块和密钥尾块；块 00 / UID 会保留目标卡原值"
        if command.startswith("hf mf cload"):
            return "GEN1A 魔术卡模式：可尝试写块 00 / UID；执行前会先检查目标卡"
        if command:
            return f"已准备写入：{command}"
        return "仅预览：当前文件还不能直接写卡"

    @staticmethod
    def _normalize_local_path(value: str) -> Path:
        if value.startswith("file://"):
            parsed = urlparse(value)
            return Path(unquote(parsed.path))
        return Path(value)

    @staticmethod
    def _count_nonempty_lines(path: Path) -> int:
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                return sum(1 for line in handle if line.strip() and not line.lstrip().startswith("#"))
        except OSError:
            return 0

    @staticmethod
    def _extract_firmware_text(output: str) -> str:
        for line in output.splitlines():
            text = line.strip()
            lower = text.lower()
            if not text:
                continue
            if "version" in lower or "firmware" in lower or "bootrom" in lower or "os:" in lower:
                return text[:100]
        return "PM3 Easy 兼容模式已通信"


def main() -> int:
    os.umask(0o077)
    ensure_runtime_assets()
    if sys.platform == "darwin":
        os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

    app = QGuiApplication(sys.argv)
    app.setOrganizationName("PM3 Native")
    app.setApplicationName("PM3 Native")

    engine = QQmlApplicationEngine()
    backend = Backend()
    app.aboutToQuit.connect(backend.shutdown)
    engine.rootContext().setContextProperty("backend", backend)
    qml_file = BUNDLED_QML_FILE if IS_BUNDLED_APP else Path(__file__).with_name("Main.qml")
    engine.load(QUrl.fromLocalFile(str(qml_file)))
    if not engine.rootObjects():
        return 1
    root_window = engine.rootObjects()[0]
    apply_macos_window_style(root_window)
    root_window.show()
    QTimer.singleShot(200, lambda: apply_macos_window_style(root_window))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
