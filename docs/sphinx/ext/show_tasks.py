from bespin.tasks import available_tasks
from bespin.overview import Overview
from bespin import helpers as hp

from docutils.statemachine import ViewList
from sphinx.util.compat import Directive
from textwrap import dedent
from docutils import nodes

class ShowTasksDirective(Directive):
    """Directive for outputting all the default bespin tasks"""
    has_content = True

    def run(self):
        """For each file in noseOfYeti/specs, output nodes to represent each spec file"""
        tokens = []
        with hp.a_temp_file() as fle:
            fle.write(dedent("""
                ---
                environments: { dev: {} }
                stacks: { app: {} }
            """))
            fle.seek(0)
            overview = Overview(fle.name)

        section = nodes.section()
        section['ids'].append("available-tasks")

        title = nodes.title()
        title += nodes.Text("Default tasks")
        section += title

        for name, task in sorted(overview.find_tasks().items(), key=lambda x: len(x[0])):

            lines = [name] + ["  {0}".format(line.strip()) for line in task.description.split('\n')]
            viewlist = ViewList()
            for line in lines:
                viewlist.append(line, name)
            self.state.nested_parse(viewlist, self.content_offset, section)

        return [section]

def setup(app):
    """Setup the show_specs directive"""
    app.add_directive('show_tasks', ShowTasksDirective)

