# This file exists within 'nark':
#
#   https://github.com/hotoffthehamster/nark
#
# Copyright © 2018-2020 Landon Bouma
# Copyright © 2015-2016 Eric Goller
# All  rights  reserved.
#
# 'nark' is free software: you can redistribute it and/or modify it under the terms
# of the GNU General Public License  as  published by the Free Software Foundation,
# either version 3  of the License,  or  (at your option)  any   later    version.
#
# 'nark' is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY  or  FITNESS FOR A PARTICULAR
# PURPOSE.  See  the  GNU General Public License  for  more details.
#
# You can find the GNU General Public License reprinted in the file titled 'LICENSE',
# or visit <http://www.gnu.org/licenses/>.

from gettext import gettext as _

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql.expression import or_

from . import BaseAlchemyManager, query_apply_limit_offset, query_apply_true_or_not
from ....managers.category import BaseCategoryManager
from ..objects import AlchemyActivity, AlchemyCategory, AlchemyFact


class CategoryManager(BaseAlchemyManager, BaseCategoryManager):
    def get_or_create(self, category, raw=False, skip_commit=False):
        """
        Custom version of the default method in order to provide access
        to alchemy instances.

        Args:
            category (nark.Category): Category we want.
            raw (bool): Wether to return the AlchemyCategory instead.

        Returns:
            nark.Category or None: Category.
        """

        message = _("Received {!r} and raw={}.").format(category, raw)
        self.store.logger.debug(message)

        try:
            category = self.get_by_name(category.name, raw=raw)
        except KeyError:
            category = self._add(category, raw=raw, skip_commit=skip_commit)
        return category

    # ***

    def _add(self, category, raw=False, skip_commit=False):
        """
        Add a new category to the database.

        This method should not be used by any client code. Call ``save`` to
        make the decission wether to modify an existing entry or to add a new
        one is done correctly.

        Args:
            category (nark.Category): nark Category instance.
            raw (bool): Wether to return the AlchemyCategory instead.

        Returns:
            nark.Category: Saved instance, as_hamster()

        Raises:
            ValueError: If the name to be added is already present in the db.
            ValueError: If category passed already got an PK. Indicating that
                update would be more appropriate.
        """
        self.adding_item_must_not_have_pk(category)

        alchemy_category = AlchemyCategory(
            pk=None,
            name=category.name,
            deleted=bool(category.deleted),
            hidden=bool(category.hidden),
        )

        result = self.add_and_commit(
            alchemy_category, raw=raw, skip_commit=skip_commit,
        )

        return result

    # ***

    def _update(self, category):
        """
        Update a given Category.

        Args:
            category (nark.Category): Category to be updated.

        Returns:
            nark.Category: Updated category.

        Raises:
            ValueError: If the new name is already taken.
            ValueError: If category passed does not have a PK.
            KeyError: If no category with passed PK was found.
        """

        message = _("Received {!r}.").format(category)
        self.store.logger.debug(message)

        if not category.pk:
            message = _(
                "The category passed ('{!r}') does not seem to havea PK. We don't know"
                "which entry to modify."
            ).format(category)
            self.store.logger.error(message)
            raise ValueError(message)
        alchemy_category = self.store.session.query(AlchemyCategory).get(category.pk)
        if not alchemy_category:
            message = _("No category with PK: {} was found!").format(category.pk)
            self.store.logger.error(message)
            raise KeyError(message)
        alchemy_category.name = category.name

        try:
            self.store.session.commit()
        except IntegrityError as err:
            message = _(
                "An error occured! Is category.name already present in the database?"
                " / Error: '{}'."
            ).format(str(err))
            self.store.logger.error(message)
            raise ValueError(message)

        return alchemy_category.as_hamster(self.store)

    # ***

    def remove(self, category):
        """
        Delete a given category.

        Args:
            category (nark.Category): Category to be removed.

        Returns:
            None: If everything went alright.

        Raises:
            KeyError: If the ``Category`` can not be found by the backend.
            ValueError: If category passed does not have an pk.
        """

        message = _("Received {!r}.").format(category)
        self.store.logger.debug(message)

        if not category.pk:
            message = _("PK-less Category. Are you trying to remove a new Category?")
            self.store.logger.error(message)
            raise ValueError(message)
        alchemy_category = self.store.session.query(AlchemyCategory).get(category.pk)
        if not alchemy_category:
            message = _("``Category`` can not be found by the backend.")
            self.store.logger.error(message)
            raise KeyError(message)
        self.store.session.delete(alchemy_category)
        self.store.session.commit()
        message = _("{!r} successfully deleted.").format(category)
        self.store.logger.debug(message)

    # ***

    def get(self, pk, deleted=None):
        """
        Return a category based on their pk.

        Args:
            pk (int): PK of the category to be retrieved.

        Returns:
            nark.Category: Category matching given PK.

        Raises:
            KeyError: If no such PK was found.

        Note:
            We need this for now, as the service just provides pks, not names.
        """

        message = _("Received PK: '{}'.").format(pk)
        self.store.logger.debug(message)

        if deleted is None:
            result = self.store.session.query(AlchemyCategory).get(pk)
        else:
            query = self.store.session.query(AlchemyCategory)
            query = query.filter(AlchemyCategory.pk == pk)
            query = query_apply_true_or_not(query, AlchemyCategory.deleted, deleted)
            results = query.all()
            assert(len(results) <= 1)
            result = results[0] if results else None

        if not result:
            message = _("No category with 'pk: {}' was found!").format(pk)
            self.store.logger.error(message)
            raise KeyError(message)
        message = _("Returning {!r}.").format(result)
        self.store.logger.debug(message)
        return result.as_hamster(self.store)

    # ***

    def get_by_name(self, name, raw=False):
        """
        Return a category based on its name.

        Args:
            name (str): Unique name of the category.
            raw (bool): Whether to return the AlchemyCategory instead.

        Returns:
            nark.Category: Category of given name.

        Raises:
            KeyError: If no category matching the name was found.

        """

        message = _("Received name: '{}', raw={}.").format(name, raw)
        self.store.logger.debug(message)

        try:
            result = self.store.session.query(AlchemyCategory).filter_by(name=name).one()
        except NoResultFound:
            message = _("No category named '{}' was found").format(name)
            self.store.logger.debug(message)
            raise KeyError(message)

        if not raw:
            result = result.as_hamster(self.store)
            self.store.logger.debug(_("Returning: {!r}.").format(result))
        return result

    # ***

    def get_all(self, *args, include_usage=False, sort_cols=('name',), **kwargs):
        """
        Return a list of all categories.

        Returns:
            list: List of ``Categories``, ordered by ``lower(name)``.
        """
        kwargs['include_usage'] = include_usage
        kwargs['sort_cols'] = sort_cols
        return super(CategoryManager, self).get_all(*args, **kwargs)

    def get_all_by_usage(self, *args, sort_cols=('usage',), **kwargs):
        assert(not args)
        kwargs['include_usage'] = True
        kwargs['sort_cols'] = sort_cols
        return super(CategoryManager, self).get_all(*args, **kwargs)

    # DRY: This fcn. very much similar between activity/category/tag.
    # - See FactManager.get_all and ActivityManager.get_all for more
    #   comments about this method.
    def _get_all(
        self,
        key=None,
        include_usage=True,
        count_results=False,
        since=None,
        until=None,
        endless=False,
        partial=False,
        deleted=False,
        search_term=None,
        activity=False,
        category=False,
        match_activities=[],
        match_categories=[],
        sort_cols=[],
        sort_orders=[],
        limit=None,
        offset=None,
        raw=False,
    ):
        """
        Get all Categories, possibly filtered by related Activity, and possible sorted.

        Returns:
            list: List of all Categories present in the database, ordered
            by lower(name) or however caller asked that they be ordered.
        """
        # If user is requesting sorting according to time, need Fact table.
        requested_usage = include_usage
        include_usage = (
            include_usage
            or set(sort_cols).intersection(('start', 'usage', 'time'))
        )

        # Bounce to the simple get() method if a PK specified.
        if key:
            category = self.get(pk=key, deleted=deleted, raw=raw)
            if requested_usage:
                category = (category,)
            return [category]

        def _get_all_categories():
            message = _('usage: {} / term: {} / act.: {} / col: {} / order: {}').format(
                include_usage, search_term, activity, sort_cols, sort_orders,
            )
            self.store.logger.debug(message)

            query, agg_cols = _get_all_start_query()

            query = self.get_all_filter_partial(
                query, since=since, until=until, endless=endless, partial=partial,
            )

            query = self._get_all_filter_by_activities(
                query, match_activities + [activity],
            )

            query = self._get_all_filter_by_categories(
                query, match_categories + [category],
            )
            query = _get_all_filter_by_search_term(query)

            # FIXME/LATER/2018-05-29: (lb): Filter by tags used around this time.
            #   E.g., if it's 4 PM, only suggest tags used on same day at same time...
            #   something like that. I.e., tags you use during weekday at work should
            #   be suggested. For now, filter by category can give similar effect,
            #   depending on how one uses categories.

            query = self._get_all_order_by(query, sort_cols, sort_orders, *agg_cols)

            query = _get_all_group_by(query, agg_cols)

            query = query_apply_limit_offset(query, limit=limit, offset=offset)

            query = _get_all_with_entities(query, agg_cols)

            self._log_sql_query(query)

            results = query.all() if not count_results else query.count()

            if count_results:
                results = query.count()
            else:
                results = query.all()
                results = _process_results(results)

            return results

        # ***

        def _get_all_start_query():
            agg_cols = []
            if (
                not (include_usage or since or until or endless)
                and not activity
                and 'activity' not in sort_cols
            ):
                query = self.store.session.query(AlchemyCategory)
            else:
                if include_usage:
                    count_col = func.count(AlchemyCategory.pk).label('uses')
                    agg_cols.append(count_col)
                    time_col = func.sum(
                        func.julianday(AlchemyFact.end)
                        - func.julianday(AlchemyFact.start)
                    ).label('span')
                    agg_cols.append(time_col)
                    query = self.store.session.query(AlchemyFact, count_col, time_col)
                query = query.join(AlchemyFact.activity)
                query = query.join(AlchemyCategory)

            return query, agg_cols

        # ***

        def _get_all_filter_by_search_term(query):
            if not search_term:
                return query

            condits = None
            for term in search_term:
                condit = AlchemyCategory.name.ilike('%{}%'.format(term))
                if condits is None:
                    condits = condit
                else:
                    condits = or_(condits, condit)

            query = query.filter(condits)
            return query

        # ***

        def _get_all_group_by(query, agg_cols):
            if not agg_cols:
                return query
            query = query.group_by(AlchemyCategory.pk)
            return query

        # ***

        def _get_all_with_entities(query, agg_cols):
            if not agg_cols:
                return query
            query = query.with_entities(AlchemyCategory, *agg_cols)
            return query

        # ***

        def _process_results(records):
            return self._get_all_process_results_simple(
                records,
                raw=raw,
                include_usage=include_usage,
                requested_usage=requested_usage,
            )

        # ***

        return _get_all_categories()

    # ***

    def _get_all_order_by_col(
        self, query, sort_col, direction, count_col=None, time_col=None,
    ):
        return self._get_all_order_by_col_common(
            query,
            sort_col,
            direction,
            default='category',
            count_col=count_col,
            time_col=time_col,
        )

    # ***

