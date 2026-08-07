"""One module per page, each exposing a single ``render(context)``.

A page's whole job is: ask services for data, hand it to components, and turn a click into a service
call. It never builds a request, never decides a verdict, and never formats a colour. When a page
starts to need a helper that other pages would also want, that helper belongs in ``components/``,
``widgets/``, or ``services/`` -- not here.

The nine pages are registered in :mod:`ragstrike.dashboard.navigation.routes`; nothing imports them
directly, so adding one is a registry entry plus a module.
"""
