# nummus

[![Unit Test][unittest-image]][unittest-url] [![Static Analysis][static-analysis-image]][static-analysis-url] [![Coverage][coverage-image]][coverage-url]

A personal financial information aggregator and planning tool. Collects and categorizes transactions, manages budgets, tracks investments, calculates net worth, and predicts future performance.

---

## Environment

List of dependencies for package to run.

### Required

- nummus python modules
  - sqlalchemy
  - AutoDict
  - gevent
  - colorama
  - rapidfuzz
  - cryptography
  - flask-assets
  - pytailwindcss
  - jsmin
  - flask
  - typing-extensions

### Optional

- Encryption extension
  - libsqlcipher-dev
  - sqlcipher3
  - Cipher
  - pycryptodome

---

## Installation / Build / Deployment

Install module

```bash
> python -m pip install .
```

Install module with encryption

```bash
> sudo apt install libsqlcipher-dev
> python -m pip install .[encrypt]
```

For development, install as a link to repository such that code changes are used. It is recommended to install pre-commit hooks

```bash
> python -m pip install -e .[dev]
> pre-commit install
```

---

## Usage

Run `web` command to launch a website to interact with the module.

```bash
> nummus web
```

---

## Running Tests
Does not test front-end at all and minimally tests web controllers. This is out of scope for the foreseeable future.

Unit tests

```bash
> python -m tests
```

Coverage report

```bash
> python -m coverage run && python -m coverage report
```

---

## Development

Code development of this project adheres to [Google Python Guide](https://google.github.io/styleguide/pyguide.html)

Linters
```bash
> ruff .
> djlint .
> codespell .
```

Formatters
```bash
> isort .
> black .
> djlint . --reformat
> clang-format $EACH_JS_FILE
```

### Tools
- `formatters.sh` will run every formatter
- `linters.sh` will run every linter
- `make_test_portfolio.py` will create a portfolio with pseudorandom data
- `profile_web_call.py` will send a request to an endpoint with vizviewer
- `run_tailwindcss.py` will run tailwindcss with proper arguments, add `-w` to watch and rerun on save

---

## Versioning

Versioning of this projects adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) and is implemented using git tags.

[unittest-image]: https://github.com/WattsUp/nummus/actions/workflows/test.yml/badge.svg
[unittest-url]: https://github.com/WattsUp/nummus/actions/workflows/test.yml
[static-analysis-image]: https://github.com/WattsUp/nummus/actions/workflows/static-analysis.yml/badge.svg
[static-analysis-url]: https://github.com/WattsUp/nummus/actions/workflows/static-analysis.yml
[coverage-image]: https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/WattsUp/36d9705addcd44fb0fccec1d23dc1338/raw/nummus__heads_master.json
[coverage-url]: https://github.com/WattsUp/nummus/actions/workflows/coverage.yml
