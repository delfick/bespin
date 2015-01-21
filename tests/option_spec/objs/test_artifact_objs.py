# coding: spec

from bespin.option_spec.artifact_objs import Artifact, ArtifactPath, ArtifactFile
from bespin.option_spec import stack_objs, stack_specs
from bespin.errors import BadOption

from tests.helpers import BespinCase

from noseOfYeti.tokeniser.support import noy_sup_setUp
from input_algorithms import spec_base as sb
import mock
import os

optional_any = lambda: sb.optional_spec(sb.any_spec())
artifact_spec = sb.create_spec(Artifact
    , compression_type = optional_any()
    , history_length = optional_any()
    , upload_to = optional_any()
    , paths = optional_any()
    , files = optional_any()
    , commands = optional_any()
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

            path = ArtifactPath(mock.Mock(name="host_path", spec=[]), mock.Mock(name="artifact_path", spec=[]))
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

            fle = ArtifactFile(content, path)
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

            fle = ArtifactFile(content, path)
            fle.add_to_tar(tar, {"BLAH": "trees", "STUFF": "dogs"})

            self.assertEqual(len(called), 1)
            self.assertEqual(called[0][1:], ("trees and dogs", path))
            assert not os.path.exists(called[0][0])

