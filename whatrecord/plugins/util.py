import contextlib
import functools
import sys


@contextlib.contextmanager
def suppress_output():
    class OutputBuffer:
        def __init__(self):
            self.buffer = []

        def write(self, buf):
            self.buffer.append(buf)

        def flush(self):
            ...

    replacement_stderr = OutputBuffer()
    sys.stderr = replacement_stderr

    replacement_stdout = OutputBuffer()
    sys.stdout = replacement_stdout

    try:
        yield replacement_stdout, replacement_stderr
    finally:
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__


def suppress_output_decorator(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with suppress_output() as (buffered_stdout, buffered_stderr):
            results = func(*args, **kwargs)
            results.execution_info["stdout"] = "\n".join(buffered_stdout.buffer)
            results.execution_info["stderr"] = "\n".join(buffered_stderr.buffer)
            return results
    return wrapper
