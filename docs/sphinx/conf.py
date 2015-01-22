"""
    Options for sphinx
    Add project specific options to conf.py in the root folder
"""
import sys, os
import sphinx_rtd_theme

this_dir = os.path.abspath(os.path.dirname(__file__))

extensions = []

html_theme = 'sphinx_rtd_theme'
html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

exclude_patterns = []

master_doc = 'index'
source_suffix = '.rst'

pygments_style = 'pastie'

# Add options specific to this project
execfile(os.path.join(this_dir, '../conf.py'), globals(), locals())
