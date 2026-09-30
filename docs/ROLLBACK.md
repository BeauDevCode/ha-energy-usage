# Rollback

Keep the exact prior reviewed archive, its commit and SHA-256, the prior component tree, and a protected pre-change supported Home Assistant backup. Backups can contain provider credentials.

Unload Energy Usage through supported Home Assistant controls. Restore the exact prior `/config/custom_components/energy_usage/` tree, or restore the supported backup if the older code cannot understand the current config entry or ledger schema. Run `ha core check`, perform one planned restart, and verify authentication, freshness, statistics, repairs, and a bounded sanitized log.

Replacing Python files does not reverse config-entry migrations, entity-registry changes, private ledger changes, or external statistics already written to Recorder. Removing Energy Usage does not delete Recorder history. Preserve that history by default. Never delete private ledgers, `.storage` records, Recorder tables, or statistics as a routine rollback step; any historical deletion is a separate deliberate Home Assistant operation.

If transitioning from the older `entergy_mobile` component, restore its exact saved tree only to its own directory. Never copy Energy Usage files over that directory, and never run both integrations against the same account at once.
