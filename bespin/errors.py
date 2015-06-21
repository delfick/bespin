from delfick_error import DelfickError, ProgrammerError, UserQuit
from input_algorithms.errors import BadSpec, BadSpecValue
from delfick_app import BadOption

class BespinError(DelfickError): pass

# Explicitly make these errors in this context
BadSpec = BadSpec
UserQuit = UserQuit
BadOption = BadOption
BadSpecValue = BadSpecValue
ProgrammerError = ProgrammerError

########################
###   CONFIGURATION
########################

class BadConfiguration(BespinError):
    desc = "Bad configuration"

class BadOptionFormat(BespinError):
    desc = "Bad option format"

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

class BadCommand(BespinError):
    desc = "Bad command"

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

class MissingPlan(BespinError):
    desc = "Couldn't find a plan"

class UnknownDowntimerSystem(BespinError):
    desc = "Don't know how to handle downtiming this alerting system"

class FailedAlertingSystem(BespinError):
    desc = "Something failed about this alerting system"

class FailedAlertingSystems(BespinError):
    desc = "Something failed about our interaction with alerting systems"

class BadNetScaler(BespinError):
    desc = "Something went wrong with the netscaler"

class BadDnsSwitch(BespinError):
    desc = "Something failed about switching dns traffic"

