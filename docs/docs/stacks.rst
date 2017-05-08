.. _stacks:

Stacks
======

Bespin revolves around the concept of a cloudformation stack. Defining them is
one of the required options in the :ref:`configuration`.

A cloudformation stack has two parts to it:

The template file
  Cloudformation is defined by a template file - see `Cloudformation template
  basics`_

  Currently bespin supports the JSON and YAML `Cloudformation formats`_.

The parameters
  Cloudformation has the idea of parameters, where you define variables in your
  stack and then provide values for those variables at creation time.

  Bespin provides the option of either specifying a file containing these values
  or, more conveniently, you may specify them inline with the configuration as a
  yaml dictionary.

.. _`Cloudformation template basics`: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/gettingstarted.templatebasics.html
.. _`Cloudformation formats`: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/template-formats.html

So if you have the following directory structure::

  /my-project/
    bespin.yml
    app.json
    params.json

And the following configuration:

.. code-block:: yaml

  ---

  environments:
    dev:
      account_id: "123456789"

  stacks:
    app:
      stack_name: my-application
      stack_json: "{config_root}/app.json"
      params_json: "{config_root}/params.json"

Then ``bespin deploy dev app`` will deploy the ``app.json`` using ``params.json`` as
the parameters.

Where ``params.json`` looks like:

.. code-block:: json

    [ { "ParameterKey": "Key1"
      , "ParameterValue": "Value1"
      }
    , { "ParameterKey": "Key2"
      , "ParameterValue": "Value2"
      }
    ]

An equivalent ``params.yaml`` file would look like:

.. code-block:: yaml

  ---

  Key1: Value1
  Key2: Value2

Alternatively you can have inline the parameters like so:

.. code-block:: yaml

    ---

    environments:
      dev:
        account_id: "123456789"

    stacks
      app:
        stack_name: my-application
        stack_json: "{config_root}/app.json"

        params_yaml:
          Key1: Value1
          Key2: Value2

.. note:: The stack_json and stack_yaml will default to
   "{config_root}/{_key_name_1}.json" and "{config_root}/{_key_name_1}.yaml".
   This means if your stack json is the same name as the stack and next to your
   configuration, then you don't need to specify ``stack_json``.

Defining variables
------------------

You can refer to variables defined in your configuration inside params_yaml using
a ``XXX_<VARIABLE>_XXX`` syntax. So if you have defined a variable called
``my_ami`` then ``XXX_MY_AMI_XXX`` inside your params_yaml values will be
replaced with the value of that variable.

So let's say I have the following configuration:

.. code-block:: yaml

  ---

  vars:
    azs: "ap-southeast-2a,ap-southeast-2b"

  environments:
    dev:
      account_id: "123456789"
      vars:
        vpcid: vpc-123456

    prod:
      account_id: "987654321"
      vars:
        vpcid: vpc-654321

  stacks:
    app:
      stack_name: my-application
      vars:
        ami: ami-4321

      environments:
        dev:
          vars:
            min_size: 0

        prod:
          vars:
            min_size: 2

      params_yaml:
        ami: XXX_AMI_XXX
        AZs: XXX_AZS_XXX
        VpcId: XXX_VPCID_XXX
        MinSize: XXX_MIN_SIZE_XXX

Then you'll get the following outputs::

  $ bespin params dev app
  my-application
  [
      {
          "ParameterValue": "vpc-123456",
          "ParameterKey": "VPCId"
      },
      {
          "ParameterValue": "ap-southeast-2a,ap-southeast-2b",
          "ParameterKey": "AZs"
      },
      {
          "ParameterValue": "ami-4321",
          "ParameterKey": "ami"
      }
  ]

  $ bespin params prod app
  my-application
  [
      {
          "ParameterValue": "vpc-654321",
          "ParameterKey": "VPCId"
      },
      {
          "ParameterValue": "ap-southeast-2a,ap-southeast-2b",
          "ParameterKey": "AZs"
      },
      {
          "ParameterValue": "ami-4321",
          "ParameterKey": "ami"
      }
  ]

If you're looking closely enough you may notice that there is a hierarchy of
variables in the configuration. Bespin will essentially collapse this
hierarchy into one dictionary of variables at runtime before using them.

The order is::

  <root>
  <environment>
  <stack>
  <stack_environment>

Where values of the same name are overridden.

This allows you to have:

* Variables across all stacks for all environments
* Variables across all stacks for particular environments
* Variables specific to a stack for all environments
* Variables specific to a stack for particular environments

.. note:: The XXX_<VARIABLE>_XXX syntax is a search and replace, so you can
  do something like:

  .. code-block:: yaml

    ---

    environments:
      dev:
        account_id: "123456789"
        vars:
          subnet_a: subnet-12345
          subnet_b: subnet-67890

    stacks:
      app:
        stack_name: my-application

        params_yaml:
          subnets: XXX_SUBNET_A_XXX,XXX_SUBNET_B_XXX

  and reference more than one variable and intermingle with other characters.

Dynamic Variables
-----------------

When you define a variable, you may also specify a list of two items:

.. code-block:: yaml

  ---

  vars:
    vpcid: [vpc-base, VpcId]

This is a special syntax and stands for ``[<stack_name>, <output_name>]`` and
will dynamically find the specified `Cloudformation output`_ for that stack.

For those unfamiliar with cloudformation, it allows you to define Outputs for
your stacks. These outputs are essentially a Key-Value store of template defined
strings.

So in the example above, the ``vpcid`` variable would resolve to the ``VpcId``
Output from the ``vpc-base`` cloudformation stack in the environment being
deployed to.

.. _`Cloudformation output`: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/outputs-section-structure.html

.. _stack_env:

Environment Variables
---------------------

You may populate variables with environment variables.

First you must specify ``env`` as a list of environment variables that need to
be defined and then you may refer to them using ``XXX_<VARIABLE>_XXX``.

For example:

.. code-block:: yaml

  ---

  environments:
    dev:
      account_id: "123456789"

  stacks:
    app:
      stack_name: my-application

      env:
        - BUILD_NUMBER
        - GIT_COMMIT

      params_yaml:
        Version: app-XXX_BUILD_NUMBER_XXX

Environment variables can also be defined with defaults or overrides.

"BUILD_NUMBER"
  No default is specified, so if this variable isn't in the environment at runtime
  then bespin will complain and quit.

"BUILD_NUMBER:123"
  A default has been specified, so if it's not in the environment at runtime,
  bespin will populate this variable with the value "123"

"BUILD_NUMBER=123"
  An override has been specified. This means that regardless of whether this
  environment variable has been specified or not, it will be populated with the
  value of "123"

.. note:: To use environment variables in ``stack_name`` refer to Stack's
   ``stack_name`` and ``stack_name_env`` :doc:`configuration` documentation.
