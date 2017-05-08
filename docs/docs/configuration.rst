.. _configuration:

Configuration
=============

Bespin is configured via a YAML file that contains Bespin configuration,
environment specific configuration, and stack specific configuration.

Layout
------

The layout of your directory is configured by default to look something like::

    root/
      bespin.yml
      <stack>.json
      <stack2>.yaml

      <environment1>/
        <stack>-params.json
        <stack2>-params.yaml

      <environment2>/
        <stack>-params.json
        <stack2>-params.yaml

So say you have two stacks, one called ``app`` and one called ``dns``, along with
only one environment called ``dev``::

    root/
      bespin.yml
      app.json
      dns.json

      dev/
        app-params.json
        dns-params.json

and your bespin.yml would look something like::

    ---

    environments:
      dev:
        account_id: 0123456789
        vars:
          variable1: value1

    stacks:
      app:
        <options>

      dns:
        <options>

Where ``<options>`` are the options for that stack.

.. note:: The location of the stack template file is configured by the
   ``stack_json`` or ``stack_yaml`` option. The location of the params file is
   configured by the ``params_json`` or ``params_yaml`` option. Alternatively
   parameters can be specified inline (inside bespin.yml) using ``params_yaml``.

.. show_specs::


Formatter
---------

Configuration values may reference other parts of the config using 'replacement
fields' surrounded by curly braces ``{}``. Nested values can be referenced
using dot notation, eg: ``{foo.bar.quax}``.
If you need to include a brace character in the literal text, it can be escaped
by doubling: ``{{`` and ``}}``.

Available fields:

environment
  Current environment name as a string

environments.<env_name>.*
  Environment mappings.

  Environment fields includes:

  account_id
    Environment AWS account id

  region
    Environment AWS region

stacks.<stack_name>.*
  Stack mappings.
  See `Stack <#Stack>`_ spec for more detail.

tags.*
  Tags mapping

vars.*
  Vars mapping

__stack_name__
  Current stack name as a string.

__stack__
  Current stack mapping (ie: stacks.__stack_name__).
  See `Stack <#Stack>`_ spec for more detail.

__environment__
  Current environment mapping (ie: environments.environment).


In addition to configuration fields, bespin defines the following special
values:

config_root
  Directory of the main configuration file (ie: ``dirname`` of
  ``--bespin-config``)

:config_dir
  *(advanced)* *(python2.7+ or python3 required)*

  Directory of the configuration file where the value was defined. See
  ``bespin.extra_files``.

_key_name_X
  *(advanced)*

  Refers to the key's content X positions up from the current value, indexed
  from zero. For example, the following would result in "example vars test"::

      stacks:
        test:
          vars:
            example: "{_key_name_0} {_key_name_1} {_key_name_2}"


Fields may also declare a formatter by suffixing the field with a colon ``:``
and the name of the formatter to use.
Available formatters include:

:env
  Formats environment variables suitable to be used in shell.  ``{USER:env}``
  would produce ``${USER}``.

:date
  Return a string representing the current datetime
  (``datetime.datetime.now()``) formatted by strftime. See `Python strftime`_
  for available format codes.
  eg: ``{%Y:date}`` would result in the current year (eg: "2017")

:underscored
  Converts '-' to '_'.

.. note:: The formatter does not support nested values (eg: {a.{foo}.c}). See
   :doc:`stacks` for details on using variable formatting (ie: XXX_MYVAR_XXX)
   instead.


.. _Python strftime: https://docs.python.org/2/library/datetime.html#strftime-strptime-behavior
