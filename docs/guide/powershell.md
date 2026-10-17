# Windows PowerShell

By default the command is formatted for POSIX shells — `bash`, `zsh`, `ksh` and the like. `shell="powershell"` renders one that pastes into Windows PowerShell 5.1:

```python
import requests
from curlify3 import POWERSHELL, to_curl

req = requests.Request("POST", "https://httpbin.org/post", json={"date": "2026-08-10"}).prepare()

print(to_curl(req, shell=POWERSHELL))
# curl.exe --% -X POST -H "content-type: application/json" -d "{\"date\": \"2026-08-10\"}" "https://httpbin.org/post"
```

{py:data}`~curlify3.SH` and {py:data}`~curlify3.POWERSHELL` are exported for use instead of the raw strings `"sh"` and `"powershell"`. Any other value raises `ValueError`.

## How the command is built

- `curl.exe` rather than `curl`, which is an alias of `Invoke-WebRequest` in Windows PowerShell.
- `--%`, PowerShell's stop-parsing token, hands the rest of the line to `curl.exe` verbatim. It is what makes arbitrary JSON survive: without it, the argument binder of 5.1 re-quotes values by counting every double quote, escaped or not, and mangles the body.
- Behind `--%` the only parser left is the C runtime of `curl.exe`. Every value is wrapped in `"…"`, a `"` inside is escaped as `\"`, and backslashes before a quote or at the end of a value are doubled.

## Limits

`--%` is effective only until the end of the line, and nothing behind it can spell a raw byte. Hence:

- `pretty=True` raises `ValueError`: a backtick cannot extend `--%`, so a multi-line command would reach `curl.exe` in pieces.
- A value holding a line break — a pretty-printed JSON body, a multi-line text field, a header with a CR — raises `ValueError`. The line after the break would run as a PowerShell command of its own. Render such requests with `shell="sh"`.
- A body or a multipart field value that is not valid UTF-8 raises `ValueError`.
- `%NAME%` environment-variable references in a value are still expanded by PowerShell.

## Where the command runs

The command is for PowerShell only. In `cmd`, git-bash or WSL, `curl.exe` chokes on `--%`; use the default `shell="sh"` output there.

On PowerShell 7.2+ (`pwsh`), native arguments are passed differently by default. Run this in the session first:

```powershell
$PSNativeCommandArgumentPassing = 'Legacy'
```

The PowerShell output is tested end to end on CI against the real `powershell.exe` 5.1 and `pwsh`.
