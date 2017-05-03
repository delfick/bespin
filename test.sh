#!/bin/bash -e
coverage erase
coverage run --branch $(which nosetests) --with-noy "$@"
coverage report
# coverage html
