import copy

__all__ = [
    "local_datetime_element_factory",
    "at_all_element_factory",
    "launch_card_factory",
    "finish_card_factory",
    "error_card_factory",
]

_LOCAL_DATETIME_ELEMENT = {
    "tag": "markdown",
    "content": " ".join(
        (
            "<local_datetime format_type='date_num'></local_datetime>",
            "<local_datetime format_type='time_sec'></local_datetime>",
            "<local_datetime format_type='timezone'></local_datetime>",
        ),
    ),
}

_AT_ALL_ELEMENT = {
    "tag": "markdown",
    "content": "<at id=all></at>",
}

_LAUNCH_CARD = {
    "schema": "2.0",
    "config": {
        "width_mode": "compact",
    },
    "header": {
        "template": "green",
        "title": {
            "tag": "plain_text",
            "content": "Launched",
        },
    },
    "body": {
        "elements": [
            _LOCAL_DATETIME_ELEMENT,
        ],
    },
}

_FINISH_CARD = {
    "schema": "2.0",
    "config": {
        "width_mode": "compact",
    },
    "header": {
        "template": "green",
        "title": {
            "tag": "plain_text",
            "content": "Finished",
        },
    },
    "body": {
        "elements": [
            _LOCAL_DATETIME_ELEMENT,
        ],
    },
}

_ERROR_CARD = {
    "schema": "2.0",
    "config": {
        "width_mode": "fill",
    },
    "header": {
        "template": "red",
        "title": {
            "tag": "plain_text",
            "content": "Error",
        },
    },
    "body": {
        "elements": [
            _LOCAL_DATETIME_ELEMENT,
            {
                "tag": "div",
                "text": {
                    "tag": "plain_text",
                    "content": "",
                },
            },
            _AT_ALL_ELEMENT,
        ],
    },
}


def local_datetime_element_factory():
    return copy.deepcopy(_LOCAL_DATETIME_ELEMENT)


def at_all_element_factory():
    return copy.deepcopy(_AT_ALL_ELEMENT)


def launch_card_factory():
    return copy.deepcopy(_LAUNCH_CARD)


def finish_card_factory():
    return copy.deepcopy(_FINISH_CARD)


def error_card_factory():
    return copy.deepcopy(_ERROR_CARD)
