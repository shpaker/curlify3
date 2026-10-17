# Security policy

## Supported versions

Only the latest release on [PyPI](https://pypi.org/project/curlify3/) receives fixes. While the project is on `0.x` there are no backports: a fix ships in a new release, and upgrading is the remedy.

## Reporting a vulnerability

Please report privately through [GitHub security advisories](https://github.com/shpaker/curlify3/security/advisories/new) — not in a public issue or pull request. Include the request (or the code that builds it), the rendered command, the shell it was run in, and what it did that the request did not ask for.

## Scope

`curlify3` renders request objects — on the server side, requests whose every value was chosen by the client — into commands that people paste into a terminal. A report is in scope when the rendered command does something other than send the request it was rendered from, for either dialect (`shell="sh"` or `shell="powershell"`):

- runs anything besides `curl` — a value escaping its quoting and becoming part of the command
- reads, writes or sends a local file — for example a value curl interprets as an `@file` or `<file` reference
- sends something other than what the request carried — a truncated, altered or injected body, header, option or url

Out of scope:

- Secrets appearing in the rendered command. The command reproduces the request, credentials included, unless asked otherwise: mask them with `mask_headers` (`SENSITIVE_HEADERS` covers the usual ones) or leave them out with `exclude_headers`. Secrets in the url or the body are printed as they are.
- `%NAME%` expansion under `shell="powershell"` and the other dialect limits documented in the [documentation](https://shpaker.github.io/curlify3/guide/powershell.html).
- Bugs in `curl`, in a shell, or in the HTTP library an adapter wraps — unless `curlify3` turns that library's output into an unsafe command.

## What to expect

This is a single-maintainer project, so response is best effort: an acknowledgement within 7 days, then a fix and a release. Confirmed issues are published as a GitHub security advisory, with a CVE where one applies, and the reporter is credited unless they ask not to be.
