from enum import Enum


class DeepMomRequest:
    def __init__(self, request_state, args=None):
        self.request_state = request_state
        self.args = args


class DeepMomRequestState(Enum):
    CONNECT_REQUEST = 00
    CANCEL_REQUEST = 10
    SUBSCRIBE_REQUEST = 20


class DeepMomResponse:
    def __init__(self, response_state, error_log=None):
        self.response_state = response_state
        self.error_log = error_log


class DeepMomResponseState(Enum):
    CONNECT_OK = 00
    CONNECT_FAIL = 10
    CONNECT_CANCEL = 20
