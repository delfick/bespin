"""
This is where the mainline sits and is responsible for setting up the logging,
the argument parsing and for starting up Bespin.
"""

from bespin.collector import Collector
from bespin import VERSION

from input_algorithms.spec_base import NotSpecified
from delfick_app import App
import argparse
import logging

class App(App):
    VERSION = VERSION
    boto_useragent_name = "bespin"

    cli_categories = ['bespin']
    cli_description = "Opinionated layer around boto"
    cli_environment_defaults = {"BESPIN_CONFIG": ("--bespin-config", './bespin.yml'), "NO_ASSUME_ROLE": "--no-assume-role"}
    cli_positional_replacements = [('--task', 'list_tasks'), ('--environment', NotSpecified), ('--stack', NotSpecified), ('--artifact', NotSpecified)]

    def execute(self, args, extra_args, cli_args, logging_handler):
        collector = Collector()
        cli_args["bespin"]["extra"] = extra_args

        collector.prepare(args.bespin_config.name, cli_args)
        if "term_colors" in collector.configuration:
            self.setup_logging_theme(logging_handler, colors=collector.configuration["term_colors"])

        collector.configuration["task_runner"](collector.configuration["bespin"].chosen_task)

    def setup_other_logging(self, args, verbose=False, silent=False, debug=False):
        logging.getLogger("boto").setLevel([logging.CRITICAL, logging.ERROR][verbose or debug])
        logging.getLogger("requests").setLevel([logging.CRITICAL, logging.ERROR][verbose or debug])
        logging.getLogger("paramiko.transport").setLevel([logging.CRITICAL, logging.ERROR][verbose or debug])

    def specify_other_args(self, parser, defaults):
        parser.add_argument("--bespin-config"
            , help = "The config file specifying what bespin should care about"
            , type = argparse.FileType("r")
            , **defaults["--bespin-config"]
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

        parser.add_argument("--task"
            , help = "The task to run"
            , dest = "bespin_chosen_task"
            , **defaults["--task"]
            )

        parser.add_argument("--environment"
            , help = "Specify an environment to play with"
            , dest = "bespin_environment"
            , **defaults["--environment"]
            )

        parser.add_argument("--stack"
            , help = "Specify a particular stack"
            , dest = "bespin_chosen_stack"
            , **defaults["--stack"]
            )

        parser.add_argument("--artifact"
            , help = "Specify a particular artifact"
            , dest = "bespin_chosen_artifact"
            , **defaults['--artifact']
            )

        extra = defaults["--no-assume-role"]
        if "default" in extra and extra.get('default') in ("1", "true", "yes"):
            extra["default"] = True
        parser.add_argument("--no-assume-role"
            , help = "Don't assume role"
            , dest = "bespin_no_assume_role"
            , action = "store_true"
            , **extra
            )

main = App.main
if __name__ == '__main__':
    main()

