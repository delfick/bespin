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

def generate_tar_file(location, dirs_to_tar, files_to_tar, environment=None, compression=None):
    """
    Generate a tar file at the specified location given the paths and files
    """
    if environment is None:
        environment = {}

    # Create a blank tar file
    write_type = "w"
    if compression:
        write_type = "w|{0}".format(compression)
    tar = tarfile.open(location.name, write_type)

    # Walk each path, adding all files
    for dir_to_tar in dirs_to_tar:
        for root, dirs, files in os.walk(dir_to_tar.host_path):
            for f in files:
                file_full_path = os.path.abspath(os.path.join(root, f))
                file_tar_path = file_full_path.replace(os.path.normpath(dir_to_tar.host_path), dir_to_tar.artifact_path)
                tar.add(file_full_path, file_tar_path)

    # Add all the individual files
    for file_to_tar in files_to_tar:
        with a_temp_file() as f:
            f.write(file_to_tar.content.format(**environment).encode('utf-8'))
            f.close()
            tar.add(f.name, file_to_tar.path)

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

