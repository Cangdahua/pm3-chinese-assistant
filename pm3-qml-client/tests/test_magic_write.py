from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path


TEST_ROOT = tempfile.TemporaryDirectory()
os.environ["PM3_WORKSPACE_ROOT"] = str(Path(TEST_ROOT.name) / "workspace")
MAIN_PATH = Path(__file__).resolve().parents[1] / "main.py"
SPEC = importlib.util.spec_from_file_location("pm3_main_tests", MAIN_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MagicWriteTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(MODULE.WORKSPACE_ROOT, ignore_errors=True)
        MODULE.WORKSPACE_ROOT.mkdir(parents=True)
        runtime_dir = Path(TEST_ROOT.name) / "runtime"
        shutil.rmtree(runtime_dir, ignore_errors=True)
        runtime_dir.mkdir(parents=True)
        MODULE.COMPAT_CLIENT = runtime_dir / "proxmark3"
        MODULE.COMPAT_CLIENT.write_bytes(b"test runtime")
        runtime_scripts = runtime_dir / "scripts"
        runtime_scripts.mkdir()
        bundled_scripts = MODULE.BUNDLED_COMPAT_CLIENT_DIR / "scripts"
        for script_name in MODULE.AUDITED_READ_ONLY_SCRIPTS:
            shutil.copy2(bundled_scripts / f"{script_name}.lua", runtime_scripts)
        shutil.copy2(
            MODULE.BUNDLED_COMPAT_CLIENT_DIR / "default_keys.dic",
            runtime_dir / "default_keys.dic",
        )
        MODULE.KEY_STATUS_FILE = runtime_dir / "dumpkeys-status.json"
        MODULE.KEY_LIBRARY_DB = Path(TEST_ROOT.name) / "key_library.sqlite"
        MODULE.KEY_LIBRARY_DB.unlink(missing_ok=True)
        MODULE.LEGACY_USER_KEY_LIBRARY_DB = Path(TEST_ROOT.name) / "missing-legacy.sqlite"
        MODULE.BUNDLED_KEY_LIBRARY_DB = Path(TEST_ROOT.name) / "missing-bundled.sqlite"
        MODULE.WORKSPACE_STATE_FILE.write_text(
            json.dumps({"storage_version": 2}),
            encoding="utf-8",
        )
        self.backend = MODULE.Backend()
        self.backend._emit_task_progress = lambda *args: None

    def test_usage_reminder_is_non_blocking_and_has_no_persistence_api(self) -> None:
        qml = (MAIN_PATH.parent / "Main.qml").read_text(encoding="utf-8")

        self.assertFalse(hasattr(self.backend, "shouldShowTerms"))
        self.assertFalse(hasattr(self.backend, "acceptUsageTerms"))
        self.assertNotIn("termsPopup", qml)
        self.assertNotIn("我已理解并同意", qml)
        self.assertIn("请仅在自有或已获明确授权的卡片与设备上使用", qml)

    def test_public_library_matches_locked_compat_dictionary(self) -> None:
        source = MODULE.COMPAT_CLIENT.parent / "default_keys.dic"
        expected = sorted(
            MODULE.Backend._extract_keys_from_dictionary_text(
                source.read_text(encoding="utf-8")
            )
        )
        with sqlite3.connect(MODULE.KEY_LIBRARY_DB) as conn:
            rows = conn.execute(
                """
                SELECT key, bucket, sources, note, created_at, updated_at
                FROM key_library
                ORDER BY key
                """
            ).fetchall()

        self.assertEqual([row[0] for row in rows], expected)
        self.assertTrue(rows)
        self.assertTrue(all(row[1] == "public" for row in rows))
        self.assertTrue(all(row[2] == MODULE.PUBLIC_KEY_SOURCE for row in rows))
        self.assertTrue(all(row[3] == MODULE.PUBLIC_KEY_NOTE for row in rows))
        self.assertTrue(all(row[4:] == ("deterministic-seed", "deterministic-seed") for row in rows))
        self.assertFalse(hasattr(MODULE, "PUBLIC_KEY_SOURCES"))
        self.assertFalse(hasattr(self.backend, "updatePublicKeyLibrary"))

    def test_bundled_database_and_backend_reference_only_locked_compat_seed(self) -> None:
        locked_source = MODULE.BUNDLED_COMPAT_CLIENT_DIR / "default_keys.dic"
        expected = sorted(
            MODULE.Backend._extract_keys_from_dictionary_text(
                locked_source.read_text(encoding="utf-8")
            )
        )
        bundled_db = MAIN_PATH.parent / "data/key_library.sqlite"
        with sqlite3.connect(f"file:{bundled_db}?mode=ro", uri=True) as conn:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            rows = conn.execute(
                "SELECT key, bucket, sources, note FROM key_library ORDER BY key"
            ).fetchall()

        backend_source = MAIN_PATH.read_text(encoding="utf-8")
        self.assertEqual(integrity, "ok")
        self.assertEqual([row[0] for row in rows], expected)
        self.assertTrue(all(row[1] == "public" for row in rows))
        self.assertTrue(all(row[2] == MODULE.PUBLIC_KEY_SOURCE for row in rows))
        self.assertTrue(all(row[3] == MODULE.PUBLIC_KEY_NOTE for row in rows))
        self.assertNotIn("vendor-win", backend_source)
        self.assertNotIn("urllib.request", backend_source)

    def test_public_seed_replaces_stale_rows_and_preserves_personal_keys(self) -> None:
        stale_key = "DEADBEEF1234"
        personal_key = "13579BDF2468"
        with sqlite3.connect(MODULE.KEY_LIBRARY_DB) as conn:
            conn.execute(
                """
                INSERT INTO key_library
                    (key, bucket, sources, note, created_at, updated_at)
                VALUES (?, 'public', 'remote mutable source', '', 'old', 'old')
                """,
                (stale_key,),
            )
            conn.execute(
                """
                INSERT INTO key_library
                    (key, bucket, sources, note, created_at, updated_at)
                VALUES (?, 'personal', 'manual', '', 'now', 'now')
                """,
                (personal_key,),
            )
            conn.commit()

        self.backend._ensure_key_library_db()

        with sqlite3.connect(MODULE.KEY_LIBRARY_DB) as conn:
            stale = conn.execute(
                "SELECT 1 FROM key_library WHERE key = ?",
                (stale_key,),
            ).fetchone()
            personal = conn.execute(
                "SELECT bucket FROM key_library WHERE key = ?",
                (personal_key,),
            ).fetchone()
            remote_sources = conn.execute(
                "SELECT COUNT(*) FROM key_library WHERE bucket = 'public' AND sources != ?",
                (MODULE.PUBLIC_KEY_SOURCE,),
            ).fetchone()[0]

        self.assertIsNone(stale)
        self.assertEqual(personal, ("personal",))
        self.assertEqual(remote_sources, 0)

    def test_dumpkeys_are_rebuilt_from_sector_trailers(self) -> None:
        data = bytearray(1024)
        for sector in range(16):
            trailer_block = sector * 4 + 3
            start = trailer_block * 16
            key_a = bytes([sector]) * 6
            key_b = bytes([sector + 16]) * 6
            data[start:start + 16] = key_a + bytes.fromhex("FF078069") + key_b

        keys = MODULE.Backend._dumpkeys_bytes_from_dump(bytes(data))

        self.assertIsNotNone(keys)
        assert keys is not None
        self.assertEqual(len(keys), 192)
        self.assertEqual(keys[:6], bytes([0]) * 6)
        self.assertEqual(keys[90:96], bytes([15]) * 6)
        self.assertEqual(keys[96:102], bytes([16]) * 6)

    def test_raw_ack_requires_a_standalone_success_byte(self) -> None:
        self.assertTrue(self.backend._raw_magic_ack_received("received 1 octets\n0A"))
        self.assertFalse(self.backend._raw_magic_ack_received("wupC1 error"))
        self.assertFalse(self.backend._raw_magic_ack_received("payload 0A00"))

    def test_block_order_keeps_uid_block_last(self) -> None:
        target = bytes(1024)
        order: list[int] = []
        self.backend._write_magic_block_raw = lambda block, data: (
            order.append(block) is None,
            "ok",
        )

        _lines, failed = self.backend._write_magic_blocks_raw(
            target,
            [0, 7, 1, 3, 2],
            "测试",
        )

        self.assertFalse(failed)
        self.assertEqual(order, [1, 2, 3, 7, 0])

    def test_raw_write_always_closes_the_rf_field(self) -> None:
        commands: list[str] = []

        def run(command: str, ignore_cancel: bool = False) -> str:
            commands.append(command)
            return "" if command.endswith("5000") else "received 1 octets\n0A"

        self.backend._run_compat_client = run
        ok, _detail = self.backend._write_magic_block_raw(0, bytes(16))

        self.assertTrue(ok)
        self.assertTrue(commands[-1].endswith("5000"))

    def test_raw_write_stops_on_first_missing_ack(self) -> None:
        commands: list[str] = []

        def run(command: str, ignore_cancel: bool = False) -> str:
            commands.append(command)
            if command.endswith("43"):
                return "wupC1 error"
            return "" if command.endswith("5000") else "received 1 octets\n0A"

        self.backend._run_compat_client = run
        ok, detail = self.backend._write_magic_block_raw(0, bytes(16))

        self.assertFalse(ok)
        self.assertIn("确认后门", detail)
        self.assertTrue(commands[-1].endswith("5000"))
        self.assertEqual(len(commands), 3)

    def test_unknown_scan_does_not_replace_source_key(self) -> None:
        source = self.backend._empty_key_matrix()
        source[0].update(
            {
                "keyA": "A1A2A3A4A5A6",
                "keyB": "A1A2A3A4A5A6",
                "knownA": True,
                "knownB": True,
            }
        )
        self.backend._save_key_store("source", source, "test source")
        self.backend._record_scanned_key_rows(
            {
                0: {
                    "sector": 0,
                    "keyA": "FFFFFFFFFFFF",
                    "keyB": "FFFFFFFFFFFF",
                    "knownA": False,
                    "knownB": False,
                }
            }
        )

        merged = self.backend._read_workspace_key_matrix()

        self.assertTrue(merged[0]["knownA"])
        self.assertEqual(merged[0]["keyA"], "A1A2A3A4A5A6")

    def test_read_snapshot_does_not_touch_pending_target(self) -> None:
        target = bytes.fromhex("AA" * 1024)
        current = bytes.fromhex("55" * 1024)
        MODULE.WORKSPACE_PENDING_DATA.parent.mkdir(parents=True, exist_ok=True)
        MODULE.WORKSPACE_PENDING_DATA.write_bytes(target)
        temporary_read = MODULE.WORKSPACE_ROOT / "incoming.bin"
        temporary_read.write_bytes(current)

        self.backend._set_card_read_snapshot(temporary_read)

        self.assertEqual(MODULE.WORKSPACE_PENDING_DATA.read_bytes(), target)
        self.assertEqual(MODULE.WORKSPACE_READ_DATA.read_bytes(), current)

    def test_rescue_state_is_classified_separately(self) -> None:
        output = """卡片 UID：01 02 03 04
ATQA 防冲突参数：00 02
SAK 选择应答：88 [2]
卡片类型：Infineon MIFARE Classic 1K
魔术卡指令回应（GEN 1a）：是
"""

        capability = self.backend._classify_card_capability(output)

        self.assertEqual(capability["kind"], "rescue_gen1a")

    def test_mifare_plus_search_classification_is_pure_and_explicit(self) -> None:
        cases = {
            "没有发现已支持的 13.56MHz 高频卡": ("no_card", "", ""),
            "卡片 UID：11 22 33 44\nSAK 选择应答：08\n卡片类型：NXP MIFARE Classic 1K": (
                "not_plus",
                "11223344",
                "08",
            ),
            "卡片 UID：04 A1 B2 C3 D4 E5 F6\nSAK 选择应答：10 [2]\n卡片类型：NXP MIFARE Plus 2k SL2": (
                "plus",
                "04A1B2C3D4E5F6",
                "10",
            ),
            "卡片 UID：01 02 03 04\nSAK 选择应答：08 [2]\n卡片类型：NXP MIFARE CLASSIC 1k | Plus 2k SL1 | 1k EV1": (
                "possible_plus",
                "01020304",
                "08",
            ),
        }

        for output, (kind, uid, sak) in cases.items():
            with self.subTest(kind=kind):
                assessment = self.backend._classify_mifare_plus_search_output(output)
                self.assertEqual(assessment["kind"], kind)
                self.assertEqual(assessment["uid"], uid)
                self.assertEqual(assessment["sak"], sak)
        plus = self.backend._classify_mifare_plus_search_output(
            "卡片 UID：04 A1 B2 C3 D4 E5 F6\nSAK：10\n卡片类型：NXP MIFARE Plus 2k SL2"
        )
        self.assertIn("SL2", plus["security_level"])

    def test_mifare_plus_inspect_executes_only_safe_search(self) -> None:
        commands: list[str] = []
        finished: list[tuple[str, bool, str]] = []
        search_output = (
            "卡片 UID：04 A1 B2 C3 D4 E5 F6\n"
            "SAK 选择应答：10 [2]\n"
            "卡片类型：NXP MIFARE Plus 2k SL2"
        )
        self.backend._run_compat_client = lambda command, ignore_cancel=False: (
            commands.append(command) or search_output
        )
        self.backend.commandFinished.connect(
            lambda _label, output, ok, command: finished.append((output, ok, command))
        )

        self.backend._run_command_worker("MIFARE Plus 只读识别", "workflow mifare_plus_inspect")

        self.assertEqual(commands, ["hf search"])
        self.assertTrue(finished[-1][1])
        self.assertEqual(finished[-1][2], "workflow mifare_plus_inspect")
        result = finished[-1][0]
        self.assertIn("【结果：成功】", result)
        self.assertIn("04 A1 B2 C3 D4 E5 F6", result)
        self.assertIn("SL2", result)
        self.assertIn("SL3/AES 深度认证与数据访问仍因当前固件能力未开放", result)
        self.assertFalse(any(token in command for command in commands for token in ("raw", "write", "script run")))

    def test_mifare_plus_inspect_fails_for_no_card_and_non_plus(self) -> None:
        outputs = (
            "没有发现已支持的 13.56MHz 高频卡",
            "卡片 UID：11 22 33 44\nSAK：04\n卡片类型：ISO14443-A Ultralight",
        )

        for output in outputs:
            with self.subTest(output=output):
                commands: list[str] = []
                self.backend._run_compat_client = lambda command, ignore_cancel=False, value=output: (
                    commands.append(command) or value
                )
                result = self.backend._run_mifare_plus_inspect_workflow()
                self.assertEqual(commands, ["hf search"])
                self.assertIn("【结果：失败】", result)
                self.assertIn("流程停止：", result)

    def test_incomplete_transaction_becomes_resumable_after_restart(self) -> None:
        self.backend._begin_write_transaction("test", bytes(1024))
        self.backend._update_write_transaction("writing", "block 12", diff_blocks=[12])

        restarted = MODULE.Backend()

        self.assertEqual(restarted._write_transaction["status"], "interrupted")
        self.assertIn("按差异继续", restarted.writeTransactionText)

    def test_auto_route_refuses_unknown_card_without_writing(self) -> None:
        MODULE.WORKSPACE_PENDING_DATA.parent.mkdir(parents=True, exist_ok=True)
        MODULE.WORKSPACE_PENDING_DATA.write_bytes(bytes(1024))
        self.backend._run_compat_client = lambda command, ignore_cancel=False: "卡片 UID：11 22 33 44\n卡片类型：未知高频卡"
        self.backend._run_magic_write_workflow = lambda *_args: self.fail("magic write must not run")
        self.backend._run_smart_write_workflow = lambda: self.fail("ordinary write must not run")

        result = self.backend._run_auto_write_workflow()

        self.assertIn("无法为当前卡片选择可靠的写入策略", result)
        self.assertEqual(self.backend._write_transaction["status"], "failed")

    def test_auto_route_requires_gen1a_probe_before_magic_write(self) -> None:
        MODULE.WORKSPACE_PENDING_DATA.parent.mkdir(parents=True, exist_ok=True)
        MODULE.WORKSPACE_PENDING_DATA.write_bytes(bytes(1024))
        search = """卡片 UID：47 08 52 56
ATQA 防冲突参数：00 04
SAK 选择应答：08 [2]
卡片类型：NXP MIFARE Classic 1K
魔术卡指令回应（GEN 1a）：是
"""
        self.backend._run_compat_client = lambda command, ignore_cancel=False: search
        self.backend._probe_gen1a_write_path = lambda: (False, "no ack")
        self.backend._run_magic_write_workflow = lambda *_args: self.fail("magic write must not run")

        result = self.backend._run_auto_write_workflow()

        self.assertIn("没有发送任何块数据", result)
        self.assertEqual(self.backend._write_transaction["status"], "failed")

    def test_auto_route_ordinary_card_uses_smart_writer(self) -> None:
        MODULE.WORKSPACE_PENDING_DATA.parent.mkdir(parents=True, exist_ok=True)
        MODULE.WORKSPACE_PENDING_DATA.write_bytes(bytes(1024))
        search = """卡片 UID：11 22 33 44
ATQA 防冲突参数：00 04
SAK 选择应答：08 [2]
卡片类型：NXP MIFARE Classic 1K
"""
        called: list[str] = []
        self.backend._run_compat_client = lambda command, ignore_cancel=False: search
        self.backend._run_smart_write_workflow = lambda: called.append("smart") or "【结果：成功】\n64/64 块一致"

        result = self.backend._run_auto_write_workflow()

        self.assertEqual(called, ["smart"])
        self.assertIn("【结果：成功】", result)
        self.assertEqual(self.backend._write_transaction["status"], "completed")

    def test_magic_write_stops_when_full_backup_cannot_be_read(self) -> None:
        target = bytes(1024)
        MODULE.WORKSPACE_PENDING_DATA.parent.mkdir(parents=True, exist_ok=True)
        MODULE.WORKSPACE_PENDING_DATA.write_bytes(target)
        self.backend._data_blocks = self.backend._preview_binary_blocks(MODULE.WORKSPACE_PENDING_DATA)
        search = """卡片 UID：11 22 33 44
ATQA 防冲突参数：00 04
SAK 选择应答：08 [2]
卡片类型：NXP MIFARE Classic 1K
魔术卡指令回应（GEN 1a）：是
"""
        self.backend._run_compat_client = lambda *_args, **_kwargs: "本次没有生成转储"
        self.backend._write_magic_blocks_raw = lambda *_args: self.fail("write must not run without backup")

        result = self.backend._run_magic_write_workflow(search)

        self.assertIn("无法制作完整写前备份", result)
        self.assertIn("没有发送任何块数据", result)
        self.assertEqual(self.backend._write_transaction["status"], "failed")

    def test_magic_write_rejects_invalid_uid_bcc_before_device_access(self) -> None:
        target = bytearray(1024)
        target[:5] = bytes.fromhex("0102030400")
        MODULE.WORKSPACE_PENDING_DATA.parent.mkdir(parents=True, exist_ok=True)
        MODULE.WORKSPACE_PENDING_DATA.write_bytes(target)
        self.backend._data_blocks = self.backend._preview_binary_blocks(MODULE.WORKSPACE_PENDING_DATA)
        self.backend._run_compat_client = lambda *_args, **_kwargs: self.fail("device must not be accessed")

        result = self.backend._run_magic_write_workflow()

        self.assertIn("BCC", result)

    def test_ordinary_write_stops_on_read_length_mismatch(self) -> None:
        target = bytes(1024)
        MODULE.WORKSPACE_PENDING_DATA.parent.mkdir(parents=True, exist_ok=True)
        MODULE.WORKSPACE_PENDING_DATA.write_bytes(target)
        commands: list[str] = []

        def run(command: str, ignore_cancel: bool = False) -> str:
            commands.append(command)
            return "本次没有生成转储"

        self.backend._run_compat_client = run

        result = self.backend._run_smart_write_workflow()

        self.assertIn("本次没有发送写块命令", result)
        self.assertFalse(any(command.startswith("hf mf wrbl") for command in commands))
        self.assertEqual(self.backend._write_transaction["status"], "failed")

    def test_preview_only_import_discards_previous_write_target(self) -> None:
        old_target = bytes.fromhex("AA" * 1024)
        MODULE.WORKSPACE_PENDING_DATA.parent.mkdir(parents=True, exist_ok=True)
        MODULE.WORKSPACE_PENDING_DATA.write_bytes(old_target)
        incoming = Path(TEST_ROOT.name) / "incoming.json"
        incoming.write_text(json.dumps({"blocks": ["00" * 16] * 64}), encoding="utf-8")
        self.backend._selected_data_file = str(incoming)

        loaded = self.backend.loadSelectedDataToWorkspace()

        self.assertTrue(loaded)
        self.assertFalse(MODULE.WORKSPACE_PENDING_DATA.exists())
        self.assertEqual(self.backend._pending_data_file, "")
        self.assertEqual(self.backend.dataBlocks[0]["value"], "00 " * 15 + "00")
        self.assertIn("仅预览", self.backend.writePlanText)

    def test_exported_json_round_trips_block_data(self) -> None:
        data = bytes(range(16)) + bytes(1024 - 16)
        path = Path(TEST_ROOT.name) / "roundtrip.json"
        path.write_text(json.dumps(self.backend._bytes_to_export_json(data, "test")), encoding="utf-8")

        rows = self.backend._preview_json_blocks(path)

        self.assertEqual(rows[0]["value"], data[:16].hex(" ").upper())

    def test_timeout_is_reported_as_failure(self) -> None:
        results: list[bool] = []
        self.backend.commandFinished.connect(lambda _label, _output, ok, _command: results.append(ok))

        def timeout(*_args, **_kwargs):
            raise MODULE.CommandTimedOut("命令执行超过 12 秒，已自动停止。")

        self.backend._run_compat_client = timeout
        self.backend._run_command_worker("超时测试", "hf search")

        self.assertFalse(results[-1])
        self.assertEqual(self.backend.statusText, "失败")

    def test_dangerous_custom_commands_require_authorization(self) -> None:
        self.backend._selected_port = "/dev/cu.test"

        self.backend.runCommand("自定义命令", "hf mf wrbl 1 A FFFFFFFFFFFF 00000000000000000000000000000000")

        self.assertFalse(self.backend.busy)
        self.assertIn("危险操作已锁定", self.backend.logText)
        self.assertTrue(self.backend._command_requires_authorization("hf 14a raw -p -a 43"))

    def test_mutating_commands_fail_closed_by_capability(self) -> None:
        cases = {
            "lf hid clone 2006ec0c86": MODULE.COMMAND_CAPABILITY_CARD_MUTATION,
            "hf mfu restore source.bin": MODULE.COMMAND_CAPABILITY_CARD_MUTATION,
            "hf mfu wrbl 4 01020304": MODULE.COMMAND_CAPABILITY_CARD_MUTATION,
            "hf 15 write 1 01020304": MODULE.COMMAND_CAPABILITY_CARD_MUTATION,
            "hf 15 restore source.bin": MODULE.COMMAND_CAPABILITY_CARD_MUTATION,
            "hf iclass writeblk 6 AFA785A7DAB33378": MODULE.COMMAND_CAPABILITY_CARD_MUTATION,
            "lf t55xx wipe": MODULE.COMMAND_CAPABILITY_CARD_MUTATION,
            "hf mf csetuid 01020304": MODULE.COMMAND_CAPABILITY_CARD_MUTATION,
            "hf 14a raw -p -a 43": MODULE.COMMAND_CAPABILITY_RAW,
            "hf mf sim": MODULE.COMMAND_CAPABILITY_EMULATION,
            "hf mf chk *1 ? t": MODULE.COMMAND_CAPABILITY_EMULATION,
            "hf mf nested 1 0 A FFFFFFFFFFFF t": MODULE.COMMAND_CAPABILITY_EMULATION,
            "hf mf csave e 1": MODULE.COMMAND_CAPABILITY_EMULATION,
            "hf mf csave u 1": MODULE.COMMAND_CAPABILITY_RESTRICTED,
            "hf 14a sim": MODULE.COMMAND_CAPABILITY_EMULATION,
            "lf em 410xsim 0102030405": MODULE.COMMAND_CAPABILITY_EMULATION,
            "lf t55xx read 1 p DEADBEEF": MODULE.COMMAND_CAPABILITY_CARD_MUTATION,
            "lf t55xx read 1 p DEADBEEF o": MODULE.COMMAND_CAPABILITY_CARD_MUTATION,
            "lf t55xx detect p DEADBEEF": MODULE.COMMAND_CAPABILITY_CARD_MUTATION,
            "lf t55xx dump DEADBEEF": MODULE.COMMAND_CAPABILITY_CARD_MUTATION,
            "lf t55xx dump DEADBEEF o": MODULE.COMMAND_CAPABILITY_CARD_MUTATION,
            "hf mfu dump": MODULE.COMMAND_CAPABILITY_CARD_MUTATION,
            "hf mfu info k DEADBEEF": MODULE.COMMAND_CAPABILITY_CARD_MUTATION,
            "hf mfu rdbl b 4 k DEADBEEF": MODULE.COMMAND_CAPABILITY_CARD_MUTATION,
            "hw bootloader": MODULE.COMMAND_CAPABILITY_FIRMWARE,
            "flash fullimage.elf": MODULE.COMMAND_CAPABILITY_FIRMWARE,
            "workflow mifare_magic_rescue": MODULE.COMMAND_CAPABILITY_CARD_MUTATION,
            "hf future frobnicate": MODULE.COMMAND_CAPABILITY_RESTRICTED,
        }

        for command, capability in cases.items():
            with self.subTest(command=command):
                self.assertEqual(self.backend._classify_command_capability(command), capability)
                self.assertTrue(self.backend._command_requires_authorization(command))

    def test_read_only_commands_remain_available_without_authorization(self) -> None:
        commands = (
            "hw version",
            "hw ping",
            "hw status",
            "hw tune",
            "hf search",
            "hf 14a reader",
            "hf mf chk *1 ? d",
            "hf mf dump",
            "hf mf rdbl 1 A FFFFFFFFFFFF",
            "hf mf nested 1 0 A FFFFFFFFFFFF d",
            "hf mfu info",
            "hf mfu info h",
            "hf mfu rdbl b 4",
            "hf mfu rdbl h",
            "hf iclass reader",
            "lf search",
            "lf hid read",
            "lf em 410x_read",
            "lf indala read",
            "lf t55xx detect",
            "lf t55xx read 1",
            "lf t55xx config",
            "lf t55xx dump",
            "lf t55xx dump h",
            "workflow mifare_default_key_scan",
            "workflow mifare_nonce_assist",
            "workflow mifare_plus_inspect",
            "script run ndef_dump",
            "script run emul2dump",
            "script run tracetest",
            "script run parameters",
            "script run emul2html",
            "script run htmldump",
        )

        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(
                    self.backend._classify_command_capability(command),
                    MODULE.COMMAND_CAPABILITY_READ_ONLY,
                )
                self.assertFalse(self.backend._command_requires_authorization(command))

    def test_authorization_normalizes_case_and_horizontal_whitespace(self) -> None:
        cases = {
            "  HF\tMF   WRBL  1 A FFFFFFFFFFFF 00  ": True,
            "\tLf   HiD\tClOnE 2006ec0c86\t": True,
            "  ScRiPt\tRuN  ReMaGiC.LuA  ": True,
            "  HF\tSeArCh  ": False,
            "\tWORKFLOW   MIFARE_DEFAULT_KEY_SCAN ": False,
        }

        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(self.backend._command_requires_authorization(command), expected)

    def test_dangerous_and_unaudited_scripts_require_authorization(self) -> None:
        cases = {
            "script run remagic": MODULE.COMMAND_CAPABILITY_DANGEROUS_SCRIPT,
            "script run lf_bulk_program.lua": MODULE.COMMAND_CAPABILITY_DANGEROUS_SCRIPT,
            "script run test_t55x7_ask": MODULE.COMMAND_CAPABILITY_DANGEROUS_SCRIPT,
            "script run test_t55x7_fsk": MODULE.COMMAND_CAPABILITY_DANGEROUS_SCRIPT,
            "script run test_t55x7_psk": MODULE.COMMAND_CAPABILITY_DANGEROUS_SCRIPT,
            "script run test_t55x7_bi": MODULE.COMMAND_CAPABILITY_DANGEROUS_SCRIPT,
            "script run didump": MODULE.COMMAND_CAPABILITY_DANGEROUS_SCRIPT,
            "script run tnp3dump.lua": MODULE.COMMAND_CAPABILITY_DANGEROUS_SCRIPT,
            "script run ndef_dump -o arbitrary.eml": MODULE.COMMAND_CAPABILITY_SCRIPT,
            "script run future_read_only_name": MODULE.COMMAND_CAPABILITY_SCRIPT,
            "script run": MODULE.COMMAND_CAPABILITY_SCRIPT,
        }

        for command, capability in cases.items():
            with self.subTest(command=command):
                self.assertEqual(self.backend._classify_command_capability(command), capability)
                self.assertTrue(self.backend._command_requires_authorization(command))

    def test_audited_read_only_script_fails_closed_if_replaced(self) -> None:
        command = "script run ndef_dump"
        script_path = MODULE.COMPAT_CLIENT.parent / "scripts/ndef_dump.lua"

        self.assertFalse(self.backend._command_requires_authorization(command))
        script_path.write_text("-- replaced after review\n", encoding="utf-8")

        self.assertEqual(
            self.backend._classify_command_capability(command),
            MODULE.COMMAND_CAPABILITY_SCRIPT,
        )
        self.assertTrue(self.backend._command_requires_authorization(command))

    def test_qml_action_catalog_danger_flags_match_backend_policy(self) -> None:
        qml_path = MAIN_PATH.with_name("Main.qml")
        qml = qml_path.read_text(encoding="utf-8")
        action_pattern = re.compile(r'\{[^{}\n]*\bcommand:\s*"([^"]+)"[^{}\n]*\}')
        actions = [(match.group(0), match.group(1)) for match in action_pattern.finditer(qml)]

        self.assertGreaterEqual(len(actions), 40, "QML action catalog parser no longer covers the built-in commands")
        for action, command in actions:
            with self.subTest(command=command):
                explicitly_dangerous = bool(re.search(r"\bdanger:\s*true\b", action))
                self.assertEqual(
                    self.backend._command_requires_authorization(command),
                    explicitly_dangerous,
                    f"QML danger marker and backend capability disagree for: {command}",
                )

        direct_commands = re.findall(r'backend\.runCommand\([^,]+,\s*"([^"]+)"\)', qml)
        self.assertGreaterEqual(len(direct_commands), 10)
        for command in direct_commands:
            with self.subTest(direct_command=command):
                self.assertFalse(
                    self.backend._command_requires_authorization(command),
                    f"QML calls a restricted command without an authorization path: {command}",
                )

    def test_multiple_or_multiline_custom_command_is_rejected(self) -> None:
        self.backend._selected_port = "/dev/cu.test"

        for command in ("hf search\nhf mf cwipe", "hf search;hf mf cwipe"):
            with self.subTest(command=repr(command)):
                previous_log = self.backend.logText
                self.backend.runAuthorizedCommand("自定义命令", command, True)
                self.assertFalse(self.backend.busy)
                self.assertIn("命令已拒绝", self.backend.logText[len(previous_log):])

    def test_trailing_and_unicode_line_breaks_are_rejected_before_stripping(self) -> None:
        self.backend._selected_port = "/dev/cu.test"
        commands = (
            "hf search\n",
            "hf search\r",
            "hf search\vhf mf cwipe",
            "hf search\u2028hf mf cwipe",
            "hf search\x00hf mf cwipe",
            "hf search\x7fhf mf cwipe",
            "hf search\x80hf mf cwipe",
            "hf search\u200bhf mf cwipe",
        )

        for command in commands:
            with self.subTest(command=repr(command)):
                previous_log = self.backend.logText
                self.backend.runAuthorizedCommand("自定义命令", command, True)
                self.assertFalse(self.backend.busy)
                self.assertIn("命令已拒绝", self.backend.logText[len(previous_log):])
                self.assertTrue(self.backend._command_requires_authorization(command))

    def test_external_dump_keys_start_as_unverified_candidates(self) -> None:
        data = bytearray(1024)
        data[48:64] = bytes.fromhex("A1A2A3A4A5A6FF078069B1B2B3B4B5B6")

        matrix = self.backend._matrix_from_dump_bytes(bytes(data))

        self.assertFalse(matrix[0]["knownA"])
        self.assertFalse(matrix[0]["knownB"])
        self.assertTrue(matrix[0]["candidateA"])
        self.assertTrue(matrix[0]["candidateB"])
        self.assertEqual(matrix[0]["keyA"], "A1A2A3A4A5A6")


if __name__ == "__main__":
    unittest.main()
