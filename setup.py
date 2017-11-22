from setuptools import setup, find_packages
from bespin import VERSION

setup(
      name = "bespin"
    , version = VERSION
    , packages = ['bespin'] + ['bespin.%s' % pkg for pkg in find_packages('bespin')]
    , include_package_data = True

    , install_requires =
      [ "delfick_app==0.9.5"
      , "option_merge==1.5"
      , "input_algorithms==0.5.9"

      , "six"
      , "pytz"
      , "slacker"
      , "humanize"
      , "argparse"
      , "requests"
      , "paramiko"

      , "radssh==1.1.1"
      , "pyrelic==0.8.0"
      , "boto==2.40.0"
      , "boto3==1.4.7"
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
        , "moto==1.1.25"
        , "coverage"

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
    , classifiers=
      [
        "Environment :: Console"
      , "Intended Audience :: Developers"
      , "Intended Audience :: Information Technology"
      , "Intended Audience :: System Administrators"
      , "License :: OSI Approved :: MIT License"
      , "Natural Language :: English"
      , "Operating System :: MacOS :: MacOS X"
      , "Operating System :: POSIX"
      , "Operating System :: POSIX :: Linux"
      , "Programming Language :: Python"
      , "Programming Language :: Python :: 2"
      , "Programming Language :: Python :: 2.7"
      , "Programming Language :: Python :: 3"
      , "Programming Language :: Python :: 3.5"
      , "Programming Language :: Python :: 3.6"
      ]
    )

