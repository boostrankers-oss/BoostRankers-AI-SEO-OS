# Agency → Client Invitation & Access

Backend: client invitation workflow, secure single-use hashed tokens, private client workspaces, existing-client connection, active/disabled/revoked agency access.
Frontend: agency Clients UI with Add & Invite, Connect Existing, access controls, and copyable invitation link.

Migration: c91a7f4d2e10 (from b6d4e9c2a731).

Important: email delivery is intentionally represented as copy-link because the current project does not have a verified transactional email provider configured. The invitation is not logged or returned with its raw token except at creation time.
