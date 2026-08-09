"""Targets -- what is configured, what is reachable, and what is authorized.

RESPONSIBILITY
    The inventory of things RAGStrike is pointed at, and the CRUD around it.

"BY DEFAULT ONLY LOCALHOST TARGETS SHOULD BE AVAILABLE"
    That default is enforced in the engine, in ``target_adapters.build_adapter``, where every call
    path -- scan, verify, CLI -- passes through it and none can skip it. This page does not
    re-implement the rule; it *shows* it. A non-local URL gets a visible warning and the add form
    says plainly that the backend will refuse it unless the operator has changed the safety policy
    deliberately.

    Putting a second copy of the check here would mean two implementations of "is this host
    allowed", and the failure mode of two is that the permissive one wins by accident.
"""

from __future__ import annotations

from ragstrike.dashboard.components.cards import target_card
from ragstrike.dashboard.components.feedback import banner, empty_state, render_exception
from ragstrike.dashboard.context import PageContext
from ragstrike.dashboard.layouts.page_layout import html, page_header, section
from ragstrike.dashboard.services.errors import DashboardError
from ragstrike.dashboard.services.models import TargetView

NON_LOCAL_WARNING = (
    "This URL is not loopback. RAGStrike refuses non-local targets unless an operator has "
    "deliberately enabled them in the safety policy AND added the host to the allowlist — two "
    "separate steps, on the engine side. The backend will reject this target until both are done."
)

LOCAL_ONLY_NOTICE = (
    "Local targets only by default. RAGStrike refuses any host that is not loopback unless an "
    "operator has deliberately changed the safety policy on the engine side — the URL is not "
    "loopback if it is anything other than 127.0.0.1, localhost, or ::1."
)


def render(context: PageContext) -> None:
    page_header("Targets", "What RAGStrike is pointed at, and what it is authorized to test.")

    if not context.backend_online and not context.demo:
        html(empty_state("◇", "No backend", "Target configuration is served by the API."))
        return

    try:
        targets = context.services.targets.list_targets()
    except DashboardError as exc:
        html(render_exception(context.palette, exc))
        return

    _inventory(context, targets)
    _how_to_add(context)


def _inventory(context: PageContext, targets: list[TargetView]) -> None:
    import streamlit as st

    if not targets:
        html(empty_state("◇", "No targets configured", "Add one below to get started."))
        return

    section(f"Configured targets ({len(targets)})")
    for target in targets:
        # Card, buttons and probe result in ONE bordered container.
        #
        # As siblings, the card's border rendered across "Test connection" and "Select for scan".
        # And the probe's answer went to the toast queue, which drains at the BOTTOM of the page --
        # so clicking Test connection on the first of two targets printed its result far below the
        # second one, with nothing tying the answer to the question.
        with st.container(border=True):
            html(target_card(context.palette, target, framed=False))
            if not target.is_local:
                html(banner(context.palette, "warning", NON_LOCAL_WARNING))

        # Only the two operations the API actually supports are offered.
        #
        # Edit, Delete, and Add used to sit here too, and every one of them failed with "request
        # rejected": the API answers 501 for all three, deliberately. A target carries an
        # authorization record naming who approved testing it, so one created or altered through an
        # unauthenticated local HTTP call would be self-issued -- the backend refuses on purpose
        # (ADR-017), and `configs/targets.yaml` is the only way in.
        #
        # Offering a button that cannot work is worse than offering none: it reads as a broken
        # product rather than a deliberate boundary. The explanation below replaces them.
            actions = st.columns([1, 1, 2])
            if actions[0].button(
                "Test connection", key=f"rs.tgt.verify.{target.id}", width="stretch"
            ):
                _verify(context, target)
            if actions[1].button(
                "Select for scan",
                key=f"rs.tgt.select.{target.id}",
                disabled=not target.enabled,
                width="stretch",
            ):
                context.state.current_target = target.name
                context.navigate("scan_center")
                st.rerun()

            # The probe's answer, directly under the target it describes.
            probe = st.session_state.get(f"rs.tgt.probe.{target.id}")
            if probe:
                html(banner(context.palette, probe["level"], probe["message"]))


def _verify(context: PageContext, target: TargetView) -> None:
    import streamlit as st

    try:
        health = context.services.targets.test_connection(target.id)
    except DashboardError as exc:
        html(render_exception(context.palette, exc))
        return
    # Stored against the target, not queued as a toast. Toasts drain at the bottom of the page, so
    # the answer to "is THIS target reachable?" appeared below every other target on screen.
    st.session_state[f"rs.tgt.probe.{target.id}"] = {
        "level": "success" if health.reachable else "warning",
        "message": f"{target.name}: {health.detail}  ·  {health.latency_ms} ms",
    }
    st.rerun()


def _how_to_add(context: PageContext) -> None:
    """Explain how targets are added, instead of offering a form that cannot work.

    This page used to carry Add, Edit, and Delete controls. All three called endpoints that answer
    501, so every click produced "request rejected" and the section looked broken.

    It is not broken -- it is a boundary. Every target carries an authorization record naming who
    approved testing it, and one created over an unauthenticated local HTTP call would be
    self-issued: the tool would be authorising its own attacks. The API refuses on purpose
    (ADR-017), and the config file is the audited way in.

    So the page now says that, and shows exactly what to write.
    """
    import streamlit as st

    section("Adding or changing a target")
    html(
        banner(
            context.palette,
            "info",
            # `banner()` escapes its message, so the <code> tags rendered as visible text rather than as
        # formatting. Plain backticks read correctly either way and do not depend on the renderer.
        "Targets are declared in configs/targets.yaml, not through this page. "
            "Each one carries an authorization record naming who approved the testing, so a target "
            "created over an unauthenticated local call would be authorising itself. "
            "Edit the file, then restart the API.",
        )
    )
    with st.expander("Show the YAML to add"):
        st.code(
            """targets:
  - name: my-rag
    url: "http://127.0.0.1:9000"      # loopback only
    adapter: fastapi
    timeout: 300
    enabled: true

    authorization:                     # required -- no scan runs without it
      authorized_by: "local-operator"
      authorization_ref: "LOCAL-LAB"
      scope: "Local instance owned by the operator. Loopback only."

    options:                           # how this API is shaped
      chat_path: "/chat"
      health_path: "/health"
      prompt_field: "message"
      answer_path: "answer"
""",
            language="yaml",
        )
        st.caption(LOCAL_ONLY_NOTICE)
