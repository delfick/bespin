from input_algorithms.many_item_spec import many_item_formatted_spec
from bespin.formatter import MergedOptionStringFormatter
from bespin.option_spec.task_objs import Task
from bespin.errors import BadImport

from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb
import imp

class import_spec(many_item_formatted_spec):
    value_name = "Import specification"
    specs = [sb.string_spec(), sb.string_spec()]
    formatter = MergedOptionStringFormatter

    def create_result(self, directory, import_name, meta, val, dividers):
        directory = sb.directory_spec().normalise(meta, directory)
        return Import(directory, import_name)

class Import(dictobj):
    fields = ['directory', 'import_name']

    def do_import(self, bespin, tasks):
        def task_maker(name, description, action=None, **options):
            if not action:
                action = name
            tasks[name] = Task(action, description=description, options=options, label="Project")
            return tasks[name]

        try:
            args = imp.find_module(self.import_name, [self.directory])
        except ImportError as error:
            raise BadImport(directory=self.directory, importing=self.import_name, error=error)

        try:
            module = imp.load_module(self.import_name, *args)
        except SyntaxError as error:
            raise BadImport(directory=self.directory, importing=self.import_name, error=error)

        if not hasattr(module, "__bespin__"):
            raise BadImport("Extra import had no __bespin__ defined", directory=self.directory, importing=self.import_name)

        module.__bespin__(bespin, task_maker)


