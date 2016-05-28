from setuptools import setup, find_packages
from bespin import VERSION

setup(
      name = "bespin"
    , version = VERSION
    , packages = ['bespin'] + ['bespin.%s' % pkg for pkg in find_packages('bespin')]
    , include_package_data = True

    , install_requires =
      [ "delfick_app==0.7.3"
      , "option_merge==1.0"
      , "input_algorithms==0.4.5.4"

      , "six"
      , "pytz"
      , "slacker"
      , "humanize"
      , "argparse"
      , "requests"
      , "paramiko==1.16.0"

      , "radssh==1.0.5"
      , "pyrelic==0.8.0"
      , "boto==2.40.0"
      , "boto3==1.2.3"
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
    , url = "https://github.com/delfick/bespin"
    , author = "Stephen Moore"
    , author_email = "delfick755@gmail.com"
    , description = "Opinionated wrapper around boto that reads yaml"
    , license = "MIT"
    , keywords = "cloudformation boto"
    )

