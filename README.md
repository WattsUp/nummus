# nummus

[![Unit Test][unittest-image]][unittest-url] [![Pylint][pylint-image]][pylint-url] [![Coverage][coverage-image]][coverage-url]

A personal financial information aggregator and planning tool. Collects and categorizes transactions, manages budgets, tracks investments, calculates net worth, and predicts future performance.

---

## Environment

List of dependencies for package to run.

### Required

- nummus python modules
  - sqlalchemy
  - connexion
  - gevent
  - AutoDict

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

For development, install as a link to repository such that code changes are used.

```bash
> python -m pip install -e .[dev]
```

Execute module

```bash
> nummus
```

---

## Usage

By default a website will open to interact with the module. A REST API is available after authentication to fetch data.

---

## Running Tests

Explain how to run the automated tests.

```bash
> python -m tests
```

Coverage report

```bash
> python -m coverage run && python -m coverage report -m
```

---

## Development

Code development of this project adheres to [Google Python Guide](https://google.github.io/styleguide/pyguide.html)

### Styling

Use `yapf` to format files, based on Google's guide with the exception of indents being 2 spaces.

---

## Versioning

Versioning of this projects adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) and is implemented using git tags.

[unittest-image]: https://github.com/WattsUp/nummus/actions/workflows/test.yml/badge.svg
[unittest-url]: https://github.com/WattsUp/nummus/actions/workflows/test.yml
[pylint-image]: https://github.com/WattsUp/nummus/actions/workflows/lint.yml/badge.svg
[pylint-url]: https://github.com/WattsUp/nummus/actions/workflows/lint.yml
[coverage-image]: https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/WattsUp/36d9705addcd44fb0fccec1d23dc1338/raw/nummus__heads_master.json
[coverage-url]: https://github.com/WattsUp/nummus/actions/workflows/coverage.yml
