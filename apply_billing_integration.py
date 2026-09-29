from __future__ import annotations

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
PATCH = Path(__file__).resolve().parent


def backup(path: Path) -> None:
    backup_path = path.with_suffix(path.suffix + ".billing.bak")
    if not backup_path.exists():
        shutil.copy2(path, backup_path)


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one marker in {path}: {count} matches")
    backup(path)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_line_once(path: Path, line: str) -> None:
    text = path.read_text(encoding="utf-8")
    if line in text:
        return
    backup(path)
    suffix = "" if text.endswith("\n") else "\n"
    path.write_text(text + suffix + line + "\n", encoding="utf-8")


# Copy new backend/frontend files.
for relative in [
    "models/billing.py",
    "schemas/billing.py",
    "services/billing_service.py",
    "routers/billing.py",
    "alembic/versions/d4b8e1f9a7c2_add_billing_subscription_payment_system.py",
]:
    source = PATCH / "backend" / relative
    target = BACKEND / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        backup(target)
    shutil.copy2(source, target)

for relative in [
    "components/Billing.tsx",
    "components/AdminBillingSettings.tsx",
    "components/AdminPaymentRecords.tsx",
]:
    source = PATCH / "frontend" / "src" / relative
    target = FRONTEND / "src" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        backup(target)
    shutil.copy2(source, target)

# Backend requirements.
requirements = BACKEND / "requirements.txt"
if requirements.exists():
    append_line_once(requirements, "qrcode[pil]>=8.2")
else:
    shutil.copy2(PATCH / "backend" / "requirements.billing.txt", BACKEND / "requirements.billing.txt")

# main.py: add billing routers next to the existing admin router.
main = BACKEND / "main.py"
replace_once(
    main,
    "from routers import admin_account_management\n",
    "from routers import admin_account_management\nfrom routers.billing import router as billing_router, admin_router as admin_billing_router\n",
)
replace_once(
    main,
    'app.include_router(\n    admin_account_management.router,\n    prefix="/api",\n    tags=["Super Admin Account Management"],\n)\n',
    'app.include_router(\n    admin_account_management.router,\n    prefix="/api",\n    tags=["Super Admin Account Management"],\n)\n\napp.include_router(\n    billing_router,\n    prefix="/api",\n    tags=["Billing"],\n)\n\napp.include_router(\n    admin_billing_router,\n    prefix="/api",\n    tags=["Super Admin Billing"],\n)\n',
)

# Auth: initialize a subscription only for a newly-created company.
auth = BACKEND / "services" / "auth_service.py"
replace_once(
    auth,
    "from models.audit_log import AuditLog\n",
    "from models.audit_log import AuditLog\nfrom services.billing_service import initialize_new_signup\n",
)
replace_once(
    auth,
    "            company = None\n\n            if data.company_name:\n",
    "            company = None\n            created_company = False\n\n            if data.company_name:\n",
)
replace_once(
    auth,
    "                    company = self._create_company(\n                        data.company_name\n                    )\n\n            # --------------------------------------------\n            # Role\n",
    "                    company = self._create_company(\n                        data.company_name\n                    )\n                    created_company = True\n\n            if created_company and company is not None:\n                initialize_new_signup(\n                    self.db,\n                    company,\n                    data.account_type,\n                )\n\n            # --------------------------------------------\n            # Role\n",
)

# Frontend app navigation.
app = FRONTEND / "src" / "components" / "App.tsx"
replace_once(
    app,
    'import AdminDashboard from "@/components/AdminDashboard";\n',
    'import AdminDashboard from "@/components/AdminDashboard";\nimport Billing from "@/components/Billing";\n',
)
replace_once(
    app,
    '  | "admin";\n',
    '  | "admin"\n  | "billing";\n',
)
replace_once(
    app,
    '      case "admin":\n        return <AdminDashboard />;\n',
    '      case "admin":\n        return <AdminDashboard />;\n\n      case "billing":\n        return <Billing />;\n',
)

# Sidebar: expose the billing page without changing existing navigation items.
sidebar = FRONTEND / "src" / "components" / "Sidebar.tsx"
replace_once(
    sidebar,
    '  Settings as SettingsIcon,\n',
    '  Settings as SettingsIcon,\n  CreditCard,\n',
)
replace_once(
    sidebar,
    '  const bottomItems = [\n    { id: "settings", label: "Settings", icon: SettingsIcon },\n  ] as const;',
    '  const bottomItems = [\n    { id: "settings", label: "Settings", icon: SettingsIcon },\n    { id: "billing", label: "Billing", icon: CreditCard },\n  ] as const;',
)

# Super Admin dashboard: keep existing account-management UI and add billing controls.
admin_dashboard = FRONTEND / "src" / "components" / "AdminDashboard.tsx"
replace_once(
    admin_dashboard,
    'import { api } from "@/lib/api";\n',
    'import { api } from "@/lib/api";\nimport AdminBillingSettings from "@/components/AdminBillingSettings";\nimport AdminPaymentRecords from "@/components/AdminPaymentRecords";\n',
)
replace_once(
    admin_dashboard,
    '      <header className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">',
    '      <header className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">',
)
# Insert billing controls after the closing header. This marker is intentionally scoped to the first header block.
replace_once(
    admin_dashboard,
    '      </header>\n\n      {/*',
    '      </header>\n\n      <AdminBillingSettings />\n      <AdminPaymentRecords />\n\n      {/*',
)

print("Billing integration patch applied.")
