"""``PluginLoader`` -- turns a manifest into a live plugin instance.

Split out from discovery because they are separate concerns and Phase 4 says so:

* **Discovery** answers "what manifests are on disk?" -- pure I/O over directories and entry
  points.
* **Loading** answers "how do I turn a manifest into a ``BaseAttack`` I can call?" -- involves
  importing arbitrary third-party code, building a :class:`PluginContext`, and injecting it.

Keeping them separate means the tests can walk manifests without importing code, and the CLI's
``ragstrike plugins validate`` can validate a plugin without instantiating it.

Loading is deliberately lazy: the module is imported only when the registry has confirmed the
manifest is compatible, and only when the plugin will actually be used. That is what turns a broken
plugin into a "logged and skipped" event instead of an import cascade at startup.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from types import ModuleType
from typing import Any

from ragstrike.core.errors import PluginLoadError
from ragstrike.plugins.base.attack import BaseAttack
from ragstrike.plugins.base.context import PluginContext
from ragstrike.plugins.base.reports import Check, ValidationReport
from ragstrike.plugins.loader.manifest import PluginManifest
from ragstrike.plugins.registry.plugin_config import PluginRuntimeConfig
from ragstrike.plugins.registry.validator import validate_class

log = logging.getLogger(__name__)


class PluginLoader:
    """Instantiates plugins with dependency injection.

    A stateless service: it does not cache anything (the registry does), it does not know about
    other plugins, and it does not persist. Its whole job is
    ``(manifest, runtime_config) -> BaseAttack``.

    The rules:

    1. Import lazily. If the import fails, capture it and raise ``PluginLoadError``.
    2. Verify the class satisfies the ``BaseAttack`` contract before instantiating.
    3. Build a :class:`PluginContext` from the manifest's options and the runtime config.
    4. Pass the context in via the constructor -- **plugins do not instantiate their own
       dependencies**.
    """

    def load(
        self,
        manifest: PluginManifest,
        *,
        runtime: PluginRuntimeConfig | None = None,
    ) -> BaseAttack:
        """Import, validate, instantiate.

        Args:
            manifest: The parsed manifest.
            runtime: Runtime overrides from ``plugins.yaml``. Absent means "use manifest defaults".

        Raises:
            PluginLoadError: The module will not import, or does not contain the named class, or
                the class does not satisfy the contract.
        """
        attack_class = self.load_class(manifest)

        report = validate_class(attack_class)
        if not report.valid:
            failures = "; ".join(check.detail or check.rule for check in report.failures)
            raise PluginLoadError(
                f"{manifest.slug}: {failures}",
                hint="See docs/plugin-development.md for the BaseAttack contract.",
            )

        context = self._build_context(manifest, runtime)

        try:
            return attack_class(context=context)
        except TypeError:
            # Backwards compatibility: plugins written against the Phase 3 signature accept
            # `options=...` rather than `context=...`. Support both so an in-tree Phase 3 plugin
            # keeps loading through this same path.
            return attack_class(options=context.config)
        except Exception as exc:
            raise PluginLoadError(
                f"{manifest.slug}: constructor raised {type(exc).__name__}: {exc}",
                hint="The plugin's __init__ must not do I/O -- move setup work to setup().",
            ) from exc

    # -- pieces exposed so the validator CLI can reuse them -------------------------------

    def load_class(self, manifest: PluginManifest) -> type[BaseAttack]:
        """Import the module named by *manifest* and return its plugin class.

        Adds the plugin's parent directory to ``sys.path`` for the duration of the import so a
        dropped-in folder works without being installed. Removes it afterwards, always.
        """
        parent = str(manifest.source.parent)
        added = parent not in sys.path
        if added:
            sys.path.insert(0, parent)

        try:
            module = importlib.import_module(manifest.module_path)
        except ImportError:
            # A dropped-in directory is usually not a package on sys.path. Fall back to loading
            # the module file directly, which is what makes "drop a folder in and it works" true.
            module = self._load_from_file(manifest)
        except Exception as exc:
            raise PluginLoadError(
                f"{manifest.slug}: importing {manifest.module_path!r} failed: {exc}",
                hint="Fix the plugin, or remove it from the plugin directory.",
            ) from exc
        finally:
            if added and parent in sys.path:
                sys.path.remove(parent)

        attack_class = getattr(module, manifest.class_name, None)
        if attack_class is None:
            raise PluginLoadError(
                f"{manifest.slug}: {manifest.module_path!r} has no class {manifest.class_name!r}.",
                hint=f"Check entry_point in {manifest.manifest_path.name}.",
            )
        if not (isinstance(attack_class, type) and issubclass(attack_class, BaseAttack)):
            raise PluginLoadError(
                f"{manifest.slug}: {manifest.class_name!r} does not subclass BaseAttack.",
                hint="Every plugin must inherit from ragstrike.plugins.base.attack.BaseAttack.",
            )
        return attack_class

    def validate(self, manifest: PluginManifest) -> ValidationReport:
        """Import and validate the class without instantiating it.

        Used by ``ragstrike plugins validate``. Separated from :meth:`load` so a validation run
        does not have the side effects of a load (constructor calls, context building).
        """
        try:
            attack_class = self.load_class(manifest)
        except PluginLoadError as exc:
            return ValidationReport(
                checks=[Check(rule="loadable", passed=False, detail=exc.message)]
            )
        return validate_class(attack_class)

    # -- internals ------------------------------------------------------------------------

    @staticmethod
    def _build_context(
        manifest: PluginManifest, runtime: PluginRuntimeConfig | None
    ) -> PluginContext:
        merged: dict[str, Any] = {**manifest.options}
        timeout_s = 60
        severity_override: str | None = None
        if runtime is not None:
            merged.update(runtime.config)
            if runtime.timeout_s is not None:
                timeout_s = runtime.timeout_s
            severity_override = runtime.severity_override

        return PluginContext.for_plugin(
            plugin_id=manifest.slug,
            source=manifest.source,
            config=merged,
            timeout_s=timeout_s,
            severity_override=severity_override,
        )

    def _load_from_file(self, manifest: PluginManifest) -> ModuleType:
        """Import a plugin module straight from its file, for directories that are not packages.

        Tries the entry-point-named file first, then a small set of conventional names -- so a
        plugin named ``plugin.py`` and one named ``attack.py`` both load.
        """
        tail = manifest.module_path.rsplit(".", 1)[-1]
        candidates = [
            manifest.source / f"{tail}.py",
            manifest.source / "plugin.py",
            manifest.source / "attack.py",
        ]

        for candidate in candidates:
            if not candidate.is_file():
                continue
            spec = importlib.util.spec_from_file_location(
                f"ragstrike_plugin_{manifest.slug.replace('-', '_')}", candidate
            )
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            # Registered before exec so a plugin that imports itself does not recurse.
            sys.modules[spec.name] = module
            try:
                spec.loader.exec_module(module)
            except Exception as exc:
                sys.modules.pop(spec.name, None)
                raise PluginLoadError(
                    f"{manifest.slug}: executing {candidate.name} failed: {exc}",
                    hint="Fix the plugin, or remove it from the plugin directory.",
                ) from exc
            return module

        raise PluginLoadError(
            f"{manifest.slug}: could not find a module for {manifest.module_path!r} in "
            f"{manifest.source}.",
            hint="entry_point should be 'plugin:ClassName' for a single-file plugin.",
        )
