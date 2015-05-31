.. _artifacts:

Artifacts
=========

Bespin lets you define, create and upload artifacts as defined in the configuration.
Where an artifact is just an archive of files either generated or taken from the
filesystem.

Artifacts are defined per :ref:`stack <stacks>`:

.. code-block:: yaml

  ---

  environments:
    dev:
      account_id: "123456789"

  stacks:
    app:
      artifacts:
        main:
          compression_type: gz

          upload_to: s3://my-bucket/artifacts/main.tar.gz

          paths:
            - ["{config_root}/ansible", "/ansible"]

With this example, ``bespin publish_artifacts dev app`` will create an archive of
an ``ansible`` folder next to the configuration, which is uploaded to
``s3://my-bucket/artifacts/main.tar.gz``.

Specifying the contents
-----------------------

There are currently a few ways of specifying the contents of the archive:

paths
  As in the example above, paths is a list of lists. Each item in the list being
  ``[<local_location>, <location_in_archive>]`` and will take from the local
  location and put into the archive under the location that is specified.

files
  Allows you to add files into the archive. For example:

  .. code-block:: yaml

    files:
      - content: |
          A file
          with content
          goes here
        dest: /location/in/archive.txt

  This creates a file at ``/location/in/archive.txt`` with the content as
  specified.

  You can also generate the content from a custom :ref:`task <tasks>`. So say
  you've defined a custom task called ``generate_ansible_playbook`` then you can
  specify:

  .. code-block:: yaml

    files:
      - task: generate_ansible_playbook
        dest: /ansible/playbook.yml

commands
  This one lets you copy files from your disk into some temporary location, edit
  any files as you see fit, run an arbitrary command in the temporary location
  and add files from there into the archive:

  .. code-block:: yaml

      commands:
        - copy:
            - ["{config_root}/../../play-app", "/"]
          modify:
            "conf/application.conf":
              append:
                - 'app_version="{__stack__.vars.version}"'
          command: "sbt dist"
          add_into_tar:
            - ["target/universal/{vars.app_name}-SNAPSHOT.zip", "/artifacts/{vars.app_name}.zip"] 

  Here we've copied our play-app into the root of the temporary location,
  added the version to the ``application.conf``, run ``sbt dist`` in the
  temporary location, and then added the resulting file into the archive under
  ``/artifacts/<app_name>.zip``

Environment Variables
---------------------

It's useful to be able to pass in environment variables, like the build number
and then use it. This is done with ``build_env``, which acts like :ref:`env <stack_env>`

For example:

.. code-block:: yaml

  ---

  environments:
    dev:
      account_id: "123456789"

  stacks:
    app:
      build_env:
        - BUILD_NUMBER
        - GIT_COMMIT

      vars:
        version: "{{BUILD_NUMBER}}-{{GIT_COMMIT}}"

      artifacts:
        main:
          upload_to: "s3://my-bucket/artifacts/app-{{BUILD_NUMBER}}.tar.gz"

          files:
            - content: {__stack__.vars.version}
              dest: /artifacts/version.txt

          paths:
            - ["{config_root}/ansible", /ansible]

Note that referring to environment variables is done with "{{<variable>}}". This
is because bespin formats the string twice, once with the configuration, and a
second time with the environment variables.

Cleaning up artifacts
---------------------

It's dangerous to clean up artifacts with a time based policy in S3 because if
you don't create new artifacts for a long enough amount of time, then s3 will
clean up an artifact that is used by production and so when new machines come up
there won't be an artifact.

Instead, it is better to manually clean up artifacts and keep a certain number
of previous artifacts.

Bespin helps this with the ``clean_old_artifacts`` task:

.. code-block:: yaml

  ---

  environments:
    dev:
      account_id: "123456789"

  stacks:
    app:
      build_env:
        - BUILD_NUMBER

      artifacts:
        main:
          history_length: 5
          cleanup_prefix: app-

          compression_type: gz
          upload_to: "s3://my-bucket/artifacts/app-{{BUILD_NUMBER}}.tar.gz"

          paths:
            - ["{config_root}/ansible", /ansible]

With this configuration, ``bespin clean_old_artifacts dev app`` will find all
the artifacts under ``s3://my-bucket/artifacts`` with the prefix ``app-``, keep
the newest ``5`` and delete the rest.

.. note:: If you just want to use the clean_old_artifacts logic but your artifacts
 are generated and uploaded by something else, then specify ``not_created_here: true``

