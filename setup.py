from setuptools import setup, find_packages
from bespin import VERSION

setup(
      name = "bespin"
    , version = VERSION
    , packages = ['bespin'] + ['bespin.%s' % pkg for pkg in find_packages('bespin')]
    , include_package_data = True

    , install_requires =
      [ "delfick_error==1.6.1"
      , "option_merge==0.9.1"
      , "input_algorithms==0.4.3.1"

      , "six"
      , "pytz"
      , "humanize"
      , "argparse"
      , "requests"

      , "radssh==1.0.1"
      , "boto==2.34.0"
      , "pyYaml==3.10"
      , "rainbow_logging_handler==2.2.2"
      , "FileChunkIO==1.6"
      ]

    , extras_require =
      { "tests":
        [ "noseOfYeti>=1.5.0"
        , "nose"
        , "mock"
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

