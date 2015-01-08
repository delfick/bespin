from contextlib import contextmanager
import tempfile
import logging
import shutil
import tarfile
import time
import os

log = logging.getLogger("bespin.helpers")

@contextmanager
def a_temp_file():
    """Yield the name of a temporary file and ensure it's removed after use"""
    filename = None
    try:
        tmpfile = tempfile.NamedTemporaryFile(delete=False)
        filename = tmpfile.name
        yield tmpfile
    finally:
        if filename and os.path.exists(filename):
            os.remove(filename)

@contextmanager
def a_temp_directory():
    """Yield the name of a temporary directory and ensure it's removed after use"""
    directory = None
    try:
        directory = tempfile.mkdtemp()
        yield directory
    finally:
        if directory and os.path.exists(directory):
            shutil.rmtree(directory)

def generate_tar_file(location, paths, environment=None, compression=None):
    """
    Generate a tar file at the specified location given the paths and files
    """
    # Create a blank tar file
    write_type = "w"
    if compression:
        write_type = "w|{0}".format(compression)
    tar = tarfile.open(location.name, write_type)

    # Add all the things to the tar
    for path_spec in paths:
        path_spec.add_to_tar(tar, environment)

    # Finish the tar
    tar.close()

    return tar

def until(timeout=10, step=0.5, action=None, silent=False):
    """Yield until timeout"""
    yield

    started = time.time()
    while True:
        if action and not silent:
            log.info(action)

        if time.time() - started > timeout:
            if action and not silent:
                log.error("Timedout %s", action)
            return
        else:
            time.sleep(step)
            yield

class memoized_property(object):
    """Decorator to make a descriptor that memoizes it's value"""
    def __init__(self, func):
        self.func = func
        self.name = func.__name__
        self.cache_name = "_{0}".format(self.name)

    def __get__(self, instance=None, owner=None):
        if not instance:
            return self

        if not getattr(instance, self.cache_name, None):
            setattr(instance, self.cache_name, self.func(instance))
        return getattr(instance, self.cache_name)

    def __set__(self, instance, value):
        setattr(instance, self.cache_name, value)

    def __delete__(self, instance):
        if hasattr(instance, self.cache_name):
            delattr(instance, self.cache_name)

