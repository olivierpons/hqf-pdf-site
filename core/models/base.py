"""Temporal-versioning foundation for every domain model in this project.

The contract — read this before writing any model code
======================================================

Rows are not destroyed, bar the one sanctioned escape below. In-place mutation of
business fields is forbidden. Every "edit" is an *update*: the current row's validity
window is closed (``date_v_end = now()``) and a fresh successor row is inserted, copying
the previous field values, applying the requested changes, and opening its own window at
``now()``. Every "delete" is a *soft-delete*: ``date_v_end = now()`` on the row, and
nothing more.

Three lifecycle states exist for any row:

==========  =========================  =================  ===================== State
Location                   ``date_v_end``     Default visibility ==========
=========================  =================  ===================== Live        Main
table                 ``NULL``           Yes (``Model.objects``) Closed      Main table
NOT NULL, recent   No  (``Model.history``) Archived    ``<table>_archive`` table  NOT
NULL, old      No  (future sweeper) ==========  =========================
=================  =====================

What the state at any past instant ``t`` was is therefore a query, not a guess::

    Model.history.filter(
        date_v_start__lte=t,
        Q(date_v_end__isnull=True) | Q(date_v_end__gt=t),
    )

Two methods named ``update`` coexist and mean different things:

* :meth:`BaseModel.update` — instance method, versioned edit. Closes the row and inserts
  a successor, which it returns.
* :meth:`VersionedQuerySet.update` — bulk SQL ``UPDATE``, restricted to the whitelisted
  columns. Used for bulk soft-deletes (``qs.update(date_v_end=…)``).

The successor carries a **new primary key**
-------------------------------------------

Reverse FK rows are re-pointed at the successor by
:meth:`BaseModel._reattach_reverse_fks_to`, and M2M edges are cloned by
:meth:`BaseModel._clone_m2m_edges_to`. Anything holding a primary key *outside* the
database is not, and cannot be: a Django session stores ``_auth_user_id``, so calling
``update()`` on the logged-in user logs them out. A view that edits the current user
must re-issue ``login(request, successor)``.

Anti-patterns this module turns into a ``RuntimeError``
-------------------------------------------------------

* ``obj.business_field = 42; obj.save()`` — use ``obj.update(business_field=42)``.
* ``Model.objects.filter(…).update(business_field=42)`` — loop and call
  ``obj.update(…)`` per row.
* ``obj.delete()`` / ``qs.delete()`` — use ``obj.soft_delete()`` or
  ``qs.update(date_v_end=timezone.now())``.

The escape is :meth:`VersionedQuerySet.hard_delete`, which destroys for real. It is
spelled differently from ``delete()`` so it cannot be reached by accident, and it is
what an erasure request is served with.

Anti-patterns it cannot catch — avoid them by hand
---------------------------------------------------

* Raw SQL through ``connection.cursor()``.
* ``ManyToManyField.add()`` / ``remove()`` on an auto-generated through table, which
  issues ``DELETE FROM``. Declare ``through="…"`` and manage rows explicitly.

Checklist for a new model
-------------------------

* A uniqueness rule spans live rows only: ``UniqueConstraint(fields=[…],
  condition=Q(date_v_end__isnull=True))``, never ``unique=True`` — a closed predecessor
  keeps its values and would collide with its own successor.
* A column written by machinery outside our control (``last_login``) goes in
  :attr:`BaseModel.EXTRA_IN_PLACE_FIELDS`, or every write to it raises.
* A new M2M declares an explicit ``through=`` model.
"""

from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

# Columns that may change in place on a live row.
#
# * ``date_v_end`` — the entire point: moving it from NULL to a timestamp is what
# closes a validity window.
# * ``date_creation`` — written once by ``auto_now_add``, never again.
# * ``date_last_update`` — written by ``auto_now`` on every save, so it appears
# in every diff and the comparison must ignore it.
#
# Any other column appearing in a save's diff against the stored row raises. A subclass
# widens this through ``EXTRA_IN_PLACE_FIELDS``.
ALLOWED_IN_PLACE_FIELDS = frozenset({"date_v_end", "date_creation", "date_last_update"})


class VersionedQuerySet(models.QuerySet):
    """QuerySet that refuses the two operations able to destroy history.

    ``update()`` is partially allowed: whitelisted columns only, which permits
    ``qs.update(date_v_end=timezone.now())`` as a bulk soft-delete but refuses
    ``qs.update(business_field=value)``. ``delete()`` is always refused.
    """

    def update(self, **kwargs):
        """Bulk-update the whitelisted columns.

        Args:
            **kwargs: ``field=value`` pairs to write.

        Returns:
            int: Number of rows touched.

        Raises:
            RuntimeError: A field outside the model's in-place whitelist was
                passed.
        """
        allowed = self.model.in_place_fields()
        forbidden = set(kwargs) - allowed
        if forbidden:
            raise RuntimeError(
                f"VersionedQuerySet.update() refuses to bulk-update fields "
                f"{sorted(forbidden)} on a temporally versioned table; call "
                f"obj.update(...) per row, or restrict the bulk update to "
                f"{sorted(allowed)}."
            )
        return super().update(**kwargs)

    def delete(self):
        """Refuse bulk deletion.

        Raises:
            RuntimeError: Always. Use ``qs.update(date_v_end=timezone.now())``
                for a bulk soft-delete, :meth:`hard_delete` to destroy.
        """
        raise RuntimeError(
            f"{self.model.__name__} rows are temporally versioned, so "
            "QuerySet.delete() is forbidden. Use "
            "``qs.update(date_v_end=timezone.now())`` for a bulk soft-delete, "
            "``obj.soft_delete()`` per row, or ``hard_delete()`` to destroy."
        )

    def hard_delete(self):
        """Physically destroy the selected rows, history included.

        The single sanctioned escape from the no-destruction invariant, for what the
        invariant does not serve: a row no history is worth keeping for, and an erasure
        that is owed rather than chosen — a customer asking for their account to be gone
        leaves nothing to audit.

        It destroys exactly what the queryset matches and nothing more, so the caller
        narrows it, and reaches for ``history`` when the closed predecessors must go
        too.

        Returns:
            tuple: Rows destroyed, and the per-model count including cascades.
        """
        return super().delete()


class LiveManager(models.Manager):
    """Default manager — the rows whose validity window covers ``now()``.

    A row is live when ``date_v_start <= now`` and ``date_v_end`` is either NULL or
    still in the future. Every read in application code goes through this manager
    (``Model.objects``) unless it explicitly wants the audit trail (``Model.history``).
    """

    def get_queryset(self):
        """Return the live subset.

        ``timezone.now()`` is captured per call: a queryset cached at module-import or
        class-body time would freeze the window there and drop rows created afterwards.

        Returns:
            VersionedQuerySet: Rows valid at ``now()``.
        """
        current_time = timezone.now()
        return VersionedQuerySet(self.model, using=self._db).filter(
            Q(date_v_start__lte=current_time)
            & (Q(date_v_end__isnull=True) | Q(date_v_end__gt=current_time))
        )


class HistoryManager(models.Manager):
    """Manager over every row of the main table, live and closed alike.

    Exposed as ``Model.history``: past state, audit trails, and re-fetching a known pk
    whatever its validity. Rows moved to ``<table>_archive`` by the future sweeper are
    not included.
    """

    def get_queryset(self):
        """Return every row.

        Returns:
            VersionedQuerySet: The whole main table.
        """
        return VersionedQuerySet(self.model, using=self._db)


class BaseModel(models.Model):
    """Abstract parent carrying the temporal-versioning machinery.

    Subclasses get two managers: ``Model.objects`` (:class:`LiveManager`) and
    ``Model.history`` (:class:`HistoryManager`). A subclass needing its own default
    manager subclasses :class:`LiveManager` so the live filter survives.

    Attributes:
        EXTRA_IN_PLACE_FIELDS: Column names this model may write in place, on
            top of :data:`ALLOWED_IN_PLACE_FIELDS`. For columns owned by
            machinery that cannot be routed through ``update()``.
        date_creation: Written by ``auto_now_add`` on the first INSERT.
        date_last_update: Written by ``auto_now`` on every save.
        date_v_start: When the validity window opens.
        date_v_end: When it closes; NULL means still live. Once set, the row is
            immutable.
    """

    EXTRA_IN_PLACE_FIELDS = frozenset()

    date_creation = models.DateTimeField(auto_now_add=True)
    date_last_update = models.DateTimeField(auto_now=True)
    date_v_start = models.DateTimeField(default=timezone.now)
    date_v_end = models.DateTimeField(default=None, null=True, blank=True)

    objects = LiveManager()
    history = HistoryManager()

    class Meta:
        abstract = True
        ordering = ["date_v_start"]

    def save(self, *args, **kwargs):
        """Persist this instance, refusing a forbidden in-place mutation.

        An INSERT always passes. An update passes when every field it would write is in
        :meth:`in_place_fields`; ``update_fields`` narrows the comparison to the columns
        actually written. A closed row is immutable.

        Args:
            *args: Forwarded to ``models.Model.save``.
            **kwargs: Forwarded to ``models.Model.save``.

        Raises:
            RuntimeError: A business field would be written in place, or the
                stored row is already closed.
        """
        if self._state.adding:
            super().save(*args, **kwargs)
            return

        cls = type(self)
        try:
            stored = cls.history.get(pk=self.pk)
        except cls.DoesNotExist:
            super().save(*args, **kwargs)
            return

        if stored.date_v_end is not None:
            raise RuntimeError(
                f"Cannot modify a closed {cls.__name__} row (pk={self.pk}, "
                f"date_v_end={stored.date_v_end!r}). Closed rows are immutable."
            )

        update_fields = kwargs.get("update_fields")
        narrowed = set(update_fields) if update_fields else None
        allowed = cls.in_place_fields()
        violations = []
        for field in cls._meta.concrete_fields:
            if field.attname in allowed:
                continue
            if narrowed is not None and field.name not in narrowed:
                continue
            if getattr(self, field.attname) != getattr(stored, field.attname):
                violations.append(field.name)
        if violations:
            raise RuntimeError(
                f"In-place update of {cls.__name__}.{', '.join(sorted(violations))} "
                f"is forbidden on a temporally versioned row. Use "
                f"obj.update({violations[0]}=...) to create a successor."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Refuse hard deletion.

        Raises:
            RuntimeError: Always. Use :meth:`soft_delete`.
        """
        raise RuntimeError(
            f"{type(self).__name__}.delete() is forbidden on a temporally "
            "versioned row. Use ``obj.soft_delete()`` to close the validity "
            "window."
        )

    @classmethod
    def in_place_fields(cls):
        """Return every column this model may write in place.

        Returns:
            frozenset: :data:`ALLOWED_IN_PLACE_FIELDS` widened by
            :attr:`EXTRA_IN_PLACE_FIELDS`.
        """
        return ALLOWED_IN_PLACE_FIELDS | cls.EXTRA_IN_PLACE_FIELDS

    @property
    def is_live(self):
        """Return whether this row's validity window is open right now.

        The managers answer this in SQL. This answers it for a row already in memory —
        typically one reached through a foreign key, which Django resolves through an
        unfiltered manager and therefore hands back even when it is closed.

        Returns:
            bool: True when the window has opened and has not closed.
        """
        current_time = timezone.now()
        if self.date_v_start > current_time:
            return False
        return self.date_v_end is None or self.date_v_end > current_time

    def soft_delete(self):
        """Close this row's validity window. Idempotent.

        The only way to "delete" a versioned row from application code.
        """
        if self.date_v_end is not None:
            return
        closing_time = timezone.now()
        type(self).history.filter(pk=self.pk).update(date_v_end=closing_time)
        self.date_v_end = closing_time

    def update(self, **changes):
        """Close this row and insert a successor carrying ``changes``.

        Both writes happen in one transaction. Fields absent from ``changes`` are copied
        from the stored row, not from this instance: any in-memory edit made before the
        call is ignored.

        Args:
            **changes: ``field_name=value`` pairs to apply to the successor.

        Returns:
            BaseModel: The new live successor. Its primary key differs from
            this row's, so the caller rebinds its variable — this instance now
            refers to the closed predecessor.

        Raises:
            RuntimeError: This row is already closed.
            NotImplementedError: This model inherits from another
                :class:`BaseModel` through multi-table inheritance. A successor
                would mint a new parent pk and orphan every FK pointing at the
                parent row.
        """
        cls = type(self)
        mti_parents = [
            parent for parent in cls._meta.parents if issubclass(parent, BaseModel)
        ]
        if mti_parents:
            parent_names = ", ".join(parent.__name__ for parent in mti_parents)
            raise NotImplementedError(
                f"update() is not supported on {cls.__name__}: it inherits from "
                f"{parent_names} through multi-table inheritance, and a "
                "successor would mint a new parent primary key, orphaning "
                "every FK that points at the parent row."
            )
        if self.date_v_end is not None:
            raise RuntimeError(
                f"Cannot update {cls.__name__} pk={self.pk}: the row is already "
                f"closed (date_v_end={self.date_v_end!r})."
            )

        with transaction.atomic():
            closing_time = timezone.now()
            cls.history.filter(pk=self.pk).update(date_v_end=closing_time)
            self.date_v_end = closing_time

            stored = cls.history.get(pk=self.pk)
            successor = cls()
            skipped = {
                cls._meta.pk.attname,
                "date_creation",
                "date_last_update",
                "date_v_start",
                "date_v_end",
            }
            for field in cls._meta.concrete_fields:
                if field.attname in skipped:
                    continue
                setattr(successor, field.attname, getattr(stored, field.attname))
            # Editing a row whose window opens later is not publishing it: its reveal
            # date is a plan, and the successor keeps it.
            successor.date_v_start = max(closing_time, stored.date_v_start)
            successor.date_v_end = None

            for name, value in changes.items():
                setattr(successor, name, value)
            successor.save()

            self._clone_m2m_edges_to(successor, closing_time)
            self._reattach_reverse_fks_to(successor)
            return successor

    def _through_models(self):
        """Return every M2M through model this row has edges in.

        Covers M2Ms declared on this class and those declared on the other side with a
        ``related_name``.

        Returns:
            set: The through model classes.
        """
        cls = type(self)
        through_models = set()
        for m2m_field in cls._meta.many_to_many:
            through_models.add(m2m_field.remote_field.through)
        for related in cls._meta.get_fields():
            if not getattr(related, "many_to_many", False):
                continue
            through = getattr(related, "through", None)
            if through is not None:
                through_models.add(through)
        return through_models

    def _clone_m2m_edges_to(self, successor, closing_time):
        """Replicate every M2M through row of this row onto ``successor``.

        Metadata-driven: no model name appears here, so any future subclass is carried
        without further patching. Every FK on a through model pointing back at this
        class is treated as a back-reference, which covers self-referential M2Ms where
        two of them do.

        A through row that is itself a :class:`BaseModel` is closed, so its window
        matches its closed parent's. An auto-generated through row has no such column
        and lingers, pinned to the closed predecessor's pk, which no live query joins
        to.

        Args:
            successor: The row inserted by :meth:`update`.
            closing_time: Timestamp closing the superseded through rows.
        """
        cls = type(self)
        housekeeping = cls.in_place_fields() | {"date_v_start"}
        for through in self._through_models():
            fks_to_self = [
                field
                for field in through._meta.fields
                if field.is_relation and field.related_model is cls
            ]
            if not fks_to_self:
                continue
            # Keyed by pk so a self-loop edge, matched by both FKs, enqueues once.
            rows_by_pk = {}
            for fk in fks_to_self:
                for row in through.objects.filter(**{fk.name: self}):
                    rows_by_pk[row.pk] = row
            if not rows_by_pk:
                continue

            skipped = housekeeping | {through._meta.pk.attname}
            for source_row in rows_by_pk.values():
                through.objects.create(
                    **self._cloned_edge(source_row, successor, skipped)
                )
                if isinstance(source_row, BaseModel):
                    type(source_row).history.filter(pk=source_row.pk).update(
                        date_v_end=closing_time
                    )

    def _cloned_edge(self, source_row, successor, skipped):
        """Return the field values of ``source_row``, rebound to ``successor``.

        An FK pointing at this row becomes one pointing at ``successor``; the other end
        of the edge is carried over untouched.

        Args:
            source_row: The through row to copy.
            successor: The row inserted by :meth:`update`.
            skipped: Attnames left out, so the insert mints them afresh.

        Returns:
            dict: ``attname`` to value, ready for ``objects.create()``.
        """
        cls = type(self)
        edge = {}
        for field in type(source_row)._meta.concrete_fields:
            if field.attname in skipped:
                continue
            value = getattr(source_row, field.attname)
            points_at_self = (
                field.is_relation and field.related_model is cls and value == self.pk
            )
            edge[field.attname] = successor.pk if points_at_self else value
        return edge

    def _reattach_reverse_fks_to(self, successor):
        """Re-point every reverse-FK row from this row to ``successor``.

        Rows on other models pointing at this row's pk would otherwise stay pinned to
        the closed predecessor and drop out of any query filtering on the live
        successor. M2M through rows are excluded: they are cloned, not rebound.

        The historical link to the exact predecessor version is traded away. A reverse
        FK names the entity, not the version of the row that held it.

        Args:
            successor: The row inserted by :meth:`update`.
        """
        cls = type(self)
        through_models = self._through_models()
        for relation in cls._meta.get_fields():
            if not relation.is_relation or relation.many_to_many:
                continue
            if not (relation.one_to_many or relation.one_to_one):
                continue
            related_model = relation.related_model
            if related_model is None or related_model in through_models:
                continue
            remote_field = getattr(relation, "field", None)
            if remote_field is None:
                continue
            # A plain QuerySet: re-pointing an FK is not a business-field edit, so it
            # must bypass the whitelist a VersionedQuerySet would apply.
            models.QuerySet(model=related_model).filter(
                **{remote_field.attname: self.pk}
            ).update(**{remote_field.attname: successor.pk})
