# Security policy

## Supported code

Security fixes target the current `main` branch and the source-run
PySide6/QML client. The React/Tauri tree is experimental. This project does not
currently publish or support downloadable DMG, ZIP, or other precompiled
releases.

## Report a vulnerability privately

Use the repository's **Security → Report a vulnerability** flow when GitHub
Private Vulnerability Reporting is available. If it is unavailable, contact a
maintainer through a private channel shown on the repository owner profile.
Do not open a public issue containing exploit steps, secrets, card data, or a
working bypass.

Please include:

- the affected commit and platform;
- the smallest reproducible description;
- expected and actual behavior;
- security impact and required user interaction;
- sanitized logs or a proof of concept with all identifiers and keys removed;
- any suggested mitigation.

Maintainers aim to acknowledge a complete report within seven days. A fix and
disclosure schedule will depend on severity, hardware availability, and the
need to coordinate with upstream projects.

## High-impact areas

Reports are especially valuable when they involve:

- bypassing the dangerous-operation capability gate;
- executing commands outside the backend allowlist;
- shell, argument, path, or script injection;
- unsafe card writes, incomplete backups, or false verification success;
- exposure of card dumps, keys, device identifiers, logs, or local workspaces;
- integrity-manifest, update-source, build, signing, or provenance failures;
- malformed import files causing code execution or unintended file access.

Test only on devices and cards you own or are explicitly authorized to assess.
Use expendable media for write-path research. Never submit live credentials,
production access cards, personal keys, signing material, or unredacted serial
captures.

This operational guidance does not add a field-of-use restriction to the MIT
license.
