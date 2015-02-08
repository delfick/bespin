.. _tasks:

Tasks
=====

Bespin's mechanism for doing anything are tasks. By default Bespin comes with a
number of tasks as describe below:

.. show_tasks::

Custom Tasks
------------

There are two ways you can create custom tasks.

The first way is to define ``tasks`` as part of a stack definition::

  ---

  stacks:
    app:
      [..]

      tasks:
        deploy_app:
          action: deploy

Will mean that you can run ``bespin deploy_app dev`` and it will run the ``deploy``
action for your ``app`` stack.

Tasks have several options:

action
  The task to run. Note that the stack will default to the stack you've defined
  this task on.

options
  Extra options to merge into the stack configuration when running the task.

overrides
  Extra options to merge into the root of the configuration when running the task.

description
  A description that is shown for this task when you ask Bespin to list all the
  tasks.

The second way of defining custom tasks is with the ``extra_imports`` option.

For example, let's say you have the following layout::

  bespin.yml
  app.json
  scripts.py

And your bespin.yml looked like::

  ---

  bespin:
    extra_imports: ["{config_root}", "scripts"]

  stacks:
    app:
      [..]

Then before Bespin looks for tasks it will first import the python module named
``scripts`` that lives in the folder where ``bespin.yml`` is defined. So in this
case, the ``scripts.py``.

The only thing ``scripts.py`` needs is a ``__bespin__(bespin, task_maker)`` method
where ``bespin`` is the ``Bespin`` object and ``task_maker`` is a function that
may be used to register tasks.

For example::

  def __bespin__(bespin, task_maker):
    task_maker("deploy_app", "Deploy the app stack", action="deploy").specify_stack("app")

Here we have defined the ``deploy_app`` action that will ``deploy`` the ``app`` stack.

We can do something more interesting if we also define a custom action::

  from bespin.tasks import a_task

  def __bespin__(bespin, task_maker):
    task_maker("list_amis", "List amis with a particular tag")

  @a_task(needs_credentials=True)
  def list_amis(overview, configuration, **kwargs):
    credentials = configuration['bespin'].credentials
    amis = credentials.ec2.get_all_images(filters={"tag:application": "MyCreatedAmis"})
    for ami in amis:
      print(ami.id)

And then we can do ``bespin list_amis dev`` and it will find all the Amis that have
an ``application`` tag with ``MyCreatedAmis``.

