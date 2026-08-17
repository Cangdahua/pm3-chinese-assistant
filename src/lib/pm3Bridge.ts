import { invoke } from '@tauri-apps/api/core'

// EXPERIMENTAL: this bridge is a frozen development prototype, not a release client.

export type SerialPortInfo = {
  path: string
  kind: string
  likelyPm3: boolean
}

export type Pm3BinaryStatus = {
  found: boolean
  path?: string
  version?: string
  error?: string
}

export type RunPm3Request = {
  binaryPath?: string
  port?: string
  command: string
  offline?: boolean
  timeoutMs?: number
}

export type RunPm3Response = {
  command: string
  stdout: string
  stderr: string
  status?: number
  ok: boolean
}

declare global {
  interface Window {
    __TAURI_INTERNALS__?: unknown
  }
}

export function isTauriRuntime() {
  return typeof window !== 'undefined' && Boolean(window.__TAURI_INTERNALS__)
}

export function runtimeLabel() {
  return isTauriRuntime() ? '桌面实验模式' : '浏览器预览模式'
}

export async function listSerialPorts(): Promise<SerialPortInfo[]> {
  if (isTauriRuntime()) {
    return invoke<SerialPortInfo[]>('list_serial_ports')
  }

  return []
}

export async function detectPm3Binary(customPath?: string): Promise<Pm3BinaryStatus> {
  if (isTauriRuntime()) {
    return invoke<Pm3BinaryStatus>('detect_pm3_binary', {
      customPath: customPath || null,
    })
  }

  return {
    found: false,
    error: '预览模式未连接本机命令',
  }
}

export async function runPm3Command(request: RunPm3Request): Promise<RunPm3Response> {
  if (isTauriRuntime()) {
    return invoke<RunPm3Response>('run_pm3_command', {
      request,
    })
  }

  throw new Error('浏览器预览不会伪造设备或命令结果；请仅在 Tauri 开发模式中验证只读命令。')
}
