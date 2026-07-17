"""Admin plumbing for temporally versioned models.

Django's admin edits a row by writing over it and deletes it by destroying it.
A model inheriting :class:`~core.models.BaseModel` refuses both, so an admin
class for one mixes :class:`VersionedAdminMixin` in and keeps every screen,
permission and button the stock admin gives it: what they call underneath is
what changes.
"""

from django.urls import reverse
from django.utils import timezone


class VersionedAdminMixin:
    """Routes the admin's writes through the versioning contract.

    Mixed in **before** ``ModelAdmin``, so its methods win:

    * Saving an edit closes the row and inserts a successor, and the screens
      that follow the save are pointed at it.
    * Deleting closes the validity window and leaves the row.

    Adding a row is untouched: an INSERT is an INSERT.
    """

    def save_model(self, request, obj, form, change):
        """Insert a new row, or supersede the edited one.

        The successor is remembered on the request, because the admin holds the
        row it handed here and would otherwise send the browser to a primary key
        that is now a closed predecessor.

        Many-to-many fields are left out of the successor's changes and settled
        by :meth:`save_related`: assigning to the forward side of one is not
        allowed, and the values are not columns of this row.

        Args:
            request: The admin request.
            obj: The row the form was filled from.
            form: The bound form.
            change: False when adding.
        """
        if not change:
            super().save_model(request, obj, form, change)
            return

        cls = type(obj)
        m2m_names = {field.name for field in cls._meta.many_to_many}
        changes = {
            name: form.cleaned_data[name]
            for name in form.changed_data
            if name not in m2m_names
        }
        if not changes:
            return

        successor = cls.history.get(pk=obj.pk).update(**changes)
        request.versioned_successor = successor
        # ``save_related`` writes the M2M values through the form's instance,
        # which is still the predecessor this call just closed.
        form.instance = successor

    def response_change(self, request, obj):
        """Answer the save, naming the row that now holds the values.

        "Save" and "Save as new" build their redirect from the object handed
        here, so passing the successor is enough. "Save and continue editing"
        builds it from ``request.path`` — the predecessor's change page, which
        the live queryset no longer holds — so its redirect is rewritten to the
        successor's.

        Args:
            request: The admin request.
            obj: The row the form was filled from.

        Returns:
            HttpResponse: The stock response, pointed at the successor when the
            edit minted one.
        """
        successor = getattr(request, "versioned_successor", None)
        response = super().response_change(request, successor or obj)
        if successor is not None and "_continue" in request.POST:
            meta = successor._meta
            response["Location"] = reverse(
                f"admin:{meta.app_label}_{meta.model_name}_change",
                args=(successor.pk,),
                current_app=self.admin_site.name,
            )
        return response

    def delete_model(self, request, obj):
        """Close the row the delete button was pressed on.

        Args:
            request: The admin request.
            obj: The row to close.
        """
        obj.soft_delete()

    def delete_queryset(self, request, queryset):
        """Close every row the ``delete_selected`` action was run on.

        One statement, whatever the number of rows.

        Args:
            request: The admin request.
            queryset: The selected rows.
        """
        queryset.update(date_v_end=timezone.now())
