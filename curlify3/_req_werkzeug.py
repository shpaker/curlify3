from werkzeug.wrappers import Request

from curlify3._base import BaseRequestData
from curlify3._types import Body


# flask.Request subclasses werkzeug's, so this adapter covers Flask the same
# way the starlette adapter covers FastAPI
class WerkzeugRequest(BaseRequestData[Request]):
    _instance_of = Request

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
