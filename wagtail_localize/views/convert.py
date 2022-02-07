from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.translation import gettext as _
from wagtail.admin import messages
from wagtail.admin.views.pages.utils import get_valid_next_url_from_request
from wagtail.core.models import Page, PageLogEntry

from wagtail_localize.models import TranslationSource


def convert_to_alias(request, page_id):
    page = get_object_or_404(Page, id=page_id, alias_of_id__isnull=True)
    if not page.permissions_for_user(request.user).can_edit():
        raise PermissionDenied

    try:
        # Attempt to get the source page id, if it exists
        source_page = Page.objects.get(
            translation_key=page.translation_key,
            locale_id=TranslationSource.objects.get(
                object_id=page.translation_key,
                specific_content_type=page.content_type_id,
            ).locale_id,
        )
    except (Page.DoesNotExist, TranslationSource.DoesNotExist):
        raise Http404

    with transaction.atomic():
        next_url = get_valid_next_url_from_request(request)

        if request.method == "POST":
            page.alias_of_id = source_page.id
            page.save(update_fields=["alias_of_id"], clean=False)

            PageLogEntry.objects.log_action(
                instance=page,
                revision=page.get_latest_revision(),
                action="wagtail_localize.convert_to_alias",
                user=request.user,
                data={
                    "page": {
                        "id": page.id,
                        "title": page.get_admin_display_title(),
                    },
                    "source": {
                        "id": source_page.id,
                        "title": source_page.get_admin_display_title(),
                    },
                },
            )

            messages.success(
                request,
                _("Page '{}' has been converted into an alias.").format(
                    page.get_admin_display_title()
                ),
            )

            if next_url:
                return redirect(next_url)
            return redirect("wagtailadmin_pages:edit", page.id)

    return TemplateResponse(
        request,
        "wagtail_localize/admin/confirm_convert_to_alias.html",
        {
            "page": page,
            "next": next_url,
        },
    )