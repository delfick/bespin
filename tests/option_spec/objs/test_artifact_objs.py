# coding: spec

from bespin.option_spec.artifact_objs import Artifact, ArtifactPath, ArtifactFile, ArtifactCommand, ArtifactCollection
from bespin.option_spec import stack_specs
from bespin.errors import MissingFile
from bespin.amazon.s3 import S3

from tests.helpers import BespinCase

from noseOfYeti.tokeniser.support import noy_sup_setUp
from input_algorithms import spec_base as sb
from input_algorithms.meta import Meta
from boto.s3.key import Key
import time
import nose
import boto
import mock
import sys
import os

if sys.version_info[0] == 2 and sys.version_info[1] == 6:
    # This can be removed when we can use latest Httpretty again
    def mock_s3(func):
        def wrapped(*args):
            raise nose.SkipTest("No moto support for python2.6 atm")
        return wrapped
else:
    from moto import mock_s3

optional_any = lambda: sb.optional_spec(sb.any_spec())
artifact_spec = sb.create_spec(Artifact
    , compression_type = optional_any()
    , history_length = optional_any()
    , upload_to = optional_any()
    , paths = optional_any()
    , files = optional_any()
    , commands = optional_any()
    )

describe BespinCase, "ArtifactCollection":
    describe "clean_old_artifacts":
        @mock_s3
        it "does nothing if dry_run is True":
            s3 = S3()
            conn = s3.conn = boto.connect_s3()
            environment = {}

            bucket = conn.create_bucket("blah")
            for k in ('one.tar.gz', 'two.tar.gz', 'three.tar.gz', 'four.tar.gz'):
                key = Key(bucket)
                key.key = "stuff/{0}".format(k)
                key.set_contents_from_string(k)

            artifact = mock.Mock(name="artifact", upload_to="s3://blah/stuff/five.tar.gz", history_length=2, cleanup_prefix="")
            collection = ArtifactCollection({"main": artifact})
            collection.clean_old_artifacts(s3, environment, dry_run=True)

            self.assertEqual(
                  sorted([k.key for k in conn.get_bucket("blah").list()])
                , sorted(["stuff/one.tar.gz", "stuff/two.tar.gz", "stuff/three.tar.gz", "stuff/four.tar.gz"])
                )

        @mock_s3
        it "Deletes the oldest such that only history_length is left":
            s3 = S3()
            conn = s3.conn = boto.connect_s3()
            environment = {}

            bucket = conn.create_bucket("blah")
            for k in ('one.tar.gz', 'two.tar.gz', 'three.tar.gz', 'four.tar.gz'):
                key = Key(bucket)
                key.key = "stuff/{0}".format(k)
                key.set_contents_from_string(k)
                time.sleep(0.01)

            artifact = mock.Mock(name="artifact", upload_to="s3://blah/stuff/five.tar.gz", history_length=2, cleanup_prefix="")
            collection = ArtifactCollection({"main": artifact})
            collection.clean_old_artifacts(s3, environment, dry_run=False)

            self.assertEqual(
                  sorted([k.key for k in conn.get_bucket("blah").list()])
                , sorted(["stuff/three.tar.gz", "stuff/four.tar.gz"])
                )

            # Do it again, it deletes nothing else
            collection.clean_old_artifacts(s3, environment, dry_run=False)

            self.assertEqual(
                  sorted([k.key for k in conn.get_bucket("blah").list()])
                , sorted(["stuff/three.tar.gz", "stuff/four.tar.gz"])
                )

            # Change to only 1 for history length and try again
            artifact.history_length = 1
            collection.clean_old_artifacts(s3, environment, dry_run=False)

            self.assertEqual(
                  sorted([k.key for k in conn.get_bucket("blah").list()])
                , sorted(["stuff/four.tar.gz"])
                )

describe BespinCase, "ArtifactPath":
    describe "add_to_tar":
        it "adds everything from it's files method":
            called = []
            tar = mock.Mock(name="tar")
            tar.add.side_effect = lambda f, t: called.append((f, t))

            f1 = mock.Mock(name="f1")
            f2 = mock.Mock(name="f2")
            t1 = mock.Mock(name="t1")
            t2 = mock.Mock(name="t2")

            path = ArtifactPath(mock.Mock(name="host_path", spec=[]), mock.Mock(name="artifact_path", spec=[]), stdout=mock.Mock(name="stdout"))
            with mock.patch.object(ArtifactPath, "files", lambda s, env: iter([(f1, t1), (f2, t2)])):
                path.add_to_tar(tar, mock.Mock(name="environment", spec=[]))

            self.assertEqual(called, [(f1, t1), (f2, t2)])

    describe "Yielding full path and tar path for all files under host_path in files":
        before_each:
            self.root, self.folders = self.setup_directory(
                { "one": {"two": {"three": {"four": "4", "four_sibling": "4s", ".gitignore": "ignored"}, "five": "5"}, "six": "6"}
                , "seven": {"eight": {"nine": "9"}, "ten": "10"}
                }
            )

        it "works with a folder containing only files":
            path = ArtifactPath(self.folders["one"]["two"]["three"]["/folder/"], "/stuff")
            yielded = list(path.files({}))
            self.assertEqual(sorted(yielded), sorted(
                [ (self.folders["one"]["two"]["three"]["four"]["/file/"], "/stuff/four")
                , (self.folders["one"]["two"]["three"]["four_sibling"]["/file/"], "/stuff/four_sibling")
                , (self.folders["one"]["two"]["three"][".gitignore"]["/file/"], "/stuff/.gitignore")
                ]
            ))

        it "works with a folder containing nested folders":
            path = ArtifactPath(self.folders["one"]["/folder/"], "/stuff/blah")
            yielded = list(path.files({}))
            self.assertEqual(sorted(yielded), sorted(
                [ (self.folders["one"]["two"]["three"]["four"]["/file/"], "/stuff/blah/two/three/four")
                , (self.folders["one"]["two"]["three"]["four_sibling"]["/file/"], "/stuff/blah/two/three/four_sibling")
                , (self.folders["one"]["two"]["three"][".gitignore"]["/file/"], "/stuff/blah/two/three/.gitignore")
                , (self.folders["one"]["two"]["five"]["/file/"], "/stuff/blah/two/five")
                , (self.folders["one"]["six"]["/file/"], "/stuff/blah/six")
                ]
            ))

describe BespinCase, "ArtifactFile":
    describe "add_to_tar":
        it "creates a file and adds it to the tar before closing the file":
            content = "blah and stuff"
            path = mock.Mock(name="path")

            called = []
            tar = mock.Mock(name="tar")
            tar.add.side_effect = lambda name, path: called.append((name, open(name).read(), path))

            fle = ArtifactFile(content, path, "task", mock.Mock(name="task_runner"), stdout=mock.Mock(name="stdout"))
            fle.add_to_tar(tar)

            self.assertEqual(len(called), 1)
            self.assertEqual(called[0][1:], (content, path))
            assert not os.path.exists(called[0][0])

        it "formats in the environment":
            content = "{BLAH} and {STUFF}"
            path = mock.Mock(name="path")

            called = []
            tar = mock.Mock(name="tar")
            tar.add.side_effect = lambda name, path: called.append((name, open(name).read(), path))

            fle = ArtifactFile(content, path, "task", mock.Mock(name="task_runner"), stdout=mock.Mock(name="stdout"))
            fle.add_to_tar(tar, {"BLAH": "trees", "STUFF": "dogs"})

            self.assertEqual(len(called), 1)
            self.assertEqual(called[0][1:], ("trees and dogs", path))
            assert not os.path.exists(called[0][0])

describe BespinCase, "ArtifactCommand":
    def make_artifact_command(self, **options):
        return stack_specs.artifact_command_spec().normalise(Meta({}, []), options)

    describe "add_to_tar":
        it "does copy, modify, command, copy_into_tar":
            tar = mock.Mock(name="tar")
            called = []
            environment = mock.Mock(name="environment")

            def do_copy(root, env):
                assert os.path.exists(root)
                self.assertIs(env, environment)
                called.append((1, root))
            def do_modify(root, env):
                assert os.path.exists(root)
                self.assertIs(env, environment)
                called.append((2, root))
            def do_command(root, env):
                assert os.path.exists(root)
                self.assertIs(env, environment)
                called.append((3, root))
            def do_copy_into_tar(root, env, tr):
                assert os.path.exists(root)
                self.assertIs(tr, tar)
                self.assertIs(env, environment)
                called.append((4, root))

            command = self.make_artifact_command()
            with mock.patch.multiple(command, do_copy=do_copy, do_modify=do_modify, do_command=do_command, do_copy_into_tar=do_copy_into_tar):
                command.add_to_tar(tar, environment)

            self.assertEqual([c[0] for c in called], [1, 2, 3, 4])
            self.assertEqual(len(set(c[1] for c in called)), 1, set(c[1] for c in called))
            assert not os.path.exists(called[0][1])

    describe "copy_into_tar":
        it "adds in the full_path, tar_path from all the add_into_tar":
            tar = mock.Mock(name="tar")
            into = mock.Mock(name="into")
            environment = mock.Mock(name="environment")

            added = []

            f1 = mock.Mock(name="f1")
            f2 = mock.Mock(name="f2")
            f3 = mock.Mock(name="f3")
            f4 = mock.Mock(name="f4")
            t1 = mock.Mock(name="t1")
            t2 = mock.Mock(name="t2")
            t3 = mock.Mock(name="t3")
            t4 = mock.Mock(name="t4")

            p1 = mock.Mock(name="p1")
            p1.files.return_value = [(f1, t1)]

            p2 = mock.Mock(name="p2")
            p2.files.return_value = [(f2, t2), (f3, t3), (f4, t4)]

            def add(full_path, tar_path):
                added.append((full_path, tar_path))
            tar.add.side_effect = add

            ArtifactCommand(None, None, None, add_into_tar=[p1, p2], stdout=mock.Mock(name="stdout")).do_copy_into_tar(into, environment, tar)
            self.assertEqual(added, [(f1, t1), (f2, t2), (f3, t3), (f4, t4)])
            p1.files.assert_called_with(environment, prefix_path=into)
            p2.files.assert_called_with(environment, prefix_path=into)

    describe "do_command":
        it "formats the command with environment and runs it":
            one = mock.Mock(name="one")
            two = mock.Mock(name="two")
            environment = {"one": one, "two": two}

            root = mock.Mock(name="root")
            timeout = mock.Mock(name="timeout")

            cmd = mock.Mock(name="cmd")
            formatted_cmd = mock.Mock(name="formatted_cmd")
            cmd.format.return_value = formatted_cmd

            command = ArtifactCommand(None, None, command=cmd, add_into_tar=None, timeout=timeout)

            ret = mock.Mock(name="ret")
            command_output = mock.Mock(name="command_output", return_value=ret)

            with mock.patch("bespin.option_spec.artifact_objs.command_output", command_output):
                self.assertIs(command.do_command(root, environment), ret)

            cmd.format.assert_called_once_with(one=one, two=two)
            command_output.assert_called_once_with(formatted_cmd, cwd=root, timeout=timeout, verbose=True)

    describe "do_modify":
        it "can append lines to a file":
            modify = {"target": {"append": ["{{ONE}} blah", "yeap"]}}
            command = self.make_artifact_command(modify=modify)
            with self.a_temp_dir() as directory:
                target = os.path.join(directory, 'target')
                with open(target, 'w') as fle:
                    fle.write("one!")

                command.do_modify(directory, {"ONE": "HAHA"})
                with open(target) as fle:
                    self.assertEqual(fle.read(), "one!\nHAHA blah\nyeap\n")

        it "complains if the target file doesn't exist":
            modify = {"target": {"append": ["{{ONE}} blah", "yeap"]}}
            command = self.make_artifact_command(modify=modify)
            with self.a_temp_dir() as directory:
                target = os.path.join(directory, 'target')
                with self.fuzzyAssertRaisesError(MissingFile, "Expected a file to modify", path=target):
                    assert not os.path.exists(target)
                    command.do_modify(directory, {"ONE": "HAHA"})

    describe "do_copy":
        it "copies specified files into a temporary location":
            root, original = self.setup_directory({"one": {"two": "three", "four": {"five": "six", "nine": {"ten": {"eleven": "twelve"} } } }, "seven": "eight"})
            copy = [ArtifactPath(original["one"]["two"]["/file/"], "/yeap"), ArtifactPath(original["one"]["four"]["/folder/"], "/{ONE}")]
            command = self.make_artifact_command(copy=copy)

            with self.a_temp_dir() as into:
                environment = {"ONE": "blah"}
                command.do_copy(into, environment)
                self.assertEqual(self.dict_from_directory(into)
                    , { "yeap": "three"
                      , "blah":
                        { "five": "six"
                        , "nine":
                          { "ten":
                            { "eleven": "twelve"
                            }
                          }
                        }
                      }
                    )

