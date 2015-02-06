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
      <stack2>.json

      <environment1>/
        <stack>-params.json
        <stack2>-params.json

      <environment2>/
        <stack>-params.json
        <stack2>-params.json

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

.. note:: The location of the stack and params json files are configured by the
 ``stack_json`` and ``params_json`` options. 
    
.. show_specs::
