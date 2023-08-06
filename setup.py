"""Setup and install nummus

Typical usage:
  python setup.py develop
  python setup.py install
  python setup.py test
"""

import setuptools

module_folder = "nummus"
module_name = "nummus"

with open("README.md", encoding="utf-8") as file:
  longDescription = file.read()

required = [
    "sqlalchemy>=2", "AutoDict", "connexion==2.14.2", "gevent", "colorama",
    "thefuzz", "python-Levenshtein", "simplejson", "pyopenssl"
]
extras_require = {
    "encrypt": ["sqlcipher3", "Cipher", "pycryptodome"],
    "test": ["coverage", "pylint", "numpy", "swagger-ui-bundle>=0.0.2,<0.1"]
}
extras_require["dev"] = extras_require["test"] + [
    "toml", "witch-ver", "yapf>=0.40.0", "viztracer"
]

setuptools.setup(
    name=module_name,
    use_witch_ver=True,
    description="A personal financial information aggregator and planning tool",
    long_description=longDescription,
    long_description_content_type="text/markdown",
    license="MIT",
    packages=setuptools.find_packages(exclude=["tests", "tests.*"]),
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
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.8",
    # include_package_data=True, # Leave out cause wacky
    zip_safe=False,
    entry_points={"console_scripts": ["nummus=nummus:main"]})
