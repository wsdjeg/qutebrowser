# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2017 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Tests for completion models."""

import collections
from datetime import datetime

import pytest
from PyQt5.QtCore import QUrl

from qutebrowser.completion import completer
from qutebrowser.completion.models import miscmodels, urlmodel, configmodel
from qutebrowser.config import configdata, configtypes
from qutebrowser.utils import objreg
from qutebrowser.browser import history
from qutebrowser.commands import cmdutils


def _check_completions(model, expected):
    """Check that a model contains the expected items in any order.

    Args:
        expected: A dict of form
            {
                CategoryName: [(name, desc, misc), ...],
                CategoryName: [(name, desc, misc), ...],
                ...
            }
    """
    __tracebackhide__ = True
    actual = {}
    assert model.rowCount() == len(expected)
    for i in range(0, model.rowCount()):
        catidx = model.index(i, 0)
        catname = model.data(catidx)
        actual[catname] = []
        for j in range(model.rowCount(catidx)):
            name = model.data(model.index(j, 0, parent=catidx))
            desc = model.data(model.index(j, 1, parent=catidx))
            misc = model.data(model.index(j, 2, parent=catidx))
            actual[catname].append((name, desc, misc))
    assert actual == expected
    # sanity-check the column_widths
    assert len(model.column_widths) == 3
    assert sum(model.column_widths) == 100


@pytest.fixture()
def cmdutils_stub(monkeypatch, stubs):
    """Patch the cmdutils module to provide fake commands."""
    return monkeypatch.setattr(cmdutils, 'cmd_dict', {
        'quit': stubs.FakeCommand(name='quit', desc='quit qutebrowser'),
        'open': stubs.FakeCommand(name='open', desc='open a url'),
        'prompt-yes': stubs.FakeCommand(name='prompt-yes', deprecated=True),
        'scroll': stubs.FakeCommand(
            name='scroll',
            desc='Scroll the current tab in the given direction.',
            modes=()),
    })


@pytest.fixture()
def configdata_stub(monkeypatch, configdata_init):
    """Patch the configdata module to provide fake data."""
    return monkeypatch.setattr(configdata, 'DATA', collections.OrderedDict([
        ('aliases', configdata.Option(
            name='aliases',
            description='Aliases for commands.',
            typ=configtypes.Dict(
                keytype=configtypes.String(),
                valtype=configtypes.Command(),
            ),
            default={'q': 'quit'},
            backends=[],
            raw_backends=None)),
        ('bindings.default', configdata.Option(
            name='bindings.default',
            description='Default keybindings',
            typ=configtypes.Dict(
                keytype=configtypes.String(),
                valtype=configtypes.Dict(
                    keytype=configtypes.String(),
                    valtype=configtypes.Command(),
                ),
            ),
            default={
                'normal': {
                    '<ctrl+q>': 'quit'
                }
            },
            backends=[],
            raw_backends=None)),
        ('bindings.commands', configdata.Option(
            name='bindings.commands',
            description='Default keybindings',
            typ=configtypes.Dict(
                keytype=configtypes.String(),
                valtype=configtypes.Dict(
                    keytype=configtypes.String(),
                    valtype=configtypes.Command(),
                ),
            ),
            default={
                'normal': collections.OrderedDict([
                    ('<ctrl+q>', 'quit'),
                    ('ZQ', 'quit'),
                    ('I', 'invalid'),
                ])
            },
            backends=[],
            raw_backends=None)),
    ]))


@pytest.fixture
def quickmarks(quickmark_manager_stub):
    """Pre-populate the quickmark-manager stub with some quickmarks."""
    quickmark_manager_stub.marks = collections.OrderedDict([
        ('aw', 'https://wiki.archlinux.org'),
        ('wiki', 'https://wikipedia.org'),
        ('ddg', 'https://duckduckgo.com'),
    ])
    return quickmark_manager_stub


@pytest.fixture
def bookmarks(bookmark_manager_stub):
    """Pre-populate the bookmark-manager stub with some quickmarks."""
    bookmark_manager_stub.marks = collections.OrderedDict([
        ('https://github.com', 'GitHub'),
        ('https://python.org', 'Welcome to Python.org'),
        ('http://qutebrowser.org', 'qutebrowser | qutebrowser'),
    ])
    return bookmark_manager_stub


@pytest.fixture
def web_history(init_sql, stubs, config_stub):
    """Fixture which provides a web-history object."""
    config_stub.val.completion.timestamp_format = '%Y-%m-%d'
    config_stub.val.completion.web_history_max_items = -1
    stub = history.WebHistory()
    objreg.register('web-history', stub)
    yield stub
    objreg.delete('web-history')


@pytest.fixture
def web_history_populated(web_history):
    """Pre-populate the web-history database."""
    web_history.add_url(
        url=QUrl('http://qutebrowser.org'),
        title='qutebrowser',
        atime=datetime(2015, 9, 5).timestamp()
    )
    web_history.add_url(
        url=QUrl('https://python.org'),
        title='Welcome to Python.org',
        atime=datetime(2016, 3, 8).timestamp()
    )
    web_history.add_url(
        url=QUrl('https://github.com'),
        title='https://github.com',
        atime=datetime(2016, 5, 1).timestamp()
    )
    return web_history


@pytest.fixture
def info(config_stub, key_config_stub):
    return completer.CompletionInfo(config=config_stub,
                                    keyconf=key_config_stub)


def test_command_completion(qtmodeltester, cmdutils_stub, configdata_stub,
                            key_config_stub, info):
    """Test the results of command completion.

    Validates that:
        - only non-hidden and non-deprecated commands are included
        - the command description is shown in the desc column
        - the binding (if any) is shown in the misc column
        - aliases are included
    """
    model = miscmodels.command(info=info)
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Commands": [
            ('open', 'open a url', ''),
            ('q', "Alias for 'quit'", ''),
            ('quit', 'quit qutebrowser', 'ZQ, <ctrl+q>'),
        ]
    })


def test_help_completion(qtmodeltester, cmdutils_stub, key_config_stub,
                         configdata_stub, config_stub, info):
    """Test the results of command completion.

    Validates that:
        - only non-deprecated commands are included
        - the command description is shown in the desc column
        - the binding (if any) is shown in the misc column
        - aliases are not included
        - only the first line of a multiline description is shown
    """
    model = miscmodels.helptopic(info=info)
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Commands": [
            (':open', 'open a url', ''),
            (':quit', 'quit qutebrowser', 'ZQ, <ctrl+q>'),
            (':scroll', 'Scroll the current tab in the given direction.', '')
        ],
        "Settings": [
            ('aliases', 'Aliases for commands.', None),
            ('bindings.commands', 'Default keybindings', None),
            ('bindings.default', 'Default keybindings', None),
        ]
    })


def test_quickmark_completion(qtmodeltester, quickmarks):
    """Test the results of quickmark completion."""
    model = miscmodels.quickmark()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Quickmarks": [
            ('aw', 'https://wiki.archlinux.org', None),
            ('wiki', 'https://wikipedia.org', None),
            ('ddg', 'https://duckduckgo.com', None),
        ]
    })


@pytest.mark.parametrize('row, removed', [
    (0, 'aw'),
    (1, 'wiki'),
    (2, 'ddg'),
])
def test_quickmark_completion_delete(qtmodeltester, quickmarks, row, removed):
    """Test deleting a quickmark from the quickmark completion model."""
    model = miscmodels.quickmark()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    parent = model.index(0, 0)
    idx = model.index(row, 0, parent)

    before = set(quickmarks.marks.keys())
    model.delete_cur_item(idx)
    after = set(quickmarks.marks.keys())
    assert before.difference(after) == {removed}


def test_bookmark_completion(qtmodeltester, bookmarks):
    """Test the results of bookmark completion."""
    model = miscmodels.bookmark()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Bookmarks": [
            ('https://github.com', 'GitHub', None),
            ('https://python.org', 'Welcome to Python.org', None),
            ('http://qutebrowser.org', 'qutebrowser | qutebrowser', None),
        ]
    })


@pytest.mark.parametrize('row, removed', [
    (0, 'https://github.com'),
    (1, 'https://python.org'),
    (2, 'http://qutebrowser.org'),
])
def test_bookmark_completion_delete(qtmodeltester, bookmarks, row, removed):
    """Test deleting a quickmark from the quickmark completion model."""
    model = miscmodels.bookmark()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    parent = model.index(0, 0)
    idx = model.index(row, 0, parent)

    before = set(bookmarks.marks.keys())
    model.delete_cur_item(idx)
    after = set(bookmarks.marks.keys())
    assert before.difference(after) == {removed}


@pytest.fixture(autouse=True)
def url_args(fake_args):
    """Prepare arguments needed to test the URL completion."""
    fake_args.debug_flags = []


def test_url_completion(qtmodeltester, web_history_populated,
                        quickmarks, bookmarks, info):
    """Test the results of url completion.

    Verify that:
        - quickmarks, bookmarks, and urls are included
        - entries are sorted by access time
        - only the most recent entry is included for each url
    """
    model = urlmodel.url(info=info)
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Quickmarks": [
            ('https://wiki.archlinux.org', 'aw', None),
            ('https://wikipedia.org', 'wiki', None),
            ('https://duckduckgo.com', 'ddg', None),
        ],
        "Bookmarks": [
            ('https://github.com', 'GitHub', None),
            ('https://python.org', 'Welcome to Python.org', None),
            ('http://qutebrowser.org', 'qutebrowser | qutebrowser', None),
        ],
        "History": [
            ('https://github.com', 'https://github.com', '2016-05-01'),
            ('https://python.org', 'Welcome to Python.org', '2016-03-08'),
            ('http://qutebrowser.org', 'qutebrowser', '2015-09-05'),
        ],
    })


@pytest.mark.parametrize('url, title, pattern, rowcount', [
    ('example.com', 'Site Title', '', 1),
    ('example.com', 'Site Title', 'ex', 1),
    ('example.com', 'Site Title', 'am', 1),
    ('example.com', 'Site Title', 'com', 1),
    ('example.com', 'Site Title', 'ex com', 1),
    ('example.com', 'Site Title', 'com ex', 0),
    ('example.com', 'Site Title', 'ex foo', 0),
    ('example.com', 'Site Title', 'foo com', 0),
    ('example.com', 'Site Title', 'exm', 0),
    ('example.com', 'Site Title', 'Si Ti', 1),
    ('example.com', 'Site Title', 'Ti Si', 0),
    ('example.com', '', 'foo', 0),
    ('foo_bar', '', '_', 1),
    ('foobar', '', '_', 0),
    ('foo%bar', '', '%', 1),
    ('foobar', '', '%', 0),
])
def test_url_completion_pattern(web_history, quickmark_manager_stub,
                                bookmark_manager_stub, info,
                                url, title, pattern, rowcount):
    """Test that url completion filters by url and title."""
    web_history.add_url(QUrl(url), title)
    model = urlmodel.url(info=info)
    model.set_pattern(pattern)
    # 2, 0 is History
    assert model.rowCount(model.index(2, 0)) == rowcount


def test_url_completion_delete_bookmark(qtmodeltester, bookmarks,
                                        web_history, quickmarks, info):
    """Test deleting a bookmark from the url completion model."""
    model = urlmodel.url(info=info)
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    parent = model.index(1, 0)
    idx = model.index(1, 0, parent)

    # sanity checks
    assert model.data(parent) == "Bookmarks"
    assert model.data(idx) == 'https://python.org'
    assert 'https://github.com' in bookmarks.marks

    len_before = len(bookmarks.marks)
    model.delete_cur_item(idx)
    assert 'https://python.org' not in bookmarks.marks
    assert len_before == len(bookmarks.marks) + 1


def test_url_completion_delete_quickmark(qtmodeltester, info, qtbot,
                                         quickmarks, web_history, bookmarks):
    """Test deleting a bookmark from the url completion model."""
    model = urlmodel.url(info=info)
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    parent = model.index(0, 0)
    idx = model.index(0, 0, parent)

    # sanity checks
    assert model.data(parent) == "Quickmarks"
    assert model.data(idx) == 'https://wiki.archlinux.org'
    assert 'ddg' in quickmarks.marks

    len_before = len(quickmarks.marks)
    model.delete_cur_item(idx)
    assert 'aw' not in quickmarks.marks
    assert len_before == len(quickmarks.marks) + 1


def test_url_completion_delete_history(qtmodeltester, info,
                                       web_history_populated,
                                       quickmarks, bookmarks):
    """Test deleting a history entry."""
    model = urlmodel.url(info=info)
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    parent = model.index(2, 0)
    idx = model.index(1, 0, parent)

    # sanity checks
    assert model.data(parent) == "History"
    assert model.data(idx) == 'https://python.org'

    assert 'https://python.org' in web_history_populated
    model.delete_cur_item(idx)
    assert 'https://python.org' not in web_history_populated


def test_url_completion_zero_limit(config_stub, web_history, quickmarks, info,
                                   bookmarks):
    """Make sure there's no history if the limit was set to zero."""
    config_stub.val.completion.web_history_max_items = 0
    model = urlmodel.url(info=info)
    model.set_pattern('')
    category = model.index(2, 0)  # "History" normally
    assert model.data(category) is None


def test_session_completion(qtmodeltester, session_manager_stub):
    session_manager_stub.sessions = ['default', '1', '2']
    model = miscmodels.session()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Sessions": [('1', None, None),
                     ('2', None, None),
                     ('default', None, None)]
    })


def test_tab_completion(qtmodeltester, fake_web_tab, app_stub, win_registry,
                        tabbed_browser_stubs):
    tabbed_browser_stubs[0].tabs = [
        fake_web_tab(QUrl('https://github.com'), 'GitHub', 0),
        fake_web_tab(QUrl('https://wikipedia.org'), 'Wikipedia', 1),
        fake_web_tab(QUrl('https://duckduckgo.com'), 'DuckDuckGo', 2),
    ]
    tabbed_browser_stubs[1].tabs = [
        fake_web_tab(QUrl('https://wiki.archlinux.org'), 'ArchWiki', 0),
    ]
    model = miscmodels.buffer()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        '0': [
            ('0/1', 'https://github.com', 'GitHub'),
            ('0/2', 'https://wikipedia.org', 'Wikipedia'),
            ('0/3', 'https://duckduckgo.com', 'DuckDuckGo')
        ],
        '1': [
            ('1/1', 'https://wiki.archlinux.org', 'ArchWiki'),
        ]
    })


def test_tab_completion_delete(qtmodeltester, fake_web_tab, app_stub,
                               win_registry, tabbed_browser_stubs):
    """Verify closing a tab by deleting it from the completion widget."""
    tabbed_browser_stubs[0].tabs = [
        fake_web_tab(QUrl('https://github.com'), 'GitHub', 0),
        fake_web_tab(QUrl('https://wikipedia.org'), 'Wikipedia', 1),
        fake_web_tab(QUrl('https://duckduckgo.com'), 'DuckDuckGo', 2)
    ]
    tabbed_browser_stubs[1].tabs = [
        fake_web_tab(QUrl('https://wiki.archlinux.org'), 'ArchWiki', 0),
    ]
    model = miscmodels.buffer()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    parent = model.index(0, 0)
    idx = model.index(1, 0, parent)

    # sanity checks
    assert model.data(parent) == "0"
    assert model.data(idx) == '0/2'

    model.delete_cur_item(idx)
    actual = [tab.url() for tab in tabbed_browser_stubs[0].tabs]
    assert actual == [QUrl('https://github.com'),
                      QUrl('https://duckduckgo.com')]


def test_window_completion(qtmodeltester, fake_web_tab, tabbed_browser_stubs):
    tabbed_browser_stubs[0].tabs = [
        fake_web_tab(QUrl('https://github.com'), 'GitHub', 0),
        fake_web_tab(QUrl('https://wikipedia.org'), 'Wikipedia', 1),
        fake_web_tab(QUrl('https://duckduckgo.com'), 'DuckDuckGo', 2)
    ]
    tabbed_browser_stubs[1].tabs = [
        fake_web_tab(QUrl('https://wiki.archlinux.org'), 'ArchWiki', 0)
    ]

    model = miscmodels.window()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        'Windows': [
            ('0', 'window title - qutebrowser',
                'GitHub, Wikipedia, DuckDuckGo'),
            ('1', 'window title - qutebrowser', 'ArchWiki')
        ]
    })


def test_setting_option_completion(qtmodeltester, config_stub,
                                   configdata_stub, info):
    model = configmodel.option(info=info)
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Options": [
            ('aliases', 'Aliases for commands.', '{"q": "quit"}'),
            ('bindings.commands', 'Default keybindings',
                '{"normal": {"<ctrl+q>": "quit", "ZQ": "quit", '
                '"I": "invalid"}}'),
            ('bindings.default', 'Default keybindings',
                '{"normal": {"<ctrl+q>": "quit"}}'),
        ]
    })


def test_bind_completion(qtmodeltester, cmdutils_stub, config_stub,
                         key_config_stub, configdata_stub, info):
    """Test the results of keybinding command completion.

    Validates that:
        - only non-deprecated commands are included
        - the command description is shown in the desc column
        - the binding (if any) is shown in the misc column
        - aliases are included
    """
    model = configmodel.bind('ZQ', info=info)
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Current": [
            ('quit', 'quit qutebrowser', 'ZQ'),
        ],
        "Commands": [
            ('open', 'open a url', ''),
            ('q', "Alias for 'quit'", ''),
            ('quit', 'quit qutebrowser', 'ZQ, <ctrl+q>'),
            ('scroll', 'Scroll the current tab in the given direction.', '')
        ],
    })


def test_bind_completion_invalid(cmdutils_stub, config_stub, key_config_stub,
                                 configdata_stub, info):
    """Test command completion with an invalid command bound."""
    model = configmodel.bind('I', info=info)
    model.set_pattern('')

    _check_completions(model, {
        "Current": [
            ('invalid', 'Invalid command!', 'I'),
        ],
        "Commands": [
            ('open', 'open a url', ''),
            ('q', "Alias for 'quit'", ''),
            ('quit', 'quit qutebrowser', 'ZQ, <ctrl+q>'),
            ('scroll', 'Scroll the current tab in the given direction.', '')
        ],
    })


def test_bind_completion_no_current(qtmodeltester, cmdutils_stub, config_stub,
                                    key_config_stub, configdata_stub, info):
    """Test keybinding completion with no current binding."""
    model = configmodel.bind('x', info=info)
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Commands": [
            ('open', 'open a url', ''),
            ('q', "Alias for 'quit'", ''),
            ('quit', 'quit qutebrowser', 'ZQ, <ctrl+q>'),
            ('scroll', 'Scroll the current tab in the given direction.', '')
        ],
    })


def test_url_completion_benchmark(benchmark, info,
                                  quickmark_manager_stub,
                                  bookmark_manager_stub,
                                  web_history):
    """Benchmark url completion."""
    r = range(100000)
    entries = {
        'last_atime': list(r),
        'url': ['http://example.com/{}'.format(i) for i in r],
        'title': ['title{}'.format(i) for i in r]
    }

    web_history.completion.insert_batch(entries)

    quickmark_manager_stub.marks = collections.OrderedDict([
        ('title{}'.format(i), 'example.com/{}'.format(i))
        for i in range(1000)])

    bookmark_manager_stub.marks = collections.OrderedDict([
        ('example.com/{}'.format(i), 'title{}'.format(i))
        for i in range(1000)])

    def bench():
        model = urlmodel.url(info=info)
        model.set_pattern('')
        model.set_pattern('e')
        model.set_pattern('ex')
        model.set_pattern('ex ')
        model.set_pattern('ex 1')
        model.set_pattern('ex 12')
        model.set_pattern('ex 123')

    benchmark(bench)
