from input_algorithms.errors import BadSpec, BadSpecValue
from delfick_error import DelfickError, ProgrammerError

class BespinError(DelfickError): pass

# Explicitly make these errors in this context
BadSpec = BadSpec
BadSpecValue = BadSpecValue
ProgrammerError = ProgrammerError

class BadConfiguration(BespinError):
    desc = "Bad configuration"

class BadOptionFormat(BespinError):
    desc = "Bad option format"

class BadTask(BespinError):
    desc = "Bad task"

class BadOption(BespinError):
    desc = "Bad Option"

class NoSuchKey(BespinError):
    desc = "Couldn't find key"

class NoSuchStack(BespinError):
    desc = "Couldn't find stack"

class BadStack(BespinError):
    desc = "Bad stack"

class BadS3Bucket(BespinError):
    desc = "Bad S3 Bucket"

class BadJson(BespinError):
    desc = "Bad json"

class FailedStack(BespinError):
    desc = "Something about an stack failed"

class BadYaml(BespinError):
    desc = "Invalid yaml file"

class BadResult(BespinError):
    desc = "A bad result"

class BadAmazon(BespinError):
    desc = "Amazon says no"

class StackDoesntExist(BadAmazon):
    desc = "Missing stack"

class UserQuit(BespinError):
    desc = "User quit the program"

class BadDockerConnection(BespinError):
    desc = "Failed to connect to docker"

class BadSQSMessage(BespinError):
    desc= "Failed to decode message"

class StackDepCycle(BespinError):
    desc = "Stack dependency cycle"

class MissingOutput(BespinError):
    desc = "Couldn't find an output"

class MissingFile(BespinError):
    desc = "Couldn't find a file"

class CouldntKill(BespinError):
    desc = "Failed to kill a process"

class BadDirectory(BadSpecValue):
    desc = "Expected a path to a directory"

class BadFilename(BadSpecValue):
    desc = "Expected a path to a filename"

class BadDeployment(BespinError):
    desc = "Failed to get all the correct deployment messages"

class DeprecatedFeature(BadSpecValue):
    desc = "Feature is deprecated"

class InvalidArtifact(BespinError):
    desc = "Chosen artifact is invalid"

