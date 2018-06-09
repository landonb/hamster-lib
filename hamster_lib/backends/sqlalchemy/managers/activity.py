# -*- coding: utf-8 -*-

# This file is part of 'hamster-lib'.
#
# 'hamster-lib' is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# 'hamster-lib' is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with 'hamster-lib'.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

from builtins import str

from future.utils import python_2_unicode_compatible
from six import text_type
from sqlalchemy import asc, desc, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound

from . import query_apply_limit_offset
from ..objects import AlchemyActivity, AlchemyCategory, AlchemyFact
from ....managers.activity import BaseActivityManager


@python_2_unicode_compatible
class ActivityManager(BaseActivityManager):
    def get_or_create(self, activity, raw=False):
        """
        Custom version of the default method in order to provide access to
        Alchemy instances.

        Args:
            activity (hamster_lib.Activity): Activity we want.
            raw (bool): Wether to return the AlchemyActivity instead.

        Returns:
            hamster_lib.Activity: Activity.
        """

        message = _("Received {!r}, raw={}.".format(activity, raw))
        self.store.logger.debug(message)

        try:
            result = self.get_by_composite(activity.name, activity.category, raw=raw)
        except KeyError:
            result = self._add(activity, raw=raw)
        self.store.logger.debug(_("Returning {!r}.").format(result))
        return result

    def _add(self, activity, raw=False):
        """
        Add a new ``Activity`` instance to the databasse.

        Args:
            activity (hamster_lib.Activity): Hamster activity

        Returns:
            hamster_lib.Activity: Hamster activity representation of stored instance.

        Raises:
            ValueError: If the passed activity has a PK.
            ValueError: If the category/activity.name combination to be added is
                already present in the db.
        """

        message = _("Received {!r}, raw={}.".format(activity, raw))
        self.store.logger.debug(message)

        if activity.pk:
            message = _(
                "The activity ('{!r}') you are trying to add already has an PK."
                " Are you sure you do not want to ``_update`` instead?".format(activity)
            )
            self.store.logger.error(message)
            raise ValueError(message)

        try:
            self.get_by_composite(activity.name, activity.category)
            # FIXME/2018-06-08: (lb): DRY: See "Our database already" elsewhere.
            message = _("Our database already contains the passed name/category.name"
                        "combination.")
            self.store.logger.error(message)
            raise ValueError(message)
        except KeyError:
            pass

        alchemy_activity = AlchemyActivity(None, activity.name, None,
            activity.deleted)
        if activity.category:
            try:
                category = self.store.categories.get_by_name(
                    activity.category.name, raw=True)
            except KeyError:
                category = AlchemyCategory(None, activity.category.name)
        else:
            category = None
        alchemy_activity.category = category
        self.store.session.add(alchemy_activity)
        self.store.session.commit()
        result = alchemy_activity
        if not raw:
            result = alchemy_activity.as_hamster(self.store)
        self.store.logger.debug(_("Returning {!r}.").format(result))
        return result

    def _update(self, activity):
        """
        Update a given Activity.

        Args:
            activity (hamster_lib.Activity): Activity to be updated.

        Returns:
            hamster_lib.Activity: Updated activity.

        Raises:
            ValueError: If the new name/category.name combination is already taken.
            ValueError: If the the passed activity does not have a PK assigned.
            KeyError: If the the passed activity.pk can not be found.
        """

        message = _("Received {!r}.".format(activity))
        self.store.logger.debug(message)

        if not activity.pk:
            message = _(
                "The activity passed ('{!r}') does not seem to havea PK. We don't know"
                "which entry to modify.".format(activity))
            self.store.logger.error(message)
            raise ValueError(message)

        try:
            self.get_by_composite(activity.name, activity.category)
            # FIXME/2018-06-08: (lb): DRY: See "Our database already" elsewhere.
            message = _("Our database already contains the passed name/category.name"
                        "combination.")
            self.store.logger.error(message)
            raise ValueError(message)
        except KeyError:
            pass

        alchemy_activity = self.store.session.query(AlchemyActivity).get(activity.pk)
        if not alchemy_activity:
            message = _("No activity with this pk can be found.")
            self.store.logger.error(message)
            raise KeyError(message)
        alchemy_activity.name = activity.name
        alchemy_activity.category = self.store.categories.get_or_create(
            activity.category, raw=True,
        )
        alchemy_activity.deleted = activity.deleted
        try:
            self.store.session.commit()
        except IntegrityError as e:
            message = _(
                'There seems to already be an activity like this for the given category.'
                " Cannot change this activity's values. Original exception: {}".format(e)
            )
            self.store.logger.error(message)
            raise ValueError(message)
        result = alchemy_activity.as_hamster(self.store)
        self.store.logger.debug(_("Returning: {!r}.".format(result)))
        return result

    def remove(self, activity):
        """
        Remove an activity from our internal backend.

        Args:
            activity (hamster_lib.Activity): The activity to be removed.

        Returns:
            bool: True

        Raises:
            KeyError: If the given ``Activity`` can not be found in the database.
        """

        message = _("Received {!r}.".format(activity))
        self.store.logger.debug(message)

        if not activity.pk:
            message = _(
                "The activity you passed does not have a PK. Please provide one."
            )
            self.store.logger.error(message)
            raise ValueError(message)

        alchemy_activity = self.store.session.query(AlchemyActivity).get(activity.pk)
        if not alchemy_activity:
            message = _("The activity you try to remove does not seem to exist.")
            self.store.logger.error(message)
            raise KeyError(message)
        if alchemy_activity.facts:
            alchemy_activity.deleted = True
            self.store.activities._update(alchemy_activity)
        else:
            self.store.session.delete(alchemy_activity)
        self.store.session.commit()
        self.store.logger.debug(_("Deleted {!r}.".format(activity)))
        return True

    def get(self, pk, raw=False):
        """
        Query for an Activity with given key.

        Args:
            pk: PK to look up.
            raw (bool): Return the AlchemyActivity instead.

        Returns:
            hamster_lib.Activity: Activity with given PK.

        Raises:
            KeyError: If no such pk was found.
        """

        message = _("Received PK: '{}', raw={}.".format(pk, raw))
        self.store.logger.debug(message)

        result = self.store.session.query(AlchemyActivity).get(pk)
        if not result:
            message = _("No Activity with 'pk: {}' was found!".format(pk))
            self.store.logger.error(message)
            raise KeyError(message)
        if not raw:
            result = result.as_hamster(self.store)
        self.store.logger.debug(_("Returning: {!r}.".format(result)))
        return result

    def get_by_composite(self, name, category, raw=False):
        """
        Retrieve an activity by its name and category.

        Args:
            name (str): The activities name.
            category (hamster_lib.Category or None): The activities category.
                May be None.
            raw (bool): Return the AlchemyActivity instead.

        Returns:
            hamster_lib.Activity: The activity if it exists in this combination.

        Raises:
            KeyError: if composite key can not be found in the db.

        Note:
            As far as we understand the legacy code in ``__change_category`` and
            ``__get_activity_by`` the combination of activity.name and
            activity.category is unique. This is reflected in the uniqueness constraint
            of the underlying table.
        """

        message = _(
            "Received name: '{}' and {!r} with 'raw'={}.".format(name, category, raw)
        )
        self.store.logger.debug(message)

        name = str(name)
        if category:
            category = text_type(category.name)
            try:
                alchemy_category = self.store.categories.get_by_name(category, raw=True)
            except KeyError:
                message = _(
                    'The category passed ({}) does not exist in the backend. '
                    'Consequently no related activity can be returned.'
                    .format(category)
                )
                self.store.logger.error(message)
                raise KeyError(message)
        else:
            alchemy_category = None

        try:
            query = self.store.session.query(AlchemyActivity)
            query = query.filter_by(name=name).filter_by(category=alchemy_category)
            result = query.one()
        except NoResultFound:
            message = _(
                "No activity of given combination (name: {name}, category: {category})"
                " could be found.".format(name=name, category=category)
            )
            self.store.logger.error(message)
            raise KeyError(message)
        if not raw:
            result = result.as_hamster(self.store)
        self.store.logger.debug(_("Returning: {!r}.".format(result)))
        return result

    def get_all(self, *args, sort_col='', **kwargs):
        """Get all activities."""
        if not sort_col:
            sort_col = 'name'
        return self._get_all(*args, include_usage=False, sort_col=sort_col, **kwargs)

    def get_all_by_usage(self, *args, sort_col='', **kwargs):
        if not sort_col:
            sort_col = 'usage'
        return self._get_all(*args, include_usage=True, sort_col=sort_col, **kwargs)

    def _get_all(
        self,
        include_usage=True,
        search_term='',
        category=False,
        sort_col='',
        sort_order='',
        # kwargs: limit, offset
        **kwargs
    ):
        """
        FIXME: Update this docstring.

        Retrieve all matching activities stored in the backend.

        Args:
            include_usage (int, optional): If true, include count of Facts that reference
                each Activity.
            search_term (str, optional): Limit activities to those matching a substring
                in their name. Defaults to ``empty string``.
            category (hamster_lib.Category or str, optional): Limit activities to this
                category. Defaults to ``False``. If ``category=None`` only activities
                without a category will be considered.
            activity (hamster_lib.Activity, optional): Limit activities to this activity.
                Defaults to ``False``. If ``activity=None`` only activities with a
                matching name will be considered.
            sort_col (str, optional): Which columns to sort by. Defaults to 'activity'.
                Choices: 'activity, 'category', 'start', 'usage'.
                Note that 'start' and 'usage' only apply if include_usage.
            sort_order (str, optional): One of:
                'asc': Whether to search the results in ascending order.
                'desc': Whether to search the results in descending order.
            limit (int, optional): Query "limit".
            offset (int, optional): Query "offset".

        Returns:
            list: List of ``hamster_lib.Activity`` instances matching constrains.
                The list is ordered by ``Activity.name``.
        """

        message = _("Received '{!r}', 'search_term'={}.".format(category, search_term))
        self.store.logger.debug(message)

        query, count_col = self._get_all_query(include_usage)

        query = self._get_all_filter_by_category(query, category)

        query = self._get_all_filter_by_search_term(query, search_term)

        query = self._get_all_group_by(query, include_usage)

        query = self._get_all_order_by(query, sort_col, sort_order, include_usage, count_col)

        query = query_apply_limit_offset(query, **kwargs)

        query = self._get_all_with_entities(query, count_col)

        self.store.logger.debug(_('Query') + ': {}'.format(str(query)))

        results = query.all()

        return results

    def _get_all_query(self, include_usage):
        if not include_usage:
            count_col = None
            query = self.store.session.query(AlchemyActivity)
        else:
            count_col = func.count(AlchemyActivity.pk).label('uses')
            query = self.store.session.query(AlchemyFact, count_col)
            query = query.join(AlchemyFact.activity)
            # NOTE: (lb): SQLAlchemy will lazy load category if/when caller
            #       references it. (I tried using query.options(joinedload(...))
            #       but that route was a mess; and I don't know SQLAlchemy well.)
        # SQLAlchemy automatically lazy-loads activity.category if we
        # reference it after executing the query, so we don't need to
        # join, except that we want to sort by category.name, so we do.
        query = query.join(AlchemyCategory)
        return query, count_col

    def _get_all_filter_by_category(self, query, category):
        if category is False:
            return query
        if category:
            category_query = self.store.session.query(AlchemyCategory)
            alchemy_category = category_query.get(category.pk)
        else:
            alchemy_category = None
        query = query.filter_by(category=alchemy_category)
        return query

    def _get_all_filter_by_search_term(self, query, search_term):
        if not search_term:
            return query
        query = query.filter(
            AlchemyActivity.name.ilike('%{}%'.format(search_term))
        )
        return query

    def _get_all_group_by(self, query, include_usage):
        if not include_usage:
            return query
        query = query.group_by(AlchemyActivity.pk)
        return query

    def _get_all_order_by(self, query, sort_col, sort_order, include_usage, count_col):
        direction = desc if sort_order == 'desc' else asc
        if sort_col == 'category':
            query = query.order_by(direction(AlchemyCategory.name))
            query = query.order_by(direction(AlchemyActivity.name))
        elif sort_col == 'start':
            assert include_usage
            direction = desc if not sort_order else direction
            query = query.order_by(direction(AlchemyFact.start))
        elif sort_col == 'usage':
            assert include_usage and count_col is not None
            direction = desc if not sort_order else direction
            query = query.order_by(direction(count_col))
        else:
            assert sort_col in ('', 'name', 'activity', 'tag', 'fact')
            query = query.order_by(direction(AlchemyActivity.name))
            query = query.order_by(direction(AlchemyCategory.name))
        return query

    def _get_all_with_entities(self, query, count_col):
        if count_col is None:
            return query
        # (lb): Get tricky with it. The query now SELECTs all Fact columns,
        #  and it JOINs and GROUPs BY activities to produce the counts. But
        #  the Fact is meaningless after the group-by; we want the Activity
        #  instead. So use with_entities trickery to tell SQLAlchemy which
        #  columns we really want -- it'll transform the query so that the
        #  SELECT fetches all the Activity columns; but the JOIN and GROUP BY
        #  remain the same! (I'm not quite sure how it works, but it does.)
        # And as an aside, because of the 1-to-many relationship, the
        #  Activity table does not reference Fact, so, e.g., this wouldn't
        #  work, or at least I assume not, but maybe SQLAlchemy would figure
        #  it out: self.store.session.query(AlchemyActivity).join(AlchemyFact).
        query = query.with_entities(AlchemyActivity, count_col)
        return query

