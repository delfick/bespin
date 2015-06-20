# coding: spec

from bespin.option_spec import stack_specs as specs, stack_objs as objs
from bespin.option_spec import artifact_objs
from bespin.errors import BadSpecValue

from tests.helpers import BespinCase

from noseOfYeti.tokeniser.support import noy_sup_setUp
from input_algorithms.meta import Meta
from option_merge import MergedOptions
import mock

describe BespinCase, "Var spec":
    before_each:
        self.meta = mock.Mock(name="meta", spec=Meta)

    it "creates a Static variable if only one item is given":
        self.assertEqual(specs.var_spec().normalise(self.meta, 1), objs.StaticVariable("1"))
        self.assertEqual(specs.var_spec().normalise(self.meta, "1"), objs.StaticVariable("1"))
        self.assertEqual(specs.var_spec().normalise(self.meta, ["1"]), objs.StaticVariable("1"))

    it "creates a Dynamic variable if only one item is given":
        stack = self.unique_val()
        output = self.unique_val()
        bespin = self.unique_val()
        self.meta.everything = MergedOptions.using({"bespin": bespin})
        self.assertEqual(specs.var_spec().normalise(self.meta, [stack, output]), objs.DynamicVariable(stack, output, bespin))

describe BespinCase, "artifact_path_spec":
    before_each:
        self.meta = mock.Mock(name="artifact_path_spec")

    it "creates an artifact_path from the two items":
        host_path = self.unique_val()
        artifact_path = self.unique_val()
        self.assertEqual(specs.artifact_path_spec().normalise(self.meta, [host_path, artifact_path]), artifact_objs.ArtifactPath(host_path, artifact_path))

describe BespinCase, "Env spec":
    before_each:
        self.meta = mock.Mock(name="meta", spec=Meta)
        self.env_name = self.unique_val()
        self.fallback_val = self.unique_val()

    it "takes in just the env_name":
        assert ":" not in self.env_name
        assert "=" not in self.env_name

        made = specs.env_spec().normalise(self.meta, self.env_name)
        self.assertEqual(made.env_name, self.env_name)
        self.assertEqual(made.set_val, None)
        self.assertEqual(made.default_val, None)

    it "takes in env as a list with 1 item":
        assert ":" not in self.env_name
        assert "=" not in self.env_name

        made = specs.env_spec().normalise(self.meta, [self.env_name])
        self.assertEqual(made.env_name, self.env_name)
        self.assertEqual(made.set_val, None)
        self.assertEqual(made.default_val, None)

    it "takes in env as a list with 2 items":
        assert ":" not in self.env_name
        assert "=" not in self.env_name

        made = specs.env_spec().normalise(self.meta, [self.env_name, self.fallback_val])
        self.assertEqual(made.env_name, self.env_name)
        self.assertEqual(made.set_val, None)
        self.assertEqual(made.default_val, self.fallback_val)

    it "takes in env with blank default if suffixed with a colon":
        made = specs.env_spec().normalise(self.meta, self.env_name + ":")
        self.assertEqual(made.env_name, self.env_name)
        self.assertEqual(made.set_val, None)
        self.assertEqual(made.default_val, "")

    it "takes in env with blank set if suffixed with an equals sign":
        made = specs.env_spec().normalise(self.meta, self.env_name + "=")
        self.assertEqual(made.env_name, self.env_name)
        self.assertEqual(made.set_val, "")
        self.assertEqual(made.default_val, None)

    it "takes in default value if seperated by a colon":
        made = specs.env_spec().normalise(self.meta, self.env_name + ":" + self.fallback_val)
        self.assertEqual(made.env_name, self.env_name)
        self.assertEqual(made.set_val, None)
        self.assertEqual(made.default_val, self.fallback_val)

    it "takes in set value if seperated by an equals sign":
        made = specs.env_spec().normalise(self.meta, self.env_name + "=" + self.fallback_val)
        self.assertEqual(made.env_name, self.env_name)
        self.assertEqual(made.set_val, self.fallback_val)
        self.assertEqual(made.default_val, None)

describe BespinCase, "params_json_spec":
    before_each:
        self.meta = mock.Mock(name="meta", spec=Meta)

    it "complains if any item has no ParameterKey or ParameterValue":
        errors = [
              BadSpecValue("Expected a value but got none", meta=self.meta.indexed_at(0).at("ParameterKey"))
            , BadSpecValue("Expected a value but got none", meta=self.meta.indexed_at(0).at("ParameterValue"))
            ]

        with self.fuzzyAssertRaisesError(BadSpecValue, _errors=[BadSpecValue(meta=self.meta.indexed_at(0), _errors=errors)]):
            specs.params_json_spec().normalise(self.meta, [{"whatever": "blah"}])

        with self.fuzzyAssertRaisesError(BadSpecValue, _errors=[BadSpecValue(meta=self.meta.indexed_at(0), _errors=[errors[1]])]):
            specs.params_json_spec().normalise(self.meta, [{"ParameterKey": "blah"}])

        with self.fuzzyAssertRaisesError(BadSpecValue, _errors=[BadSpecValue(meta=self.meta.indexed_at(0), _errors=[errors[0]])]):
            specs.params_json_spec().normalise(self.meta, [{"ParameterValue": "blah"}])

    it "works if all items have ParameterKey and ParameterValue":
        spec = [{"ParameterKey": "one", "ParameterValue": 1}, {"ParameterKey": "two", "ParameterValue": "2"}]
        self.assertEqual(specs.params_json_spec().normalise(self.meta, spec), spec)

describe BespinCase, "stack_json_spec":
    before_each:
        self.meta = mock.Mock(name="meta", spec=Meta)

    it "complains if there is no Resources":
        error = BadSpecValue("Expected a value but got none", meta=self.meta.at("Resources"))
        with self.fuzzyAssertRaisesError(BadSpecValue, _errors=[error]):
            specs.stack_json_spec().normalise(self.meta, {})

    it "complains if any resource has no Type parameter":
        with self.fuzzyAssertRaisesError(BadSpecValue
            , _errors = [ BadSpecValue(meta=self.meta.at("Resources")
                , _errors = [ BadSpecValue(meta=self.meta.at("Resources").at("resource1")
                    , _errors = [ BadSpecValue("Expected a value but got none", meta=self.meta.at("Resources").at("resource1").at("Type")) ]
                    )]
                )]
            ):
            specs.stack_json_spec().normalise(self.meta, {"Resources": {"resource1": {"blah": 1}}})

    it "complains if any resource has Properties is not a dictionary":
        with self.fuzzyAssertRaisesError(BadSpecValue
            , _errors = [ BadSpecValue(meta=self.meta.at("Resources")
                , _errors = [ BadSpecValue(meta=self.meta.at("Resources").at("resource1")
                    , _errors = [ BadSpecValue("Expected a dictionary", got=int, meta=self.meta.at("Resources").at("resource1").at("Properties")) ]
                    )]
                )]
            ):
            specs.stack_json_spec().normalise(self.meta, {"Resources": {"resource1": {"Type": "something", "Properties": 1}}})

    it "complains if parameters and outputs is not a dictionary of string to dictionary":
        for key in ("Parameters", "Outputs"):
            value = {"Resources": {}, key: []}
            error = BadSpecValue("Expected a dictionary", got=list, meta=self.meta.at(key))
            with self.fuzzyAssertRaisesError(BadSpecValue, _errors=[error]):
                specs.stack_json_spec().normalise(self.meta, value)

            value = {"Resources": {}, key: {1:1}}
            error = BadSpecValue("Expected a string", got=int, meta=self.meta.at(key).at(1))
            with self.fuzzyAssertRaisesError(BadSpecValue, _errors=[BadSpecValue(meta=self.meta.at(key), _errors=[error])]):
                specs.stack_json_spec().normalise(self.meta, value)

            value = {"Resources": {}, key: {"1":1}}
            error = BadSpecValue("Expected a dictionary", got=int, meta=self.meta.at(key).at("1"))
            with self.fuzzyAssertRaisesError(BadSpecValue, _errors=[BadSpecValue(meta=self.meta.at(key), _errors=[error])]):
                specs.stack_json_spec().normalise(self.meta, value)

describe BespinCase, "artifact_command_spec":
    before_each:
        self.meta = mock.Mock(name="meta", spec=Meta)

    it "makes copy as a list of ArtifactPath":
        p1 = self.unique_val()
        p2 = self.unique_val()
        p3 = self.unique_val()
        p4 = self.unique_val()
        copy = [[p1, p2], "{0}:{1}".format(p3, p4)]
        self.assertEqual(
              specs.artifact_command_spec().normalise(self.meta, {"copy": copy}).copy
            , [artifact_objs.ArtifactPath(p1, p2), artifact_objs.ArtifactPath(p3, p4)]
            )

    it "makes add_into_tar as a list of ArtifactPath":
        p1 = self.unique_val()
        p2 = self.unique_val()
        p3 = self.unique_val()
        p4 = self.unique_val()
        add_into_tar = [[p1, p2], "{0}:{1}".format(p3, p4)]
        self.assertEqual(
              specs.artifact_command_spec().normalise(self.meta, {"add_into_tar": add_into_tar}).add_into_tar
            , [artifact_objs.ArtifactPath(p1, p2), artifact_objs.ArtifactPath(p3, p4)]
            )

    it "makes command as a list of formatted string":
        one = self.unique_val()
        meta = Meta(MergedOptions.using({"one": one}), [])
        command = "blah {one} meh"
        expected = ["blah {0} meh".format(one)]
        self.assertEqual(specs.artifact_command_spec().normalise(meta, {"command": command}).command, expected)

    it "makes modify as a dictionary":
        res = specs.artifact_command_spec().normalise(self.meta, {"modify": {"somewhere": {"append": "stuff"}}})
        self.assertEqual(res.modify, {"somewhere": {"append": ["stuff"]}})

describe BespinCase, "s3_address":
    before_each:
        self.meta = mock.Mock(name="meta", spec=Meta)

    it "returns an S3 Address":
        res = specs.s3_address().normalise(self.meta, "s3://blah/and/stuff")
        self.assertEqual(res, objs.S3Address("blah", "/and/stuff", 600))

        res = specs.s3_address().normalise(self.meta, "s3://blah")
        self.assertEqual(res, objs.S3Address("blah", "/", 600))

        res = specs.s3_address().normalise(self.meta, "s3://blah/")
        self.assertEqual(res, objs.S3Address("blah", "/", 600))

    it "can have a timeout specified as well":
        res = specs.s3_address().normalise(self.meta, ["s3://blah/and/stuff", 700])
        self.assertEqual(res, objs.S3Address("blah", "/and/stuff", 700))

    it "complains if the address is invalid":
        for val in ("http://somewhere", "amds"):
            with self.fuzzyAssertRaisesError(BadSpecValue, "Not a valid s3 address", got=val, meta=self.meta):
                specs.s3_address().normalise(self.meta, val)

