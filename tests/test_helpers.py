# coding: spec

from bespin.helpers import a_temp_file, generate_tar_file, until, memoized_property, a_temp_directory
from bespin.option_spec.artifact_objs import ArtifactPath, ArtifactFile

from tests.helpers import BespinCase

from contextlib import contextmanager
import tarfile
import nose
import mock
import six
import sys
import os

describe BespinCase, "a_temp_file":
    it "yields the file object of a file that disappears after the context":
        with a_temp_file() as fle:
            assert os.path.exists(fle.name)
        assert not os.path.exists(fle.name)

    it "can write to the temporary file, close it and still read from it":
        with a_temp_file() as fle:
            fle.write("blah".encode("utf-8"))
            fle.close()
            with open(fle.name) as fread:
                self.assertEqual(fread.read(), "blah")
        assert not os.path.exists(fle.name)

describe BespinCase, "a_temp_directory":
    it "yields the name of a directory that disappears after the context":
        with a_temp_directory() as directory:
            assert os.path.exists(directory)
            assert os.path.isdir(directory)
        assert not os.path.exists(directory)

describe BespinCase, "until":

    @contextmanager
    def mock_log_and_time(self):
        """Mock out the log object and time, yield (log, time)"""
        fake_log = mock.Mock(name="log")
        fake_time = mock.Mock(name="time")
        with mock.patch("bespin.helpers.log", fake_log):
            with mock.patch("bespin.helpers.time", fake_time):
                yield (fake_log, fake_time)

    it "yields before doing anything else":
        done = []
        with self.mock_log_and_time() as (fake_log, fake_time):
            for _ in until():
                done.append(1)
                break

        self.assertEqual(len(fake_time.time.mock_calls), 0)
        self.assertEqual(len(fake_log.info.mock_calls), 0)
        self.assertEqual(done, [1])

    it "logs the action each time":
        done = []
        action = mock.Mock(name="action")
        with self.mock_log_and_time() as (fake_log, fake_time):
            def timer():
                if not done:
                    return 10
                else:
                    return 15
            fake_time.time.side_effect = timer

            for _ in until(action=action):
                if len(done) == 5:
                    break
                else:
                    done.append(1)
        self.assertEqual(done, [1, 1, 1, 1, 1])
        self.assertEqual(fake_log.info.mock_calls, [mock.call(action), mock.call(action), mock.call(action), mock.call(action), mock.call(action)])

    it "doesn't log the action each time if silent":
        done = []
        action = mock.Mock(name="action")
        with self.mock_log_and_time() as (fake_log, fake_time):
            fake_time.time.return_value = 20
            for _ in until(action=action, silent=True):
                if len(done) == 5:
                    break
                else:
                    done.append(1)
        self.assertEqual(done, [1, 1, 1, 1, 1])
        self.assertEqual(fake_log.info.mock_calls, [])

    it "errors out if we have an action and we timeout":
        done = []
        action = mock.Mock(name="action")
        with self.mock_log_and_time() as (fake_log, fake_time):
            info = {"started": False}
            def timer():
                if info["started"]:
                    return 20
                else:
                    info["started"] = True
                    return 1
            fake_time.time.side_effect = timer
            for _ in until(action=action, timeout=2):
                done.append(1)
        self.assertEqual(done, [1])
        self.assertEqual(fake_log.error.mock_calls, [mock.call("Timedout %s", action)])

    it "errors out if we have an action and we timeout unless silent":
        done = []
        action = mock.Mock(name="action")
        with self.mock_log_and_time() as (fake_log, fake_time):
            info = {"started": False}
            def timer():
                if info["started"]:
                    return 20
                else:
                    info["started"] = True
                    return 1
            fake_time.time.side_effect = timer
            for _ in until(action=action, timeout=2, silent=True):
                done.append(1)
        self.assertEqual(done, [1])
        self.assertEqual(fake_log.error.mock_calls, [])

    it "sleeps the step each time":
        done = []
        step = mock.Mock(name="step")
        action = mock.Mock(name="action")

        with self.mock_log_and_time() as (fake_log, fake_time):
            fake_time.time.return_value = 20
            def sleeper(self):
                done.append("sleep")
            fake_time.sleep.side_effect = sleeper

            for _ in until(step=step):
                if done.count(1) == 5:
                    done.append("break")
                    break
                else:
                    done.append(1)

        self.assertEqual(done, [1, "sleep", 1, "sleep", 1, "sleep", 1, "sleep", 1, "sleep", "break"])
        self.assertEqual(fake_time.sleep.mock_calls, [mock.call(step), mock.call(step), mock.call(step), mock.call(step), mock.call(step)])

describe BespinCase, "generate_tar_file":
    it "Creates an empty file when paths and files is empty":
        if six.PY2 and sys.version_info[1] == 6:
            raise nose.SkipTest()
        with a_temp_file() as temp_tar_file:
            generate_tar_file(temp_tar_file, [])
            tar = tarfile.open(temp_tar_file.name)

            self.assertEqual(len(tar.getnames()), 0)

    it "Creates a file with the files and directories given a path to process":
        with a_temp_file() as temp_tar_file:
            root, folders = self.setup_directory({"one": {"two": "blah", "three": {"four": ""}}})
            path1 = ArtifactPath(root, "/app")
            generate_tar_file(temp_tar_file, [path1])
            tar = tarfile.open(temp_tar_file.name, "r")

            self.assertEqual(len(tar.getnames()), 2)
            self.assertTarFileContent(temp_tar_file.name, {"app/one/two": "blah", "app/one/three/four": ""})

    it "Creates a file with the files given a file list to add":
        with a_temp_file() as temp_tar_file:
            file1 = ArtifactFile("watermelon", "/app/file1")
            file2 = ArtifactFile("banana", "/app/file2")

            generate_tar_file(temp_tar_file, [file1, file2])

            self.assertTarFileContent(temp_tar_file.name, {"app/file1": "watermelon", "app/file2": "banana"})

    it "formats environment into the files":
        with a_temp_file() as temp_tar_file:
            file1 = ArtifactFile("watermelon {ONE}", "/app/file1")
            file2 = ArtifactFile("ban{TWO}ana", "/app/file2")

            generate_tar_file(temp_tar_file, [file1, file2], {"ONE": "one", "TWO": "two"})

            self.assertTarFileContent(temp_tar_file.name, {"app/file1": "watermelon one", "app/file2": "bantwoana"})

    it "works with gz compression":
        with a_temp_file() as temp_tar_file:
            file1 = ArtifactFile("watermelon {ONE}", "/app/file1")
            file2 = ArtifactFile("ban{TWO}ana", "/app/file2")

            generate_tar_file(temp_tar_file, [file1, file2], {"ONE": "one", "TWO": "two"}, compression="gz")
            self.assertTarFileContent(temp_tar_file.name, {"app/file1": "watermelon one", "app/file2": "bantwoana"}, "gz")

    it "works with xz compression":
        if six.PY2: raise nose.SkipTest()
        with a_temp_file() as temp_tar_file:
            file1 = ArtifactFile("watermelon {ONE}", "/app/file1")
            file2 = ArtifactFile("ban{TWO}ana", "/app/file2")

            generate_tar_file(temp_tar_file, [file1, file2], {"ONE": "one", "TWO": "two"}, compression="xz")
            self.assertTarFileContent(temp_tar_file.name, {"app/file1": "watermelon one", "app/file2": "bantwoana"}, "xz")

describe BespinCase, "Memoized_property":
    it "takes in a function and sets name and cache_name":
        def a_func_blah(): pass
        prop = memoized_property(a_func_blah)
        self.assertIs(prop.func, a_func_blah)
        self.assertEqual(prop.name, "a_func_blah")
        self.assertEqual(prop.cache_name, "_a_func_blah")

    it "returns the memoized_property if accessed from the owner":
        owner = type("owner", (object, ), {})
        def a_func_blah(): pass
        prop = memoized_property(a_func_blah)
        self.assertIs(prop.__get__(None, owner), prop)

        class Things(object):
            @memoized_property
            def blah(self): pass
        self.assertEqual(Things.blah.name, "blah")

    it "caches the value on the instance":
        processed = []
        value = mock.Mock(name="value")
        class Things(object):
            @memoized_property
            def yeap(self):
                processed.append(1)
                return value
        instance = Things()

        self.assertEqual(processed, [])
        assert not hasattr(instance, "_yeap")

        self.assertIs(instance.yeap, value)
        self.assertEqual(processed, [1])
        assert hasattr(instance, '_yeap')
        self.assertEqual(instance._yeap, value)

        # For proof it's not calling yeap again
        self.assertIs(instance.yeap, value)
        self.assertEqual(processed, [1])
        assert hasattr(instance, '_yeap')
        self.assertEqual(instance._yeap, value)

        # And proof it's using the _yeap value
        value2 = mock.Mock(name="value2")
        instance._yeap = value2
        self.assertIs(instance.yeap, value2)
        self.assertEqual(processed, [1])
        assert hasattr(instance, '_yeap')
        self.assertEqual(instance._yeap, value2)

    it "recomputes the value if the cache isn't there anymore":
        processed = []
        value = mock.Mock(name="value")
        class Things(object):
            @memoized_property
            def yeap(self):
                processed.append(1)
                return value
        instance = Things()

        self.assertEqual(processed, [])
        assert not hasattr(instance, "_yeap")

        self.assertIs(instance.yeap, value)
        self.assertEqual(processed, [1])
        assert hasattr(instance, '_yeap')
        self.assertEqual(instance._yeap, value)

        # For proof it's not calling yeap again
        self.assertIs(instance.yeap, value)
        self.assertEqual(processed, [1])
        assert hasattr(instance, '_yeap')
        self.assertEqual(instance._yeap, value)

        # Unless the value isn't there anymore
        del instance._yeap
        self.assertIs(instance.yeap, value)
        self.assertEqual(processed, [1, 1])
        assert hasattr(instance, '_yeap')
        self.assertEqual(instance._yeap, value)

    it "sets the cache value using setattr syntax":
        processed = []
        value = mock.Mock(name="value")
        class Things(object):
            @memoized_property
            def yeap(self):
                processed.append(1)
                return value
        instance = Things()

        self.assertEqual(processed, [])
        assert not hasattr(instance, "_yeap")

        instance.yeap = value
        self.assertIs(instance.yeap, value)
        self.assertEqual(processed, [])
        assert hasattr(instance, '_yeap')
        self.assertEqual(instance._yeap, value)

        value2 = mock.Mock(name="value2")
        instance.yeap = value2
        self.assertIs(instance.yeap, value2)
        self.assertEqual(processed, [])
        assert hasattr(instance, '_yeap')
        self.assertEqual(instance._yeap, value2)

    it "deletes the cache with del syntax":
        value = mock.Mock(name="value")
        class Things(object):
            @memoized_property
            def yeap(self):
                processed.append(1)
                return value
        instance = Things()

        assert not hasattr(instance, "_yeap")

        instance.yeap = value
        self.assertIs(instance.yeap, value)
        assert hasattr(instance, '_yeap')
        self.assertEqual(instance._yeap, value)

        del instance.yeap
        assert not hasattr(instance, "_yeap")

