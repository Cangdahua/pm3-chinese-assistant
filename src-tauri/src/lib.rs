use serde::{Deserialize, Serialize};
use std::env;
use std::ffi::CString;
use std::fs::{self, OpenOptions};
use std::io::{self, Read, Write};
use std::mem::MaybeUninit;
use std::os::fd::RawFd;
use std::os::unix::fs::{FileTypeExt, OpenOptionsExt, PermissionsExt};
use std::os::unix::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process;
use std::process::{Child, Command, ExitStatus, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use wait_timeout::ChildExt;

const LEGACY_PM3_PACKET_SIZE: usize = 544;
const LEGACY_CMD_VERSION: u64 = 0x0107;
const LEGACY_CMD_ACK: u16 = 0x00ff;
const LEGACY_FRAME_HEADER_SIZE: usize = 16;
const LEGACY_MAX_PAYLOAD_SIZE: usize = 512;
const PROBE_TIMEOUT: Duration = Duration::from_secs(5);
const MAX_CAPTURE_BYTES: usize = 1024 * 1024;

const ALLOWED_COMMANDS: &[&str] = &[
    "hw version",
    "hw status",
    "hw tune",
    "hw ping",
    "hw detectreader",
    "mem info",
    "hf search",
    "hf tune",
    "hf list",
    "hf 14a reader",
    "hf 14a info",
    "hf 14a sniff",
    "hf 14b info",
    "hf felica reader",
    "hf iclass info",
    "hf legic info",
    "hf topaz reader",
    "hf st25tb info",
    "hf emv search",
    "hf mf info",
    "hf mf chk",
    "hf mf autopwn",
    "hf mf dump",
    "hf mf nested",
    "hf mf hardnested",
    "hf mf sniff",
    "hf mf darkside",
    "hf mf staticnested",
    "hf mfu info",
    "lf search",
    "lf tune",
    "lf read",
    "lf hid read",
    "lf em 410x_read",
    "lf t55xx detect",
    "lf t55xx dump",
    "lf indala read",
    "lf awid read",
    "lf sniff",
    "data plot",
    "data samples",
    "data print",
    "data askedge",
    "data detectclock",
    "script list",
    "script help",
    "prefs show",
];

const HELP_ROOTS: &[&str] = &[
    "analyse", "data", "emv", "hf", "hw", "lf", "mem", "mqtt", "nfc", "piv", "prefs", "reveng",
    "script", "smart", "trace", "usart", "wiegand",
];

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum CommandPolicy {
    Allowed,
    Mutating,
    Unsupported,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct SerialPortInfo {
    path: String,
    kind: String,
    likely_pm3: bool,
}

#[derive(Serialize)]
struct Pm3BinaryStatus {
    found: bool,
    path: Option<String>,
    version: Option<String>,
    error: Option<String>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct RunPm3Request {
    binary_path: Option<String>,
    port: Option<String>,
    command: String,
    offline: Option<bool>,
    timeout_ms: Option<u64>,
}

#[derive(Serialize)]
struct RunPm3Response {
    command: String,
    stdout: String,
    stderr: String,
    status: Option<i32>,
    ok: bool,
}

#[tauri::command]
fn list_serial_ports() -> Result<Vec<SerialPortInfo>, String> {
    let mut ports = Vec::new();
    let entries = fs::read_dir("/dev").map_err(|error| error.to_string())?;

    for entry in entries.flatten() {
        let name = entry.file_name().to_string_lossy().to_string();
        if !name.starts_with("cu.") {
            continue;
        }

        let path = format!("/dev/{name}");
        if validate_serial_port(&path).is_err() {
            continue;
        }

        let lower = name.to_lowercase();
        let likely_pm3 = serial_port_name_is_likely_pm3(Path::new(&path));
        let kind = if lower.contains("usbmodem") {
            "USB 设备"
        } else if lower.contains("usbserial") || lower.contains("wch") || lower.contains("slab") {
            "USB 串口"
        } else {
            "串口"
        };

        ports.push(SerialPortInfo {
            path,
            kind: kind.to_string(),
            likely_pm3,
        });
    }

    ports.sort_by(|left, right| {
        right
            .likely_pm3
            .cmp(&left.likely_pm3)
            .then_with(|| left.path.cmp(&right.path))
    });

    Ok(ports)
}

#[tauri::command]
async fn detect_pm3_binary(custom_path: Option<String>) -> Pm3BinaryStatus {
    match tauri::async_runtime::spawn_blocking(move || detect_pm3_binary_blocking(custom_path))
        .await
    {
        Ok(status) => status,
        Err(error) => Pm3BinaryStatus {
            found: false,
            path: None,
            version: None,
            error: Some(format!("PM3 内核检测任务失败：{error}")),
        },
    }
}

fn detect_pm3_binary_blocking(custom_path: Option<String>) -> Pm3BinaryStatus {
    if let Some(custom_path) = custom_path.filter(|path| !path.trim().is_empty()) {
        return detect_single_binary(&custom_path);
    }

    let candidates = binary_candidates();

    for candidate in candidates {
        if let Ok(binary) = validate_binary_candidate(&candidate) {
            if let Some(version) = run_version_probe(&binary) {
                return Pm3BinaryStatus {
                    found: true,
                    path: Some(binary),
                    version: Some(version),
                    error: None,
                };
            }
        }
    }

    Pm3BinaryStatus {
        found: false,
        path: None,
        version: None,
        error: Some("未在受信任位置找到 pm3 / proxmark3".to_string()),
    }
}

fn detect_single_binary(candidate: &str) -> Pm3BinaryStatus {
    match validate_binary_candidate(candidate) {
        Ok(binary) => {
            if let Some(version) = run_version_probe(&binary) {
                return Pm3BinaryStatus {
                    found: true,
                    path: Some(binary),
                    version: Some(version),
                    error: None,
                };
            }

            Pm3BinaryStatus {
                found: false,
                path: None,
                version: None,
                error: Some("受信任的 PM3 内核无法响应版本探测".to_string()),
            }
        }
        Err(error) => Pm3BinaryStatus {
            found: false,
            path: None,
            version: None,
            error: Some(error),
        },
    }
}

#[tauri::command]
async fn run_pm3_command(request: RunPm3Request) -> Result<RunPm3Response, String> {
    tauri::async_runtime::spawn_blocking(move || run_pm3_command_blocking(request))
        .await
        .map_err(|error| format!("PM3 后台任务失败：{error}"))?
}

fn run_pm3_command_blocking(request: RunPm3Request) -> Result<RunPm3Response, String> {
    let command_text = authorize_command(&request.command)?;

    let offline = request.offline.unwrap_or(false);
    let validated_port = if offline {
        None
    } else {
        let port = request
            .port
            .as_deref()
            .filter(|port| !port.trim().is_empty())
            .ok_or_else(|| "还没有选择 PM3 设备串口".to_string())?;
        Some(validate_serial_port(port)?)
    };
    let mut legacy_error = None;

    if !offline && command_text == "hw version" {
        if let Some(port) = validated_port.as_deref() {
            match run_legacy_version_probe(port, request.timeout_ms.unwrap_or(8_000)) {
                Ok(response) => return Ok(response),
                Err(error) => legacy_error = Some(error),
            }
        }
    }

    let binary = match resolve_binary(request.binary_path.as_deref()) {
        Ok(binary) => binary,
        Err(error) => {
            if let Some(legacy_error) = legacy_error {
                return Err(format!("PM3 Easy 兼容读取失败：{legacy_error}\n{error}"));
            }
            return Err(error);
        }
    };

    let mut command = Command::new(&binary);

    if offline && binary_is_pm3_wrapper(&binary) {
        command.arg("-o");
    }

    if binary_is_legacy_compat(&binary) {
        if offline {
            return run_legacy_offline_command(&binary, &command_text, request.timeout_ms);
        }

        let port = validated_port
            .as_deref()
            .ok_or_else(|| "还没有选择 PM3 设备串口".to_string())?;
        return run_legacy_cli_command(&binary, port, &command_text, request.timeout_ms);
    }

    if let Some(port) = validated_port.as_deref() {
        command.arg("-p").arg(port);
    }

    if command_text == "__version" {
        command.arg("--version");
    } else {
        command.arg("-c").arg(&command_text);
    }

    run_child_capture(
        command,
        command_text,
        request.timeout_ms.unwrap_or(120_000),
        None,
    )
}

fn authorize_command(raw_command: &str) -> Result<String, String> {
    if raw_command.chars().any(char::is_control) {
        return Err("命令不能包含换行或控制字符".to_string());
    }

    let command = raw_command.trim();
    if command.is_empty() {
        return Err("命令为空".to_string());
    }
    if command.len() > 256 {
        return Err("命令过长".to_string());
    }
    if command.contains([';', '|', '`']) || command.contains("&&") {
        return Err("一次只能执行一个 PM3 命令".to_string());
    }

    match classify_command(command) {
        CommandPolicy::Allowed => Ok(command.to_string()),
        CommandPolicy::Mutating => Err(
            "React/Tauri 实验原型已冻结为只读模式；写卡、模拟、擦除、刷写和脚本执行均被后端拒绝"
                .to_string(),
        ),
        CommandPolicy::Unsupported => Err(
            "React/Tauri 实验原型只允许后端明确列出的只读诊断命令；请使用 QML 主客户端".to_string(),
        ),
    }
}

fn classify_command(command: &str) -> CommandPolicy {
    let normalized = command
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .to_ascii_lowercase();
    let tokens = normalized.split_whitespace().collect::<Vec<_>>();

    if tokens.iter().any(|token| is_mutating_token(token))
        || ["script run", "prefs set", "hw reset"]
            .iter()
            .any(|prefix| normalized == *prefix || normalized.starts_with(&format!("{prefix} ")))
    {
        return CommandPolicy::Mutating;
    }

    if normalized == "help"
        || normalized == "__version"
        || ALLOWED_COMMANDS.contains(&normalized.as_str())
        || normalized
            .strip_suffix(" help")
            .is_some_and(|root| HELP_ROOTS.contains(&root))
    {
        CommandPolicy::Allowed
    } else {
        CommandPolicy::Unsupported
    }
}

fn is_mutating_token(token: &str) -> bool {
    matches!(
        token,
        "bootloader"
            | "clone"
            | "csetuid"
            | "cwipe"
            | "eload"
            | "emulate"
            | "emulation"
            | "flash"
            | "gen3uid"
            | "load"
            | "restore"
            | "sim"
            | "simulate"
            | "simulation"
            | "wipe"
            | "wrbl"
            | "write"
            | "writeblk"
    ) || token.contains("clone")
        || token.contains("restore")
        || token.contains("wipe")
        || token.contains("write")
}

fn serial_port_path_has_safe_shape(path: &Path) -> bool {
    if path.parent() != Some(Path::new("/dev")) {
        return false;
    }

    let Some(name) = path.file_name().and_then(|name| name.to_str()) else {
        return false;
    };

    name.len() > 3
        && name.starts_with("cu.")
        && name
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b'-'))
}

fn serial_port_name_is_likely_pm3(path: &Path) -> bool {
    path.file_name()
        .and_then(|name| name.to_str())
        .map(str::to_ascii_lowercase)
        .is_some_and(|name| {
            name.contains("usbmodem") || name.contains("proxmark") || name.contains("pm3")
        })
}

fn validate_serial_port(port: &str) -> Result<String, String> {
    if port != port.trim() || port.contains('\0') {
        return Err("串口路径格式无效".to_string());
    }

    let path = Path::new(port);
    if !serial_port_path_has_safe_shape(path) {
        return Err("仅允许使用 /dev/cu.* 串口设备".to_string());
    }

    let metadata = fs::metadata(path).map_err(|error| format!("无法检查串口 {port}：{error}"))?;
    if !metadata.file_type().is_char_device() {
        return Err("串口路径不是字符设备".to_string());
    }

    Ok(port.to_string())
}

fn run_legacy_offline_command(
    binary: &str,
    command_text: &str,
    timeout_ms: Option<u64>,
) -> Result<RunPm3Response, String> {
    if command_text != "help" && command_text != "__version" {
        return Ok(RunPm3Response {
            command: command_text.to_string(),
            stdout: String::new(),
            stderr: "兼容内核的离线帮助只支持总目录。连接设备后可以执行具体功能。".to_string(),
            status: Some(1),
            ok: false,
        });
    }

    let mut command = Command::new(binary);
    command.arg("-h");
    run_child_capture(
        command,
        command_text.to_string(),
        timeout_ms.unwrap_or(120_000),
        None,
    )
}

fn run_legacy_cli_command(
    binary: &str,
    port: &str,
    command_text: &str,
    timeout_ms: Option<u64>,
) -> Result<RunPm3Response, String> {
    let script = create_private_command_script(command_text)?;

    let mut command = Command::new(binary);
    command
        .arg(port)
        .arg(script.path())
        .env("PM3_LEGACY_BAUD", "9600");

    run_child_capture(
        command,
        command_text.to_string(),
        timeout_ms.unwrap_or(120_000),
        Some(command_text),
    )
}

struct TempCommandScript {
    path: PathBuf,
}

impl TempCommandScript {
    fn path(&self) -> &Path {
        &self.path
    }
}

impl Drop for TempCommandScript {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.path);
    }
}

fn create_private_command_script(command_text: &str) -> Result<TempCommandScript, String> {
    static NEXT_SCRIPT_ID: AtomicU64 = AtomicU64::new(0);

    for _ in 0..32 {
        let id = NEXT_SCRIPT_ID.fetch_add(1, Ordering::Relaxed);
        let path = env::temp_dir().join(format!(
            "pm3-cn-command-{}-{}-{id}.txt",
            process::id(),
            unix_nanos()
        ));
        let file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .open(&path);

        let mut file = match file {
            Ok(file) => file,
            Err(error) if error.kind() == io::ErrorKind::AlreadyExists => continue,
            Err(error) => return Err(format!("创建临时命令脚本失败：{error}")),
        };
        let script = TempCommandScript { path };

        fs::set_permissions(script.path(), fs::Permissions::from_mode(0o600))
            .map_err(|error| format!("设置临时命令脚本权限失败：{error}"))?;
        file.write_all(format!("{command_text}\nquit\n").as_bytes())
            .map_err(|error| format!("写入临时命令脚本失败：{error}"))?;
        file.flush()
            .map_err(|error| format!("刷新临时命令脚本失败：{error}"))?;

        return Ok(script);
    }

    Err("无法创建唯一的临时命令脚本".to_string())
}

fn run_child_capture(
    command: Command,
    command_text: String,
    timeout_ms: u64,
    legacy_command: Option<&str>,
) -> Result<RunPm3Response, String> {
    let timeout = Duration::from_millis(timeout_ms.clamp(1_000, 600_000));
    let captured = capture_command(command, timeout)?;
    let mut stdout = decode_and_clean_process_bytes(&captured.stdout.bytes, legacy_command);
    let mut stderr = decode_process_bytes(&captured.stderr.bytes);

    if captured.stdout.truncated {
        append_notice(&mut stdout, "PM3 标准输出超过 1 MiB，后续内容已丢弃");
    }
    if captured.stderr.truncated {
        append_notice(&mut stderr, "PM3 错误输出超过 1 MiB，后续内容已丢弃");
    }
    if captured.timed_out {
        append_notice(&mut stderr, "PM3 命令执行超时");
    }

    Ok(RunPm3Response {
        command: command_text,
        stdout,
        stderr,
        status: captured.status.code(),
        ok: !captured.timed_out && captured.status.success(),
    })
}

struct BoundedOutput {
    bytes: Vec<u8>,
    truncated: bool,
}

struct CapturedProcess {
    stdout: BoundedOutput,
    stderr: BoundedOutput,
    status: ExitStatus,
    timed_out: bool,
}

fn capture_command(mut command: Command, timeout: Duration) -> Result<CapturedProcess, String> {
    command
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .process_group(0);

    let mut child = command.spawn().map_err(|error| error.to_string())?;
    let process_group_id = child.id();
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| "无法捕获 PM3 标准输出".to_string())?;
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| "无法捕获 PM3 错误输出".to_string())?;
    let stdout_reader = spawn_bounded_reader(stdout);
    let stderr_reader = spawn_bounded_reader(stderr);

    let wait_result = child.wait_timeout(timeout);
    let (status, timed_out) = match wait_result {
        Ok(Some(status)) => (status, false),
        Ok(None) => {
            terminate_process_group(&mut child);
            let status = match child.wait() {
                Ok(status) => status,
                Err(error) => {
                    ensure_readers_finish(process_group_id, &stdout_reader, &stderr_reader);
                    let _ = stdout_reader.join();
                    let _ = stderr_reader.join();
                    return Err(error.to_string());
                }
            };
            (status, true)
        }
        Err(error) => {
            terminate_process_group(&mut child);
            let _ = child.wait();
            ensure_readers_finish(process_group_id, &stdout_reader, &stderr_reader);
            let _ = stdout_reader.join();
            let _ = stderr_reader.join();
            return Err(error.to_string());
        }
    };

    ensure_readers_finish(process_group_id, &stdout_reader, &stderr_reader);
    let stdout = join_bounded_reader(stdout_reader, "标准输出")?;
    let stderr = join_bounded_reader(stderr_reader, "错误输出")?;

    Ok(CapturedProcess {
        stdout,
        stderr,
        status,
        timed_out,
    })
}

fn spawn_bounded_reader<R>(mut reader: R) -> JoinHandle<io::Result<BoundedOutput>>
where
    R: Read + Send + 'static,
{
    thread::spawn(move || {
        let mut bytes = Vec::with_capacity(64 * 1024);
        let mut buffer = [0_u8; 16 * 1024];
        let mut truncated = false;

        loop {
            let count = reader.read(&mut buffer)?;
            if count == 0 {
                break;
            }

            let remaining = MAX_CAPTURE_BYTES.saturating_sub(bytes.len());
            let retained = count.min(remaining);
            bytes.extend_from_slice(&buffer[..retained]);
            truncated |= retained < count;
        }

        Ok(BoundedOutput { bytes, truncated })
    })
}

fn ensure_readers_finish(
    process_group_id: u32,
    stdout_reader: &JoinHandle<io::Result<BoundedOutput>>,
    stderr_reader: &JoinHandle<io::Result<BoundedOutput>>,
) {
    let deadline = Instant::now() + Duration::from_secs(1);
    while Instant::now() < deadline
        && (!stdout_reader.is_finished() || !stderr_reader.is_finished())
    {
        thread::sleep(Duration::from_millis(10));
    }

    if !stdout_reader.is_finished() || !stderr_reader.is_finished() {
        kill_process_group(process_group_id);
    }
}

fn join_bounded_reader(
    reader: JoinHandle<io::Result<BoundedOutput>>,
    label: &str,
) -> Result<BoundedOutput, String> {
    reader
        .join()
        .map_err(|_| format!("PM3 {label}读取线程异常退出"))?
        .map_err(|error| format!("读取 PM3 {label}失败：{error}"))
}

fn terminate_process_group(child: &mut Child) {
    kill_process_group(child.id());
    let _ = child.kill();
}

fn kill_process_group(process_group_id: u32) {
    if let Ok(process_group_id) = i32::try_from(process_group_id) {
        unsafe {
            libc::kill(-process_group_id, libc::SIGKILL);
        }
    }
}

fn append_notice(text: &mut String, notice: &str) {
    if !text.is_empty() && !text.ends_with('\n') {
        text.push('\n');
    }
    text.push_str(notice);
}

fn run_legacy_version_probe(port: &str, timeout_ms: u64) -> Result<RunPm3Response, String> {
    if !serial_port_name_is_likely_pm3(Path::new(port)) {
        return Err("兼容短帧探测仅允许名称包含 usbmodem、proxmark 或 pm3 的串口".to_string());
    }

    let timeout = Duration::from_millis(timeout_ms.clamp(1_000, 3_000));
    let response = legacy_pm3_exchange(port, LEGACY_CMD_VERSION, timeout)?;
    let text = decode_legacy_response(&response)?;
    let stdout = format!(
        "PM3 中文助手兼容模式：已按 PM3 Easy / 兼容短回包协议读取设备。\n{}\n\n原始回包：{} 字节",
        text.trim(),
        response.len()
    );

    Ok(RunPm3Response {
        command: "hw version".to_string(),
        stdout,
        stderr: String::new(),
        status: Some(0),
        ok: true,
    })
}

fn legacy_pm3_exchange(port: &str, command_id: u64, timeout: Duration) -> Result<Vec<u8>, String> {
    let path = CString::new(port).map_err(|_| "串口路径包含无效字符".to_string())?;
    let fd = unsafe {
        libc::open(
            path.as_ptr(),
            libc::O_RDWR | libc::O_NOCTTY | libc::O_NONBLOCK | libc::O_NOFOLLOW,
        )
    };
    if fd < 0 {
        return Err(format!(
            "无法打开串口 {port}: {}",
            io::Error::last_os_error()
        ));
    }

    let fd = FdGuard(fd);
    configure_legacy_serial(fd.raw())?;

    let mut packet = vec![0_u8; LEGACY_PM3_PACKET_SIZE];
    packet[..8].copy_from_slice(&command_id.to_le_bytes());
    write_all_fd(fd.raw(), &packet, timeout.min(Duration::from_secs(3)))?;

    let response = read_until_idle(fd.raw(), timeout, Duration::from_millis(600))?;
    if response.is_empty() {
        return Err("设备没有返回兼容模式数据".to_string());
    }

    Ok(response)
}

fn configure_legacy_serial(fd: RawFd) -> Result<(), String> {
    unsafe {
        let mut attrs = MaybeUninit::<libc::termios>::uninit();
        if libc::tcgetattr(fd, attrs.as_mut_ptr()) != 0 {
            return Err(format!("读取串口参数失败：{}", io::Error::last_os_error()));
        }

        let mut attrs = attrs.assume_init();
        attrs.c_iflag = libc::IGNPAR;
        attrs.c_oflag = 0;
        attrs.c_cflag = libc::CS8 | libc::CLOCAL | libc::CREAD;
        attrs.c_lflag = 0;

        if libc::cfsetispeed(&mut attrs, libc::B9600) != 0
            || libc::cfsetospeed(&mut attrs, libc::B9600) != 0
        {
            return Err(format!(
                "设置 9600 波特率失败：{}",
                io::Error::last_os_error()
            ));
        }

        attrs.c_cc[libc::VMIN] = 0;
        attrs.c_cc[libc::VTIME] = 0;

        if libc::tcsetattr(fd, libc::TCSANOW, &attrs) != 0 {
            return Err(format!("写入串口参数失败：{}", io::Error::last_os_error()));
        }

        libc::tcflush(fd, libc::TCIOFLUSH);
    }

    Ok(())
}

fn write_all_fd(fd: RawFd, mut data: &[u8], timeout: Duration) -> Result<(), String> {
    let start = Instant::now();

    while !data.is_empty() {
        if start.elapsed() >= timeout {
            return Err("写入 PM3 命令超时".to_string());
        }

        let wait = timeout
            .saturating_sub(start.elapsed())
            .min(Duration::from_millis(100));
        let mut poll_fd = libc::pollfd {
            fd,
            events: libc::POLLOUT,
            revents: 0,
        };
        let ready = unsafe { libc::poll(&mut poll_fd, 1, wait.as_millis().max(1) as i32) };
        if ready < 0 {
            let error = io::Error::last_os_error();
            if error.kind() == io::ErrorKind::Interrupted {
                continue;
            }
            return Err(format!("等待 PM3 可写失败：{error}"));
        }
        if ready == 0 {
            continue;
        }
        if poll_fd.revents & (libc::POLLERR | libc::POLLHUP | libc::POLLNVAL) != 0 {
            return Err("PM3 串口在写入前断开".to_string());
        }
        if poll_fd.revents & libc::POLLOUT == 0 {
            continue;
        }

        let written = unsafe { libc::write(fd, data.as_ptr().cast(), data.len()) };
        if written > 0 {
            data = &data[written as usize..];
            continue;
        }

        let error = io::Error::last_os_error();
        if error.kind() == io::ErrorKind::WouldBlock || error.kind() == io::ErrorKind::Interrupted {
            continue;
        }

        return Err(format!("写入 PM3 命令失败：{error}"));
    }

    Ok(())
}

fn read_until_idle(fd: RawFd, timeout: Duration, idle: Duration) -> Result<Vec<u8>, String> {
    let start = Instant::now();
    let mut last_data = None;
    let mut response = Vec::new();
    let mut buffer = [0_u8; 4096];

    while start.elapsed() < timeout {
        let wait = timeout
            .saturating_sub(start.elapsed())
            .min(Duration::from_millis(100));
        let mut poll_fd = libc::pollfd {
            fd,
            events: libc::POLLIN,
            revents: 0,
        };

        let ready = unsafe { libc::poll(&mut poll_fd, 1, wait.as_millis() as i32) };
        if ready < 0 {
            let error = io::Error::last_os_error();
            if error.kind() == io::ErrorKind::Interrupted {
                continue;
            }
            return Err(format!("等待 PM3 回应失败：{error}"));
        }

        if ready > 0 && (poll_fd.revents & libc::POLLIN) != 0 {
            loop {
                let read = unsafe { libc::read(fd, buffer.as_mut_ptr().cast(), buffer.len()) };
                if read > 0 {
                    if response.len().saturating_add(read as usize) > MAX_CAPTURE_BYTES {
                        return Err("PM3 兼容回包超过 1 MiB，已中止读取".to_string());
                    }
                    response.extend_from_slice(&buffer[..read as usize]);
                    last_data = Some(Instant::now());
                    continue;
                }

                let error = io::Error::last_os_error();
                if read == 0
                    || error.kind() == io::ErrorKind::WouldBlock
                    || error.kind() == io::ErrorKind::Interrupted
                {
                    break;
                }

                return Err(format!("读取 PM3 回包失败：{error}"));
            }
        }

        if response.len() >= 16 && last_data.is_some_and(|instant| instant.elapsed() >= idle) {
            break;
        }
    }

    Ok(response)
}

fn decode_legacy_response(response: &[u8]) -> Result<String, String> {
    let payload = legacy_frame_payload(response, LEGACY_CMD_ACK)?;
    let end = payload
        .iter()
        .rposition(|byte| *byte != 0)
        .map(|index| index + 1)
        .unwrap_or(0);
    let payload = &payload[..end];

    let encoding = encoding_rs::Encoding::for_label(b"gb18030")
        .ok_or_else(|| "系统缺少 GB18030 解码器".to_string())?;
    let (decoded, _, _) = encoding.decode(payload);
    let clean = decoded.replace('\0', "").trim().to_string();

    if clean.is_empty() {
        return Err("设备回包为空".to_string());
    }

    Ok(clean)
}

fn legacy_frame_payload(response: &[u8], expected_command: u16) -> Result<&[u8], String> {
    if response.len() < LEGACY_FRAME_HEADER_SIZE {
        return Err("PM3 兼容回包短于 16 字节帧头".to_string());
    }

    let wire_command = u16::from_le_bytes([response[0], response[1]]);
    let payload_len = u16::from_le_bytes([response[2], response[3]]) as usize;
    if wire_command & 0x8000 == 0 {
        return Err("PM3 兼容回包缺少短帧标志".to_string());
    }
    if wire_command & 0x7fff != expected_command {
        return Err(format!(
            "PM3 兼容回包命令号不匹配：收到 0x{:04x}，期望 0x{expected_command:04x}",
            wire_command & 0x7fff
        ));
    }
    if payload_len > LEGACY_MAX_PAYLOAD_SIZE {
        return Err(format!("PM3 兼容回包负载过长：{payload_len} 字节"));
    }

    let frame_len = LEGACY_FRAME_HEADER_SIZE + payload_len;
    if response.len() != frame_len {
        return Err(format!(
            "PM3 兼容回包长度不匹配：帧头声明 {frame_len} 字节，实际 {} 字节",
            response.len()
        ));
    }

    Ok(&response[LEGACY_FRAME_HEADER_SIZE..frame_len])
}

struct FdGuard(RawFd);

impl FdGuard {
    fn raw(&self) -> RawFd {
        self.0
    }
}

impl Drop for FdGuard {
    fn drop(&mut self) {
        unsafe {
            libc::close(self.0);
        }
    }
}

fn binary_is_pm3_wrapper(binary: &str) -> bool {
    Path::new(binary)
        .file_name()
        .and_then(|name| name.to_str())
        .is_some_and(|name| name == "pm3")
}

fn binary_is_legacy_compat(binary: &str) -> bool {
    local_compat_binary()
        .as_deref()
        .is_some_and(|expected| Path::new(binary) == Path::new(expected))
}

fn resolve_binary(custom_path: Option<&str>) -> Result<String, String> {
    let status = detect_pm3_binary_blocking(custom_path.map(str::to_string));
    status.path.filter(|_| status.found).ok_or_else(|| {
        status
            .error
            .unwrap_or_else(|| "未找到 pm3 / proxmark3".to_string())
    })
}

fn binary_candidates() -> Vec<String> {
    let mut candidates = Vec::new();

    if let Ok(path) = env::var("PM3_BIN") {
        if !path.trim().is_empty() {
            push_candidate(&mut candidates, path);
        }
    }

    if let Some(path) = local_compat_binary() {
        push_candidate(&mut candidates, path);
    }

    for candidate in [
        "/opt/homebrew/bin/pm3",
        "/usr/local/bin/pm3",
        "/opt/homebrew/bin/proxmark3",
        "/usr/local/bin/proxmark3",
    ] {
        push_candidate(&mut candidates, candidate.to_string());
    }

    candidates
}

fn binary_name_is_pm3(path: &Path) -> bool {
    path.file_name()
        .and_then(|name| name.to_str())
        .is_some_and(|name| matches!(name, "pm3" | "proxmark3"))
}

fn approved_binary_path_shape(path: &Path, local_compat: &Path) -> bool {
    if !path.is_absolute() || !binary_name_is_pm3(path) {
        return false;
    }

    let trusted_entry_points = [
        Path::new("/opt/homebrew/bin/pm3"),
        Path::new("/opt/homebrew/bin/proxmark3"),
        Path::new("/usr/local/bin/pm3"),
        Path::new("/usr/local/bin/proxmark3"),
    ];

    path == local_compat
        || trusted_entry_points.contains(&path)
        || path.starts_with("/opt/homebrew/Cellar/proxmark3/")
        || path.starts_with("/opt/homebrew/opt/proxmark3/")
        || path.starts_with("/usr/local/Cellar/proxmark3/")
        || path.starts_with("/usr/local/opt/proxmark3/")
}

fn validate_binary_candidate(candidate: &str) -> Result<String, String> {
    if candidate != candidate.trim() || candidate.contains('\0') {
        return Err("PM3 内核路径格式无效".to_string());
    }

    let requested = Path::new(candidate);
    let local_compat = local_compat_binary_path();
    let canonical_local = fs::canonicalize(&local_compat).unwrap_or(local_compat);
    if !approved_binary_path_shape(requested, &canonical_local) {
        return Err(
            "拒绝执行不受信任的程序；仅允许 Homebrew 的 pm3/proxmark3 或随项目固定的兼容内核"
                .to_string(),
        );
    }

    let canonical =
        fs::canonicalize(requested).map_err(|error| format!("无法解析 PM3 内核路径：{error}"))?;
    if !approved_binary_path_shape(&canonical, &canonical_local) {
        return Err("PM3 内核链接指向了不受信任的位置".to_string());
    }

    let metadata =
        fs::metadata(&canonical).map_err(|error| format!("无法检查 PM3 内核文件：{error}"))?;
    if !metadata.is_file() || metadata.permissions().mode() & 0o111 == 0 {
        return Err("PM3 内核必须是可执行的普通文件".to_string());
    }

    Ok(canonical.to_string_lossy().to_string())
}

fn push_candidate(candidates: &mut Vec<String>, candidate: String) {
    if !candidates.iter().any(|existing| existing == &candidate) {
        candidates.push(candidate);
    }
}

fn local_compat_binary_path() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../compat-clients/iceman-ice_v3.1.0/client/proxmark3")
}

fn local_compat_binary() -> Option<String> {
    let path = local_compat_binary_path();

    if path.exists() {
        Some(
            fs::canonicalize(path)
                .ok()
                .unwrap_or_else(local_compat_binary_path)
                .to_string_lossy()
                .to_string(),
        )
    } else {
        None
    }
}

fn run_version_probe(binary: &str) -> Option<String> {
    if binary_is_legacy_compat(binary) {
        return Some("PM3 Easy 兼容内核（本地修补版，支持兼容短帧）".to_string());
    }

    for flag in ["--version", "-h"] {
        let mut command = Command::new(binary);
        command.arg(flag);
        let output = capture_command(command, PROBE_TIMEOUT).ok()?;
        if output.timed_out {
            continue;
        }
        if !output.status.success()
            && output.stdout.bytes.is_empty()
            && output.stderr.bytes.is_empty()
        {
            continue;
        }

        let text = format!(
            "{}{}",
            String::from_utf8_lossy(&output.stdout.bytes),
            String::from_utf8_lossy(&output.stderr.bytes)
        );
        let version = text
            .lines()
            .map(str::trim)
            .find(|line| !line.is_empty())
            .unwrap_or(binary)
            .to_string();

        return Some(version);
    }

    None
}

fn decode_process_bytes(bytes: &[u8]) -> String {
    match String::from_utf8(bytes.to_vec()) {
        Ok(text) => text,
        Err(_) => {
            let encoding = encoding_rs::Encoding::for_label(b"gb18030")
                .expect("GB18030 decoder should be available");
            let (decoded, _, _) = encoding.decode(bytes);
            decoded.to_string()
        }
    }
}

fn decode_and_clean_process_bytes(bytes: &[u8], legacy_command: Option<&str>) -> String {
    let text = decode_process_bytes(bytes);

    if let Some(command) = legacy_command {
        return clean_legacy_output(&text, command);
    }

    text
}

fn clean_legacy_output(text: &str, command: &str) -> String {
    text.lines()
        .filter_map(|line| {
            let trimmed = line.trim();

            if trimmed.is_empty()
                || trimmed.starts_with("Num of args:")
                || trimmed.starts_with("using 'scripting' commands file")
                || trimmed == command
                || trimmed == "quit"
                || trimmed == "pm3 -->"
            {
                return None;
            }

            Some(
                trimmed
                    .strip_prefix("#db#")
                    .unwrap_or(trimmed)
                    .trim()
                    .to_string(),
            )
        })
        .collect::<Vec<_>>()
        .join("\n")
}

fn unix_nanos() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_nanos())
        .unwrap_or(0)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            list_serial_ports,
            detect_pm3_binary,
            run_pm3_command
        ])
        .run(tauri::generate_context!())
        .expect("error while running PM3 Studio");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn command_policy_allows_only_known_diagnostics() {
        assert_eq!(classify_command("hw version"), CommandPolicy::Allowed);
        assert_eq!(classify_command("HF   SEARCH"), CommandPolicy::Allowed);
        assert_eq!(classify_command("hf help"), CommandPolicy::Allowed);
        assert_eq!(classify_command("hf 15 info"), CommandPolicy::Unsupported);
        assert_eq!(classify_command("hf mfu dump"), CommandPolicy::Unsupported);
    }

    #[test]
    fn command_policy_rejects_write_simulation_flash_and_scripts() {
        for command in [
            "lf hid clone",
            "hf mfu restore",
            "hf mfu wrbl b 4 d 00",
            "hf 15 write",
            "hf iclass writeblk",
            "lf t55xx wipe",
            "hf mf sim",
            "hw flash",
            "script run anything",
        ] {
            assert_eq!(
                classify_command(command),
                CommandPolicy::Mutating,
                "{command} must be blocked"
            );
        }
    }

    #[test]
    fn authorization_rejects_multiline_and_chained_commands() {
        assert!(authorize_command("hw version\nhf search").is_err());
        assert!(authorize_command("hw version\rhf search").is_err());
        assert!(authorize_command("hw version; hf search").is_err());
        assert!(authorize_command("hw version && hf search").is_err());
    }

    #[test]
    fn legacy_version_response_requires_a_complete_ack_frame() {
        let mut valid = Vec::from((LEGACY_CMD_ACK | 0x8000).to_le_bytes());
        valid.extend_from_slice(&(5_u16).to_le_bytes());
        valid.extend_from_slice(&[0_u8; 12]);
        valid.extend_from_slice(b"hello");
        assert_eq!(decode_legacy_response(&valid).as_deref(), Ok("hello"));

        assert!(decode_legacy_response(b"hello").is_err());

        let mut wrong_command = valid.clone();
        wrong_command[..2].copy_from_slice(&(0x8100_u16).to_le_bytes());
        assert!(decode_legacy_response(&wrong_command).is_err());

        let mut no_short_frame_flag = valid.clone();
        no_short_frame_flag[..2].copy_from_slice(&LEGACY_CMD_ACK.to_le_bytes());
        assert!(decode_legacy_response(&no_short_frame_flag).is_err());

        let mut truncated = valid.clone();
        truncated.pop();
        assert!(decode_legacy_response(&truncated).is_err());

        let mut trailing = valid;
        trailing.push(0);
        assert!(decode_legacy_response(&trailing).is_err());
    }

    #[test]
    fn serial_port_shape_is_restricted_to_direct_dev_cu_children() {
        assert!(serial_port_path_has_safe_shape(Path::new(
            "/dev/cu.usbmodem31201"
        )));
        assert!(!serial_port_path_has_safe_shape(Path::new("/dev/null")));
        assert!(!serial_port_path_has_safe_shape(Path::new(
            "/tmp/cu.usbmodem31201"
        )));
        assert!(!serial_port_path_has_safe_shape(Path::new(
            "/dev/cu.test/../../tmp/file"
        )));
        assert!(validate_serial_port("/etc/passwd").is_err());
        assert!(serial_port_name_is_likely_pm3(Path::new(
            "/dev/cu.usbmodem31201"
        )));
        assert!(!serial_port_name_is_likely_pm3(Path::new(
            "/dev/cu.Bluetooth-Incoming-Port"
        )));
    }

    #[test]
    fn binary_path_policy_rejects_arbitrary_executables() {
        let local = Path::new("/workspace/compat-clients/iceman-ice_v3.1.0/client/proxmark3");

        assert!(approved_binary_path_shape(
            Path::new("/opt/homebrew/bin/pm3"),
            local
        ));
        assert!(approved_binary_path_shape(
            Path::new("/opt/homebrew/Cellar/proxmark3/4.0/bin/proxmark3"),
            local
        ));
        assert!(approved_binary_path_shape(local, local));
        assert!(!approved_binary_path_shape(Path::new("/bin/echo"), local));
        assert!(!approved_binary_path_shape(Path::new("/tmp/pm3"), local));
        assert!(!approved_binary_path_shape(
            Path::new("/opt/homebrew/bin/bash"),
            local
        ));
        assert!(validate_binary_candidate("/bin/echo").is_err());
    }

    #[test]
    fn temporary_command_scripts_are_private_and_removed_on_drop() {
        let script = create_private_command_script("hw version").expect("create script");
        let path = script.path().to_path_buf();
        let metadata = fs::metadata(&path).expect("script metadata");

        assert_eq!(metadata.permissions().mode() & 0o777, 0o600);
        drop(script);
        assert!(!path.exists());
    }

    #[test]
    fn bounded_capture_drains_output_larger_than_pipe_capacity() {
        let output = capture_command(capture_test_child("output"), Duration::from_secs(5))
            .expect("capture child output");

        assert!(output.status.success());
        assert!(output.stdout.truncated);
        assert_eq!(output.stdout.bytes.len(), MAX_CAPTURE_BYTES);
    }

    #[test]
    fn bounded_capture_kills_timed_out_process_group() {
        let output = capture_command(capture_test_child("sleep"), Duration::from_millis(100))
            .expect("capture timed out child");

        assert!(output.timed_out);
        assert!(!output.status.success());
    }

    fn capture_test_child(mode: &str) -> Command {
        let mut command = Command::new(env::current_exe().expect("current test executable"));
        command
            .arg("--exact")
            .arg("tests::capture_process_helper")
            .arg("--nocapture")
            .env("PM3_CAPTURE_TEST_MODE", mode);
        command
    }

    #[test]
    fn capture_process_helper() {
        match env::var("PM3_CAPTURE_TEST_MODE").as_deref() {
            Ok("output") => {
                let chunk = [b'x'; 16 * 1024];
                let mut stdout = io::stdout().lock();
                for _ in 0..(MAX_CAPTURE_BYTES / chunk.len() + 64) {
                    stdout.write_all(&chunk).expect("write capture test output");
                }
            }
            Ok("sleep") => thread::sleep(Duration::from_secs(30)),
            _ => {}
        }
    }
}
