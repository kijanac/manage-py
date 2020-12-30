============================
Manage.py Development Script
============================

-----------
Usage Guide
-----------

#. Download manage.py
#. Run “python manage.py setup ENV_NAME” to create a new conda development environment with name ENV_NAME
#. Run “conda activate ENV_NAME” to activate your development environment
#. If starting from scratch:
    #. Create a new directory for your project and enter that directory on the command line
    #. Run “python manage.py init REPO HOMEPAGE README CONDA_SUB” to create a pyproject.toml file, where:
        * REPO is a link to the repository for this project (e.g. https://github.com/<username>/<project_name>)
        * HOMEPAGE is a link to the homepage for this project [default: REPO]
        * README is the name of the readme file to be used by this project [default: README.rst]
        * CONDA_SUB is a dictionary of substitutions for poetry2conda to translate pip dependencies into conda dependencies. For example, if your project has PyTorch as a dependency (named as “torch” on PyPI and “pytorch” on the conda channel “pytorch”) you should use ‘{“torch”: {“name”: “pytorch”, “channel”: “pytorch”}}’ for CONDA_SUB.  [default: {}]
#. git pull
#. git checkout -b <branch-name>
#. Make changes to code.
#. python manage.py lint (lint code)
#. python manage.py install (install code locally)
#. python manage.py test (run tests)
#. python manage.py clean (clean up project directory)
#. Add and commit the relevant files to git.
    #. git add <file name>
    #. git commit -m “<commit_type>: <comment>”, where <comment> should be written in a way that makes sense as a changelog entry. Possible git comment types (from Udacity Nanodegree Style Guide):
        * feat: a new feature
        * fix: a bug fix
        * docs: changes to documentation
        * style: formatting, missing semicolons, etc; no code change
        * refactor: refactoring production code
        * test: adding tests, refactoring test; no production code change
        * chore: updating build tasks, package manager configs, etc; no production code change
#. python manage.py release <release_type> <remote> (release code)