# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# http://www.sphinx-doc.org/en/master/config

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import sys
# sys.path.insert(0, os.path.abspath('.'))

import os
import shutil
import datetime
from glob import glob
import subprocess

DOCS_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
TOP_DIRECTORY = os.path.dirname(DOCS_DIRECTORY)


year = datetime.date.today().year

# -- Project information -----------------------------------------------------

project = 'Koji Ansible collection'
author = 'Ken Dreyer'
version = ''

html_short_title = 'Koji Ansible Collection Documentation'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = ['sphinx.ext.autodoc', 'sphinx_antsibull_ext']

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []

pygments_style = 'ansible'

highlight_language = 'YAML+Jinja'

# Substitutions, variables, entities, & shortcuts for text which do not need to link to anything.
# For titles which should be a link, use the intersphinx anchors set at the index, chapter, and section levels, such as  qi_start_:
# |br| is useful for formatting fields inside of tables
# |_| is a nonbreaking space; similarly useful inside of tables
rst_epilog = """
.. |br| raw:: html

   <br>
.. |_| unicode:: 0xA0
    :trim:
"""


html_theme = 'sphinx_rtd_theme'
html_show_sphinx = False
html_show_copyright = False

display_version = False

html_theme_options = {
}

html_use_smartypants = True
html_use_modindex = False
html_use_index = False
html_copy_source = False

intersphinx_mapping = {
    'python3': ('https://docs.python.org/3/', (None, '../python3.inv')),
    'jinja2': ('http://jinja.palletsprojects.com/', (None, '../jinja2.inv')),
    'ansible_4': ('https://docs.ansible.com/ansible/4/', (None, '../ansible_4.inv')),
}

linkcheck_workers = 25
# linkcheck_anchors = False

# local debugging:
html_context = {
    'display_github': True,
    'conf_py_path': '/docs/',
    'github_user': 'ktdreyer',
    'github_repo': 'koji-ansible',
    'github_version': 'local',
}


def install_collection(app):
    """Install collection for antsibull-doc to find
    """
    if 'READTHEDOCS' in os.environ:
        # RTD uses shallow clones, which throws off the version calculation.
        subprocess.check_call(['git', 'fetch', '--unshallow'])
    subprocess.check_call([TOP_DIRECTORY + '/build-collection'])
    tarball = glob(TOP_DIRECTORY + '/_build/*.tar.gz')[0]
    subprocess.check_call([
        'ansible-galaxy', 'collection', 'install', '--force', tarball])


def antsibull_collection(app):
    """Render the module docs as rst"""
    rst_files = glob(DOCS_DIRECTORY + '/*.rst')
    for file in rst_files:
        os.remove(file)
    os.chmod(DOCS_DIRECTORY, 0o700)
    subprocess.check_call([
        'antsibull-docs',
        'collection',
        '--use-current',
        '--squash-hierarchy',
        '--dest-dir', DOCS_DIRECTORY,
        '--no-indexes',
        'ktdreyer.koji_ansible',
    ])

    # shutil.copy2(DOCS_DIRECTORY + '/index/index.rst',
    #              DOCS_DIRECTORY + 'index.rst')


def setup(app):
    # Note the env var for collections in a non-standard directory is
    # "COLLECTIONS_PATHS". Not sure if antsibull-doc respects that, though.
    app.connect('builder-inited', install_collection)
    app.connect('builder-inited', antsibull_collection)

    # Use sphinx_substitution_extensions instead?
