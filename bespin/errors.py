from input_algorithms.errors import BadSpec, BadSpecValue
from delfick_error import DelfickError, ProgrammerError

class BespinError(DelfickError): pass

# Explicitly make these errors in this context
BadSpec = BadSpec
BadSpecValue = BadSpecValue
ProgrammerError = ProgrammerError

########################
###   CONFIGURATION
########################

class BadConfiguration(BespinError):
    desc = "Bad configuration"

class BadOptionFormat(BespinError):
    desc = "Bad option format"

class BadOption(BespinError):
    desc = "Bad Option"

class MissingOutput(BespinError):
    desc = "Couldn't find an output"

class MissingFile(BespinError):
    desc = "Couldn't find a file"

class MissingVariable(BespinError):
    desc = "Couldn't find a variable"

class BadFile(BespinError):
    desc = "bad file"

class BadJson(BespinError):
    desc = "Bad json"

class BadYaml(BespinError):
    desc = "Invalid yaml file"

########################
###   OBJECTS
########################

class BadTask(BespinError):
    desc = "Bad task"

class NoSuchStack(BespinError):
    desc = "Couldn't find stack"

class BadStack(BespinError):
    desc = "Bad stack"

class BadDeployment(BespinError):
    desc = "Failed to get all the correct deployment messages"

class InvalidArtifact(BespinError):
    desc = "Chosen artifact is invalid"

########################
###   AMAZON
########################

class BadAmazon(BespinError):
    desc = "Amazon says no"

class BadS3Bucket(BadAmazon):
    desc = "Bad S3 Bucket"

class BadSQSMessage(BadAmazon):
    desc= "Failed to decode message"

class StackDoesntExist(BadAmazon):
    desc = "Missing stack"

########################
###   OTHER
########################

class UserQuit(BespinError):
    desc = "User quit the program"

class StackDepCycle(BespinError):
    desc = "Stack dependency cycle"

class CouldntKill(BespinError):
    desc = "Failed to kill a process"

class BadImport(BespinError):
    desc = "Failed to import"

class Throttled(BespinError):
    desc = "limit rate exceeded"

class MissingSSHKey(BespinError):
    desc = "Couldn't find an ssh key"

