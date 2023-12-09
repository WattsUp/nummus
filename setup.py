"""Setup and install nummus.

Typical usage:
  python setup.py develop
  python setup.py install
  python setup.py test
"""
from __future__ import annotations

from pathlib import Path

import setuptools

module_folder = "nummus"
module_name = "nummus"

with Path("README.md").open(encoding="utf-8") as file:
    long_description = file.read()

required = [
    "sqlalchemy>=2",
    "AutoDict",
    "gevent",
    "colorama",
    "rapidfuzz",
    "pyopenssl",
    "flask-assets",
    "pytailwindcss",
    "jsmin",
    "flask<2.3,>=2",
    "typing-extensions",
    "pdfplumber",
]
extras_require = {
    "encrypt": ["sqlcipher3", "Cipher", "pycryptodome"],
    "test": ["coverage", "numpy", "time-machine", "tomli"],
}
extras_require["dev"] = extras_require["test"] + [
    "ruff",
    "codespell",
    "witch-ver",
    "black",
    "isort",
    "viztracer",
    "pre-commit",
    "djlint",
]

setuptools.setup(
    name=module_name,
    use_witch_ver=True,
    description="A personal financial information aggregator and planning tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="MIT",
    packages=setuptools.find_packages(include=[module_folder, f"{module_folder}.*"]),
    package_data={module_folder: []},
    install_requires=required,
    extras_require=extras_require,
    test_suite="tests",
    scripts=[],
    author="Bradley Davis",
    author_email="me@bradleydavis.tech",
    url="https://github.com/WattsUp/nummus",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Development Status :: 2 - Pre-Alpha",
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: Financial and Insurance Industry",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Office/Business :: Financial",
        "Topic :: Office/Business :: Financial :: Accounting",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    zip_safe=False,
    entry_points={"console_scripts": ["nummus=nummus.main:main"]},
)
