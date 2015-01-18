# coding: spec

from bespin.processes import command_output

from tests.helpers import BespinCase
from textwrap import dedent
import sys

describe BespinCase, "command_output":
    it "returns the output and exit code from running a command":
        with self.a_temp_file() as filename:
            with open(filename, 'w') as fle:
                fle.write(dedent("""
                print("hello")
                print("there")
                """))
            output, exit_code = command_output("{0} {1}".format(sys.executable, filename))

            self.assertEqual(output, ["hello", "there"])
            self.assertEqual(exit_code, 0)

    it "can kill a command after a certain timeout":
        with self.a_temp_file() as filename:
            with open(filename, 'w') as fle:
                fle.write(dedent("""
                import time
                print("hello")
                import sys; sys.stdout.flush()
                time.sleep(3)
                print("there")
                """))
            output, exit_code = command_output("{0} {1}".format(sys.executable, filename), timeout=0.05)

            self.assertEqual(exit_code, -15)
            self.assertEqual(output, ["hello"])

    it "can force kill a command that won't normally terminate":
        with self.a_temp_file() as filename:
            with open(filename, 'w') as fle:
                fle.write(dedent("""
                import signal
                def handler(*args):
                    print("Can't terminate me!")
                    import sys; sys.stdout.flush()
                signal.signal(signal.SIGTERM, handler)
                while True:
                    try:
                        import time
                        time.sleep(0.1)
                    except KeyboardInterrupt:
                        print("can't interrupt me!")
                        import sys; sys.stdout.flush()
                """))
            output, exit_code = command_output("{0} {1}".format(sys.executable, filename), timeout=0.05)

            self.assertEqual(exit_code, -9)
            self.assertEqual(output, ["Can't terminate me!"])

    it "doesn't block if there is nothing to read":
        with self.a_temp_file() as filename:
            with open(filename, 'w') as fle:
                fle.write(dedent("""
                import time
                time.sleep(3)
                """))
            output, exit_code = command_output("{0} {1}".format(sys.executable, filename), timeout=0.05)

            self.assertEqual(exit_code, -15)
            self.assertEqual(output, [])

