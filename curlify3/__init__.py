"""Convert request objects from popular Python HTTP libraries into ready-to-run curl commands.

    import requests
    from curlify3 import to_curl

    response = requests.get("https://httpbin.org/get")
    print(to_curl(response.request))

Every supported request type goes through to_curl() (sync) or to_curl_async() (async);
the docstring of each curlify3._req_* module carries an example for its library.
"""

from curlify3._curl import POWERSHELL, SH, to_curl, to_curl_async

__version__ = "0.1.0"
__all__ = [
    "POWERSHELL",
    "SH",
    "to_curl",
    "to_curl_async",
]
