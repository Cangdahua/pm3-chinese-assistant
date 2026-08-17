Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$processName = if ($args.Count -gt 0) { $args[0] } else { "pm3gui" }
$proc = Get-Process -Name $processName -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $proc) {
  Write-Output "NO_WINDOW"
  exit 1
}

$root = [System.Windows.Automation.AutomationElement]::FromHandle($proc.MainWindowHandle)
Write-Output ("WINDOW`t{0}`t{1}" -f $proc.Id, $root.Current.Name)

$walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker

function Dump-Element($element, $depth) {
  if (-not $element) { return }
  $name = $element.Current.Name
  $type = $element.Current.ControlType.ProgrammaticName -replace '^ControlType\.', ''
  $autoId = $element.Current.AutomationId
  $rect = $element.Current.BoundingRectangle
  $line = "{0}`t{1}`t{2}`t{3}`t{4},{5},{6},{7}" -f $depth, $type, $autoId, $name, [int]$rect.X, [int]$rect.Y, [int]$rect.Width, [int]$rect.Height
  Write-Output $line

  $child = $walker.GetFirstChild($element)
  while ($child) {
    Dump-Element $child ($depth + 1)
    $child = $walker.GetNextSibling($child)
  }
}

Dump-Element $root 0
