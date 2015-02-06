"""
This is where the mainline sits and is responsible for setting up the logging,
the argument parsing and for starting up Bespin.
"""

from __future__ import print_function

from bespin.errors import BadOption, UserQuit
from bespin.overview import Overview
from bespin import VERSION

from rainbow_logging_handler import RainbowLoggingHandler
from input_algorithms.spec_base import NotSpecified
from delfick_error import DelfickError
import argparse
import logging
import sys
import os

log = logging.getLogger("bespin.executor")

def setup_logging(verbose=False, silent=False, debug=False):
    log = logging.getLogger("")
    handler = RainbowLoggingHandler(sys.stderr)
    handler._column_color['%(asctime)s'] = ('cyan', None, False)
    handler._column_color['%(levelname)-7s'] = ('green', None, False)
    handler._column_color['%(message)s'][logging.INFO] = ('blue', None, False)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)-15s %(message)s"))
    log.addHandler(handler)
    log.setLevel([logging.INFO, logging.DEBUG][verbose or debug])
    if silent:
        log.setLevel(logging.ERROR)

    logging.getLogger("boto").setLevel([logging.CRITICAL, logging.ERROR][verbose or debug])
    logging.getLogger("requests").setLevel([logging.CRITICAL, logging.ERROR][verbose or debug])
    logging.getLogger("paramiko.transport").setLevel([logging.CRITICAL, logging.ERROR][verbose or debug])
    return handler

class CliParser(object):
    """Knows what argv looks like"""
    def parse_args(self, argv=None):
        """Split the args into <args> -- <extra_args> and run <args> through our argparse.ArgumentParser"""
        if argv is None:
            argv = sys.argv[1:]

        argv = list(argv)
        args = []
        extras = None
        default_task = NotSpecified
        default_stack = NotSpecified
        default_environment = NotSpecified
        default_artifact = NotSpecified

        if argv:
            if not argv[0].startswith("-"):
                default_task = argv[0]
                argv.pop(0)

            if argv and not argv[0].startswith("-"):
                default_environment = argv[0]
                argv.pop(0)

            if argv and not argv[0].startswith("-"):
                default_stack = argv[0]
                argv.pop(0)

            if argv and not argv[0].startswith("-"):
                default_artifact = argv[0]
                argv.pop(0)

        while argv:
            nxt = argv.pop(0)
            if extras is not None:
                extras.append(nxt)
            elif nxt == "--":
                extras = []
            else:
                args.append(nxt)

        other_args = ""
        if extras:
            other_args = " ".join(extras)

        parser = self.make_parser(default_task=default_task, default_stack=default_stack, default_environment=default_environment, default_artifact=default_artifact)
        args = parser.parse_args(args)
        if default_task is not NotSpecified and args.bespin_chosen_task != default_task:
            raise BadOption("Please don't specify task as a positional argument and as a --task option", positional=default_task, kwarg=args.bespin_chosen_task)
        if default_environment is not NotSpecified and args.bespin_environment != default_environment:
            raise BadOption("Please don't specify environment as a positional argument and as a --environment option", positional=default_environment, kwarg=args.bespin_environment)
        if default_stack is not NotSpecified and args.bespin_chosen_stack != default_stack:
            raise BadOption("Please don't specify stack as a positional argument and as a --stack option", positional=default_stack, kwargs=args.bespin_chosen_stack)
        if default_artifact is not NotSpecified and args.bespin_chosen_artifact != default_artifact:
            raise BadOption("Please don't specify artifact as a positional argument and as an --artifact option", positional=default_artifact, kwargs=args.bespin_chosen_artifact)

        return args, other_args

    def make_parser(self, default_task=NotSpecified, default_stack=NotSpecified, default_environment=NotSpecified, default_artifact=NotSpecified):
        parser = argparse.ArgumentParser(description="Opinionated layer around boto")

        logging = parser.add_mutually_exclusive_group()
        logging.add_argument("--verbose"
            , help = "Enable debug logging"
            , action = "store_true"
            )

        logging.add_argument("--silent"
            , help = "Only log errors"
            , action = "store_true"
            )

        logging.add_argument("--debug"
            , help = "Debug logs"
            , action = "store_true"
            )

        opts = {}
        if os.path.exists("./bespin.yml"):
            opts["default"] = "./bespin.yml"
            opts["required"] = False
        else:
            opts["required"] = True

        if "BESPIN_CONFIG" in os.environ:
            opts["default"] = os.environ["BESPIN_CONFIG"]
            del opts["required"]
        parser.add_argument("--bespin-config"
            , help = "The config file specifying what bespin should care about"
            , type = argparse.FileType("r")
            , **opts
            )

        parser.add_argument("--flat"
            , help = "Used by the show command"
            , dest = "bespin_flat"
            , action = "store_true"
            )

        parser.add_argument("--dry-run"
            , help = "Should Bespin take any real action or print out what is intends to do"
            , dest = "bespin_dry_run"
            , action = "store_true"
            )

        parser.add_argument("--command"
            , help = "Command to run for the command_on_instances task"
            , default = ""
            )

        extra = {"default": "list_tasks"}
        if default_task is not NotSpecified:
            extra["default"] = default_task
        parser.add_argument("--task"
            , help = "The task to run"
            , dest = "bespin_chosen_task"
            , **extra
            )

        extra = {"default": ""}
        if default_environment is not NotSpecified:
            extra["default"] = default_environment
        parser.add_argument("--environment"
            , help = "Specify an environment to play with"
            , dest = "bespin_environment"
            , **extra
            )

        extra = {"default": ""}
        if default_stack is not NotSpecified:
            extra["default"] = default_stack
        parser.add_argument("--stack"
            , help = "Specify a particular stack"
            , dest = "bespin_chosen_stack"
            , **extra
            )

        extra = {"default": ""}
        if default_artifact is not NotSpecified:
            extra["default"] = default_artifact
        parser.add_argument("--artifact"
            , help = "Specify a particular artifact"
            , dest = "bespin_chosen_artifact"
            , **extra
            )

        extra = {"default": False}
        if os.environ.get("NO_ASSUME_ROLE"):
            extra["default"] = True
        parser.add_argument("--no-assume-role"
            , help = "Don't assume role"
            , dest = "bespin_no_assume_role"
            , **extra
            )

        return parser

    def interpret_args(self, argv):
        """Parse argv, do some transformation and return cli_args suitable for Overview"""
        args, extra = CliParser().parse_args(argv)

        cli_args = {"bespin": {}}
        for key, val in sorted(vars(args).items()):
            if key.startswith("bespin_"):
                cli_args["bespin"][key[7:]] = val
            else:
                cli_args[key] = val
        cli_args["bespin"]["extra"] = extra

        return args, cli_args

def set_boto_useragent():
    """Make boto report bespin as the user agent"""
    __import__("boto")
    useragent = sys.modules["boto.connection"].UserAgent
    if "bespin" not in useragent:
        sys.modules["boto.connection"].UserAgent = "{0} bespin/{1}".format(useragent, VERSION)

def main(argv=None):
    try:
        try:
            args, cli_args = CliParser().interpret_args(argv)
            handler = setup_logging(verbose=args.verbose, silent=args.silent, debug=args.debug)
            set_boto_useragent()
            Overview(configuration_file=args.bespin_config.name, logging_handler=handler).start(cli_args)
        except KeyboardInterrupt:
            if CliParser().parse_args(argv)[0].debug:
                raise
            raise UserQuit()
    except DelfickError as error:
        print("")
        print("!" * 80)
        print("Something went wrong! -- {0}".format(error.__class__.__name__))
        print("\t{0}".format(error))
        if CliParser().parse_args(argv)[0].debug:
            raise
        sys.exit(1)

if __name__ == '__main__':
    main()

