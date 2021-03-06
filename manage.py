import argparse
import datetime
import pathlib
import re
import subprocess
import tempfile

channels = ["conda-forge"]
dev_packages_conda = [
    "anaconda-client",
    "cmake",
    "codecov",
    "conda-build",
    "conda-verify",
    "git",
    # "latexmk",
    "make",
    "poetry",
    "sphinx",
    "sphinx-autodoc-typehints",
]
dev_packages_py = [
    "black",
    "flake8",
    "poetry2conda",
    "ruamel.yaml",
    "sphinx-rtd-theme",
    "toml",
]
test_packages_py = ["pytest", "pytest-cov"]

# HELPER FUNCTIONS


def _parse_pyproject():
    import toml

    with open(pathlib.Path("pyproject.toml"), "r") as f:
        return toml.load(f)


def _write_pyproject(d, name="pyproject.toml"):
    import toml

    with open(pathlib.Path(name), "w") as f:
        toml.dump(d, f)


def _interleave(s, args):
    return [val for a in args for val in (s, a)]


def _hash_tarball(tarball_path):
    import hashlib

    m = hashlib.sha256()
    with open(tarball_path, "rb") as f:
        while True:
            data = f.read(65536)
            if not data:
                break
            m.update(data)

    return m.hexdigest()


def _remove_paths(*paths):
    for p in paths:
        if p.is_file():
            p.unlink()
        else:
            _remove_paths(*p.glob("*"))

        try:
            p.rmdir()
        except FileNotFoundError:
            continue


def _changelog_helper(tag, repo, previous_tag=None):
    if previous_tag is None:
        return []

    version_header = (
        "`Version "
        + tag[1:]
        + " <"
        + repo
        + "/compare/"
        + previous_tag
        + "..."
        + tag
        + ">`__"
    )
    gitlog = subprocess.check_output(
        [
            "git",
            "log",
            previous_tag + "..." + tag,
            "--pretty=* %s (`%h <" + repo + "/commit/%H>`__)",
            "--no-merges",
        ],
        text=True,
    )

    lines = []
    lines.append(version_header)
    lines.append("-" * len(version_header) + "\n")
    lines.extend(
        [line for line in gitlog.splitlines() if re.search(r"feat:|fix:", line)]
    )
    lines.append("\n")

    return lines


def _conda_dependencies(toml_file):
    import ruamel.yaml

    s = subprocess.check_output(["poetry2conda", toml_file, "-"])
    return ruamel.yaml.YAML(typ="safe").load(s)["dependencies"]


# COMMAND LINE FUNCTIONS


def setup(name, version):
    subprocess.run(
        ["conda", "create", "-n", name, "python=" + version]
        + dev_packages_conda
        + _interleave("-c", channels)
        + ["-y"]
    )


def init(repo=None, homepage=None, conda_sub={}, readme="README.rst"):
    # INTERACTIVE POETRY INIT
    subprocess.run(["poetry", "init"])

    subprocess.run(["poetry", "add", "--dev"] + dev_packages_py + test_packages_py)

    # MANUALLY MODIFY PYPROJECT.TOML

    d = _parse_pyproject()

    # WRITE POETRY OPTIONAL ENTRIES

    d["tool"]["poetry"]["readme"] = readme

    if repo is not None:
        d["tool"]["poetry"]["repository"] = repo

    if homepage is not None:
        d["tool"]["poetry"]["homepage"] = homepage
    elif repo is not None:
        d["tool"]["poetry"]["repository"]

    # WRITE PYTEST CONFIG

    d["tool"]["pytest"] = dict(
        ini_options=dict(
            minversion=6.0, addopts="-x -v --cov --cov-report=xml", testpaths="tests"
        )
    )

    # WRITE POETRY2CONDA CONFIG

    d["tool"]["poetry2conda"] = dict(name=d["tool"]["poetry"]["name"])
    d["tool"]["poetry2conda"]["dependencies"] = conda_sub

    _write_pyproject(d)

    init_conda()

    init_doc()


def init_conda():
    pathlib.Path("conda").mkdir(exist_ok=True)
    with open(pathlib.Path("conda", "meta.yaml"), "w") as f:
        f.write(meta_yaml)


def init_doc():
    pathlib.Path("sphinx-templates").mkdir(exist_ok=True)
    with open(pathlib.Path("sphinx-templates", "conf.py_t"), "w") as f:
        f.write(conf_template)

    with open(pathlib.Path("sphinx-templates", "master_doc.rst_t"), "w") as f:
        f.write(master_doc_template)

    d = _parse_pyproject()

    # RUN SPHINX-QUICKSTART TO SETUP DOCS FOLDER

    author, *_ = d["tool"]["poetry"]["authors"]
    *author_name, author_email = author.split()
    author_name = " ".join(author_name)

    template_vars = dict(
        module_path=pathlib.Path("src").resolve(),
        name=d["tool"]["poetry"]["name"],
        year=str(datetime.datetime.now().year),
        author="'" + author_name + "'",
        version=d["tool"]["poetry"]["version"],
        release=d["tool"]["poetry"]["version"],
        add_module_names=False,
        html_theme="sphinx_rtd_theme",
        use_napoleon_params=True,
        autoclass_content="both",
    )

    template_params = []
    for k, v in template_vars.items():
        template_params.append("-d")
        template_params.append(k + "=" + str(v))

    extensions = [
        "sphinx.ext.napoleon",
        "sphinx.ext.autodoc",
        "sphinx_autodoc_typehints",
        "sphinx_rtd_theme",
    ]

    subprocess.run(
        [
            "sphinx-quickstart",
            "docs",
            "--sep",
            "-p",
            "luz",
            "-a",
            author_name,
            "-r",
            d["tool"]["poetry"]["version"],
            "-l",
            "en",
            "--extensions",
            ",".join(extensions),
            "-t",
            pathlib.Path("sphinx-templates").resolve(),
            *template_params,
        ]
    )


def doc():
    init_doc()

    d = _parse_pyproject()

    name = d["tool"]["poetry"]["name"]

    subprocess.run(
        [
            "sphinx-apidoc",
            pathlib.Path("src", name).resolve(),
            "-f",
            "-e",
            "-o",
            pathlib.Path("docs", "source").resolve(),
            "-t",
            pathlib.Path("sphinx-templates").resolve(),
        ]
    )

    subprocess.run(["make", "-C", "docs", "clean", "html"])  # , "latexpdf"])

    build_dir = pathlib.Path("docs", "build")

    paths_to_remove = (p for p in pathlib.Path("docs").glob("*") if p != build_dir)

    _remove_paths(*paths_to_remove)

    for p in pathlib.Path("docs", "build", "html").glob("*"):
        p.rename(pathlib.Path("docs").joinpath(p.name))

    paths_to_remove = [
        pathlib.Path("sphinx-templates"),
        build_dir,
        build_dir.joinpath("_sources"),
    ]
    _remove_paths(*paths_to_remove)
    pathlib.Path("docs", ".nojekyll").touch()


def lint():
    paths_to_lint = ["src", "tests", "examples"]
    subprocess.run(["black", *paths_to_lint])
    subprocess.check_call(
        [
            "flake8",
            *paths_to_lint,
            "--max-line-length",
            "88",
            "--extend-ignore",
            "E203,W503",
            "--per-file-ignores",
            "__init__.py:F401,F403",
        ]
    )


def install():
    # INSTALL NON-CONDA DEPENDENCIES

    subprocess.run(["poetry", "install"])

    # INSTALL CONDA DEPENDENCIES

    d = _parse_pyproject()

    if "manage" in d["tool"]:
        import toml

        with tempfile.NamedTemporaryFile(mode="w+", suffix=".toml") as conda_toml:
            # temporarily replace deps with conda deps

            d["tool"]["poetry"]["dependencies"] = d["tool"]["manage"][
                "conda-dependencies"
            ]
            d["tool"]["poetry2conda"]["name"] = ""
            toml.dump(d, conda_toml)
            conda_toml.flush()

            conda_deps = _conda_dependencies(conda_toml.name)
            subprocess.run(["conda", "install", "-y", *conda_deps])


def test(token):
    subprocess.check_call(["pytest"])
    if token is not None:
        subprocess.run(["codecov", "-t", token])


def build(conda, channels):
    subprocess.run(["poetry", "build"])

    if not conda:
        return

    # init_conda()

    import ruamel.yaml

    # READ PYPROJECT.TOML

    d = _parse_pyproject()["tool"]["poetry"]

    # TARBALL PATH

    p = pathlib.Path("dist", d["name"] + "-" + d["version"] + ".tar.gz")

    # RUNTIME DEPENDENCIES

    run_deps = _conda_dependencies("pyproject.toml")

    # AUTHOR INFO

    author, *_ = d["authors"]
    *author_name, author_email = author.split()
    author_name = " ".join(author_name)
    author_email = author_email[1:-1]

    # CONSTRUCT META.YAML

    x = {}
    x["package"] = dict(name=d["name"], version=d["version"])
    x["source"] = dict(url="file://" + str(p.resolve()), sha256=str(_hash_tarball(p)))
    x["build"] = dict(
        number=0,
        noarch="python",
        script="python -m pip install . --no-deps -vv",
    )
    x["requirements"] = dict(run=run_deps)
    x["test"] = dict(requires=test_packages_py)
    x["about"] = dict(
        home=d["homepage"],
        author=author_name,
        author_email=author_email,
        license=d["license"],
        license_file=str(pathlib.Path("LICENSE").resolve()),
    )

    # WRITE META.YAML
    with open("meta.yaml", "w") as f:
        ruamel.yaml.YAML().dump(x, f)

    # RUN CONDA BUILD
    subprocess.run(
        ["conda", "build", str(pathlib.Path(".").resolve())]
        + _interleave("-c", channels)
    )

    # _remove_paths(pathlib.Path("conda"))


def publish(pypi_token, conda_token):
    # READ PYPROJECT.TOML

    d = _parse_pyproject()["tool"]["poetry"]

    if pypi_token is not None:
        subprocess.run(["poetry", "config", "pypi-token.pypi", pypi_token])
        subprocess.run(["poetry", "publish"])
    if conda_token is not None:
        subprocess.run(["anaconda", "--token", conda_token, "upload", d["name"]])


def release(release_type, remote):
    subprocess.check_call(["poetry", "version", release_type])

    # GET VERSION NUMBER

    d = _parse_pyproject()
    repo = str(d["tool"]["poetry"]["repository"])
    version = str(d["tool"]["poetry"]["version"])

    subprocess.run(["git", "add", "pyproject.toml"])
    subprocess.run(["git", "commit", "-m", '"chore: Update version number"'])

    subprocess.run(["git", "tag", "-a", "v" + version, "-m", "'v" + version + "'"])

    # UPDATE CHANGELOG

    first_commit, *_ = subprocess.check_output(
        ["git", "log", "--reverse", "--pretty=%h"], text=True
    ).splitlines()
    tags = (
        [first_commit]
        + subprocess.check_output(["git", "tag", "-l"], text=True).splitlines()
        + ["v" + version]
    )

    changelog = []
    for i in range(1, len(tags)):
        changelog.extend(_changelog_helper(tags[i], repo, tags[i - 1]))

    changelog = "\n".join(changelog)

    with open(pathlib.Path("CHANGELOG.rst"), "w") as f:
        f.write(changelog)

    subprocess.run(["git", "tag", "-d", "v" + version])

    subprocess.run(["git", "add", "CHANGELOG.rst"])
    subprocess.run(["git", "commit", "-m", '"chore: Update changelog"'])

    # UPDATE DOCUMENTATION

    doc()

    subprocess.run(["git", "add", pathlib.Path("docs").resolve()])
    subprocess.run(["git", "commit", "-m", '"docs: Update documentation"'])

    # PUSH MAIN

    subprocess.run(["git", "push", remote, "main"])

    # CREATE AND PUSH TAG

    subprocess.run(["git", "tag", "-a", "v" + version, "-m", "'v" + version + "'"])
    subprocess.run(["git", "push", remote, "v" + version])


def clean(name):
    _remove_paths(
        pathlib.Path("build"),
        pathlib.Path("conda-build"),
        pathlib.Path("docs", "build"),
        pathlib.Path("docs", "source"),
        pathlib.Path("docs", "make.bat"),
        pathlib.Path("docs", "Makefile"),
        pathlib.Path("conda"),
        pathlib.Path("sphinx-templates"),
        pathlib.Path(".pytest_cache"),
        pathlib.Path(".coverage"),
        pathlib.Path("coverage.xml"),
        pathlib.Path("dist"),
        pathlib.Path("meta.yaml"),
        pathlib.Path("poetry.lock"),
        *pathlib.Path("src").glob("*.egg-info"),
        *pathlib.Path(".").glob(".coverage*"),
        *pathlib.Path(".").rglob("__pycache__"),
    )
    if name is not None:
        subprocess.run(["conda", "env", "remove", "-n", name])


# CONDA BUILD META.YAML

meta_yaml = """{% set data = load_setup_py_data(setup_file='../setup.py',from_recipe_dir=True)  %}

package:
  name: {{ data.name }}
  version: {{ data.version }}

source:
  url: https://pypi.io/packages/source/{{ data.name[0] }}/{{ data.name }}/{{ data.name }}-{{ data.version }}.tar.gz
  sha256: {{ environ["PYPI_TARBALL_SHA_256"] }}

build:
  number: 0
  noarch: python
  script: "{{ PYTHON }} -m pip install . --no-deps -vv"

requirements:
  build:
    {% for item in data.extras_require['dev'] %}
    - {{ item }}
    {% endfor %}
  host:
    - python {{ data.python_requires }}
  run:
    - python {{ data.python_requires }}
    {% for item in data.install_requires %}
    - {{ item }}
    {% endfor %}

test:
  requires:
    {% for item in data.tests_require %}
    - {{ item }}
    {% endfor %}

about:
  home: {{ data.url }}
  author: {{ data.author }}
  author_email: {{ data.author_email }}
  license: {{ data.license }}
  license_file: '{{ os.path.join(os.path.dirname(environ["RECIPE_DIR"]),"LICENSE") }}'
  summary: {{ data.description }}
"""

# SPHINX TEMPLATE CONF.PY

conf_template = """# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import sys
sys.path.insert(0, {{ module_path | repr }})

# -- Project information -----------------------------------------------------

project = {{ name | repr }}
copyright = {{ year | repr }}
author = {{ author | repr }}

# The short X.Y version
version = {{ version | repr }}

# The full version, including alpha/beta/rc tags
release = {{ release | repr }}

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
{%- for ext in extensions %}
    '{{ ext }}',
{%- endfor %}
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['{{ dot }}templates']

{% if suffix != '.rst' -%}
# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
# source_suffix = ['.rst', '.md']
source_suffix = {{ suffix | repr }}

{% endif -%}
{% if master != 'index' -%}
# The master toctree document.
master_doc = {{ master | repr }}

{% endif -%}
{% if language -%}
# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = {{ language | repr }}

{% endif -%}
# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = [{{ exclude_patterns }}]

{% if add_module_names %}
add_module_names = {{ add_module_names }}
{% endif -%}
# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = {{ html_theme | repr }}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['{{ dot }}static']
#os.path.abspath(os.path.join('..','docs','source','_static'))
{%- if extensions %}


# -- Extension configuration -------------------------------------------------
{%- endif %}
{%- if 'sphinx.ext.intersphinx' in extensions %}

# -- Options for intersphinx extension ---------------------------------------

# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {'https://docs.python.org/3/': None}
{%- endif %}
{%- if 'sphinx.ext.todo' in extensions %}

# -- Options for todo extension ----------------------------------------------

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = True
{%- endif %}

{%- if 'sphinx.ext.autodoc' in extensions %}

# -- Options for autodoc extension -------------------------------------------

autoclass_content = {{ autoclass_content | repr }}
{%- endif %}

{%- if 'sphinx.ext.napoleon' in extensions %}

# -- Options for napoleon extension ------------------------------------------

use_napoleon_params = {{ use_napoleon_params }}
{%- endif %}
"""

# SPHINX TEMPLATE MASTER_DOC.RST_T

master_doc_template = """.. {{ project }} documentation master file, created by
   sphinx-quickstart on {{ now }}.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to {{ project }}'s documentation!
==========={{ project_underline }}=================

.. toctree::
   :maxdepth: {{ mastertocmaxdepth }}
   :caption: Contents:

   modules

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

"""

if __name__ == "__main__":
    import json

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="subparser")

    setup_parser = subparsers.add_parser("setup")
    setup_parser.add_argument("-n", "--name", type=str)
    setup_parser.add_argument("-v", "--version", type=str, default="3")

    install_parser = subparsers.add_parser("install")

    lint_parser = subparsers.add_parser("lint")

    test_parser = subparsers.add_parser("test")
    test_parser.add_argument("-t", "--token", type=str)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("-c", "--conda", action="store_true")
    build_parser.add_argument("-l", "--channels", nargs="+", type=str)

    clean_parser = subparsers.add_parser("clean")
    clean_parser.add_argument("-n", "--name", type=str)

    release_parser = subparsers.add_parser("release")
    release_parser.add_argument("-t", "--type", type=str)
    release_parser.add_argument("-r", "--remote", type=str, default="origin")

    publish_parser = subparsers.add_parser("publish")
    publish_parser.add_argument("-p", "--pypi-token", type=str)
    publish_parser.add_argument("-c", "--conda-token", type=str)

    # parser.add_argument("pos_args", nargs="*")
    # parser.add_argument("--conda_sub", type=json.loads)
    args = parser.parse_args()

    funcs = dict(
        setup=setup,
        init=init,
        init_doc=init_doc,
        init_conda=init_conda,
        doc=doc,
        lint=lint,
        install=install,
        test=test,
        build=build,
        publish=publish,
        clean=clean,
        release=release,
    )

    kwargs = vars(parser.parse_args())
    funcs[kwargs.pop("subparser")](**kwargs)
