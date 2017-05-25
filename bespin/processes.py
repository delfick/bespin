"""
Some helper functions for running subprocesses and ensuring they don't hang or
stick around.
"""
from bespin.errors import CouldntKill

import subprocess
import logging
import signal
import shlex
import time
import six
import sys
import os

log = logging.getLogger("bespin.processes")

def read_non_blocking(stream):
    """Read from a non-blocking stream"""
    if stream:
        while True:
            nxt = ''
            try:
                nxt = stream.readline()
            except IOError:
                pass

            if nxt:
                yield nxt
            else:
                break

def set_non_blocking_io(fh):
    if sys.platform in ['win32']:
        # TODO: windows magic
        raise NotImplementedError("Non-blocking process I/O not implemented on {}".format(sys.platform))
    else:
        import fcntl
        fl = fcntl.fcntl(fh, fcntl.F_GETFL)
        fcntl.fcntl(fh, fcntl.F_SETFL, fl | os.O_NONBLOCK)

def command_output(command, *command_extras, **kwargs):
    """Get the output from a command"""
    output = []
    cwd = kwargs.get("cwd", None)
    if isinstance(command, six.string_types):
        args = shlex.split(' '.join([command] + list(command_extras)))
    else:
        args = command + shlex.split(' '.join(list(command_extras)))
    timeout = kwargs.get("timeout", 10)
    verbose = kwargs.get("verbose", False)

    log_level = log.info if verbose else log.debug
    log_level("Running command\targs=%s", args)
    process = subprocess.Popen(args, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, cwd=cwd)

    set_non_blocking_io(process.stdout)

    start = time.time()
    while True:
        if time.time() - start > timeout:
            break
        if process.poll() is not None:
            break
        for nxt in read_non_blocking(process.stdout):
            nxt_out = nxt.decode("utf8").strip()
            output.append(nxt_out)
            if verbose:
                print(nxt_out)

        time.sleep(0.01)

    attempted_sigkill = False
    if process.poll() is None:
        start = time.time()
        log.error("Command taking longer than timeout (%s). Terminating now\tcommand=%s", timeout, args)
        process.terminate()

        while True:
            if time.time() - start > timeout:
                break
            if process.poll() is not None:
                break
            for nxt in read_non_blocking(process.stdout):
                output.append(nxt.decode("utf8").strip())
            time.sleep(0.01)

        if process.poll() is None:
            log.error("Command took another %s seconds after terminate, so sigkilling it now", timeout)
            os.kill(process.pid, signal.SIGKILL)
            attempted_sigkill = True

    for nxt in read_non_blocking(process.stdout):
        nxt_out = nxt.decode("utf8").strip()
        output.append(nxt_out)
        if verbose:
            print(nxt_out)

    if attempted_sigkill:
        time.sleep(0.01)
        if process.poll() is None:
            raise CouldntKill("Failed to sigkill hanging process", pid=process.pid, command=args, output="\n".join(output))

    if process.poll() != 0:
        log.error("Failed to run command\tcommand=%s", args)

    for nxt in read_non_blocking(process.stdout):
        nxt_out = nxt.decode("utf8").strip()
        output.append(nxt_out)
        if verbose:
            print(nxt_out)

    return output, process.poll()

