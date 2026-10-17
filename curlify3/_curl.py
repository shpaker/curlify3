import re

from collections.abc import Callable, Iterable, Iterator, Mapping
from typing import Final, NamedTuple, TypeAlias

from curlify3._types import Body, Headers
from curlify3._utils import make_request_obj, make_request_obj_async

# a body that did not decode never reaches a text quote function: it goes through
# the dialect's quote_bytes instead, see make_curl_body
Quote: TypeAlias = Callable[[str], str]
BytesQuote: TypeAlias = Callable[[bytes], str]
Options: TypeAlias = Mapping[str, str]

# media type and parameter names are case-insensitive (RFC 9110)
MULTIPART_FORM: Final = "multipart/form-data"
MULTIPART_BOUNDARY: Final = re.compile(r'boundary="?([^";]+)"?', re.IGNORECASE)
# the parameter with the ; before it: -F makes curl pick a boundary of its own and append
# it to a content-type header given with -H, so one left in sent two boundary parameters
MULTIPART_BOUNDARY_PARAM: Final = re.compile(r'\s*;\s*boundary=("[^"]*"|[^;]*)', re.IGNORECASE)
# anchored on the ; before them: an unanchored name=" also matched inside filename="
PART_NAME: Final = re.compile(rb';\s*name="([^"]*)"', re.IGNORECASE)
PART_FILENAME: Final = re.compile(rb';\s*filename="([^"]*)"', re.IGNORECASE)

# curl reads a leading @ in a --data value, and a leading @ or < in a --form value, as
# "load the value from this file" rather than as the value itself. Such a value has to go
# through the option that takes it literally: otherwise the command reads a local file and
# sends it to the url it was rendered for — and through the server-side adapters the value
# is the caller's to choose, so the file is the caller's to name
DATA_FILE_REF: Final = "@"
FORM_FILE_REF: Final = (b"@", b"<")
# the rest of what -F parses in a plain value: a ; starts an attribute (type=, filename=,
# headers=@file, which reads a local file into the part headers) and a leading " opens a
# quoted string whose tail is dropped. Such a value goes through --form-string as well
FORM_QUOTED: Final = b'"'
FORM_ATTRIBUTE: Final = b";"
# a filename holding one of these is cut short by -F, at a ; or at a , (a list of files),
# unless it is written as a quoted string, in which " and \ are escaped with a backslash
FORM_FILENAME_UNSAFE: Final = re.compile(rb'[;,"\\]')
FORM_FILENAME_ESCAPE: Final = re.compile(rb'(["\\])')
# without an = in it, the value of -b is the name of a cookie file to read
COOKIE_PAIR: Final = "="

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

# what a masked value is replaced with; the header name, the auth scheme and the cookie
# names stay, so the command still shows what the request carried, just not the secret
MASKED: Final = "***"
# the headers that carry credentials in the common case, for mask_headers=SENSITIVE_HEADERS
SENSITIVE_HEADERS: Final = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "x-api-key",
        "x-auth-token",
        "x-csrf-token",
    }
)
# their value is "<scheme> <credentials>", and the scheme tells Basic from Bearer
AUTH_SCHEME_HEADERS: Final = frozenset({"authorization", "proxy-authorization"})

SHORT_OPTIONS: Final[Options] = {
    "request": "-X",
    "header": "-H",
    "cookie": "-b",
    "data": "-d",
    # curl has no short form of --data-raw or --form-string, hence the same string in both maps
    "data_raw": "--data-raw",
    "form": "-F",
    "form_string": "--form-string",
    "globoff": "-g",
}
LONG_OPTIONS: Final[Options] = {
    "request": "--request",
    "header": "--header",
    "cookie": "--cookie",
    "data": "--data",
    "data_raw": "--data-raw",
    "form": "--form",
    "form_string": "--form-string",
    "globoff": "--globoff",
}

# curl expands [1-3] and {a,b} in a url into several requests, and drops the braces of a
# lone {x}; a url holding any of these goes out with globbing off
URL_GLOB: Final = re.compile(r"[\[\]{}]")


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
    # directly before it, and double a trailing run so it cannot swallow the closing quote.
    # A line break has no spelling there: --% is effective only until the end of the line,
    # so whatever follows a newline would run as a powershell command of its own
    if "\n" in value or "\r" in value:
        raise ValueError(
            "a value containing a line break cannot be rendered for shell 'powershell': the "
            "--% stop-parsing token ends at the line break and the rest would run as powershell, "
            "use shell='sh' instead"
        )
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


def _header_names(
    names: Iterable[str],
    what: str,
) -> frozenset[str]:
    # a str is an iterable of its characters, so exclude_headers="accept" would quietly
    # exclude nothing; the adapters lowercase every header name, so the names are too
    if isinstance(names, str):
        raise TypeError(f"{what} expects an iterable of header names, not a str: {names!r}")
    names = list(names)
    # a bytes name would never equal a str header name, so it would match nothing in silence
    for name in names:
        if not isinstance(name, str):
            raise TypeError(f"{what} expects header names as str, got {type(name).__name__}: {name!r}")
    return frozenset(name.lower() for name in names)


def make_header_filter(
    include_headers: Iterable[str] | None,
    exclude_headers: Iterable[str],
) -> Callable[[str], bool]:
    # include narrows first and exclude subtracts from what is left, so passing both is
    # well-defined; None leaves the allowlist off, while an empty one keeps no header
    include = None if include_headers is None else _header_names(include_headers, "include_headers")
    exclude = _header_names(exclude_headers, "exclude_headers")
    return lambda name: (include is None or name in include) and name not in exclude


def mask_header_value(
    name: str,
    value: str,
) -> str:
    if name in AUTH_SCHEME_HEADERS:
        scheme, separator, _ = value.strip().partition(" ")
        if separator:
            return f"{scheme} {MASKED}"
    return MASKED


def mask_cookies(
    cookies: str,
) -> str:
    # each pair keeps its name: which cookies a request carried is often the whole question
    pairs = []
    for pair in cookies.split(";"):
        name, separator, _ = pair.strip().partition("=")
        pairs.append(f"{name}={MASKED}" if separator else MASKED)
    return "; ".join(pairs)


def make_curl_headers(
    headers: Headers,
    quote: Quote,
    options: Options,
    keep: Callable[[str], bool],
    mask: frozenset[str],
) -> list[str]:
    option = options["header"]
    args = []
    for header, value in headers.items():
        if not keep(header):
            continue
        # an empty value has nothing to hide and keeps the ; spelling that sends it empty
        if value and header in mask:
            value = mask_header_value(header, value)
        args.append(f"{option} {quote(make_header_arg(header, value))}")
    return args


def make_header_arg(
    header: str,
    value: str,
) -> str:
    # curl drops a header passed with nothing after the colon; the ; spelling is the one
    # that sends it with an empty value
    return f"{header}: {value}" if value else f"{header};"


def make_curl_cookies(
    cookies: str | None,
    quote: Quote,
    quote_word: Quote,
    options: Options,
) -> list[str]:
    if not cookies:
        return []
    # -b reads a value without an = as the name of a cookie file and sends the cookies
    # stored in it; the header carries the value as it came instead
    if COOKIE_PAIR not in cookies:
        return [f"{options['header']} {quote(f'cookie: {cookies}')}"]
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


def is_form_parsed(
    value: bytes,
) -> bool:
    return value.startswith((*FORM_FILE_REF, FORM_QUOTED)) or FORM_ATTRIBUTE in value


def quote_form_filename(
    filename: bytes,
) -> bytes:
    # the common filename stays bare; the quoted form is what keeps the rest of one whole
    if FORM_FILENAME_UNSAFE.search(filename) is None:
        return filename
    return b'"' + FORM_FILENAME_ESCAPE.sub(rb"\\\1", filename) + b'"'


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
        if filename is not None and not filename.group(1):
            # what a browser sends for a file input left empty; -F 'name=@' names a file
            # curl cannot open, and the filename attribute is the one way to keep it a file part
            part, option = name.group(1) + b'=;filename=""', options["form"]
        elif filename is not None:
            # here the leading @ is the point: -F is what makes curl send the file the
            # request sent, so a file part is spelled name=@filename
            part, option = name.group(1) + b"=@" + quote_form_filename(filename.group(1)), options["form"]
        else:
            # the value of a plain field is a literal, so --form-string as soon as it holds
            # anything -F would parse: a file reference, a quoted string or an attribute. -F
            # stays the common case: it is the terser option and such values are rare
            part = name.group(1) + b"=" + value
            option = options["form_string"] if is_form_parsed(value) else options["form"]
        body_parts.append(f"{option} {quote_multipart_part(part, quote, quote_bytes)}")
    return body_parts


def is_multipart_form(
    content_type: str,
) -> bool:
    # only form-data is what -F builds: the parts of multipart/mixed or multipart/related
    # carry no field names, and those bodies go out as they are, with their own boundary
    return content_type.partition(";")[0].strip().lower() == MULTIPART_FORM


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
    if is_multipart_form(content_type):
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
    include_headers: Iterable[str] | None = None,
    exclude_headers: Iterable[str] = (),
    mask_headers: Iterable[str] = (),
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
    # the filter decides only what is printed: the body below still reads the headers it
    # needs, so leaving content-type out hides the -H line but not the multipart parts.
    # The adapters lift the Cookie header into -b, and the filter follows it there
    keep = make_header_filter(include_headers, exclude_headers)
    if not keep("cookie"):
        cookies = None
    # masking only changes how a value is printed, the same as the filter: the body
    # below still reads the real headers
    mask = _header_names(mask_headers, "mask_headers")
    if cookies and "cookie" in mask:
        cookies = mask_cookies(cookies)
    if "content-length" in headers:
        del headers["content-length"]
    if body and isinstance(body, (str, bytes)) and not headers.get("content-type"):
        headers["content-type"] = "text/plain"
    body_args = make_curl_body(body, headers, shell_conf.quote, shell_conf.quote_bytes, options)
    # the parts are rendered with -F, which brings a boundary of its own
    if body_args and is_multipart_form(headers.get("content-type", "")):
        headers["content-type"] = MULTIPART_BOUNDARY_PARAM.sub("", headers["content-type"])
    args = [
        "--http2" if http2 else None,
        options["globoff"] if URL_GLOB.search(url) else None,
        f"{options['request']} {method}" if method != "GET" else None,
        *make_curl_cookies(cookies, shell_conf.quote, shell_conf.quote_word, options),
        *make_curl_headers(headers, shell_conf.quote, options, keep, mask),
        *body_args,
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
    include_headers: Iterable[str] | None = None,
    exclude_headers: Iterable[str] = (),
    mask_headers: Iterable[str] = (),
) -> str:
    """Render a request object as a curl command.

    Accepts the synchronous client-side request types (requests.PreparedRequest,
    niquests.PreparedRequest, httpx.Request, httpx2.Request, urllib.request.Request,
    tornado.httpclient.HTTPRequest) and the server-side requests whose body the
    framework has already buffered (django.http.HttpRequest, werkzeug.wrappers.Request
    / flask.Request, tornado.httputil.HTTPServerRequest).

    shell selects the output dialect: "sh" (default, POSIX shells) or "powershell"
    (Windows PowerShell 5.1). pretty breaks the command across lines, long_options
    spells the options out (--header instead of -H); both default to False, which
    keeps the output on a single line with short options.

    include_headers renders only the named headers, exclude_headers leaves the named
    ones out; names are matched case-insensitively, include applies first and
    exclude then subtracts from what is left. Cookie counts as a header, so a
    filter that drops it drops -b too. Both default to rendering every header.

    mask_headers keeps the named headers but prints *** in place of their values;
    authorization and proxy-authorization keep the auth scheme (Bearer ***), and a
    masked cookie keeps each cookie's name (-b 'session=***'). It applies to what
    the filters left, matches names case-insensitively and defaults to masking
    nothing; SENSITIVE_HEADERS holds the usual credential-carrying names.

    Raises ValueError if the request type or the shell value is not recognized, if
    pretty=True is combined with shell="powershell", if the body — or a multipart
    field value — is not valid UTF-8 and shell="powershell", if any value contains a
    line break and shell="powershell", or if the body or a field value contains a
    NUL byte. Raises TypeError if include_headers, exclude_headers or mask_headers
    is a str rather than an iterable of names, or holds a name that is not a str.
    """
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
        include_headers=include_headers,
        exclude_headers=exclude_headers,
        mask_headers=mask_headers,
    )


async def to_curl_async(
    request: object,
    shell: str = SH,
    pretty: bool = False,
    long_options: bool = False,
    include_headers: Iterable[str] | None = None,
    exclude_headers: Iterable[str] = (),
    mask_headers: Iterable[str] = (),
) -> str:
    """Render a request object as a curl command, awaiting the body.

    Accepts the request types whose body must be awaited — the server-side
    aiohttp.web.Request and starlette.requests.Request (which covers FastAPI), the
    client-side aiohttp.ClientRequest — plus httpx.Request / httpx2.Request through
    the async pathway.

    shell selects the output dialect: "sh" (default, POSIX shells) or "powershell"
    (Windows PowerShell 5.1). pretty breaks the command across lines, long_options
    spells the options out (--header instead of -H); both default to False, which
    keeps the output on a single line with short options.

    include_headers renders only the named headers, exclude_headers leaves the named
    ones out; names are matched case-insensitively, include applies first and
    exclude then subtracts from what is left. Cookie counts as a header, so a
    filter that drops it drops -b too. Both default to rendering every header.

    mask_headers keeps the named headers but prints *** in place of their values;
    authorization and proxy-authorization keep the auth scheme (Bearer ***), and a
    masked cookie keeps each cookie's name (-b 'session=***'). It applies to what
    the filters left, matches names case-insensitively and defaults to masking
    nothing; SENSITIVE_HEADERS holds the usual credential-carrying names.

    Raises ValueError if the request type or the shell value is not recognized, if
    pretty=True is combined with shell="powershell", if the body — or a multipart
    field value — is not valid UTF-8 and shell="powershell", if any value contains a
    line break and shell="powershell", or if the body or a field value contains a
    NUL byte. Raises TypeError if include_headers, exclude_headers or mask_headers
    is a str rather than an iterable of names, or holds a name that is not a str.
    """
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
        include_headers=include_headers,
        exclude_headers=exclude_headers,
        mask_headers=mask_headers,
    )
