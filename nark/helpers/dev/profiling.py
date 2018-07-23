# -*- coding: utf-8 -*-

# This file is part of 'dob'.
#
# 'dob' is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# 'dob' is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with 'dob'.  If not, see <http://www.gnu.org/licenses/>.

""""""

from __future__ import absolute_import, unicode_literals

import time
from functools import update_wrapper

from ... import __PROFILING__, __time_0__


__all__ = [
    'profile_elapsed',
    'timefunc',
    'timefunct',
    'timewith',
]


MSGS_FUNC = []
MSGS_SPAN = []


def capture_func(msg):
    MSGS_FUNC.append(msg)


def capture_span(msg):
    MSGS_SPAN.append(msg)


def profile_elapsed(text):
    if not __PROFILING__:
        return
    capture_span('{0}: {1:.3f} secs.'.format(text, time.time() - __time_0__))


# Thanks! The following is an edited version of:
#
#   https://zapier.com/engineering/profiling-python-boss/

def timefunc(func):
    if not __PROFILING__:
        return func

    def f_timer(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        capture_func('{0}: {1:.3f} secs.'.format(func.__name__, end - start))
        return result

    return f_timer


def timefunct(text=None):
    def _timefunc(func):
        if not __PROFILING__:
            return func

        def f_timer(*args, **kwargs):
            name = text if text is not None else func.__name__
            start = time.time()
            result = func(*args, **kwargs)
            end = time.time()
            capture_func('{0}: {1:.3f} secs.'.format(name, end - start))
            return result

        return update_wrapper(f_timer, func)
    return _timefunc


class timewith():
    """"""
    def __init__(self, name='', start=None):
        self.name = name
        self.start = time.time() if start is None else start

    @property
    def elapsed(self):
        return time.time() - self.start

    def checkpoint(self, name=''):
        capture_span('{timer} {checkpoint}: {elapsed} secs.'.format(
            timer=self.name,
            checkpoint=name,
            elapsed=self.elapsed,
        ).strip())

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.checkpoint('finished')
        pass


if __PROFILING__:
    def exit_elapsed():
        profile_elapsed('To dob:   exit')
        for msg in MSGS_SPAN:
            print(msg)
        for msg in MSGS_FUNC:
            print(msg)

    import atexit
    atexit.register(exit_elapsed)
