"""Adapter for werkzeug.wrappers.Request. flask.Request subclasses it, so Flask
is covered the same way — as are plain Werkzeug apps.

    import flask
    from curlify3 import to_curl

    app = flask.Flask(__name__)

    @app.post("/echo")
    def echo():
        return {"curl": to_curl(flask.request)}
"""

from urllib.parse import urlencode

from werkzeug.wrappers import Request

from curlify3._base import BaseRequestData
from curlify3._types import Body

FORM_URLENCODED = "application/x-www-form-urlencoded"


class WerkzeugRequest(BaseRequestData[Request]):
    _instance_of = Request

    def body(
        self,
    ) -> Body:
        # cached, so form parsing after the command is rendered still sees the
        # stream; parse_form_data stays off so reading never triggers the parser
        data = self._request.get_data(cache=True, parse_form_data=False)
        if not data and "form" in self._request.__dict__:
            # the form was parsed before the command was rendered, and parsing reads the
            # stream to the end without caching it. An urlencoded body is all in the parsed
            # form, so it is encoded again — the same fields, though not necessarily the same
            # bytes; a multipart one also held files, so like django the command carries no -d
            if self._request.mimetype == FORM_URLENCODED:
                return urlencode(list(self._request.form.items(multi=True)))
            return None
        try:
            return data.decode()
        except UnicodeDecodeError:
            pass
        return data
