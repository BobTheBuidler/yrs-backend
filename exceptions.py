import json
from http.client import HTTPException, HTTPResponse

from httplib2 import Response

from yrs import app


@app.errorhandler(HTTPException)
def handle_http_exception(e):
    """Return JSON instead of HTML for HTTP errors."""
    # start with the correct headers and status code from the error
    response = e.get_response()
    # replace the body with JSON
    response.data = json.dumps({
        "code": e.code,
        "name": e.name,
        "description": e.description,
    })
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.content_type = "application/json"
    return response

@app.errorhandler(Exception)
def handle_generic_exception(e):
    response = Response()
    response.data = json.dumps({
        "code": 500,
        "name": type(e).__name__,
        "description": str(e),
    })
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.content_type = "application/json"
    return response

