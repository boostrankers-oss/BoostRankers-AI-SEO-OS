Boost Rankers AI SEO OS - Agency Workspace Switcher

Files:
- frontend/src/App.tsx
- frontend/src/components/AuthProvider.tsx
- frontend/src/lib/api.ts
- backend/api/deps/current_user.py

Behavior:
- Agency users get a workspace selector.
- Agency workspace uses the agency company.
- Selecting a managed client stores boost_workspace_client_id.
- API sends X-Workspace-Client-ID for module requests, while /api/clients and /api/auth remain in their normal context.
- Backend validates ownership or active agency_client_access before changing request-scoped company context.
- No client company_id is changed.
- Standalone client users do not get the agency switcher.

Important: modules that bypass get_current_company and directly query a hard-coded/current_user company_id should be tested after installation; the dependency also updates the request-scoped current_user.company_id to the selected workspace.
