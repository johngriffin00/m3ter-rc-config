"""Two helpers every Salesforce-reading brick uses."""


def clean(record: dict) -> dict:
    """Drop the 'attributes' noise Salesforce adds to every record, recursively."""
    out = {}
    for key, value in record.items():
        if key == 'attributes':
            continue
        out[key] = clean(value) if isinstance(value, dict) else value
    return out


def in_list(ids) -> str:
    """Ids -> the quoted, comma-separated list a SOQL IN (...) wants."""
    return ', '.join(f"'{i}'" for i in ids)
