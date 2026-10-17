"""Adapter for werkzeug.wrappers.Request. flask.Request subclasses it, so Flask
is covered the same way — as are plain Werkzeug apps.

    import flask
    from curlify3 import to_curl

    app = flask.Flask(__name__)

    @app.post("/echo")
    def echo():
        return {"curl": to_curl(flask.request)}
"""

from werkzeug.wrappers import Request

from curlify3._base import BaseRequestData, raw_request_uri
from curlify3._types import Body


class WerkzeugRequest(BaseRequestData[Request]):
    _instance_of = Request

    @property
    def url(
        self,
    ) -> str:
        # request.url is rebuilt from PATH_INFO, which WSGI hands over percent-decoded, so an
        # encoded / comes back as a path separator. The server that sets RAW_URI or
        # REQUEST_URI (gunicorn, uwsgi, werkzeug's own) keeps the target as it arrived
        raw_uri = raw_request_uri(self._request.environ)
        if raw_uri is None:
            return self._request.url
        return f"{self._request.scheme}://{self._request.host}{raw_uri}"

    def body(
        self,
    ) -> Body:
        # cached, so form parsing after the command is rendered still sees the
        # stream; parse_form_data stays off so reading never triggers the parser
        data = self._request.get_data(cache=True, parse_form_data=False)
        try:
            return data.decode()
        except UnicodeDecodeError:
            pass
        return data
