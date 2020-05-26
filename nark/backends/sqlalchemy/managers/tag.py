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
from ....managers.tag import BaseTagManager
from ..objects import (
    AlchemyActivity,
    AlchemyCategory,
    AlchemyFact,
    AlchemyTag,
    fact_tags
)


class TagManager(BaseAlchemyManager, BaseTagManager):
    def get_or_create(self, tag, raw=False, skip_commit=False):
        """
        Custom version of the default method in order to provide access to
        alchemy instances.

        Args:
            tag (nark.Tag): Tag we want.
            raw (bool): Wether to return the AlchemyTag instead.

        Returns:
            nark.Tag or None: Tag.
        """

        message = _("Received {!r} and raw={}.").format(tag, raw)
        self.store.logger.debug(message)

        try:
            tag = self.get_by_name(tag.name, raw=raw)
        except KeyError:
            tag = self._add(tag, raw=raw, skip_commit=skip_commit)
        return tag

    # ***

    def _add(self, tag, raw=False, skip_commit=False):
        """
        Add a new tag to the database.

        This method should not be used by any client code. Call ``save`` to make
        the decission wether to modify an existing entry or to add a new one is
        done correctly..

        Args:
            tag (nark.Tag): nark Tag instance.
            raw (bool): Wether to return the AlchemyTag instead.

        Returns:
            nark.Tag: Saved instance, as_hamster()

        Raises:
            ValueError: If the name to be added is already present in the db.
            ValueError: If tag passed already got an PK. Indicating that update
                would be more appropriate.
        """
        self.adding_item_must_not_have_pk(tag)

        alchemy_tag = AlchemyTag(
            pk=None,
            name=tag.name,
            deleted=bool(tag.deleted),
            hidden=bool(tag.hidden),
        )

        result = self.add_and_commit(
            alchemy_tag, raw=raw, skip_commit=skip_commit,
        )

        return result

    # ***

    def _update(self, tag):
        """
        Update a given Tag.

        Args:
            tag (nark.Tag): Tag to be updated.

        Returns:
            nark.Tag: Updated tag.

        Raises:
            ValueError: If the new name is already taken.
            ValueError: If tag passed does not have a PK.
            KeyError: If no tag with passed PK was found.
        """

        message = _("Received {!r}.").format(tag)
        self.store.logger.debug(message)

        if not tag.pk:
            message = _(
                "The tag passed ('{!r}') does not seem to havea PK. "
                "We don't know which entry to modify."
            ).format(tag)

            self.store.logger.error(message)
            raise ValueError(message)
        alchemy_tag = self.store.session.query(AlchemyTag).get(tag.pk)
        if not alchemy_tag:
            message = _("No tag with PK: {} was found!").format(tag.pk)
            self.store.logger.error(message)
            raise KeyError(message)
        alchemy_tag.name = tag.name

        try:
            self.store.session.commit()
        except IntegrityError as err:
            message = _(
                "An error occured! Are you sure that tag.name is not "
                "already present in the database? Error: '{}'."
            ).format(str(err))
            self.store.logger.error(message)
            raise ValueError(message)

        return alchemy_tag.as_hamster(self.store)

    # ***

    def remove(self, tag):
        """
        Delete a given tag.

        Args:
            tag (nark.Tag): Tag to be removed.

        Returns:
            None: If everything went alright.

        Raises:
            KeyError: If the ``Tag`` can not be found by the backend.
            ValueError: If tag passed does not have an pk.
        """

        message = _("Received {!r}.").format(tag)
        self.store.logger.debug(message)

        if not tag.pk:
            message = _("PK-less Tag. Are you trying to remove a new Tag?")
            self.store.logger.error(message)
            raise ValueError(message)
        alchemy_tag = self.store.session.query(AlchemyTag).get(tag.pk)
        if not alchemy_tag:
            message = _("``Tag`` can not be found by the backend.")
            self.store.logger.error(message)
            raise KeyError(message)
        self.store.session.delete(alchemy_tag)
        self.store.session.commit()
        message = _("{!r} successfully deleted.").format(tag)
        self.store.logger.debug(message)

    # ***

    def get(self, pk, deleted=None):
        """
        Return a tag based on their pk.

        Args:
            pk (int): PK of the tag to be retrieved.

        Returns:
            nark.Tag: Tag matching given PK.

        Raises:
            KeyError: If no such PK was found.

        Note:
            We need this for now, as the service just provides pks, not names.
        """

        message = _("Received PK: '{}'.").format(pk)
        self.store.logger.debug(message)

        if deleted is None:
            result = self.store.session.query(AlchemyTag).get(pk)
        else:
            query = self.store.session.query(AlchemyTag)
            query = query.filter(AlchemyTag.pk == pk)
            query = query_apply_true_or_not(query, AlchemyTag.deleted, deleted)
            results = query.all()
            assert(len(results) <= 1)
            result = results[0] if results else None

        if not result:
            message = _("No tag with 'pk: {}' was found!").format(pk)
            self.store.logger.error(message)
            raise KeyError(message)
        message = _("Returning {!r}.").format(result)
        self.store.logger.debug(message)
        return result.as_hamster(self.store)

    # ***

    def get_by_name(self, name, raw=False):
        """
        Return a tag based on its name.

        Args:
            name (str): Unique name of the tag.
            raw (bool): Wether to return the AlchemyTag instead.

        Returns:
            nark.Tag: Tag of given name.

        Raises:
            KeyError: If no tag matching the name was found.

        """

        message = _("Received name: '{}', raw={}.").format(name, raw)
        self.store.logger.debug(message)

        try:
            result = self.store.session.query(AlchemyTag).filter_by(name=name).one()
        except NoResultFound:
            message = _("No tag named '{}' was found").format(name)
            self.store.logger.debug(message)
            raise KeyError(message)

        if not raw:
            result = result.as_hamster(self.store)
            self.store.logger.debug(_("Returning: {!r}.").format(result))
        return result

    # ***
    # *** gather() call-outs (used by get_all/get_all_by_usage).
    # ***

    @property
    def _gather_query_alchemy_cls(self):
        return AlchemyTag

    @property
    def _gather_query_order_by_name_col(self):
        return 'tag'

    def _gather_query_start_aggregate(self, qt, agg_cols):
        query = self.store.session.query(AlchemyTag, *agg_cols)
        query = query.join(
            fact_tags, AlchemyTag.pk == fact_tags.columns.tag_id,
        )
        query = query.join(AlchemyFact)
        return query

    def query_filter_by_activity(self, activity):
        if activity is not False:
            query = query.join(AlchemyActivity)
        return super(TagManager, self).query_filter_by_activity(activity)

    def query_filter_by_category(self, category):
        if category is not False:
            query = query.join(AlchemyActivity).join(AlchemyCategory)
        return super(TagManager, self).query_filter_by_category(category)

    # ***

