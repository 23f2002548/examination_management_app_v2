from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from flask import request, current_app
from werkzeug.exceptions import HTTPException
import math

class APIError(HTTPException):
    def __init__(self, message, code=400):
        super().__init__(description=message)
        self.code = code

def require(condition, message, code=400):
    if not condition:
        raise APIError(message, code)

def payload():
    data = request.get_json(silent=True)
    require(isinstance(data, dict), 'A JSON object is required')
    return data

def string(data, field, maximum=200, required=True):
    value = data.get(field, '')
    require(isinstance(value, str), f'{field} must be text')
    value = value.strip()
    require(not required or bool(value), f'{field} is required')
    require(len(value) <= maximum, f'{field} is too long')
    return value

def number(data, field, minimum=0, integer=False):
    try:
        value = float(data[field])
    except (KeyError, TypeError, ValueError):
        raise APIError(f'{field} must be a number')
    require(math.isfinite(value) and value >= minimum, f'{field} must be at least {minimum}')
    if integer:
        require(value.is_integer(), f'{field} must be a whole number')
        return int(value)
    return value

def parse_datetime(value):
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(current_app.config['APP_TIMEZONE']))
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError, TypeError, AttributeError):
        raise APIError('Invalid date/time')

def local_now():
    return datetime.now(ZoneInfo(current_app.config['APP_TIMEZONE'])).replace(tzinfo=None)

def iso(value):
    return value.isoformat() + 'Z' if value else None
