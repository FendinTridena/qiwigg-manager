class QiwiGGError(Exception):
    pass


class AuthenticationError(QiwiGGError):
    pass


def _none_or_str(something):
    if something is None or isinstance(something, str):
        return something
    elif isinstance(something, bytes):
        return something.decode(errors="ignore")
    else:
        raise ValueError(f"Unexpected value: {repr(something)}")


class UploadFailedError(QiwiGGError):
    def __init__(self, message, body, headers):
        super().__init__(message)
        self.message = message
        self.body = _none_or_str(body)
        self.headers = _none_or_str(headers)

    def __str__(self):
        lines = [self.message]
        if self.body is not None:
            lines.append(self.body)
        if self.headers is not None:
            lines.append(self.headers)
        return "\n\n".join(lines)


class ChunkSizeError(QiwiGGError):
    def __init__(self, message, saved_size, expected_size):
        super().__init__(message)
        self.message = message
        self.saved_size = saved_size
        self.expected_size = expected_size

    def __str__(self):
        return (
            f"{self.message}. Expected size: {self.expected_size}, "
            f"chunk size in metadata: {self.saved_size}"
        )
