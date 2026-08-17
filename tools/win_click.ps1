param(
  [int]$X = 870,
  [int]$Y = 650
)

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public class MouseNative {
  [DllImport("user32.dll")]
  public static extern bool SetCursorPos(int x, int y);

  [DllImport("user32.dll")]
  public static extern void mouse_event(int dwFlags, int dx, int dy, int cButtons, int dwExtraInfo);
}
"@

[MouseNative]::SetCursorPos($X, $Y) | Out-Null
Start-Sleep -Milliseconds 100
[MouseNative]::mouse_event(2, 0, 0, 0, 0)
Start-Sleep -Milliseconds 50
[MouseNative]::mouse_event(4, 0, 0, 0, 0)
