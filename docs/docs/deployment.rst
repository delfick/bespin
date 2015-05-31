.. _deployment:

Deployment
==========

Bespin offers the ability to deploy stacks, taking into account dependency
resolution and deployment checking.

For example, let's say we have the following configuration:

.. code-block:: yaml

  ---

  environment:
    dev:
      account_id: "12345789"

  stacks:
    security_groups:
      stack_name: appplication_security_groups

    app:
      stack_name: application

      vars:
        app_security_groups: ["{stacks.security_groups}", "AppSecurityGroup"]

      params_yaml:
        AppSecurityGroup: XXX_APP_SECURITY_GROUP_XXX

      build_after:
        - dns

    dns:
      stack_name: application-dns

And we do ``bespin deploy dev app``, then it will first deploy ``security_groups``,
use the output from that stack as a variable for the parameters for the ``app``
stack, which gets deployed next. After the app stack is deployed, the ``dns`` stack
will then be deployed (because of the ``build_after`` option).

Plans
-----

You can explicitly specify an order of stacks by creating a ``plan``:

.. code-block:: yaml

  ---

  environments:
    dev:
      account_id: "12345678"

  plan:
    all:
      - vpc
      - gateways
      - subnets
      - subnet_rules
      - nat
      - dns
      - dhcp
      - dns_names
      - peering

  stacks:
    vpc:
      [..]

    gateways:
      [..]

    [..etc..]

And then you may deploy that plan with ``bespin deploy_plan dev all``

Confirming deployment
---------------------

It's useful to be able to confirm that a deployment was actually successful even
if the cloudformation successfully deployed:

.. code-block:: yaml

  ---

  environments:
    dev:
      account_id: "123456789"

  stacks:
    app:
      stack_name: application

      env:
        - BUILD_NUMBER

      params_yaml:
        BuildNumber: XXX_BUILD_NUMBER_XXX

      confirm_deployment:
        url_checker:
          expect: "{{BUILD_NUMBER}}"
          endpoint: ["{stacks.app}", PublicEndpoint]
          check_url: /diagnostic/version
          timeout_after: 600

In this example, the deployment is checked by checking that a url returns some
expected value. In this case it expects the url ``/diagnostic/version`` to return
the BUILD_NUMBER we deployed with.

Confirm_deployment has multiple options

url_checker
  As per the example above, this checks a url on our app returns a particular
  value

sns_confirmation:
  This confirms that an sqs topic receives a particular message:

  .. code-block:: yaml

    confirm_deployment:
      auto_scaling_group_name: AppServerAutoScalingGroup

      sns_confirmation:
        timeout: 300
        version_message: "{{BUILD_NUMBER}}"
        deployment_queue: deployment-queue

  This configuration will expect that the sqs queue called ``deployment-queue``
  will receive a message for each new instance in the auto scaling group saying
  ``<instance_id>:success:<version_message>``

  Actually sending these messages is up to the definition of the cloudformation
  stack.

  .. note:: The naming of this is the result of an implementation detail where
   this was first implemented for a stack that populated the sqs queue via an
   sns notification.

deploys_s3_path:
  This allows you to specify an s3 path that you expect to have a value with a
  modified time newer than the deployment of the stack:

  .. code-block:: yaml

    confirm_deployment:
      deploys_s3_path:
        - ["s3://my-bucket/generated/thing.tar.gz", 600]

  Where the number is the timeout of looking for this s3 path.

When zero instances is ok
-------------------------

In some environments it may be ok that a stack deploys and has no instances
associated with it. In this case you may set the ``zero_instances_is_ok: true``.

If this isn't set and no instances are in the autoscaling group after the stack
is deployed, then Bespin will complain saying the deployment failed to make any
instances:

.. code-block:: yaml

  ---

  environments:
    dev:
      account_id: "123456789"

    prod:
      account_id: "123456789"

  stacks:
    app:
      stack_name: my-application

      confirm_deployment:
        auto_scaling_group_name: AppServerAutoScalingGroup

        url_checker:
          endpoint: endpoint.my-company.com
          expects: success
          check_url: /diagnostic/status

      # Add zero_instances_is_ok just for the dev environment
      environments:
        dev:
          confirm_deployment:
            zero_instances_is_ok: true

