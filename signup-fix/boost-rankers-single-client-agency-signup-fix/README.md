# Boost Rankers — Single Client + Agency Signup Fix

## Signup behavior
- Single Client / Business Owner: creates a private workspace and exactly one Client record owned by the signup email.
- Agency: creates an agency workspace with `agency_admin` role and can add/manage multiple clients.
- Public signup cannot choose privileged roles such as super_admin, manager, or seo_specialist.
- Existing client/agency application modules remain available; this patch only changes signup tenancy and client-management boundaries.
- No database migration is required because the client-owner mapping is derived from the new private company plus the Client email.

## Files
- backend/services/auth_service.py
- backend/schemas/auth.py
- backend/routers/clients.py
- frontend/src/components/AuthProvider.tsx
- frontend/src/components/AuthScreen.tsx

## Deployment
Copy only these files into the corresponding project paths, run the backend compile check, then build the frontend. Commit only these files.
