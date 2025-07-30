# nummus-financial

[![Unit Test][unittest-image]][unittest-url] [![Static Analysis][static-analysis-image]][static-analysis-url] [![Coverage][coverage-image]][coverage-url] [![Latest Version][pypi-image]][pypi-url]

A personal financial information aggregator and planning tool. Collects and categorizes transactions, manages budgets, tracks investments, calculates net worth, and predicts future performance.

---

## Environment

List of dependencies for package to run.

### Required

- nummus python modules
  - sqlalchemy
  - gevent
  - colorama
  - rapidfuzz
  - flask
  - flask-assets
  - flask-login
  - pdfplumber
  - yfinance
  - pyspellchecker
  - tqdm
  - argcomplete
  - scipy
  - emoji
  - werkzeug
  - prometheus-flask-exporter
  - packaging
  - gunicorn

### Optional

- Encryption extension to encrypt database file. Does not encrypt SSL or importers folders
  - sqlcipher3-binary
  - Cipher
  - pycryptodome

---

## Installation / Build / Deployment

Install module

```bash
> python -m pip install .
> # For autocomplete, activate completion hook
> activate-global-python-argcomplete
```

Install module with encryption

```bash
> python -m pip install .[encrypt]
```

For development, install as a link to repository such that code changes are used. It is recommended to install pre-commit hooks

```bash
> python -m pip install -e .[dev]
> pre-commit install
```

---

## Usage

Run `create` command to make a new portfolio. Then start a web server using flask.

```bash
> nummus create
> flask --app nummus.web run
```

---

## Docker

A better way to use nummus is hosting the web server on in a docker instance.

```bash
> docker run \
  --name nummus \
  --detach \
  --publish 8000:8000 \
  --publish 8001:8001 \
  --volume nummus-data:/data \
  nummus-financial
```

### Configuration

The following environment variables are used to configure the instance.

| Env                | Default              | Description                                                                      |
| ------------------ | -------------------- | -------------------------------------------------------------------------------- |
| `NUMMUS_PORTFOLIO` | `/data/portfolio.db` | Path to portfolio inside `data` volume.                                          |
| `NUMMUS_KEY_PATH`  | `/data/.key.secret`  | File containing portfolio key for encryption                                     |
| `NUMMUS_WEB_KEY`   | `nummus-admin`       | Web key used when creating a new portfolio                                       |
| `WEB_PORT`         | `8000`               | Port to bind server to                                                           |
| `WEB_PORT_METRICS` | `8001`               | Port to bind metrics server to                                                   |
| `WEB_CONCURRENCY`  | n(CPU) \* 2 + 1      | Number of gunicorn workers to spawn                                              |
| `WEB_N_THREADS`    | `1`                  | Number of gunicorn workers threads to spawn                                      |
| `WEB_TIMEOUT`      | `30`                 | Gunicorn workers silent for more than this many seconds are killed and restarted |

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

- `ruff` for Python
- `pyright` for Python type analysis
- `djlint` for Jinja HTML templates
- `codespell` for all files

Formatters

- `isort` for Python import order
- `black` for Python
- `prettier` for Jinja HTML templates, CSS, and JS
- `taplo` for TOML

### Tools

- `formatters.sh` will run every formatter
- `linters.sh` will run every linter
- `make_test_portfolio.py` will create a portfolio with pseudorandom data
- `run_tailwindcss.sh` will run tailwindcss with proper arguments

---

## Configuration

Most configuration is made per portfolio via the web interface

There is a global config file for common user options, found at `~/.nummus/.config.ini`. Defaults are:

```ini
[nummus]
secure-icon = ⚿ # Icon to print on secure CLI prompts such as unlocking password
```

---

## Versioning

Versioning of this projects adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) and is implemented using git tags.

[pypi-image]: https://img.shields.io/pypi/v/nummus-financial.svg
[pypi-url]: https://pypi.org/project/nummus-financial/
[unittest-image]: https://github.com/WattsUp/nummus/actions/workflows/test.yml/badge.svg
[unittest-url]: https://github.com/WattsUp/nummus/actions/workflows/test.yml
[static-analysis-image]: https://github.com/WattsUp/nummus/actions/workflows/static-analysis.yml/badge.svg
[static-analysis-url]: https://github.com/WattsUp/nummus/actions/workflows/static-analysis.yml
[coverage-image]: https://gist.githubusercontent.com/WattsUp/36d9705addcd44fb0fccec1d23dc1338/raw/nummus__heads_master.svg
[coverage-url]: https://github.com/WattsUp/nummus/actions/workflows/coverage.yml
