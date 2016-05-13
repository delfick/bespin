Bespin
======

An opinionated wrapper around Amazon Cloudformation that reads yaml files.
and make things happen.

.. image:: https://travis-ci.org/realestate-com-au/bespin.png?branch=master
    :target: https://travis-ci.org/realestate-com-au/bespin

The documentation can be found at http://bespin.readthedocs.io

Installation
------------

Just use pip::

  pip install bespin

Usage
-----

Once bespin is installed, there will be a new program called ``bespin``.

When you call bespin without any arguments it will print out the tasks you
have available.

You may invoke these tasks with the ``task`` option.

Simpler Usage
-------------

To save typing ``--task``, ``--stack`` and ``--environment`` too much
, the first positional argument is treated as ``task``
(unless it is prefixed with a ``-``); the second positional argument
(if also not prefixed with a ``-``) is taken as the ``environment`` and the third is
treated as the ``stack``.

So::

    $ bespin --task deploy --environment dev --stack app

Is equivalent to::

    $ bespin deploy dev app

Logging colors
--------------

If you find the logging output doesn't look great on your terminal, you can
try setting the ``term_colors`` option in ``bespin.yml`` to either ``light`` or
``dark``.

The yaml configuration
----------------------

Bespin reads everything from a yaml configuration. By default this is a
``bespin.yml`` file in the current directory, but may be changed with the
``--bespin-config`` option or ``BESPIN_CONFIG`` environment variable.

It will also read from ``~/.bespin.yml`` and will be overridden by anything in
the configuration file you've specified.

Tests
-----

Install testing deps and run the helpful script::

  pip install -e .
  pip install -e ".[tests]"
  ./test.sh

