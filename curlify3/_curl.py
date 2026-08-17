import re

from collections.abc import Callable, Iterator, Mapping
from typing import Final, NamedTuple, TypeAlias

from curlify3._types import Body, Headers
from curlify3._utils import make_request_obj, make_request_obj_async

# a body that did not decode never reaches a text quote function: it goes through
# the dialect's quote_bytes instead, see make_curl_body
Quote: TypeAlias = Callable[[str], str]
BytesQuote: TypeAlias = Callable[[bytes], str]
Options: TypeAlias = Mapping[str, str]

MULTIPART_BOUNDARY: Final = re.compile(r'boundary="?([^";]+)"?')
PART_NAME: Final = re.compile(rb'name="([^"]*)"')
PART_FILENAME: Final = re.compile(rb'filename="([^"]*)"')

# curl reads a leading @ in a --data value, and a leading @ or < in a --form value, as
# "load the value from this file" rather than as the value itself. Such a value has to go
# through the option that takes it literally: otherwise the command reads a local file and
# sends it to the url it was rendered for — and through the server-side adapters the value
# is the caller's to choose, so the file is the caller's to name
DATA_FILE_REF: Final = "@"
FORM_FILE_REF: Final = (b"@", b"<")

PS_QUOTE: Final = re.compile(r'(\\*)"')
PS_TRAILING_BACKSLASHES: Final = re.compile(r"\\+$")

# the character class shlex.quote() treats as safe: no shell metacharacter, no glob
# character, no whitespace. A value holding anything else is quoted, which still leaves
# a plain url and a lone cookie pair bare and keeps the common command terse
SH_UNSAFE: Final = re.compile(r"[^\w@%+=:,./-]", re.ASCII)
# inside $'...' these two are the only characters that carry meaning
SH_BYTE_ESCAPES: Final[Mapping[int, str]] = {0x27: "\\'", 0x5C: "\\\\"}

SH: Final = "sh"
POWERSHELL: Final = "powershell"

SHORT_OPTIONS: Final[Options] = {
    "request": "-X",
    "header": "-H",
    "cookie": "-b",
    "data": "-d",
    # curl has no short form of --data-raw or --form-string, hence the same string in both maps
    "data_raw": "--data-raw",
    "form": "-F",
    "form_string": "--form-string",
}
LONG_OPTIONS: Final[Options] = {
    "request": "--request",
    "header": "--header",
    "cookie": "--cookie",
    "data": "--data",
    "data_raw": "--data-raw",
    "form": "--form",
    "form_string": "--form-string",
}


def quote_sh(
    value: str,
) -> str:
    # close the literal, emit an escaped quote, reopen it: the quote that ends the word
    # is the only character a single-quoted sh word cannot carry
    return "'" + value.replace("'", "'\\''") + "'"


def quote_sh_word(
    value: str,
) -> str:
    # a url and a cookie header are normally made of safe characters, and leaving them
    # bare is what keeps the command readable. Everything else is quoted — including the
    # ? of a single-parameter query string, which zsh would otherwise refuse as a glob
    if not value:
        return "''"
    return quote_sh(value) if SH_UNSAFE.search(value) else value


def _escape_sh_byte(
    byte: int,
) -> str:
    if byte in SH_BYTE_ESCAPES:
        return SH_BYTE_ESCAPES[byte]
    if 0x20 <= byte <= 0x7E:
        return chr(byte)
    return f"\\x{byte:02x}"


def quote_sh_bytes(
    value: bytes,
) -> str:
    # $'...' is ANSI-C quoting: bash, zsh and ksh expand the escapes, POSIX sh does not.
    # Escaping only the bytes that have to be escaped keeps a mis-encoded text body legible,
    # and leaves the command pure ascii with no newline in it, which pretty output relies on
    return "$'" + "".join(_escape_sh_byte(byte) for byte in value) + "'"


def quote_powershell(
    value: str,
) -> str:
    # the command is emitted behind the --% stop-parsing token, so the only parser left is the
    # C runtime of curl.exe: wrap in "...", escape " as \" doubling any run of backslashes
    # directly before it, and double a trailing run so it cannot swallow the closing quote
    quoted = PS_QUOTE.sub(lambda matched: matched.group(1) * 2 + '\\"', value)
    quoted = PS_TRAILING_BACKSLASHES.sub(lambda matched: matched.group() * 2, quoted)
    return f'"{quoted}"'


def quote_powershell_bytes(
    value: bytes,
) -> str:
    raise ValueError(
        "a value that is not valid utf-8 cannot be rendered for shell 'powershell': raw bytes "
        "have no spelling behind the --% stop-parsing token, use shell='sh' instead"
    )


class ShellConfig(NamedTuple):
    binary: str
    args_prefix: str
    # quotes unconditionally: header values and a text body
    quote: Quote
    # quotes only a value that needs it: the url and the cookie header
    quote_word: Quote
    # a body the adapter could not decode; raises when the dialect cannot spell raw bytes
    quote_bytes: BytesQuote
    # what separates arguments in pretty mode, None when the shell cannot span lines
    pretty_separator: str | None


SHELLS: Final[Mapping[str, ShellConfig]] = {
    SH: ShellConfig("curl", "", quote_sh, quote_sh_word, quote_sh_bytes, " \\\n  "),
    # --% is the stop-parsing token: Windows PowerShell 5.1 (the dialect's target) hands
    # everything after it to curl.exe verbatim (only %VAR% references expand), leaving the
    # C runtime as the single parser — 5.1's own argument binder re-quotes by counting every
    # double quote, escaped or not, and corrupts JSON payloads no matter how they are written;
    # pwsh 7.2+ binds even these arguments the new way and needs
    # $PSNativeCommandArgumentPassing = 'Legacy' in the session first (documented in README);
    # the url and cookies are always quoted to keep whitespace safe for the C runtime parser
    # pretty is impossible here: --% is effective only until the next newline and the line
    # continuation character (`) cannot extend it (about_Parsing), so a multi-line command
    # would pass the backtick to curl.exe and run the next line on its own
    POWERSHELL: ShellConfig("curl.exe", "--%", quote_powershell, quote_powershell, quote_powershell_bytes, None),
}


def reject_nul(
    value: str | bytes,
    what: str,
) -> None:
    # a command-line argument is NUL-terminated on every platform, so a NUL byte would
    # silently truncate it, and a command that runs while sending something other than the
    # request it was rendered from is worse than one that refuses to be rendered. A NUL is
    # valid utf-8, so it arrives here as text as readily as it does as bytes
    if (0 in value) if isinstance(value, bytes) else ("\x00" in value):
        raise ValueError(
            f"a {what} containing a NUL byte cannot be rendered as a curl command: a "
            f"command-line argument is NUL-terminated, so the byte would silently truncate it"
        )


def make_curl_headers(
    headers: Headers,
    quote: Quote,
    options: Options,
) -> list[str]:
    option = options["header"]
    return [f"{option} {quote(f'{header}: {value}')}" for header, value in headers.items()]


def make_curl_cookies(
    cookies: str | None,
    quote_word: Quote,
    options: Options,
) -> list[str]:
    if not cookies:
        return []
    return [f"{options['cookie']} {quote_word(cookies)}"]


def quote_multipart_part(
    part: bytes,
    quote: Quote,
    quote_bytes: BytesQuote,
) -> str:
    # a part is matched out of the encoded body, so its name, value and filename are bytes and
    # any of the three can turn out not to be text: a field value straight off the wire, or a
    # filename in an encoding of its own. Such a part is spelled the way a body that did not
    # decode is, through the dialect's byte quoting — which is also where powershell refuses it
    reject_nul(part, "multipart field")
    try:
        return quote(part.decode())
    except UnicodeDecodeError:
        return quote_bytes(part)


def split_multipart_body(
    body: bytes,
    boundary: bytes,
) -> Iterator[tuple[bytes, bytes]]:
    # a part is --boundary CRLF headers CRLF CRLF value CRLF, and the body is closed by
    # --boundary--, whose chunk carries no CRLF CRLF and so drops out below. Splitting on the
    # delimiter the sender chose is what lets a value hold a CRLF of its own: matching a
    # value as one line truncated it there, and the command sent the prefix without a word
    for chunk in body.split(b"--" + boundary)[1:]:
        head, separator, value = chunk.partition(b"\r\n\r\n")
        if separator:
            yield head, value.removesuffix(b"\r\n")


def make_multipart_curl_args(
    body: str | bytes,
    content_type: str,
    quote: Quote,
    quote_bytes: BytesQuote,
    options: Options,
) -> list[str]:
    boundary = MULTIPART_BOUNDARY.search(content_type)
    # without the boundary parameter the body cannot be taken apart, and a body that cannot be
    # taken apart has no parts to render — the same command a multipart content-type without a
    # body produces
    if boundary is None:
        return []
    body = body.encode() if isinstance(body, str) else body
    body_parts = []
    for head, value in split_multipart_body(body, boundary.group(1).encode()):
        name = PART_NAME.search(head)
        if name is None:
            continue
        filename = PART_FILENAME.search(head)
        if filename is not None:
            # here the leading @ is the point: -F is what makes curl send the file the
            # request sent, so a file part is spelled name=@filename
            part, option = name.group(1) + b"=@" + filename.group(1), options["form"]
        else:
            # the value of a plain field is a literal, so --form-string as soon as it begins
            # with a character -F would read as a file reference. -F stays the common case: it
            # is the terser option and the value rarely begins with either character
            part = name.group(1) + b"=" + value
            option = options["form_string"] if value.startswith(FORM_FILE_REF) else options["form"]
        body_parts.append(f"{option} {quote_multipart_part(part, quote, quote_bytes)}")
    return body_parts


def make_curl_body(
    body: Body,
    headers: Headers,
    quote: Quote,
    quote_bytes: BytesQuote,
    options: Options,
) -> list[str]:
    # an absent body carries no arguments whatever the content-type claims
    if not body:
        return []
    # multipart comes first: such a body arrives as bytes whenever one of its file parts
    # is binary, and the parts are taken apart and rendered individually below — each with
    # its own NUL check, since only part of such a body reaches the command line
    content_type = headers.get("content-type", "")
    if "multipart" in content_type:
        return make_multipart_curl_args(body, content_type, quote, quote_bytes, options)
    reject_nul(body, "body")
    if isinstance(body, bytes):
        # the adapter could not decode it. --data-raw rather than --data, because both --data
        # and --data-binary read a leading @ as a filename, and @ is an ordinary byte here
        return [f"{options['data_raw']} {quote_bytes(body)}"]
    # the same file reference, in a body that did decode: --data would send the contents of
    # the named file instead of the body the request carried
    option = options["data_raw"] if body.startswith(DATA_FILE_REF) else options["data"]
    return [f"{option} {quote(body)}"]


def make_curl_string(
    method: str,
    url: str,
    headers: Headers,
    body: Body,
    cookies: str | None,
    http2: bool = False,
    shell: str = SH,
    pretty: bool = False,
    long_options: bool = False,
) -> str:
    if shell not in SHELLS:
        raise ValueError(f"unknown shell: {shell!r}, expected one of {sorted(SHELLS)}")
    shell_conf = SHELLS[shell]
    # non-None only when the output is asked to span lines and the shell can
    separator = shell_conf.pretty_separator if pretty else None
    if pretty and separator is None:
        raise ValueError(f"pretty output is not supported for shell: {shell!r}")
    # the other two rejections live in SHELLS, in the quote functions of the dialect that
    # cannot render the value: a NUL byte in any shell, and raw bytes in powershell
    options = LONG_OPTIONS if long_options else SHORT_OPTIONS
    if "content-length" in headers:
        del headers["content-length"]
    if body and isinstance(body, (str, bytes)) and not headers.get("content-type"):
        headers["content-type"] = "text/plain"
    args = [
        "--http2" if http2 else None,
        f"{options['request']} {method}" if method != "GET" else None,
        *make_curl_cookies(cookies, shell_conf.quote_word, options),
        *make_curl_headers(headers, shell_conf.quote, options),
        *make_curl_body(body, headers, shell_conf.quote, shell_conf.quote_bytes, options),
    ]
    parts = [str(entity) for entity in args if entity]
    command = " ".join([part for part in (shell_conf.binary, shell_conf.args_prefix) if part])
    url = shell_conf.quote_word(url)
    if separator is not None:
        return separator.join([f"{command} {url}", *parts])
    return " ".join([command, *parts, url])


def to_curl(
    request: object,
    shell: str = SH,
    pretty: bool = False,
    long_options: bool = False,
) -> str:
    data = make_request_obj(request)
    return make_curl_string(
        method=data.method,
        url=data.url,
        headers=data.headers,
        body=data.body(),
        cookies=data.cookies,
        http2=data.http2,
        shell=shell,
        pretty=pretty,
        long_options=long_options,
    )


async def to_curl_async(
    request: object,
    shell: str = SH,
    pretty: bool = False,
    long_options: bool = False,
) -> str:
    data = make_request_obj_async(request)
    return make_curl_string(
        method=data.method,
        url=data.url,
        headers=data.headers,
        body=await data.body(),
        cookies=data.cookies,
        http2=data.http2,
        shell=shell,
        pretty=pretty,
        long_options=long_options,
    )
