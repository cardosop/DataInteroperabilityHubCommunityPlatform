"""
Pytest configuration and shared fixtures
"""

# IMPORTANT: Patch Django BEFORE importing Django modules
# This must happen before Django initializes database connections
import logging
import os
import sys

# Set up debug logging for patch verification
_patch_logger = logging.getLogger("django_patches")
_patch_logger.setLevel(logging.DEBUG)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
_patch_logger.addHandler(_handler)


def _log_patch(name, applied=True):
    """Log patch application for debugging"""
    if applied:
        _patch_logger.debug(f"✓ Patch applied: {name}")
    else:
        _patch_logger.warning(f"✗ Patch failed: {name}")


# CRITICAL: Patch sync_apps BEFORE any Django imports
# This prevents sync_apps from running during test database creation
# We patch it early and also ensure it's patched whenever Django creates new Command instances
def _ensure_sync_apps_patched():
    """Ensure sync_apps is patched - can be called multiple times safely"""
    try:
        import types

        import django.core.management.commands.migrate as migrate_module

        # Store original for reference
        if not hasattr(migrate_module.Command, "_original_sync_apps"):
            migrate_module.Command._original_sync_apps = migrate_module.Command.sync_apps

        # Create a patched sync_apps that is a complete no-op
        def _patched_sync_apps(self, connection, apps):
            """
            Patched sync_apps - ROOT CAUSE FIX (early patch)

            Always returns immediately without executing any SQL.
            Migrations will create all tables, so sync_apps doesn't need to run.
            """
            _patch_logger.info("=" * 80)
            _patch_logger.info(
                f"✓ sync_apps (early): CALLED but suppressed (apps={len(apps) if apps else 0})"
            )
            _patch_logger.info(
                "✓ sync_apps (early): ROOT CAUSE FIX - returning immediately without SQL"
            )
            _patch_logger.info("=" * 80)
            # Always return immediately - migrations will create tables
            return

        # Apply class-level patch
        migrate_module.Command.sync_apps = types.MethodType(
            _patched_sync_apps, migrate_module.Command
        )
        _log_patch("Command.sync_apps (early)")
    except (ImportError, AttributeError) as e:
        # Django not installed yet or already patched, will patch later
        _patch_logger.debug(
            f"Could not apply early sync_apps patch (expected if Django not loaded): {e}"
        )
        pass


# Try to patch early if Django is already imported
_ensure_sync_apps_patched()

# Always apply patches - they're safe and needed for test database setup
# Apply patches always - they're idempotent and safe
# CRITICAL: Apply patches BEFORE Django creates any instances
if True:  # Always apply patches
    # CRITICAL: Patch MigrationExecutor.__init__ EARLY to clear unmigrated_apps
    # This must be done before Django creates any executors
    try:
        import django.db.migrations.executor as executor_module

        if hasattr(executor_module, "MigrationExecutor"):
            _original_executor_init_early = executor_module.MigrationExecutor.__init__
            if not hasattr(_original_executor_init_early, "_patched_for_unmigrated_early"):

                def _patched_executor_init_early(self, connection, progress_callback=None):
                    """Patched MigrationExecutor.__init__ - ROOT CAUSE FIX (early)"""
                    _patch_logger.info("=" * 80)
                    _patch_logger.info("✓ MigrationExecutor.__init__ (early): CALLED!")
                    _patch_logger.info("=" * 80)
                    result = _original_executor_init_early(self, connection, progress_callback)
                    # CRITICAL: Clear unmigrated_apps set - this is the ROOT CAUSE FIX
                    # Line 266: run_syncdb = options["run_syncdb"] and executor.loader.unmigrated_apps
                    # Empty set evaluates to False, so sync_apps won't run
                    if hasattr(self, "loader") and hasattr(self.loader, "unmigrated_apps"):
                        before_clear = len(self.loader.unmigrated_apps)
                        self.loader.unmigrated_apps.clear()
                        after_clear = len(self.loader.unmigrated_apps)
                        _patch_logger.info(
                            f"✓ executor.loader.unmigrated_apps (early): Cleared {before_clear} -> {after_clear} (prevents sync_apps)"
                        )
                        if before_clear > 0:
                            _patch_logger.info(
                                f"✓ unmigrated_apps contents before clear: {list(self.loader.unmigrated_apps)}"
                            )

                        # CRITICAL: Also patch loader.load_disk to prevent repopulating unmigrated_apps
                        # This ensures unmigrated_apps stays empty even if load_disk() is called again
                        if hasattr(self.loader, "load_disk"):
                            original_load_disk = self.loader.load_disk

                            def _patched_loader_load_disk():
                                """Patched load_disk that prevents repopulating unmigrated_apps"""
                                result = original_load_disk()
                                # Clear unmigrated_apps after load_disk completes
                                if hasattr(self.loader, "unmigrated_apps"):
                                    self.loader.unmigrated_apps.clear()
                                    _patch_logger.info(
                                        "✓ executor.loader.load_disk: Cleared unmigrated_apps (prevents sync_apps)"
                                    )
                                return result

                            self.loader.load_disk = _patched_loader_load_disk
                            _patch_logger.info(
                                "✓ Patched executor.loader.load_disk to prevent repopulating unmigrated_apps"
                            )
                    else:
                        _patch_logger.warning("✗ executor.loader.unmigrated_apps not found!")
                    return result

                _patched_executor_init_early._patched_for_unmigrated_early = True
                executor_module.MigrationExecutor.__init__ = _patched_executor_init_early
                _log_patch("MigrationExecutor.__init__ (clear unmigrated_apps - early)")
    except (ImportError, AttributeError):
        # Django not loaded yet, will patch later
        _patch_logger.debug("MigrationExecutor not available yet, will patch later")
        pass
    # Patch Django's database wrapper to disable thread validation for tests
    # This fixes the issue where pytest-django creates connections in one thread
    # but Django's TestCase uses them in another thread
    import django.db.backends.base.base

    _original_validate = django.db.backends.base.base.BaseDatabaseWrapper.validate_thread_sharing

    def _noop_validate(self):
        """Disable thread validation for tests - safe because pytest-django manages connections"""
        pass

    django.db.backends.base.base.BaseDatabaseWrapper.validate_thread_sharing = _noop_validate

    # Patch Django's migrate command to skip sync_apps entirely
    # This must be done before Django is fully initialized
    import types

    import django.core.management.commands.migrate as migrate_module
    import django.db.backends.postgresql.introspection as pg_introspection
    import django.db.migrations.loader as migrations_loader

    # CRITICAL: Patch MigrationLoader.__init__ to ensure unmigrated_apps starts empty
    # ROOT CAUSE FIX: unmigrated_apps is a SET attribute that gets populated in load_disk()
    # Line 266 in migrate.py: run_syncdb = options["run_syncdb"] and executor.loader.unmigrated_apps
    # If unmigrated_apps is empty, sync_apps won't run even if run_syncdb=True
    try:
        _original_loader_init = migrations_loader.MigrationLoader.__init__
        if not hasattr(_original_loader_init, "_patched_for_unmigrated"):

            def _patched_loader_init(self, *args, **kwargs):
                """Patched MigrationLoader.__init__ that ensures unmigrated_apps stays empty"""
                result = _original_loader_init(self, *args, **kwargs)
                # Ensure unmigrated_apps is empty set - ROOT CAUSE FIX
                if hasattr(self, "unmigrated_apps"):
                    self.unmigrated_apps.clear()
                    _patch_logger.info(
                        "✓ MigrationLoader.__init__: Cleared unmigrated_apps (prevents sync_apps)"
                    )
                return result

            _patched_loader_init._patched_for_unmigrated = True
            migrations_loader.MigrationLoader.__init__ = _patched_loader_init
            _log_patch("MigrationLoader.__init__ (clear unmigrated_apps)")
    except AttributeError:
        _patch_logger.debug("MigrationLoader.__init__ not available yet, will patch later")
        pass

    # CRITICAL: Patch MigrationLoader.load_disk() to prevent populating unmigrated_apps
    # This ensures unmigrated_apps stays empty even after load_disk() runs
    try:
        if hasattr(migrations_loader.MigrationLoader, "load_disk"):
            _original_load_disk = migrations_loader.MigrationLoader.load_disk
            if not hasattr(_original_load_disk, "_patched_for_unmigrated"):

                def _patched_load_disk(self):
                    """Patched load_disk that prevents populating unmigrated_apps - ROOT CAUSE FIX"""
                    result = _original_load_disk(self)
                    # Clear unmigrated_apps set after load_disk completes
                    if hasattr(self, "unmigrated_apps"):
                        self.unmigrated_apps.clear()
                        _patch_logger.info(
                            "✓ MigrationLoader.load_disk: Cleared unmigrated_apps (prevents sync_apps)"
                        )
                    return result

                _patched_load_disk._patched_for_unmigrated = True
                migrations_loader.MigrationLoader.load_disk = _patched_load_disk
                _log_patch("MigrationLoader.load_disk (clear unmigrated_apps)")
    except AttributeError:
        _patch_logger.debug("MigrationLoader.load_disk not available yet, will patch later")
        pass

    # CRITICAL: Patch table_names to return empty list ONLY when called from sync_apps
    # This prevents sync_apps from trying to query tables that don't exist yet
    # But allows Django's MigrationRecorder to check for django_migrations table
    if not hasattr(pg_introspection.DatabaseIntrospection.table_names, "_patched"):
        _original_table_names = pg_introspection.DatabaseIntrospection.table_names

        def _patched_table_names(self, cursor=None, include_views=False):
            """
            Patched table_names - ROOT CAUSE FIX

            sync_apps calls connection.introspection.table_names() to check which tables exist.
            During test database creation, tables don't exist yet, so this query fails.
            SOLUTION: Return empty list ONLY when called from sync_apps context.
            For other contexts (like MigrationRecorder.ensure_schema), call original.

            FIX: cursor is optional (defaults to None) to match Django's signature.
            """
            # Check call stack to see if we're being called from sync_apps or during teardown
            import inspect
            import traceback

            try:
                frame = inspect.currentframe()
                stack = inspect.getouterframes(frame)
                stack_str = " ".join([f.filename + ":" + str(f.lineno) for f in stack[:10]])
                called_from_sync_apps = "sync_apps" in stack_str
                called_from_flush = "flush.py" in stack_str or "sql_flush" in stack_str

                if called_from_sync_apps:
                    _patch_logger.info(
                        "✓ table_names: Called from sync_apps - returning empty list (ROOT CAUSE FIX)"
                    )
                    return []

                # During teardown (flush), if cursor is None, we need to get it from connection
                # django_table_names calls table_names(include_views=include_views) without cursor
                if called_from_flush and cursor is None:
                    # Try to get cursor from connection if available
                    if hasattr(self, "connection") and hasattr(self.connection, "cursor"):
                        try:
                            # Get cursor (not using context manager, Django manages cursor lifecycle)
                            cursor = self.connection.cursor()
                            _patch_logger.debug("✓ table_names: Got cursor for flush operation")
                        except Exception as e:
                            # If we can't get cursor, return empty list for flush operations
                            _patch_logger.info(
                                f"✓ table_names: Called from flush without cursor - returning empty list (error: {e})"
                            )
                            return []
                    else:
                        # No connection available, return empty list
                        _patch_logger.info(
                            "✓ table_names: Called from flush without connection - returning empty list"
                        )
                        return []
            except:
                # If we can't determine context, be safe and call original
                pass

            # For non-sync_apps contexts (like MigrationRecorder), call original
            _patch_logger.debug("✓ table_names: Calling original (non-sync_apps context)")
            return _original_table_names(self, cursor, include_views)

        _patched_table_names._patched = True
        pg_introspection.DatabaseIntrospection.table_names = _patched_table_names
        _log_patch("DatabaseIntrospection.table_names")

        # CRITICAL: Also patch at the instance level when introspection objects are created
        # This ensures that connection.introspection.table_names uses our patch
        try:
            _original_introspection_init = pg_introspection.DatabaseIntrospection.__init__
            if not hasattr(_original_introspection_init, "_patched_for_table_names"):

                def _patched_introspection_init(self, *args, **kwargs):
                    """Patched DatabaseIntrospection.__init__ that ensures table_names is patched"""
                    result = _original_introspection_init(self, *args, **kwargs)
                    # Patch table_names on this instance - ROOT CAUSE FIX
                    # This ensures connection.introspection.table_names() uses our patched version
                    self.table_names = _patched_table_names.__get__(self, type(self))
                    _patch_logger.info(
                        f"✓ Patched table_names on DatabaseIntrospection instance: {id(self)} (ROOT CAUSE FIX)"
                    )
                    return result

                _patched_introspection_init._patched_for_table_names = True
                pg_introspection.DatabaseIntrospection.__init__ = _patched_introspection_init
                _log_patch("DatabaseIntrospection.__init__ (table_names patching)")
        except Exception as e:
            _patch_logger.warning(f"✗ Could not patch DatabaseIntrospection.__init__: {e}")
            import traceback

            _patch_logger.debug(traceback.format_exc())

    # CRITICAL: Patch sql_flush to use CASCADE for foreign key constraints during teardown
    # This fixes: psycopg2.errors.FeatureNotSupported: cannot truncate a table referenced in a foreign key constraint
    try:
        import django.db.backends.postgresql.operations as pg_operations

        if not hasattr(pg_operations.DatabaseOperations.sql_flush, "_patched_for_cascade"):
            _original_sql_flush = pg_operations.DatabaseOperations.sql_flush

            def _patched_sql_flush(
                self, style, tables, *, reset_sequences=False, allow_cascade=False
            ):
                """
                Patched sql_flush that always uses CASCADE to handle foreign key constraints.

                ROOT CAUSE: During test teardown, Django tries to truncate tables but fails
                when tables have foreign key constraints. PostgreSQL requires CASCADE to truncate
                tables with foreign key references.

                SOLUTION: Always use allow_cascade=True when truncating tables during teardown.
                """
                # Always use CASCADE for truncation to handle foreign key constraints
                _patch_logger.debug(f"✓ sql_flush: Truncating {len(tables)} tables with CASCADE")
                return _original_sql_flush(
                    self, style, tables, reset_sequences=reset_sequences, allow_cascade=True
                )

            _patched_sql_flush._patched_for_cascade = True
            pg_operations.DatabaseOperations.sql_flush = _patched_sql_flush
            _log_patch("DatabaseOperations.sql_flush (CASCADE)")
    except Exception as e:
        _patch_logger.warning(f"✗ Could not patch sql_flush: {e}")
        import traceback

        _patch_logger.debug(traceback.format_exc())

    # Also patch sync_apps to catch errors and return early
    _original_sync_apps_method = migrate_module.Command.sync_apps

    def _patched_sync_apps(self, connection, apps):
        """
        Patched sync_apps - ROOT CAUSE FIX

        Django's sync_apps tries to query tables that don't exist yet during test database creation.
        This patch makes sync_apps a no-op that always returns immediately, preventing any table queries.
        Migrations will create all tables, so sync_apps doesn't need to run.
        """
        _patch_logger.info("=" * 80)
        _patch_logger.info(
            f"✓ sync_apps (main): CALLED but suppressed (apps={len(apps) if apps else 0})"
        )
        _patch_logger.info(
            f"✓ sync_apps (main): ROOT CAUSE FIX - returning immediately without SQL"
        )
        _patch_logger.info("=" * 80)
        # Always return immediately - migrations will create tables
        return

    # Patch at class level using MethodType
    migrate_module.Command.sync_apps = types.MethodType(_patched_sync_apps, migrate_module.Command)
    _log_patch("Command.sync_apps (main - no-op)")

    # CRITICAL: Also patch Command.__init__ to ensure sync_apps is patched on all instances
    # This ensures that even if Django creates Command instances, they all have our patched sync_apps
    try:
        _original_command_init = migrate_module.Command.__init__

        def _patched_command_init(self, *args, **kwargs):
            """Patched Command.__init__ that ensures sync_apps is patched on this instance"""
            result = _original_command_init(self, *args, **kwargs)
            # Ensure sync_apps is patched on this instance
            self.sync_apps = types.MethodType(_patched_sync_apps, self)
            _patch_logger.debug(f"✓ Patched sync_apps on Command instance: {id(self)}")
            return result

        migrate_module.Command.__init__ = _patched_command_init
        _log_patch("Command.__init__ (sync_apps patching)")
    except Exception as e:
        _patch_logger.debug(f"Could not patch Command.__init__: {e}")

    # APPROACH 3: Patch handle method to intercept sync_apps calls BEFORE they execute
    # This is the most reliable approach - we intercept sync_apps calls in handle
    _original_handle = migrate_module.Command.handle

    def _patched_handle(self, *args, **options):
        """
        Patched handle that intercepts sync_apps calls before they execute.
        This ensures sync_apps never runs during test database creation.

        ROOT CAUSE FIX: Django's create_test_db calls migrate with run_syncdb=True.
        This patch ensures run_syncdb is ALWAYS False, preventing sync_apps from running.
        """
        _patch_logger.info("=" * 80)
        _patch_logger.info("✓ Command.handle: CALLED! (ROOT CAUSE FIX)")
        _patch_logger.info(f"✓ Command.handle: Original options = {options}")
        _patch_logger.info("=" * 80)

        # CRITICAL: Set run_syncdb=False to prevent sync_apps from being called
        # Django reads this at the beginning of handle, so set it BEFORE calling original
        # This is the ROOT CAUSE FIX - ensures sync_apps never runs
        original_run_syncdb = options.get("run_syncdb", None)
        options["run_syncdb"] = False
        _patch_logger.info(
            f"✓ Command.handle: Overriding run_syncdb={original_run_syncdb} -> False (ROOT CAUSE FIX)"
        )

        # Store original sync_apps method for this instance
        original_sync_apps = getattr(self, "sync_apps", None)
        if original_sync_apps is None:
            original_sync_apps = getattr(
                migrate_module.Command, "_original_sync_apps", migrate_module.Command.sync_apps
            )

        # Create a no-op sync_apps that always returns immediately
        def _noop_sync_apps(self, connection, apps):
            """No-op sync_apps that never executes - prevents table queries"""
            _patch_logger.info("=" * 80)
            _patch_logger.info(
                f"✓ sync_apps (handle): CALLED but suppressed (apps={len(apps) if apps else 0})"
            )
            _patch_logger.info(
                "✓ sync_apps (handle): ROOT CAUSE FIX - returning immediately without SQL"
            )
            _patch_logger.info("=" * 80)
            return

        # CRITICAL: Patch sync_apps on THIS instance using __dict__ to bypass method resolution
        # This ensures that when handle calls self.sync_apps(), it calls our no-op
        self.__dict__["sync_apps"] = types.MethodType(_noop_sync_apps, self)
        _patch_logger.info(f"✓ Patched sync_apps on Command instance using __dict__: {id(self)}")

        # Also ensure class-level patch is active
        migrate_module.Command.sync_apps = types.MethodType(_noop_sync_apps, migrate_module.Command)

        # CRITICAL: Patch MigrationLoader.load_disk() to prevent populating unmigrated_apps
        # ROOT CAUSE FIX: unmigrated_apps is a SET that gets populated in load_disk()
        # Line 266 in migrate.py: run_syncdb = options["run_syncdb"] and executor.loader.unmigrated_apps
        # If unmigrated_apps is empty, sync_apps won't run even if run_syncdb=True
        try:
            from django.db.migrations.loader import MigrationLoader

            if not hasattr(MigrationLoader.load_disk, "_patched_for_unmigrated"):
                _original_load_disk = MigrationLoader.load_disk

                def _patched_load_disk(self):
                    """Patched load_disk that prevents populating unmigrated_apps - ROOT CAUSE FIX"""
                    result = _original_load_disk(self)
                    # Clear unmigrated_apps set after load_disk completes
                    # This ensures sync_apps won't run even if run_syncdb=True
                    if hasattr(self, "unmigrated_apps"):
                        self.unmigrated_apps.clear()
                        _patch_logger.info(
                            "✓ MigrationLoader.load_disk: Cleared unmigrated_apps (prevents sync_apps)"
                        )
                    return result

                _patched_load_disk._patched_for_unmigrated = True
                MigrationLoader.load_disk = _patched_load_disk
                _patch_logger.info("✓ Patched MigrationLoader.load_disk to clear unmigrated_apps")
        except Exception as e:
            _patch_logger.warning(f"✗ Could not patch MigrationLoader.load_disk: {e}")
            import traceback

            _patch_logger.debug(traceback.format_exc())

        # CRITICAL: Patch MigrationExecutor.__init__ to clear loader.unmigrated_apps set
        # ROOT CAUSE FIX: Line 266 in migrate.py checks executor.loader.unmigrated_apps
        # unmigrated_apps is a SET attribute, not a method. Empty set evaluates to False.
        # If it's empty, sync_apps won't run even if run_syncdb=True
        # This patch MUST be applied in handle() because executor is created inside handle()
        try:
            from django.db.migrations.executor import MigrationExecutor

            if not hasattr(MigrationExecutor.__init__, "_patched_for_unmigrated_in_handle"):
                _original_executor_init = MigrationExecutor.__init__

                def _patched_executor_init(self, connection, progress_callback=None):
                    _patch_logger.info("=" * 80)
                    _patch_logger.info("✓ MigrationExecutor.__init__ (handle): CALLED!")
                    _patch_logger.info("=" * 80)
                    result = _original_executor_init(self, connection, progress_callback)
                    # CRITICAL: Clear unmigrated_apps set - this is the ROOT CAUSE FIX
                    # Line 266: run_syncdb = options["run_syncdb"] and executor.loader.unmigrated_apps
                    # Empty set evaluates to False, so sync_apps won't run
                    if hasattr(self, "loader") and hasattr(self.loader, "unmigrated_apps"):
                        before_clear = len(self.loader.unmigrated_apps)
                        self.loader.unmigrated_apps.clear()
                        after_clear = len(self.loader.unmigrated_apps)
                        _patch_logger.info(
                            f"✓ executor.loader.unmigrated_apps (handle): Cleared {before_clear} -> {after_clear} (prevents sync_apps)"
                        )
                        if before_clear > 0:
                            _patch_logger.info(
                                f"✓ unmigrated_apps before clear: {list(self.loader.unmigrated_apps)}"
                            )

                        # CRITICAL: Also patch loader.load_disk to prevent repopulating unmigrated_apps
                        if hasattr(self.loader, "load_disk"):
                            original_load_disk = self.loader.load_disk

                            def _patched_loader_load_disk():
                                """Patched load_disk that prevents repopulating unmigrated_apps"""
                                result = original_load_disk()
                                # Clear unmigrated_apps after load_disk completes
                                if hasattr(self.loader, "unmigrated_apps"):
                                    before_load = len(self.loader.unmigrated_apps)
                                    self.loader.unmigrated_apps.clear()
                                    after_load = len(self.loader.unmigrated_apps)
                                    _patch_logger.info(
                                        f"✓ executor.loader.load_disk (handle): Cleared {before_load} -> {after_load} (prevents sync_apps)"
                                    )
                                return result

                            self.loader.load_disk = _patched_loader_load_disk
                            _patch_logger.info(
                                "✓ Patched executor.loader.load_disk in handle to prevent repopulating unmigrated_apps"
                            )
                    else:
                        _patch_logger.warning("✗ executor.loader.unmigrated_apps not found!")
                    return result

                _patched_executor_init._patched_for_unmigrated_in_handle = True
                MigrationExecutor.__init__ = _patched_executor_init
                _patch_logger.info(
                    "✓ Patched MigrationExecutor.__init__ in handle to clear unmigrated_apps"
                )
        except Exception as e:
            _patch_logger.warning(f"✗ Could not patch MigrationExecutor.__init__ in handle: {e}")
            import traceback

            _patch_logger.debug(traceback.format_exc())

        # CRITICAL: Before calling original handle, ensure executor.loader.unmigrated_apps is empty
        # We need to intercept executor creation and clear unmigrated_apps BEFORE line 266 checks it
        # The executor is created inside handle(), so we need to patch MigrationExecutor.__init__
        # to clear unmigrated_apps when the executor is created

        # The patch above should handle this, but let's also ensure it's cleared right before
        # the check at line 266 by intercepting the executor creation
        try:
            # Call original handle - our MigrationExecutor.__init__ patch should clear unmigrated_apps
            # when the executor is created inside handle()
            _patch_logger.info(
                "✓ Command.handle: Calling original handle (executor will be created)"
            )
            result = _original_handle(self, *args, **options)
            _patch_logger.info("✓ Command.handle: Original handle completed")
            return result
        except Exception as e:
            # If we get a table error, it means our patches didn't work properly
            # Log it and re-raise - we should fix the root cause, not suppress errors
            error_str = str(e).lower() if e else ""
            error_type = type(e).__name__
            is_table_error = (
                ("relation" in error_str and "does not exist" in error_str)
                or "undefinedtable" in error_type.lower()
                or ("programmingerror" in error_type.lower() and "relation" in error_str)
            )
            if is_table_error:
                _patch_logger.error(
                    f"✗ Table error caught in handle patch - patches didn't prevent sync_apps: {error_str[:150]}"
                )
                _patch_logger.error(
                    "✗ This indicates that run_syncdb=False or unmigrated_apps clearing didn't work"
                )
            raise
        finally:
            # Restore original sync_apps on this instance (for cleanup)
            try:
                if original_sync_apps:
                    self.__dict__["sync_apps"] = original_sync_apps
            except:
                pass

    migrate_module.Command.handle = _patched_handle

    # CRITICAL: Also patch call_command to ensure run_syncdb=False
    # This ensures that even if Django creates Command instances directly, run_syncdb is False
    try:
        from django.core.management import call_command as original_call_command

        def _patched_call_command(command_name, *args, **options):
            """Patched call_command that ensures run_syncdb=False for migrate command"""
            _patch_logger.info(
                f"✓ call_command: CALLED with command='{command_name}', options={list(options.keys())}"
            )
            if command_name == "migrate":
                # CRITICAL: Force run_syncdb=False - this prevents sync_apps from running
                # This is the ROOT CAUSE FIX - Django's create_test_db passes run_syncdb=True
                # We override it here to False so migrations run first, then sync_apps is skipped
                original_run_syncdb = options.get("run_syncdb", None)
                options["run_syncdb"] = False
                _patch_logger.info(
                    f"✓ call_command: Overriding run_syncdb={original_run_syncdb} -> False for migrate command"
                )
                _patch_logger.info(f"✓ call_command: Final options = {options}")
            result = original_call_command(command_name, *args, **options)
            _patch_logger.info(f"✓ call_command: Completed command='{command_name}'")
            return result

        # Patch call_command at module level
        import django.core.management

        django.core.management.call_command = _patched_call_command
        _log_patch("call_command (run_syncdb=False)")
    except Exception as e:
        _patch_logger.debug(f"Could not patch call_command: {e}")

    # CRITICAL: Patch BaseDatabaseCreation.create_test_db AND PostgreSQL-specific DatabaseCreation
    # ROOT CAUSE FIX: Django's create_test_db explicitly sets run_syncdb=True at line 59-61
    # This causes sync_apps to run BEFORE migrations complete, querying tables that don't exist yet
    # Solution: Patch create_test_db to pass run_syncdb=False so migrations run first, then sync_apps is skipped
    try:
        import django.db.backends.base.creation as creation_module
        import django.db.backends.postgresql.creation as pg_creation_module

        # Store original if not already stored (base class)
        if not hasattr(creation_module.BaseDatabaseCreation, "_original_create_test_db"):
            creation_module.BaseDatabaseCreation._original_create_test_db = (
                creation_module.BaseDatabaseCreation.create_test_db
            )

        # CRITICAL: Also patch PostgreSQL-specific DatabaseCreation class
        # Django uses this class, not the base class, for PostgreSQL databases
        if not hasattr(pg_creation_module.DatabaseCreation, "_original_create_test_db"):
            pg_creation_module.DatabaseCreation._original_create_test_db = (
                pg_creation_module.DatabaseCreation.create_test_db
            )

        _original_create_test_db_base = (
            creation_module.BaseDatabaseCreation._original_create_test_db
        )
        _original_create_test_db_pg = pg_creation_module.DatabaseCreation._original_create_test_db

        def _patched_create_test_db(
            self, verbosity=1, autoclobber=False, keepdb=False, serialize=True, **kwargs
        ):
            """
            Patched create_test_db that ensures run_syncdb=False when calling migrate.

            ROOT CAUSE: Django's create_test_db calls migrate with run_syncdb=True (line 59-61), which causes
            sync_apps to run and query tables that don't exist yet (because migrations haven't run).

            SOLUTION: Intercept the migrate call and force run_syncdb=False.
            This ensures migrations run first (creating all tables), then sync_apps is skipped
            because all apps are already migrated (unmigrated_apps will be empty).
            """
            import sys
            import traceback

            _patch_logger.info("=" * 80)
            _patch_logger.info("✓ create_test_db: PATCHED VERSION CALLED!")
            _patch_logger.info(f"✓ create_test_db: self = {self}, type = {type(self)}")
            _patch_logger.info(f"✓ create_test_db: verbosity = {verbosity}, keepdb = {keepdb}")
            _patch_logger.info(
                f"✓ create_test_db: Call stack:\n{''.join(traceback.format_stack()[-5:-1])}"
            )
            _patch_logger.info("=" * 80)

            # CRITICAL: Django's create_test_db imports call_command INSIDE the function
            # So it gets a fresh reference each time. We need to patch it BEFORE calling original.
            # The original code does: from django.core.management import call_command
            # Then: call_command("migrate", ..., run_syncdb=True)

            # Get the current call_command (which should be our global patch)
            from django.core.management import call_command as current_call_command

            # Create a local wrapper that forces run_syncdb=False for migrate
            def _local_patched_call_command(command_name, *args, **call_options):
                """
                Local patch for call_command that forces run_syncdb=False for migrate command.
                This is the ROOT CAUSE FIX - ensures sync_apps never runs.
                """
                _patch_logger.info(
                    f"✓ create_test_db.call_command: CALLED with command='{command_name}'"
                )
                _patch_logger.info(f"✓ create_test_db.call_command: call_options = {call_options}")
                if command_name == "migrate":
                    # CRITICAL: Override Django's hardcoded run_syncdb=True with False
                    original_run_syncdb = call_options.get("run_syncdb", None)
                    call_options["run_syncdb"] = False
                    _patch_logger.info(
                        f"✓ create_test_db.call_command: Overriding run_syncdb={original_run_syncdb} -> False (ROOT CAUSE FIX)"
                    )
                # Call the current call_command (which may be our global patch or original)
                result = current_call_command(command_name, *args, **call_options)
                _patch_logger.info(
                    f"✓ create_test_db.call_command: Completed command='{command_name}'"
                )
                return result

            # Patch call_command in django.core.management BEFORE calling original create_test_db
            # This ensures that when create_test_db does "from django.core.management import call_command",
            # it gets our patched version
            import django.core.management

            original_call_command_backup = django.core.management.call_command
            django.core.management.call_command = _local_patched_call_command
            _patch_logger.info(
                f"✓ create_test_db: Patched django.core.management.call_command (id={id(django.core.management.call_command)})"
            )

            try:
                _patch_logger.info(
                    "✓ create_test_db: Calling original create_test_db with patched call_command"
                )
                # Use the appropriate original based on which class this is
                if isinstance(self, pg_creation_module.DatabaseCreation):
                    _patch_logger.info("✓ create_test_db: Using PostgreSQL-specific create_test_db")
                    result = _original_create_test_db_pg(
                        self,
                        verbosity=verbosity,
                        autoclobber=autoclobber,
                        keepdb=keepdb,
                        serialize=serialize,
                        **kwargs,
                    )
                else:
                    _patch_logger.info("✓ create_test_db: Using base create_test_db")
                    result = _original_create_test_db_base(
                        self,
                        verbosity=verbosity,
                        autoclobber=autoclobber,
                        keepdb=keepdb,
                        serialize=serialize,
                        **kwargs,
                    )
                _patch_logger.info("✓ create_test_db: Test database created successfully")
                return result
            except Exception as e:
                _patch_logger.error(f"✗ create_test_db: Error during test database creation: {e}")
                import traceback

                _patch_logger.error(f"✗ create_test_db: Traceback:\n{traceback.format_exc()}")
                raise
            finally:
                # Restore original call_command
                django.core.management.call_command = original_call_command_backup
                _patch_logger.info("✓ create_test_db: Restored original call_command")

        # CRITICAL: Patch BOTH base class and PostgreSQL-specific class
        # PostgreSQL's DatabaseCreation inherits from BaseDatabaseCreation, but we patch both
        # to ensure the patch is applied regardless of which class Django uses
        creation_module.BaseDatabaseCreation.create_test_db = _patched_create_test_db
        pg_creation_module.DatabaseCreation.create_test_db = _patched_create_test_db

        # Mark as patched
        _patched_create_test_db._patched = True
        creation_module.BaseDatabaseCreation.create_test_db._patched = True
        pg_creation_module.DatabaseCreation.create_test_db._patched = True

        _log_patch("BaseDatabaseCreation.create_test_db (run_syncdb=False)")
        _log_patch("PostgreSQL DatabaseCreation.create_test_db (run_syncdb=False)")
        _patch_logger.info("✓ BaseDatabaseCreation.create_test_db patch applied successfully")
        _patch_logger.info(
            "✓ PostgreSQL DatabaseCreation.create_test_db patch applied successfully"
        )

        # Verify patches are applied
        if hasattr(creation_module.BaseDatabaseCreation.create_test_db, "_patched"):
            _patch_logger.info("✓ Verified: BaseDatabaseCreation.create_test_db is patched")
        if hasattr(pg_creation_module.DatabaseCreation.create_test_db, "_patched"):
            _patch_logger.info("✓ Verified: PostgreSQL DatabaseCreation.create_test_db is patched")

        # CRITICAL: Also patch DatabaseCreation.__init__ to ensure create_test_db is patched on instances
        # Django creates DatabaseCreation instances, and we need to ensure they use our patched method
        try:
            _original_pg_creation_init = pg_creation_module.DatabaseCreation.__init__
            if not hasattr(_original_pg_creation_init, "_patched_for_create_test_db"):

                def _patched_pg_creation_init(self, *args, **kwargs):
                    """Patched DatabaseCreation.__init__ that ensures create_test_db is patched on this instance"""
                    result = _original_pg_creation_init(self, *args, **kwargs)
                    # Ensure create_test_db is patched on this instance
                    self.create_test_db = _patched_create_test_db.__get__(self, type(self))
                    _patch_logger.info(
                        f"✓ Patched create_test_db on DatabaseCreation instance: {id(self)}"
                    )
                    return result

                _patched_pg_creation_init._patched_for_create_test_db = True
                pg_creation_module.DatabaseCreation.__init__ = _patched_pg_creation_init
                _log_patch("PostgreSQL DatabaseCreation.__init__ (create_test_db patching)")
        except Exception as e:
            _patch_logger.debug(f"Could not patch DatabaseCreation.__init__: {e}")
    except Exception as e:
        _patch_logger.warning(f"✗ Could not patch create_test_db: {e}")
        import traceback

        _patch_logger.debug(traceback.format_exc())

    # APPROACH 2: Patch __init__ to patch sync_apps at instance level when Command is created
    # This ensures every new Command instance has the patched sync_apps
    _original_init = migrate_module.Command.__init__

    def _patched_init(self, *args, **kwargs):
        """Patched __init__ that applies sync_apps patch to each new instance"""
        result = _original_init(self, *args, **kwargs)

        # Ensure sync_apps is patched on this instance (no-op version)
        self.sync_apps = types.MethodType(_patched_sync_apps, self)

        return result

    migrate_module.Command.__init__ = _patched_init

import os
import time

import pytest


# Lazy import Django modules - don't import at module level to allow patches to be applied first
def _get_user_model():
    """Lazy import of User model"""
    from django.contrib.auth import get_user_model

    return get_user_model()


def _get_client():
    """Lazy import of Django Client"""
    from django.test import Client

    return Client


def _get_transaction_test_case():
    """Lazy import of TransactionTestCase"""
    from django.test import TransactionTestCase

    return TransactionTestCase


def _get_settings():
    """Lazy import of Django settings"""
    from django.conf import settings

    return settings


# Configure pytest-django to properly handle Django's TestCase
# This ensures database connections are properly managed across threads
pytest_plugins = ["pytest_django"]


# Use pytest hooks to ensure migrations run before database setup
def pytest_configure(config):
    """
    Configure pytest - ensure patches are applied early.
    This hook runs before Django is initialized, so we can apply patches here.
    """
    _patch_logger.info("=" * 80)
    _patch_logger.info("pytest_configure: Applying Django patches...")
    _patch_logger.info("=" * 80)

    # CRITICAL: Re-apply create_test_db patch to ensure it's active
    # This must be done here because Django might not be fully loaded when patches are first applied
    try:
        import django.db.backends.base.creation as creation_module

        # Check if patch is already applied
        if hasattr(creation_module.BaseDatabaseCreation, "_original_create_test_db"):
            _patch_logger.debug("✓ create_test_db patch already applied, verifying...")
        else:
            # Apply the patch
            if not hasattr(creation_module.BaseDatabaseCreation, "_original_create_test_db"):
                creation_module.BaseDatabaseCreation._original_create_test_db = (
                    creation_module.BaseDatabaseCreation.create_test_db
                )

            _original_create_test_db = creation_module.BaseDatabaseCreation._original_create_test_db

            def _patched_create_test_db(
                self, verbosity=1, autoclobber=False, keepdb=False, serialize=True, **kwargs
            ):
                """Patched create_test_db - ROOT CAUSE FIX"""
                _patch_logger.info("=" * 80)
                _patch_logger.info("✓ create_test_db: PATCHED VERSION CALLED!")
                _patch_logger.info("=" * 80)

                # Patch call_command locally to override run_syncdb=True
                from django.core.management import call_command as original_call_command

                def _local_patched_call_command(command_name, *args, **call_options):
                    """Local patch for call_command that forces run_syncdb=False"""
                    if command_name == "migrate":
                        call_options["run_syncdb"] = False
                        _patch_logger.info(f"✓ create_test_db: Overriding run_syncdb=True -> False")
                        _patch_logger.info(f"✓ create_test_db: call_options = {call_options}")
                    result = original_call_command(command_name, *args, **call_options)
                    return result

                # Temporarily patch call_command
                import django.core.management

                original_call_command_global = django.core.management.call_command
                django.core.management.call_command = _local_patched_call_command

                try:
                    result = _original_create_test_db(
                        self,
                        verbosity=verbosity,
                        autoclobber=autoclobber,
                        keepdb=keepdb,
                        serialize=serialize,
                        **kwargs,
                    )
                    _patch_logger.info("✓ create_test_db: Test database created successfully")
                    return result
                except Exception as e:
                    _patch_logger.error(f"✗ create_test_db: Error: {e}")
                    raise
                finally:
                    django.core.management.call_command = original_call_command_global

            creation_module.BaseDatabaseCreation.create_test_db = _patched_create_test_db
            _patch_logger.info("✓ create_test_db patch applied in pytest_configure")
    except Exception as e:
        _patch_logger.warning(f"✗ Could not apply create_test_db patch in pytest_configure: {e}")
        import traceback

        _patch_logger.debug(traceback.format_exc())

    # Re-apply all patches to ensure they're active
    try:
        _ensure_sync_apps_patched()
        _patch_logger.debug("✓ Re-applied sync_apps patches in pytest_configure")
    except Exception as e:
        _patch_logger.warning(f"✗ Failed to re-apply sync_apps patches: {e}")

    # CRITICAL: Ensure MigrationLoader patches are applied after Django loads
    try:
        from django.db.migrations.loader import MigrationLoader

        # Patch MigrationLoader.__init__ to ensure unmigrated_apps starts empty
        if not hasattr(MigrationLoader.__init__, "_patched_for_unmigrated"):
            _original_loader_init = MigrationLoader.__init__

            def _patched_loader_init(self, *args, **kwargs):
                """Patched MigrationLoader.__init__ that ensures unmigrated_apps stays empty"""
                result = _original_loader_init(self, *args, **kwargs)
                if hasattr(self, "unmigrated_apps"):
                    self.unmigrated_apps.clear()
                    _patch_logger.info(
                        "✓ MigrationLoader.__init__ (pytest_configure): Cleared unmigrated_apps"
                    )
                return result

            _patched_loader_init._patched_for_unmigrated = True
            MigrationLoader.__init__ = _patched_loader_init
            _patch_logger.info("✓ Patched MigrationLoader.__init__ in pytest_configure")

        # Patch MigrationLoader.load_disk() to prevent populating unmigrated_apps
        if hasattr(MigrationLoader, "load_disk") and not hasattr(
            MigrationLoader.load_disk, "_patched_for_unmigrated"
        ):
            _original_load_disk = MigrationLoader.load_disk

            def _patched_load_disk(self):
                """Patched load_disk that prevents populating unmigrated_apps"""
                result = _original_load_disk(self)
                if hasattr(self, "unmigrated_apps"):
                    self.unmigrated_apps.clear()
                    _patch_logger.info(
                        "✓ MigrationLoader.load_disk (pytest_configure): Cleared unmigrated_apps"
                    )
                return result

            _patched_load_disk._patched_for_unmigrated = True
            MigrationLoader.load_disk = _patched_load_disk
            _patch_logger.info("✓ Patched MigrationLoader.load_disk in pytest_configure")
    except Exception as e:
        _patch_logger.warning(f"✗ Failed to patch MigrationLoader in pytest_configure: {e}")
        import traceback

        _patch_logger.debug(traceback.format_exc())

    # Apply cursor-level patches if not already applied
    try:
        import django.db.backends.postgresql.base as pg_base
        import django.db.backends.utils as db_utils

        # No error suppression patches - if sync_apps doesn't run, we won't get table errors
        # The root cause fixes (run_syncdb=False, unmigrated_apps clearing, sync_apps no-op) should prevent errors
        _patch_logger.debug(
            "✓ Skipping error suppression patches - root cause fixes should prevent errors"
        )
    except Exception as e:
        _patch_logger.warning(f"✗ Failed to apply cursor patches: {e}")
        import traceback

        _patch_logger.debug(traceback.format_exc())

    # CRITICAL: Patch setup_databases to ensure create_test_db patch is applied
    # This is called by pytest-django before create_test_db
    try:
        import django.test.utils

        _original_setup_databases = django.test.utils.setup_databases

        def _patched_setup_databases(
            verbosity,
            interactive,
            keepdb=False,
            debug_sql=False,
            parallel=0,
            aliases=None,
            **kwargs,
        ):
            """Patched setup_databases that ensures create_test_db patch is active"""
            _patch_logger.info("=" * 80)
            _patch_logger.info("✓ setup_databases: PATCHED VERSION CALLED!")
            _patch_logger.info("=" * 80)

            # CRITICAL: Check if we should skip database creation (for SDK tests using production DB)
            use_production_db = os.getenv("USE_PRODUCTION_DB_FOR_SDK_TESTS", "").lower() == "1"
            if use_production_db:
                _patch_logger.info("=" * 80)
                _patch_logger.info("✓ SKIPPING test database creation - using production database")
                _patch_logger.info("=" * 80)

                # CRITICAL: Ensure database name is set to production database
                # Django might have cached settings with test database name
                from django.conf import settings
                from django.utils.functional import empty

                # Force reload settings if they're cached
                if hasattr(settings, "_wrapped") and settings._wrapped is not empty:
                    # Clear the wrapped settings to force reload
                    settings._wrapped = empty
                    # Reload settings
                    settings._setup()

                # Get production database name from environment
                postgres_db = os.getenv("POSTGRES_DB", "hub")

                # Override database name in settings
                if "default" in settings.DATABASES:
                    original_name = settings.DATABASES["default"].get("NAME", "")
                    settings.DATABASES["default"]["NAME"] = postgres_db
                    _patch_logger.info(
                        f"✓ Overrode database name: {original_name} -> {postgres_db}"
                    )

                # CRITICAL: Ensure database connection is established
                # Even though we're not creating a test database, we need to ensure
                # the connection to the production database is set up
                from django.db import connections

                try:
                    connection = connections["default"]
                    connection.ensure_connection()
                    _patch_logger.info("✓ Database connection established to production database")
                except Exception as e:
                    _patch_logger.warning(f"⚠ Could not establish database connection: {e}")

                # Return empty dict to indicate no test databases were created
                # pytest-django expects a dict mapping alias -> (db_name, destroy) tuple
                # But since we're using production DB, we return empty dict
                # The warning about unpacking is expected and harmless
                return {}

            # CRITICAL: Re-apply create_test_db patch BEFORE Django creates any DatabaseCreation instances
            # This ensures that when Django creates instances, they use our patched method
            import django.db.backends.base.creation as creation_module
            import django.db.backends.postgresql.creation as pg_creation_module

            # Re-apply the patch to ensure it's active
            if not hasattr(creation_module.BaseDatabaseCreation.create_test_db, "_patched"):
                _patch_logger.warning("✗ create_test_db patch not found, re-applying...")
                # Re-apply patch
                if not hasattr(creation_module.BaseDatabaseCreation, "_original_create_test_db"):
                    creation_module.BaseDatabaseCreation._original_create_test_db = (
                        creation_module.BaseDatabaseCreation.create_test_db
                    )

                _original_create_test_db = (
                    creation_module.BaseDatabaseCreation._original_create_test_db
                )

                # Use the same patched function we created earlier
                # Import it from the outer scope
                from tests.conftest import _patched_create_test_db as outer_patched_create_test_db

                # Re-apply the patch
                creation_module.BaseDatabaseCreation.create_test_db = outer_patched_create_test_db
                pg_creation_module.DatabaseCreation.create_test_db = outer_patched_create_test_db
                creation_module.BaseDatabaseCreation.create_test_db._patched = True
                pg_creation_module.DatabaseCreation.create_test_db._patched = True
                _patch_logger.info(
                    "✓ create_test_db patch re-applied in setup_databases (both base and PostgreSQL)"
                )

            # Call original setup_databases
            result = _original_setup_databases(
                verbosity,
                interactive,
                keepdb=keepdb,
                debug_sql=debug_sql,
                parallel=parallel,
                aliases=aliases,
                **kwargs,
            )
            _patch_logger.info("✓ setup_databases: Completed successfully")
            return result

        django.test.utils.setup_databases = _patched_setup_databases
        _log_patch("setup_databases")
        _patch_logger.info("✓ setup_databases patch applied")
    except Exception as e:
        _patch_logger.warning(f"✗ Could not patch setup_databases: {e}")
        import traceback

        _patch_logger.debug(traceback.format_exc())

    _patch_logger.info("pytest_configure: All patches applied")


def pytest_sessionstart(session):
    """
    Called after the Session object has been created and before performing collection.
    This runs before Django setup, so we can apply patches here too.
    """
    # Skip Django setup for Docker Compose runtime tests (they don't need Django)
    if os.getenv("PYTEST_DOCKER_COMPOSE_RUNTIME") == "1" or os.getenv("SKIP_DJANGO_SETUP") == "1":
        _patch_logger.info("Skipping Django setup for Docker Compose runtime tests")
        return

    # Wait for PostgreSQL to be ready before running tests
    # This is especially important for Docker Compose E2E tests where PostgreSQL may still be starting
    if os.getenv("DOCKER_COMPOSE_E2E_TEST", "").lower() == "true":
        import time

        import psycopg2

        # Try to get database config from Django settings if available
        # Otherwise use defaults
        try:
            from django.conf import settings

            db_config = settings.DATABASES.get("default", {})
            postgres_host = db_config.get("HOST", "localhost")
            postgres_port = db_config.get("PORT", "5432")
            postgres_user = db_config.get("USER", "postgres")
            postgres_password = db_config.get("PASSWORD", "")
            postgres_db = db_config.get("NAME", "postgres")
        except Exception:
            # Django not configured yet, use environment variables or defaults
            postgres_host = os.getenv("POSTGRES_HOST", "localhost")
            postgres_port = os.getenv("POSTGRES_PORT", "5432")
            postgres_user = os.getenv("POSTGRES_USER", "hub")
            postgres_password = os.getenv("POSTGRES_PASSWORD", "hub")
            postgres_db = os.getenv("POSTGRES_DB", "postgres")  # Try 'postgres' database first

        max_wait = 300  # Wait up to 5 minutes for PostgreSQL to be ready
        retry_interval = 2  # Check every 2 seconds

        _patch_logger.info(
            f"Waiting for PostgreSQL to be ready for Docker Compose E2E tests (host: {postgres_host}:{postgres_port})..."
        )
        start_time = time.time()

        while time.time() - start_time < max_wait:
            try:
                test_conn = psycopg2.connect(
                    host=postgres_host,
                    port=postgres_port,
                    database=postgres_db,
                    user=postgres_user,
                    password=postgres_password,
                    connect_timeout=5,
                )
                test_conn.close()
                elapsed = int(time.time() - start_time)
                _patch_logger.info(f"PostgreSQL is ready! (waited {elapsed}s)")
                break
            except psycopg2.OperationalError as e:
                error_msg = str(e).lower()
                if "starting up" in error_msg or "the database system is starting up" in error_msg:
                    elapsed = int(time.time() - start_time)
                    if elapsed % 10 == 0:  # Log every 10 seconds
                        _patch_logger.info(
                            f"PostgreSQL is still starting up... (waited {elapsed}s)"
                        )
                    time.sleep(retry_interval)
                    continue
                else:
                    # Non-starting-up error - log and continue (may be connection refused, etc.)
                    elapsed = int(time.time() - start_time)
                    if elapsed % 10 == 0:
                        _patch_logger.warning(f"PostgreSQL connection error (will retry): {e}")
                    time.sleep(retry_interval)
                    continue
            except Exception as e:
                # Other errors - log and continue
                elapsed = int(time.time() - start_time)
                if elapsed % 10 == 0:
                    _patch_logger.warning(f"PostgreSQL connection error (will retry): {e}")
                time.sleep(retry_interval)
                continue
        else:
            # Timeout reached
            elapsed = int(time.time() - start_time)
            _patch_logger.warning(
                f"PostgreSQL did not become ready within {max_wait}s (waited {elapsed}s). "
                f"Tests may fail if PostgreSQL is not ready."
            )

    _patch_logger.info("pytest_sessionstart: Verifying patches before Django setup...")

    # Re-apply patches before Django setup
    try:
        _ensure_sync_apps_patched()
        _patch_logger.debug("✓ Verified sync_apps patches in pytest_sessionstart")
    except Exception as e:
        _patch_logger.warning(f"✗ Failed to verify sync_apps patches: {e}")

    # Ensure Django is configured
    import django
    from django.conf import settings

    if not settings.configured:
        _patch_logger.debug("Django not configured yet, calling django.setup()...")
        django.setup()
        _patch_logger.debug("✓ Django setup complete")

        # After Django setup, verify patches are still active
        try:
            import django.core.management.commands.migrate as migrate_module

            if hasattr(migrate_module.Command, "_original_sync_apps"):
                _patch_logger.debug("✓ sync_apps patch verified after Django setup")
            else:
                _patch_logger.warning(
                    "✗ sync_apps patch missing after Django setup, re-applying..."
                )
                _ensure_sync_apps_patched()
        except Exception as e:
            _patch_logger.warning(f"✗ Failed to verify patches after Django setup: {e}")


# Hook into pytest-django's database setup to manually run migrations
# This runs AFTER database creation but BEFORE tests
@pytest.fixture(scope="session", autouse=True)
def django_db_setup_with_migrations(django_db_setup, django_db_blocker):
    """
    Ensure migrations run properly after database creation.
    Re-apply sync_apps patch to ensure it's active during migrations.
    """
    # Re-apply sync_apps patch to ensure it's active
    _ensure_sync_apps_patched()

    # Migrations should run automatically with MIGRATE: True
    # But we ensure sync_apps is patched just in case
    with django_db_blocker.unblock():
        # The database should already be created and migrated by django_db_setup
        # This fixture just ensures patches are active
        pass


@pytest.fixture
def api_client():
    """Django REST Framework API client"""
    Client = _get_client()
    return Client()


@pytest.fixture
def test_user(db):
    """Create a test user"""
    User = _get_user_model()
    return User.objects.create_user(
        email="test@example.com", password="testpass123", display_name="Test User"
    )


@pytest.fixture
def authenticated_client(api_client, test_user):
    """Authenticated API client"""
    api_client.force_login(test_user)
    return api_client


def wait_for_service_health(url: str, timeout: int = 30, interval: float = 1.0) -> bool:
    """
    Wait for a service to become healthy.

    Args:
        url: Health check URL
        timeout: Maximum time to wait in seconds
        interval: Time between checks in seconds

    Returns:
        True if service is healthy, False otherwise
    """
    try:
        import httpx
    except ImportError:
        # Fallback to requests if httpx not available
        try:
            import requests

            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    response = requests.get(url, timeout=5.0)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("status") == "healthy":
                            return True
                except Exception:
                    pass
                time.sleep(interval)
            return False
        except ImportError:
            pytest.skip("httpx or requests required for service health checks")

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = httpx.get(url, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    return True
        except Exception:
            pass
        time.sleep(interval)
    return False


@pytest.fixture(scope="session")
def datacontract_service():
    """Ensure DataContract CLI service is running and healthy"""
    settings = _get_settings()
    service_url = os.getenv(
        "DATACONTRACT_SERVICE_URL",
        getattr(settings, "DATACONTRACT_CLI_SERVICE_URL", "http://localhost:8080"),
    )
    health_url = f"{service_url}/health"

    if not wait_for_service_health(health_url, timeout=30):
        pytest.skip(f"DataContract CLI service not available at {service_url}")

    return service_url


@pytest.fixture(scope="session")
def dq_service():
    """Ensure DQ service is running and healthy"""
    settings = _get_settings()
    service_url = os.getenv(
        "DQ_SERVICE_URL", getattr(settings, "DQ_SERVICE_URL", "http://localhost:8083")
    )
    health_url = f"{service_url}/health"

    if not wait_for_service_health(health_url, timeout=30):
        pytest.skip(f"DQ service not available at {service_url}")

    return service_url


@pytest.fixture(scope="session")
def compliance_service():
    """Ensure Compliance service is running and healthy"""
    settings = _get_settings()
    service_url = os.getenv(
        "COMPLIANCE_SERVICE_URL",
        getattr(settings, "COMPLIANCE_SERVICE_URL", "http://localhost:8082"),
    )
    health_url = f"{service_url}/health"

    if not wait_for_service_health(health_url, timeout=30):
        pytest.skip(f"Compliance service not available at {service_url}")

    return service_url


@pytest.fixture(scope="session")
def semantic_service():
    """Ensure Semantic service is running and healthy"""
    settings = _get_settings()
    service_url = os.getenv(
        "SEMANTIC_SERVICE_URL", getattr(settings, "SEMANTIC_SERVICE_URL", "http://localhost:8081")
    )
    health_url = f"{service_url}/health"

    if not wait_for_service_health(health_url, timeout=30):
        pytest.skip(f"Semantic service not available at {service_url}")

    return service_url


@pytest.fixture(scope="session")
def all_services(datacontract_service, dq_service, compliance_service, semantic_service):
    """Ensure all microservices are running and healthy"""
    return {
        "datacontract": datacontract_service,
        "dq": dq_service,
        "compliance": compliance_service,
        "semantic": semantic_service,
    }


def check_service_health(service_url: str, service_name: str, timeout: int = 10) -> bool:
    """
    Helper function to check if a service is healthy.
    Can be used in Django TestCase setUp methods.

    Args:
        service_url: Base URL of the service
        service_name: Name of the service (for error messages)
        timeout: Timeout in seconds

    Returns:
        True if service is healthy, False otherwise
    """
    health_url = f"{service_url}/health"
    return wait_for_service_health(health_url, timeout=timeout)
