"""Парсери скраперів без мережі: Djinni (компанія з og:title), email-листи, LinkedIn."""
import re

from scrapers import REGISTRY
from scrapers.djinni import _feed_urls, company_from_og_title
from scrapers.dou import _list_urls
from scrapers.email_common import parse_jobs_from_html
from scrapers.linkedin_email import parse_linkedin_jobs


# ---------------------------------------------------------------- контракт

def test_every_scraper_accepts_queries_and_params():
    for name, module in REGISTRY.items():
        params = module.search.__code__.co_varnames[:module.search.__code__.co_argcount]
        assert params == ("queries", "params"), name


# ---------------------------------------------------------------- Djinni

def test_djinni_company_from_og_title():
    assert company_from_og_title("iOS Engineer Senior (Driver Team) в Uklon – Djinni",
                                 "iOS Engineer Senior (Driver Team)") == "Uklon"
    assert company_from_og_title("Junior AI Engineer at PwC Lviv SDC - Djinni") == "PwC Lviv SDC"
    assert company_from_og_title("", "x") == ""


def test_djinni_company_when_title_itself_contains_v():
    # " в " усередині посади не повинно розбити рядок у неправильному місці
    og = "Розробник в команду продукту в Acme – Djinni"
    assert company_from_og_title(og, "Розробник в команду продукту") == "Acme"


def test_djinni_one_request_per_exp_level():
    urls = _feed_urls({"primary_keyword": "iOS", "exp_level": ["3y", "5y"]})
    assert urls == [
        "https://djinni.co/jobs/rss/?primary_keyword=iOS&exp_level=3y",
        "https://djinni.co/jobs/rss/?primary_keyword=iOS&exp_level=5y",
    ]
    assert _feed_urls({}) == ["https://djinni.co/jobs/rss/"]


# ---------------------------------------------------------------- DOU

def test_dou_category_replaces_query_search():
    urls = _list_urls(["iOS Developer"], {"category": "iOS/macOS", "exp": ["3-5", "5plus"]})
    assert len(urls) == 2
    assert all("category=iOS%2FmacOS" in u and "remote=" in u for u in urls)
    assert "exp=5plus" in urls[1]


def test_dou_without_category_searches_each_query():
    urls = _list_urls(["A", "B"], {"exp": "0-1"})
    assert len(urls) == 2 and "search=A" in urls[0] and "exp=0-1" in urls[0]


# ---------------------------------------------------------------- email (Work.ua / Robota.ua)

def test_parse_jobs_from_html_canonicalises_and_dedups_links():
    html = """
    <a href="https://www.work.ua/jobs/111/?utm_source=alert">Junior AI Engineer</a>
    <a href="https://www.work.ua/jobs/111/?utm_source=alert&pos=2">Junior AI Engineer</a>
    <a href="https://www.work.ua/jobs/222/">iOS Developer</a>
    <a href="https://www.work.ua/">Work.ua</a>
    <a href="https://www.work.ua/jobs/333/">..</a>
    """
    jobs = parse_jobs_from_html(html, re.compile(r"/jobs/(\d+)"), "Work.ua")
    assert [(j["title"], j["url"]) for j in jobs] == [
        ("Junior AI Engineer", "https://www.work.ua/jobs/111"),
        ("iOS Developer", "https://www.work.ua/jobs/222"),
    ]
    assert all(j["company"] == "" and j["source"] == "Work.ua" for j in jobs)


# ---------------------------------------------------------------- LinkedIn

LINKEDIN_HTML = """
<table><tr><td>
  <a href="https://www.linkedin.com/comm/jobs/view/4001234567/?trkEmail=abc"><img alt=""></a>
  <a href="https://www.linkedin.com/comm/jobs/view/4001234567/?trkEmail=abc">Junior AI Engineer</a>
  <p>Acme Corp · Kyiv, Ukraine (Remote)</p>
  <a href="https://www.linkedin.com/comm/jobs/view/4001234567/?trkEmail=xyz">View job</a>
</td></tr><tr><td>
  <a href="https://www.linkedin.com/jobs/view/senior-ios-developer-4009999999?x=1">Senior iOS Developer</a>
  <p>Beta LLC · Remote</p>
</td></tr></table>
"""


def test_parse_linkedin_jobs_one_entry_per_job_id_with_company():
    jobs = parse_linkedin_jobs(LINKEDIN_HTML, None, "LinkedIn")
    assert [(j["title"], j["company"], j["url"]) for j in jobs] == [
        ("Junior AI Engineer", "Acme Corp", "https://www.linkedin.com/jobs/view/4001234567/"),
        ("Senior iOS Developer", "Beta LLC", "https://www.linkedin.com/jobs/view/4009999999/"),
    ]
