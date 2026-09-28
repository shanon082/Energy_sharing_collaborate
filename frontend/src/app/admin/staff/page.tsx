'use client';

export const dynamic = "force-dynamic";

import { useEffect, useState, useCallback } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Plus, RefreshCw, Shield, UserX } from 'lucide-react';
import { get, post } from "@/lib/fetch-client";

interface StaffMember {
  id: number;
  email: string;
  full_name: string;
  phone_number: string;
  role: string;
  account_active: boolean;
  email_verified: boolean;
  created_at: string;
  last_login: string | null;
}

interface PendingInvitation {
  id: number;
  email: string;
  full_name: string;
  role: string;
  created_at: string;
  expires_at: string;
}

const ROLE_LABELS: Record<string, string> = {
  ADMIN: "Admin",
  CUSTOMER_SERVICE: "Customer Service",
  OPERATOR: "Operator",
};

const ROLE_COLORS: Record<string, string> = {
  ADMIN: "bg-red-100 text-red-800",
  OPERATOR: "bg-blue-100 text-blue-800",
  CUSTOMER_SERVICE: "bg-green-100 text-green-800",
};

export default function StaffPage() {
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [pending, setPending] = useState<PendingInvitation[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteDialog, setInviteDialog] = useState(false);
  const [deactivateDialog, setDeactivateDialog] = useState<StaffMember | null>(null);
  const [deactivateNotes, setDeactivateNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const [form, setForm] = useState({
    email: '', full_name: '', phone_number: '', department: '', role: '',
  });

  const fetchStaff = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<any>('admin/staff/');
      if (res.data) {
        setStaff(res.data.staff || []);
        setPending(res.data.pending_invitations || []);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchStaff(); }, [fetchStaff]);

  async function handleInvite() {
    if (!form.email || !form.full_name || !form.role) return;
    setSubmitting(true);
    try {
      const res = await post<any>('admin/staff/', form);
      if (res.data?.success) {
        setInviteDialog(false);
        setForm({ email: '', full_name: '', phone_number: '', department: '', role: '' });
        fetchStaff();
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDeactivate() {
    if (!deactivateDialog) return;
    setSubmitting(true);
    try {
      const res = await fetch(`/api/v1/admin/staff/${deactivateDialog.id}/`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes: deactivateNotes }),
        credentials: 'include',
      });
      if (res.ok) {
        setDeactivateDialog(null);
        setDeactivateNotes('');
        fetchStaff();
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Staff Accounts</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Admin access required</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={fetchStaff}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button size="sm" onClick={() => setInviteDialog(true)}>
            <Plus className="h-4 w-4 mr-2" /> Invite Staff
          </Button>
        </div>
      </div>

      {/* Active staff */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Active Staff ({staff.filter(s => s.account_active).length})</CardTitle>
          <CardDescription>
            Deactivate accounts same-day when a team member leaves (per security policy)
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-2">{[...Array(4)].map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
          ) : staff.length === 0 ? (
            <p className="text-muted-foreground text-center py-6">No staff accounts found</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-muted-foreground text-xs">
                    <th className="text-left py-2 pr-3">Name</th>
                    <th className="text-left py-2 pr-3">Email</th>
                    <th className="text-left py-2 pr-3">Role</th>
                    <th className="text-left py-2 pr-3">Status</th>
                    <th className="text-left py-2 pr-3">Last Login</th>
                    <th className="text-left py-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {staff.map(s => (
                    <tr key={s.id} className="border-b last:border-0 hover:bg-muted/30">
                      <td className="py-2 pr-3 font-medium">{s.full_name}</td>
                      <td className="py-2 pr-3 text-muted-foreground text-xs">{s.email}</td>
                      <td className="py-2 pr-3">
                        <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${ROLE_COLORS[s.role] ?? 'bg-gray-100 text-gray-700'}`}>
                          <Shield className="h-3 w-3 mr-1" />
                          {ROLE_LABELS[s.role] ?? s.role}
                        </span>
                      </td>
                      <td className="py-2 pr-3">
                        <Badge variant={s.account_active ? "default" : "secondary"} className="text-xs">
                          {s.account_active ? "Active" : "Inactive"}
                        </Badge>
                      </td>
                      <td className="py-2 pr-3 text-xs text-muted-foreground">
                        {s.last_login ? new Date(s.last_login).toLocaleDateString() : "Never"}
                      </td>
                      <td className="py-2">
                        {s.account_active && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 text-xs text-red-600 hover:text-red-700"
                            onClick={() => setDeactivateDialog(s)}
                          >
                            <UserX className="h-3 w-3 mr-1" /> Deactivate
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Pending invitations */}
      {pending.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Pending Invitations ({pending.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {pending.map(inv => (
                <div key={inv.id} className="flex items-center justify-between p-3 border rounded-lg">
                  <div>
                    <p className="font-medium text-sm">{inv.full_name} <span className="text-muted-foreground">({inv.email})</span></p>
                    <p className="text-xs text-muted-foreground">
                      Role: {ROLE_LABELS[inv.role] ?? inv.role} · Expires {new Date(inv.expires_at).toLocaleDateString()}
                    </p>
                  </div>
                  <Badge variant="outline" className="text-xs">Pending</Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Invite dialog */}
      <Dialog open={inviteDialog} onOpenChange={setInviteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Invite New Staff Member</DialogTitle>
            <DialogDescription>
              They will receive an invitation email with a setup link. ADMIN role requires PI approval before assignment.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-sm font-medium">Full Name *</label>
                <Input
                  value={form.full_name}
                  onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                  placeholder="Jane Doe"
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium">Email *</label>
                <Input
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  placeholder="jane@example.com"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-sm font-medium">Phone</label>
                <Input
                  value={form.phone_number}
                  onChange={(e) => setForm({ ...form, phone_number: e.target.value })}
                  placeholder="+256..."
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium">Department</label>
                <Input
                  value={form.department}
                  onChange={(e) => setForm({ ...form, department: e.target.value })}
                  placeholder="Operations"
                />
              </div>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Role *</label>
              <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                <SelectTrigger>
                  <SelectValue placeholder="Select role" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="CUSTOMER_SERVICE">Customer Service</SelectItem>
                  <SelectItem value="OPERATOR">Operator</SelectItem>
                  <SelectItem value="ADMIN">Admin (requires PI approval)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setInviteDialog(false)}>Cancel</Button>
            <Button onClick={handleInvite} disabled={!form.email || !form.full_name || !form.role || submitting}>
              {submitting ? "Sending…" : "Send Invitation"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Deactivate confirm dialog */}
      <Dialog open={!!deactivateDialog} onOpenChange={() => setDeactivateDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Deactivate Staff Account</DialogTitle>
            <DialogDescription>
              This will immediately revoke access for <strong>{deactivateDialog?.full_name}</strong>.
              Per security policy, do this same-day when a team member leaves.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-1">
            <label className="text-sm font-medium">Notes (optional)</label>
            <Input
              placeholder="e.g. Resigned on 2025-01-10"
              value={deactivateNotes}
              onChange={(e) => setDeactivateNotes(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeactivateDialog(null)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDeactivate} disabled={submitting}>
              {submitting ? "Deactivating…" : "Deactivate Account"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
