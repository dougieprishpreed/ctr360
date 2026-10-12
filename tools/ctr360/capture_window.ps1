Add-Type -AssemblyName System.Drawing
$processName = if ($args.Count -gt 1) { $args[1] } else { 'xenia_canary' }
$p = Get-Process $processName -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if ($null -eq $p) { Write-Output "NO_WINDOW"; exit 1 }
$sig = '[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect); [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow(); [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd); public struct RECT { public int Left, Top, Right, Bottom; }'
$null = Add-Type -MemberDefinition $sig -Name W -Namespace X -PassThru
if ([X.W]::IsIconic($p.MainWindowHandle) -or [X.W]::GetForegroundWindow() -ne $p.MainWindowHandle) {
    Write-Output 'CAPTURE_SKIPPED: test window is minimized or covered'
    exit 2
}
$r = New-Object X.W+RECT
[void][X.W]::GetWindowRect($p.MainWindowHandle, [ref]$r)
$w = $r.Right - $r.Left; $h = $r.Bottom - $r.Top
Write-Output ("WINDOW {0},{1} {2}x{3}" -f $r.Left, $r.Top, $w, $h)
if ($w -le 0 -or $h -le 0) { exit 1 }
$bmp = New-Object System.Drawing.Bitmap($w, $h)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($r.Left, $r.Top, 0, 0, (New-Object System.Drawing.Size($w, $h)))
$out = if ($args.Count -gt 0) { $args[0] } else { "F:\downloads\temp\python\hermes\ctrport\ctr360\build-360\window_capture.png" }
$bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Output ("SAVED " + $out)
