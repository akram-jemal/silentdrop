import pytest

from silentdrop.dataset import (
    CATEGORIES,
    filter_category,
    load_dataset,
    normalize_domain,
    read_dataset,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (" HTTPS://WWW.Example.COM.:443/docs?q=x#section ", "www.example.com"),
        ("http://example.org:80/news", "example.org"),
        ("example.org/path", "example.org"),
        ("//Bücher.example/", "xn--bcher-kva.example"),
    ],
)
def test_normalize_domain(value, expected):
    assert normalize_domain(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "file:///tmp/file",
        "https://user:secret@example.com/",
        "https://example.com:8080",
        "https://example.com:bad",
        "example..com",
        "local",
        "127.0.0.1",
        "http://[::1]/",
        "a\t.example",
        "-invalid.example",
    ],
)
def test_rejects_unsupported_targets(value):
    with pytest.raises(ValueError):
        normalize_domain(value)


def test_csv_deduplicates_hosts_but_keeps_distinct_www_hostname():
    entries = read_dataset(
        [
            "domain,category,source,upstream_category",
            "https://EXAMPLE.org/a,gaming,citizenlab/lists/global.csv,GAME",
            "http://example.org/b,education,silentdrop,",
            "www.example.org,education,silentdrop,",
        ]
    )
    assert [(row.hostname, row.category) for row in entries] == [
        ("example.org", "gaming"),
        ("www.example.org", "education"),
    ]
    assert entries[0].upstream_category == "GAME"


def test_bundled_dataset_and_category_filter():
    entries = load_dataset()
    assert 100 <= len(entries) <= 200
    assert len({entry.hostname for entry in entries}) == len(entries)
    assert {entry.category for entry in entries} == set(CATEGORIES)
    upstream = [entry for entry in entries if entry.source.startswith("citizenlab/lists/")]
    assert len(upstream) > len(entries) / 2
    assert all(entry.upstream_category for entry in upstream)
    assert len(filter_category(entries, "gaming")) < len(entries)
    assert {entry.category for entry in filter_category(entries, "social")} == {"social"}
    assert filter_category(entries, None) == entries
    with pytest.raises(ValueError, match="unknown category"):
        filter_category(entries, "made-up")
