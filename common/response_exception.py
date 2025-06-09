class ResponseException(Exception):
    def __init__(self, message):
        self.message = message

    def setMessage(self, message):
        self.message = message
    def getMessage(self):
        return self.message
