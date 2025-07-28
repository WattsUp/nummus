from __future__ import annotations

import datetime
import re
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import flask
import pytest

import nummus
from nummus import controllers
from nummus import exceptions as exc
from nummus import utils
from nummus.controllers import base
from nummus.models import Account, Asset, AssetValuation, TransactionCategoryGroup
from tests import conftest

if TYPE_CHECKING:
    from collections.abc import Callable

    import werkzeug.test
    from sqlalchemy import orm

    from tests.conftest import RandomStringGenerator
    from tests.controllers.conftest import HTMLValidator, WebClient


def test_find(session: orm.Session, account: Account) -> None:
    assert base.find(session, Account, account.uri) == account


def test_find_404(session: orm.Session) -> None:
    with pytest.raises(exc.http.NotFound):
        base.find(session, Account, Account.id_to_uri(0))


def test_find_400(session: orm.Session) -> None:
    with pytest.raises(exc.http.BadRequest):
        base.find(session, Account, "fake")


@pytest.mark.parametrize(
    ("period", "months"),
    [
        ("1m", -1),
        ("6m", -6),
        ("1yr", -12),
        ("max", None),
    ],
)
def test_parse_period(today: datetime.date, period: str, months: int | None) -> None:
    start = None if months is None else utils.date_add_months(today, months)
    assert base.parse_period(period) == (start, today)


def test_parse_period_ytd(today: datetime.date) -> None:
    start = datetime.date(today.year, 1, 1)
    assert base.parse_period("ytd") == (start, today)


def test_parse_period_400() -> None:
    with pytest.raises(exc.http.BadRequest):
        base.parse_period("")


def test_date_labels_days(today: datetime.date) -> None:
    start = today - datetime.timedelta(days=utils.DAYS_IN_WEEK)
    result = base.date_labels(start.toordinal(), today.toordinal())
    assert result.labels[0] == start.isoformat()
    assert result.labels[-1] == today.isoformat()
    assert result.mode == "days"


@pytest.mark.parametrize(
    ("months", "mode"),
    [
        (-1, "weeks"),
        (-3, "months"),
        (-24, "years"),
    ],
)
def test_date_labels(today: datetime.date, months: int, mode: str) -> None:
    start = utils.date_add_months(today, months)
    result = base.date_labels(start.toordinal(), today.toordinal())
    assert result.labels[0] == start.isoformat()
    assert result.labels[-1] == today.isoformat()
    assert result.mode == mode


def test_ctx_to_json() -> None:
    ctx: dict[str, object] = {"number": Decimal("1234.1234")}
    assert base.ctx_to_json(ctx) == '{"number":1234.12}'


def test_ctx_to_json_unknown_type() -> None:
    class Fake:
        pass

    with pytest.raises(TypeError):
        base.ctx_to_json({"fake": Fake()})


@pytest.mark.parametrize(
    "func",
    [
        base.validate_string,
        base.validate_real,
        base.validate_int,
        base.validate_date,
    ],
    ids=conftest.id_func,
)
def test_validate_required(func: Callable) -> None:
    assert func("", is_required=True) == "Required"


@pytest.mark.parametrize("s", ["", "abc"])
def test_validate_string(s: str) -> None:
    assert not base.validate_string(s)


def test_validate_string_short() -> None:
    assert base.validate_string("a", check_length=True) == "2 characters required"


def test_validate_string_no_session() -> None:
    with pytest.raises(TypeError):
        base.validate_string("abc", no_duplicates=Account.name)


def test_validate_string_duplicate(session: orm.Session, account: Account) -> None:
    err = base.validate_string(
        account.name,
        session=session,
        no_duplicates=Account.name,
    )
    assert err == "Must be unique"


def test_validate_string_duplicate_self(session: orm.Session, account: Account) -> None:
    err = base.validate_string(
        account.name,
        session=session,
        no_duplicates=Account.name,
        no_duplicate_wheres=[Account.id_ != account.id_],
    )
    assert not err


@pytest.mark.parametrize("s", ["", "2025-01-01"])
@pytest.mark.parametrize("max_future", [7, 0, None])
def test_validate_date(s: str, max_future: int | None) -> None:
    assert not base.validate_date(s, max_future=max_future)


@pytest.mark.parametrize(
    "func",
    [
        base.validate_real,
        base.validate_int,
        base.validate_date,
    ],
    ids=conftest.id_func,
)
def test_validate_unable_to_parse(func: Callable) -> None:
    assert func("a") == "Unable to parse"


@pytest.mark.parametrize(
    ("max_future", "target"),
    [
        (7, "Only up to 7 days in advance"),
        (0, "Cannot be in advance"),
        (None, ""),
    ],
)
def test_validate_date_future(max_future: int | None, target: str) -> None:
    assert base.validate_date("2190-01-01", max_future=max_future) == target


@pytest.mark.parametrize(
    ("s", "max_future", "target"),
    [
        ("a", 7, "Unable to parse"),
        ("", 7, "Date must not be empty"),
        ("2190-01-01", 7, "Only up to 7 days in advance"),
        ("2190-01-01", 0, "Cannot be in advance"),
        ("2190-01-01", None, None),
        ("2000-01-01", 7, None),
        ("2000-01-01", 0, None),
    ],
)
def test_parse_date(s: str, max_future: int | None, target: str | None) -> None:
    if target:
        with pytest.raises(ValueError, match=target):
            base.parse_date(s, max_future=max_future)
    else:
        date = base.parse_date(s, max_future=max_future)
        assert isinstance(date, datetime.date)


def test_validate_date_duplicate(
    session: orm.Session,
    asset_valuation: AssetValuation,
) -> None:
    err = base.validate_date(
        asset_valuation.date.isoformat(),
        session=session,
        no_duplicates=AssetValuation.date_ord,
    )
    assert err == "Must be unique"


@pytest.mark.parametrize("s", ["0.1", "1.0", "-1*(-2)"])
@pytest.mark.parametrize("is_positive", [True, False])
def test_validate_real(s: str, is_positive: bool) -> None:
    assert not base.validate_real(s, is_positive=is_positive)


@pytest.mark.parametrize("s", ["0", "-1.0", "-1*2"])
def test_validate_real_not_positive(s: str) -> None:
    assert base.validate_real(s, is_positive=True) == "Must be positive"


@pytest.mark.parametrize("is_positive", [True, False])
def test_validate_int(is_positive: bool) -> None:
    assert not base.validate_int("1", is_positive=is_positive)


@pytest.mark.parametrize("s", ["0", "-1"])
def test_validate_int_not_positive(s: str) -> None:
    assert base.validate_int(s, is_positive=True) == "Must be positive"


def test_ctx_base() -> None:
    base.PAGES.clear()
    base.TEMPLATES.clear()
    templates = Path(nummus.__file__).with_name("templates")

    ctx = base.ctx_base(templates, is_encrypted=False, debug=True)

    assert isinstance(ctx["nav_items"], list)
    for group in ctx["nav_items"]:
        assert isinstance(group, base.PageGroup)
        assert group.pages
        for name, p in group.pages.items():
            assert isinstance(p, base.Page)
            assert p
            assert name == name.capitalize()

    assert isinstance(ctx["icons"], str)
    assert ctx["icons"].count(",") > 50

    assert base.PAGES
    assert base.TEMPLATES


def test_dialog_swap_empty(
    flask_app: flask.Flask,
    valid_html: HTMLValidator,
) -> None:
    with flask_app.app_context():
        response = base.dialog_swap()

    data: bytes = response.data
    html = valid_html.clean(data.decode())
    assert valid_html(html)
    assert "snackbar" not in html
    assert "HX-Trigger" not in response.headers


def test_dialog_swap(
    flask_app: flask.Flask,
    valid_html: HTMLValidator,
    rand_str_generator: RandomStringGenerator,
) -> None:
    content = rand_str_generator()
    event = rand_str_generator()
    snackbar = rand_str_generator()

    with flask_app.app_context():
        response = base.dialog_swap(content, event, snackbar)

    data: bytes = response.data
    html = valid_html.clean(data.decode())
    assert valid_html(html)
    assert content in html
    assert "snackbar" in html
    assert snackbar in html
    assert response.headers["HX-Trigger"] == event


def test_error_str(
    valid_html: HTMLValidator,
    rand_str: str,
) -> None:
    html = base.error(rand_str)
    assert valid_html(html)
    assert rand_str in html


def test_error_empty_field(
    session: orm.Session,
    valid_html: HTMLValidator,
) -> None:
    session.add(Account())
    try:
        session.commit()
    except exc.IntegrityError as e:
        html = base.error(e)
        assert valid_html(html)
        assert "Account name must not be empty" in html
    else:
        pytest.fail("did not create exception to test with")


def test_error_unique(
    session: orm.Session,
    account: Account,
    valid_html: HTMLValidator,
) -> None:
    new_account = Account(
        name=account.name,
        institution=account.institution,
        category=account.category,
        closed=False,
        budgeted=False,
    )
    session.add(new_account)
    try:
        session.commit()
    except exc.IntegrityError as e:
        html = base.error(e)
        assert valid_html(html)
        assert "Account name must be unique" in html
    else:
        pytest.fail("did not create exception to test with")


def test_error_check(
    session: orm.Session,
    account: Account,
    valid_html: HTMLValidator,
) -> None:
    _ = account
    try:
        session.query(Account).update({"name": "a"})
    except exc.IntegrityError as e:
        html = base.error(e)
        assert valid_html(html)
        assert "Name must be at least 2 characters long" in html
    else:
        pytest.fail("did not create exception to test with")


def test_page(web_client: WebClient) -> None:
    result, headers = web_client.GET("common.page_dashboard", headers={})
    assert "<title>" in result
    assert "<html" in result
    assert "HX-Request" in headers["Vary"]


def test_page_hx(web_client: WebClient) -> None:
    result, headers = web_client.GET("common.page_dashboard")
    assert "<title>" in result
    assert "<html" not in result
    assert "HX-Request" in headers["Vary"]


def test_add_routes() -> None:
    app = flask.Flask(__file__)
    app.debug = False
    controllers.add_routes(app)

    routes = app.url_map
    for rule in routes.iter_rules():
        assert not rule.endpoint.startswith("nummus.controllers.")
        assert not rule.endpoint.startswith(".")
        assert rule.rule.startswith("/")
        assert not rule.rule.startswith("/d/")
        assert not (rule.rule != "/" and rule.rule.endswith("/"))


def test_metrics(web_client: WebClient, asset: Asset) -> None:
    # Visit account page
    web_client.GET(("assets.page", {"uri": asset.uri}))
    web_client.GET("assets.page_all")

    result, _ = web_client.GET(
        "prometheus_metrics",
        content_type="text/plain; version=0.0.4; charset=utf-8",
    )
    if isinstance(result, bytes):
        result = result.decode()
    assert "flask_exporter_info" in result
    assert "nummus_info" in result
    assert "flask_http_request_duration_seconds_count" in result
    assert 'endpoint="assets.page"' in result
    assert 'endpoint="assets.page_all"' in result


@pytest.mark.xfail
def test_follow_links(web_client: WebClient) -> None:
    # Recursively click on every link checking that it is a valid link and valid
    # method
    visited: set[str] = set()

    # Save hx-delete for the end in case it does successfully delete something
    deletes: set[str] = set()

    def visit_all_links(url: str, method: str, *, hx: bool = False) -> None:
        request = f"{method} {url}"
        if request in visited:
            return
        visited.add(request)
        response: werkzeug.test.TestResponse | None = None
        try:
            data: dict[str, str] | None = None
            if method in {"POST", "PUT", "DELETE"}:
                data = {
                    "name": "",
                    "institution": "",
                    "number": "",
                }
            response = web_client.raw_open(
                url,
                method=method,
                buffered=False,
                follow_redirects=False,
                headers={"HX-Request": "true"} if hx else None,
                data=data,
            )
            page = response.text
            assert response.status_code == base.HTTP_CODE_OK
            assert response.content_type == "text/html; charset=utf-8"

        finally:
            if response is not None:
                response.close()
        hrefs = list(re.findall(r'href="([\w\d/\-]+)"', page))
        hx_gets = list(re.findall(r'hx-get="([\w\d/\-]+)"', page))
        hx_puts = list(re.findall(r'hx-put="([\w\d/\-]+)"', page))
        hx_posts = list(re.findall(r'hx-post="([\w\d/\-]+)"', page))
        hx_deletes = list(re.findall(r'hx-delete="([\w\d/\-]+)"', page))
        page = ""  # Clear page so --locals isn't too noisy

        for link in hrefs:
            visit_all_links(link, "GET")
        # With hx requests, add HX-Request header
        for link in hx_gets:
            visit_all_links(link, "GET", hx=True)
        for link in hx_puts:
            visit_all_links(link, "PUT", hx=True)
        for link in hx_posts:
            visit_all_links(link, "POST", hx=True)
        deletes.update(hx_deletes)

    visit_all_links("/", "GET")
    for link in deletes:
        visit_all_links(link, "DELETE", hx=True)


def test_change_redirect_no_changes() -> None:
    resp = flask.Response()
    result = base.change_redirect_to_htmx(resp)
    assert "HX-Redirect" not in result.headers


def test_change_redirect(web_client: WebClient) -> None:
    _, headers = web_client.GET("redirect")
    assert headers["HX-Redirect"] == "/"


def test_change_redirect_no_htmx(web_client: WebClient) -> None:
    _, headers = web_client.GET("redirect", headers={}, rc=base.HTTP_CODE_REDIRECT)
    assert "HX-Redirect" not in headers


def test_tranaction_category_groups(
    session: orm.Session,
    categories: dict[str, int],
) -> None:
    groups = base.tranaction_category_groups(session)
    assert len(groups) == len(TransactionCategoryGroup)
    assert sum(len(group) for group in groups.values()) == len(categories)


@pytest.mark.parametrize(
    "path",
    sorted(Path(nummus.__file__).with_name("templates").glob("**/*.jinja")),
    ids=conftest.id_func,
)
def test_template(valid_html: HTMLValidator, path: Path) -> None:
    with path.open("r", encoding="utf-8") as file:
        buf = file.read()

    re_jinja = re.compile(r"(\{[{%#]).+?([#%}]\})")
    buf = valid_html.clean(re_jinja.sub("", buf))
    # Since each template is tested, it ensures any HX actions require local targets
    assert valid_html(buf)
