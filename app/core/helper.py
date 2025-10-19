import json


def parse_cors_origins(value: str | list[str] | None) -> tuple[str, ...]:
    if not value:
        return ()
    if value in ('*', '"*"'):
        return ('*',)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, str):
                return (parsed.strip().rstrip('/'),)
            if isinstance(parsed, (list, tuple)):
                return tuple(o.strip().rstrip('/') for o in parsed)
        except json.JSONDecodeError:
            return tuple(o.strip().rstrip('/') for o in value.split(',') if o.strip())
    if isinstance(value, (list, tuple)):
        return tuple(str(o).strip().rstrip('/') for o in value)
    return (str(value).strip().rstrip('/'),)
