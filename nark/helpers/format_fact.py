# -*- coding: utf-8 -*-

# This file is part of 'nark'.
#
# 'nark' is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# 'nark' is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with 'nark'.  If not, see <http://www.gnu.org/licenses/>.
"""A Fact formatting module, to keep Item.Fact() more pure."""

from __future__ import absolute_import, unicode_literals

from six import text_type

from ..helpers.colored import attr, colorize, set_coloring
from ..helpers.strings import format_value_truncate

__all__ = [
    'friendly_str',
    'html_notif',
    'tags_inline',
    'tags_tuples',
    # Private:
    #  'actegory_string',
    #  'description_string',
    #  'ordered_tagnames',
]


def friendly_str(
    self,
    shellify=False,
    description_sep=': ',
    tags_sep=': ',
    localize=False,
    include_id=False,
    colorful=False,
    cut_width=None,
    show_elapsed=False,
    omit_empty_actegory=False,
):
    """
    Flexible Fact serializer.
    """
    def _friendly_str(fact):
        was_coloring = set_coloring(colorful)
        meta = assemble_parts(fact)
        result = format_result(fact, meta)
        # (lb): EXPLAIN: Why do we cast here?
        result = text_type(result)
        set_coloring(was_coloring)
        return result

    def assemble_parts(fact):
        parts = [
            get_id_string(fact),
            get_times_string(fact),
            fact.actegory_string(shellify, omit_empty_actegory),
        ]
        parts_str = ' '.join(list(filter(None, parts)))
        tags = get_tags_string(fact)
        parts_str += tags_sep + tags if tags else ''
        parts_str += _(" [del]") if fact.deleted else ''
        return parts_str

    def format_result(fact, meta):
        result = '{fact_meta}{description}'.format(
            fact_meta=meta,
            description=fact.description_string(cut_width, description_sep),
        )
        return result

    def get_id_string(fact):
        if not include_id:
            return ''
        return colorize('(${})'.format(fact.pk), 'grey_78')

    def get_times_string(fact):
        times = ''
        times += get_times_string_start(fact)
        times += get_times_string_end(fact, times)
        times += get_times_duration(fact)
        return times

    def get_times_string_start(fact):
        if not fact.start:
            return ''
        if not self.localize:
            start_time = fact.start_fmt_utc
        else:
            start_time = fact.start_fmt_local
        start_time = colorize(start_time, 'sandy_brown')
        return start_time

    def get_times_string_end(fact, times):
        # NOTE: The CLI's DATE_TO_DATE_SEPARATORS[0] is 'to'.
        prefix = colorize(' to ', 'grey_85') if times else ''
        if not fact.end:
            # (lb): What's a good term here? '<ongoing>'? Or just 'now'?
            end_time = _('<now>')
        elif not self.localize:
            end_time = fact.end_fmt_utc
        else:
            end_time = fact.end_fmt_local
        end_time = colorize(end_time, 'sandy_brown')
        return prefix + end_time

    def get_times_duration(fact):
        if not show_elapsed:
            return ''
        duration = ' [{}]'.format(fact.format_delta(''))
        return colorize(duration, 'grey_78')

    def get_tags_string(fact):
        # (lb): There are three ways to "shellify" a hashtag token:
        #         1.) "#quote" it;
        #         2.) \#delimit it; or
        #         3.) use the inoffensive @ symbol instead of #.
        # Let's do 1.) by default, because most people associate the pound
        # sign with tags, because quotes are less offensive than a slash,
        # and because the @ symbol makes me think of "at'ing someone".
        #   Nope:  hashtag_token = '@' if shellify else '#'
        return fact.tags_inline(quote_tokens=shellify)

    # ***

    return _friendly_str(self)


# ***

def html_notif(self):
    """
    A briefer Fact one-liner using HTML. Useful for, e.g., notifier toast.
    """
    was_coloring = set_coloring(False)
    duration = '[{}]'.format(self.format_delta(''))
    actegory = self.actegory_string(omit_empty_actegory=True)
    actegory = actegory or '<i>No activity</i>'
    description = self.description_string(cut_width=39, sep=': ')
    simple_str = (
        '{} {}{}'
        .format(
            duration,
            actegory,
            description,
        )
    )
    set_coloring(was_coloring)
    return simple_str


# ***

def actegory_string(self, shellify=False, omit_empty_actegory=False):
    # (lb): We can skip delimiter after time when using ISO 8601.
    if not self.activity_name:
        if not self.category_name:
            act_cat = '' if omit_empty_actegory else '@'
        else:
            act_cat = '@{}'.format(self.category_name)
    else:
        act_cat = (
            '{}@{}'.format(
                self.activity_name,
                self.category_name,
            )
        )
# FIXME: Skinify these colors.
    act_cat = colorize(act_cat, 'cornflower_blue', 'bold', 'underlined')
    act_cat = '"{}"'.format(act_cat) if act_cat and shellify else act_cat
    return act_cat


# ***

def description_string(self, cut_width=None, sep=', '):
    description = self.description or ''
    if description:
        if cut_width is not None:
            description = format_value_truncate(description, cut_width)
        description = '{}{}'.format(sep, description)
    return description


# ***

# (lb): People associate tags with pound signs -- like, #hashtag!
# But Bash, and other shells, use octothorpes to start comments.
# The user can tell Bash to interpret a pound sign as input by
# "#quoting" it, or by \#delimiting it. Hamster also lets the user
# use an '@' at symbol instead (not to be confused with typical
# social media usage of '@' to refer to other users or people).
# By default, this function assumes the tags do not need special
# delimiting; that the pound sign is fine.
def tags_inline(
    self,
    hashtag_token='#',
    quote_tokens=False,
    underlined=False,
):
    def format_tagname(tag):
        tagged = '{}{}'.format(
# FIXME: Skinify these colors.
            colorize(hashtag_token, 'grey_78'),
            colorize(tag.name, 'dark_olive_green_1b'),
        )
# FIXME: Skinify underlined.
        if underlined:
            tagged = '{}{}{}'.format(
                attr('underlined'), tagged, attr('res_underlined'),
            )
        if quote_tokens:
            tagged = '"{}"'.format(tagged)
        return tagged

    # NOTE: The returned string includes leading space if nonempty!
    tagnames = ''
    if self.tags:
        tagnames = ' '.join(self.ordered_tagnames(format_tagname))
    return tagnames


def tags_tuples(
    self,
    hashtag_token='#',
    quote_tokens=False,
    underlined=False,
    split_lines=False,
):
    def format_tagname(tag):
# FIXME: Skinify underlined.
        uline = ' underline' if underlined else ''
        tagged = []
# FIXME: Skinify these colors.
        tagged.append(('fg: #C6C6C6{}'.format(uline), hashtag_token))
        tagged.append(('fg: #D7FF87{}'.format(uline), tag.name))
        if quote_tokens:
            fmt_quote = ('', '"')
            tagged.insert(0, fmt_quote)
            tagged.append(fmt_quote)
        return tagged

    # NOTE: The returned string includes leading space if nonempty!
    tagnames = []
    if self.tags:
        fmt_sep = ('', "\n") if split_lines else ('', ' ')
        n_tag = 0
        for fmtd_tagn in self.ordered_tagnames(format_tagname):
            if n_tag > 0:
                tagnames += [fmt_sep]
            n_tag += 1
            tagnames += fmtd_tagn
    return tagnames


def ordered_tagnames(self, format_tagname):
    return [
        format_tagname(tag) for tag in self.tags_sorted
    ]
