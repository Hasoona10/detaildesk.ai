import { redirect } from "next/navigation";

// Legacy route — the dashboard now lives under /inbox.
export default function OwnerDashboardRedirect() {
  redirect("/inbox");
}
