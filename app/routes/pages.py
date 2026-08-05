"""Page routes for the CivicLens foundation."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.templating import create_template_context, templates


router = APIRouter()


@router.get("/", response_class=HTMLResponse, name="explore")
async def explore(request: Request):
    """Render the public Explore placeholder."""

    context = create_template_context(
        request,
        page_title="Explore",
        active_nav="explore",
        heading="Explore civic issues in HSR Layout",
        description=(
            "The public issue map and community-verified issue list will be "
            "introduced in a later CivicLens milestone."
        ),
    )

    return templates.TemplateResponse(
        request=request,
        name="pages/explore.html",
        context=context,
    )


@router.get("/report", response_class=HTMLResponse, name="report")
async def report(request: Request):
    """Render the future reporting-flow placeholder."""

    context = create_template_context(
        request,
        page_title="Report an issue",
        active_nav="report",
        heading="Report a civic issue",
        description=(
            "Photo upload, approximate location confirmation, AI suggestions, "
            "and duplicate matching are not implemented in this foundation."
        ),
    )

    return templates.TemplateResponse(
        request=request,
        name="pages/report.html",
        context=context,
    )


@router.get("/following", response_class=HTMLResponse, name="following")
async def following(request: Request):
    """Render the future followed-issues placeholder."""

    context = create_template_context(
        request,
        page_title="Following",
        active_nav="following",
        heading="Issues you follow",
        description=(
            "Following and resident notifications will be introduced after "
            "authentication and persistent issue records are available."
        ),
    )

    return templates.TemplateResponse(
        request=request,
        name="pages/following.html",
        context=context,
    )


@router.get("/account", response_class=HTMLResponse, name="account")
async def account(request: Request):
    """Render the future account placeholder."""

    context = create_template_context(
        request,
        page_title="Account",
        active_nav="account",
        heading="Your CivicLens account",
        description=(
            "Account creation and sign-in are not available yet. Supabase "
            "authentication will be added in a later milestone."
        ),
    )

    return templates.TemplateResponse(
        request=request,
        name="pages/account.html",
        context=context,
    )


@router.get(
    "/issues/{issue_id}",
    response_class=HTMLResponse,
    name="issue_detail",
)
async def issue_detail(request: Request, issue_id: str):
    """Render a demonstration issue-detail placeholder."""

    context = create_template_context(
        request,
        page_title="Issue details",
        active_nav="explore",
        heading="Civic issue details",
        description=(
            "This is a routing demonstration only. It does not represent a "
            "stored, verified, or active civic issue."
        ),
        issue_id=issue_id,
        is_demonstration=True,
    )

    return templates.TemplateResponse(
        request=request,
        name="pages/issue_detail.html",
        context=context,
    )