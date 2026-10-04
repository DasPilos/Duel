$ErrorActionPreference = 'Stop'

$secure = Read-Host -AsSecureString 'Password for user game'
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
if ([string]::IsNullOrEmpty($plain)) { throw 'Empty password' }

# pgpass format requires escaping of backslash and colon
$escaped = $plain.Replace('\', '\\').Replace(':', '\:')

$dir = Join-Path $env:APPDATA 'postgresql'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$file = Join-Path $dir 'pgpass.conf'

$lines = @()
if (Test-Path $file) {
    $lines = @(Get-Content $file | Where-Object { $_ -notmatch '^(127\.0\.0\.1|localhost):5432:game:game:' })
}
$lines += "127.0.0.1:5432:game:game:$escaped"
$lines += "localhost:5432:game:game:$escaped"
# libpq does not understand a UTF-8 BOM
[IO.File]::WriteAllLines($file, [string[]]$lines, (New-Object Text.UTF8Encoding $false))

& 'E:\PostgreSQL\18\data\bin\psql.exe' -U game -h 127.0.0.1 -d game -w -c 'SELECT current_user, current_database();'
exit $LASTEXITCODE
