.. _ssh:

SSH'ing into instances
======================

It's useful to be able to ssh into instances that your bring up in your stack.

Bespin provides the ``instances`` command for finding the instances, getting the
ssh key, and ssh'ing into one of the instances.

This command also handles going via a jumphost/bastion instance.

.. code-block:: yaml

  ---

  environments:
    dev:
      account_id: "123456789"

  stacks:
    app:
      stack_name: my_application

      ssh:
        bastion_host: bastion.my_company.com
        bastion_user: ec2-user
        bastion_key_path: "{config_root}/{environment}/bastion_ssh_key.pem"

        user: ec2-user
        auto_scaling_group_name: AppServerAutoScalingGroup
        instance_key_path: "{config_root}/{environment}/ssh_key.pem

With this configuration, ``bespin instances dev app`` will look for all the
instances in the ``AppServerAutoScalingGroup`` defined by the ``my_application``
cloudformation stack and list the ips::

  $ bespin instances dev app
  Found 1 instances
  ====================
  i-d848ca04      10.35.3.151     running Up 9990 seconds

Then you can run ``bespin instances dev app 10.35.3.151`` and with this configuration
will ssh through ``ec2-user@bastion.my_company.com`` into ``ec2-user@10.35.3.151``.

If the bastion options are not specified, then no bastion is used.

Fetching ssh keys from Rattic
-----------------------------

Bespin offers the ability to fetch ssh keys stored in `Rattic <http://rattic.org/>`_:

.. code-block:: yaml

  ---

  environments:
    dev:
      account_id: "123456789"

  stacks:
    app:
      stack_name: my_application

      ssh:
        bastion_host: bastion.my_company.com
        bastion_user: ec2-user
        bastion_key_path: "{config_root}/{environment}/bastion_ssh_key.pem"
        bastion_key_location: "2200"

        user:ec2-user
        auto_scaling_group_name: Appserverautoscalinggroup
        instance_key_location: "2201"

        storage_type: rattic
        storage_host: rattic.my_company.com
        instance_key_path: "{config_root}/{environment}/ssh_key.pem

With this configuration, if bespin can't find the ssh key specified by
``bastion_key_path`` and ``instance_key_path`` then it will get the ssh keys
from ``rattic.my_company.com`` using the key ids specified by ``bastion_key_location``
and ``instance_key_location``.

Note that the ssh keys must be uploaded to rattic as ssh keys, not as attachments.

.. note:: The instance_key_path and bastion_key_path in these two examples are
  the same as the defaults, so leaving them out would have the same effect.

Specifying hosts
----------------

The hosts can be found by either specifying ``auto_scaling_group_name`` which
will look for all the instances attached to that scaling group, or by specifying
``instance`` which will look for that instance as specified in the cloudformation
stack.

For example, if my stack.json has this in it:

.. code-block:: json

  { "Resources":
    { "MyInstance":
      { "Type": "AWS::EC2::Instance"
      , "Properties": [..]
      }
    }
  }

Then I can specify it by having:

.. code-block:: yaml

  ssh:
    user: ec2-user
    instance: MyInstance

When you do this you may also specify an address that is displayed instead of
an ip address:

.. code-block:: yaml

  ssh:
    user: ec2-user
    instance: BastionHost
    address: bastion.{environment}.my-company.com

So you'd get something like::

  $ bespin instances dev app
  Found 1 instances
  ====================
  i-d848ca04      bastion.dev.my-company.com     running Up 9001 seconds

  $ bespin instances prod app
  Found 1 instances
  ====================
  i-f849ca94      bastion.prod.my-company.com     running Up 9001 seconds

