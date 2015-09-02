from setuptools import setup, find_packages
from bespin import VERSION

setup(
      name = "bespin"
    , version = VERSION
    , packages = ['bespin'] + ['bespin.%s' % pkg for pkg in find_packages('bespin')]
    , include_package_data = True

    , install_requires =
      [ "delfick_app==0.6.2"
      , "option_merge==0.9.9.1"
      , "input_algorithms==0.4.4.7"

      , "six"
      , "pytz"
      , "slacker"
      , "humanize"
      , "argparse"
      , "requests"
      , "paramiko"

      , "radssh==1.0.5"
      , "pyrelic==0.8.0"
      , "boto==2.38.0"
      , "pyYaml==3.10"
      , "ultra_rest_client==0.1.4"
      , "FileChunkIO==1.6"
      , "dnslib==0.9.4"
      ]

    , extras_require =
      { "tests":
        [ "noseOfYeti>=1.5.0"
        , "nose"
        , "mock"
        , "moto"

        # Need to ensure httpretty is not 0.8.7
        # To prevent an infinite loop in python3 tests
        , "httpretty==0.8.6"
        ]
      }

    , entry_points =
      { 'console_scripts' :
        [ 'bespin = bespin.executor:main'
        ]
      }

    # metadata for upload to PyPI
    , url = "https://github.com/realestate-com-au/bespin"
    , author = "Stephen Moore"
    , author_email = "stephen.moore@rea-group.com"
    , description = "Opinionated wrapper around boto that reads yaml"
    , license = "MIT"
    , keywords = "cloudformation boto"
    )

