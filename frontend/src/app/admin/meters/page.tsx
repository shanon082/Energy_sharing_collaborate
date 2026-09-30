'use client';

export const dynamic = "force-dynamic";

import { useEffect, useState, useCallback } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
} from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Download,
  Eye,
  KeyRound,
  Plus,
  Search,
  Zap,
} from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/use-toast';
import { useRouter } from 'next/navigation';
import { get, post, patch } from '@/lib/fetch-client';
import { getErrorMessage } from '@/lib/errors';

interface Meter {
  meter_id: number;
  meter_no: string;
  label: string;
  status: string;
  architecture: 'STS' | 'AMI';
  static_ip: string;
  units: number;
  iot_device_token?: string;
  has_iot_token?: boolean;
  user: {
    id: number;
    email: string;
    name: string;
    phone: string;
  };
  created_at: string;
  last_updated: string;
}

const STATUS_COLORS: Record<string, string> = {
  ACTIVE: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300",
  INACTIVE: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  SUSPENDED: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
};

const defaultRegisterForm = {
  meter_no: '',
  owner_name: '',
  owner_email: '',
  owner_phone: '',
  label: 'Home',
  architecture: 'STS' as 'STS' | 'AMI',
  static_ip: '',
  iot_device_token: '',
};

export default function MetersManagementPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [meters, setMeters] = useState<Meter[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalMeters, setTotalMeters] = useState(0);

  const [registerDialog, setRegisterDialog] = useState(false);
  const [deactivateDialog, setDeactivateDialog] = useState<Meter | null>(null);
  const [transferDialog, setTransferDialog] = useState<Meter | null>(null);
  const [tokenDialog, setTokenDialog] = useState<Meter | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [registerForm, setRegisterForm] = useState(defaultRegisterForm);
  const [deactivateReason, setDeactivateReason] = useState('');
  const [deactivateNote, setDeactivateNote] = useState('');
  const [transferUserId, setTransferUserId] = useState('');
  const [transferNote, setTransferNote] = useState('');
  const [editToken, setEditToken] = useState('');

  const fetchMeters = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(currentPage), limit: '20' });
      if (search) params.set('search', search);
      const res = await get<any>(`admin/meters/?${params}`);
      if (res.data?.meters) {
        setMeters(res.data.meters);
        setTotalPages(res.data.pagination?.pages ?? 1);
        setTotalMeters(res.data.pagination?.total ?? 0);
      } else if (res.error) {
        toast({ title: 'Error', description: getErrorMessage(res.error) || 'Failed to load meters', variant: 'destructive' });
      }
    } catch {
      toast({ title: 'Error', description: 'Failed to load meters', variant: 'destructive' });
    } finally {
      setLoading(false);
    }
  }, [currentPage, search]);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchMeters();
    }, search ? 300 : 0);
    return () => clearTimeout(timer);
  }, [fetchMeters, search]);

  async function handleRegister() {
    if (!registerForm.meter_no || !registerForm.owner_name || !registerForm.owner_email || !registerForm.owner_phone) {
      toast({ title: 'Missing fields', description: 'Meter number, owner name, email, and phone are required.', variant: 'destructive' });
      return;
    }
    if (registerForm.architecture === 'AMI' && !registerForm.iot_device_token.trim()) {
      toast({ title: 'Device token required', description: 'AMI meters need a ThingsBoard device access token.', variant: 'destructive' });
      return;
    }
    setSubmitting(true);
    try {
      const payload: Record<string, string> = {
        meter_no: registerForm.meter_no,
        owner_name: registerForm.owner_name.trim(),
        owner_email: registerForm.owner_email.trim(),
        owner_phone: registerForm.owner_phone.trim(),
        label: registerForm.label,
        architecture: registerForm.architecture,
      };
      if (registerForm.static_ip.trim()) payload.static_ip = registerForm.static_ip.trim();
      if (registerForm.architecture === 'AMI') {
        payload.iot_device_token = registerForm.iot_device_token.trim();
      }
      const res = await post<any>('admin/meters/', payload);
      if (res.data?.success) {
        toast({
          title: 'Account & meter created',
          description: `${registerForm.owner_email} must use Forgot Password to set a private password before signing in.`,
        });
        setRegisterDialog(false);
        setRegisterForm(defaultRegisterForm);
        fetchMeters();
      } else {
        toast({ title: 'Error', description: res.data?.error || getErrorMessage(res.error) || 'Registration failed', variant: 'destructive' });
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSaveToken() {
    if (!tokenDialog) return;
    if (!editToken.trim()) {
      toast({ title: 'Token required', description: 'Enter the ThingsBoard device access token.', variant: 'destructive' });
      return;
    }
    setSubmitting(true);
    try {
      const res = await patch<any>(`admin/meters/${tokenDialog.meter_id}/`, {
        architecture: 'AMI',
        iot_device_token: editToken.trim(),
      });
      if (res.data?.success) {
        toast({ title: 'Saved', description: 'ThingsBoard device token updated' });
        setTokenDialog(null);
        setEditToken('');
        fetchMeters();
      } else {
        toast({ title: 'Error', description: res.data?.error || getErrorMessage(res.error) || 'Update failed', variant: 'destructive' });
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDeactivate() {
    if (!deactivateDialog || !deactivateReason) return;
    setSubmitting(true);
    try {
      const res = await post<any>(`admin/meters/${deactivateDialog.meter_id}/deactivate/`, {
        reason: deactivateReason,
        note: deactivateNote,
      });
      if (res.data?.success) {
        toast({ title: 'Success', description: 'Meter deactivated' });
        setDeactivateDialog(null);
        setDeactivateReason('');
        setDeactivateNote('');
        fetchMeters();
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handleTransfer() {
    if (!transferDialog || !transferUserId) return;
    setSubmitting(true);
    try {
      const res = await post<any>(`admin/meters/${transferDialog.meter_id}/transfer/`, {
        new_user_id: transferUserId,
        note: transferNote,
      });
      if (res.data?.success) {
        toast({ title: 'Success', description: 'Ownership transferred' });
        setTransferDialog(null);
        setTransferUserId('');
        setTransferNote('');
        fetchMeters();
      }
    } finally {
      setSubmitting(false);
    }
  }

  function exportCSV() {
    const rows = [
      ['Meter No', 'Label', 'Type', 'Status', 'Units', 'Device Token', 'User', 'Email', 'Registered'],
      ...meters.map(m => [
        m.meter_no, m.label, m.architecture, m.status, String(m.units),
        m.architecture === 'AMI' ? (m.iot_device_token || '') : '',
        m.user.name, m.user.email,
        new Date(m.created_at).toLocaleDateString()
      ])
    ].map(r => r.join(',')).join('\n');
    const blob = new Blob([rows], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `meters-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  }

  function openTokenDialog(m: Meter) {
    setTokenDialog(m);
    setEditToken(m.iot_device_token || '');
  }

  function tokenPreview(m: Meter) {
    if (m.architecture !== 'AMI') return '—';
    if (!m.has_iot_token) {
      return (
        <Badge variant="outline" className="text-amber-700 border-amber-300 bg-amber-50 dark:bg-amber-950/30">
          Missing
        </Badge>
      );
    }
    const t = m.iot_device_token || '';
    const preview = t.length > 8 ? `${t.slice(0, 4)}…${t.slice(-4)}` : t;
    return <span className="font-mono text-xs">{preview}</span>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Meter Management</h1>
          <p className="text-sm text-muted-foreground">{totalMeters} meters registered · AMI meters use ThingsBoard device tokens</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={exportCSV}>
            <Download className="h-4 w-4 mr-2" /> Export
          </Button>
          <Button size="sm" onClick={() => setRegisterDialog(true)}>
            <Plus className="h-4 w-4 mr-2" /> Register Meter
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search by meter number, user email..."
              className="pl-9"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setCurrentPage(1); }}
            />
          </div>
        </CardHeader>
        <CardContent>
          {loading && meters.length === 0 ? (
            <div className="space-y-2">{[...Array(5)].map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
          ) : (
            <>
              <div className="rounded-md border overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Meter</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Device Token</TableHead>
                      <TableHead>Units</TableHead>
                      <TableHead>Owner</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {meters.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                          No meters found
                        </TableCell>
                      </TableRow>
                    ) : meters.map((m) => (
                      <TableRow key={m.meter_id}>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Zap className="h-4 w-4 text-primary shrink-0" />
                            <div>
                              <p className="font-mono font-medium text-sm">{m.meter_no}</p>
                              <p className="text-xs text-muted-foreground">{m.label}</p>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant={m.architecture === 'AMI' ? 'default' : 'secondary'}>
                            {m.architecture || 'STS'}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[m.status] ?? ''}`}>
                            {m.status}
                          </span>
                        </TableCell>
                        <TableCell>{tokenPreview(m)}</TableCell>
                        <TableCell className="tabular-nums">{Number(m.units).toFixed(2)} kWh</TableCell>
                        <TableCell>
                          <p className="font-medium text-sm">{m.user.name}</p>
                          <p className="text-xs text-muted-foreground">{m.user.email}</p>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1 flex-wrap">
                            <Button variant="ghost" size="sm" className="h-7 text-xs"
                              onClick={() => router.push(`/admin/meters/${m.meter_id}`)}>
                              <Eye className="h-3 w-3 mr-1" /> View
                            </Button>
                            {m.architecture === 'AMI' && (
                              <Button variant="ghost" size="sm" className="h-7 text-xs"
                                onClick={() => openTokenDialog(m)}>
                                <KeyRound className="h-3 w-3 mr-1" />
                                {m.has_iot_token ? 'Token' : 'Set token'}
                              </Button>
                            )}
                            <Button variant="ghost" size="sm" className="h-7 text-xs"
                              onClick={() => setTransferDialog(m)}>
                              Transfer
                            </Button>
                            {m.status === 'ACTIVE' && (
                              <Button variant="ghost" size="sm" className="h-7 text-xs text-red-600"
                                onClick={() => setDeactivateDialog(m)}>
                                Deactivate
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-4">
                  <p className="text-sm text-muted-foreground">Page {currentPage} of {totalPages}</p>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1}>Previous</Button>
                    <Button variant="outline" size="sm" onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))} disabled={currentPage === totalPages}>Next</Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Register meter dialog */}
      <Dialog open={registerDialog} onOpenChange={setRegisterDialog}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Register New Meter</DialogTitle>
            <DialogDescription>
              Creates a new customer account and assigns this meter. The owner uses Forgot Password to set a private password before signing in. For self-registration, customers can use the public sign-up page instead.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-sm font-medium">Meter type</label>
              <select
                className="w-full border rounded-md px-3 py-2 text-sm bg-background"
                value={registerForm.architecture}
                onChange={(e) => setRegisterForm({ ...registerForm, architecture: e.target.value as 'STS' | 'AMI' })}
              >
                <option value="STS">STS (token keypad)</option>
                <option value="AMI">AMI (ThingsBoard networked)</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Owner name *</label>
              <Input
                placeholder="e.g. John Okello"
                value={registerForm.owner_name}
                onChange={(e) => setRegisterForm({ ...registerForm, owner_name: e.target.value })}
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Owner email *</label>
              <Input
                type="email"
                placeholder="customer@example.com"
                value={registerForm.owner_email}
                onChange={(e) => setRegisterForm({ ...registerForm, owner_email: e.target.value })}
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Owner phone *</label>
              <Input
                placeholder="e.g. +256700000000"
                value={registerForm.owner_phone}
                onChange={(e) => setRegisterForm({ ...registerForm, owner_phone: e.target.value })}
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Meter Number *</label>
              <Input
                placeholder="e.g. 12345678901234567890"
                value={registerForm.meter_no}
                onChange={(e) => setRegisterForm({ ...registerForm, meter_no: e.target.value })}
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Label</label>
              <Input
                placeholder="e.g. Home, Shop"
                value={registerForm.label}
                onChange={(e) => setRegisterForm({ ...registerForm, label: e.target.value })}
              />
            </div>
            {registerForm.architecture === 'AMI' && (
              <>
                <div className="space-y-1">
                  <label className="text-sm font-medium">ThingsBoard device token *</label>
                  <Input
                    placeholder="Device access token from ThingsBoard"
                    value={registerForm.iot_device_token}
                    onChange={(e) => setRegisterForm({ ...registerForm, iot_device_token: e.target.value })}
                    className="font-mono text-sm"
                  />
                  <p className="text-xs text-muted-foreground">Use dev- prefix for local testing without HTTP.</p>
                </div>
                <div className="space-y-1">
                  <label className="text-sm font-medium">Static IP (optional)</label>
                  <Input
                    placeholder="192.168.1.1"
                    value={registerForm.static_ip}
                    onChange={(e) => setRegisterForm({ ...registerForm, static_ip: e.target.value })}
                  />
                </div>
              </>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRegisterDialog(false)}>Cancel</Button>
            <Button onClick={handleRegister} disabled={
              !registerForm.meter_no ||
              !registerForm.owner_name ||
              !registerForm.owner_email ||
              !registerForm.owner_phone ||
              submitting
            }>
              {submitting ? "Registering…" : "Register Meter"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* AMI device token dialog */}
      <Dialog open={!!tokenDialog} onOpenChange={() => { setTokenDialog(null); setEditToken(''); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>ThingsBoard device token</DialogTitle>
            <DialogDescription>
              AMI meter <strong className="font-mono">{tokenDialog?.meter_no}</strong> — this token is used to push units and read live balance from ThingsBoard.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <label className="text-sm font-medium">Device access token</label>
            <Input
              value={editToken}
              onChange={(e) => setEditToken(e.target.value)}
              placeholder="Paste token from ThingsBoard device"
              className="font-mono text-sm"
            />
            <p className="text-xs text-muted-foreground">
              Find this in ThingsBoard under the device → Access token. Only applies to AMI meters.
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setTokenDialog(null); setEditToken(''); }}>Cancel</Button>
            <Button onClick={handleSaveToken} disabled={!editToken.trim() || submitting}>
              {submitting ? 'Saving…' : 'Save token'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Deactivate dialog */}
      <Dialog open={!!deactivateDialog} onOpenChange={() => setDeactivateDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Deactivate Meter</DialogTitle>
            <DialogDescription>
              Deactivate meter <strong className="font-mono">{deactivateDialog?.meter_no}</strong>. This is reversible by Admin.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-sm font-medium">Reason *</label>
              <select
                className="w-full border rounded-md px-3 py-2 text-sm bg-background"
                value={deactivateReason}
                onChange={(e) => setDeactivateReason(e.target.value)}
              >
                <option value="">Select reason</option>
                <option value="Meter Stolen">Meter Stolen</option>
                <option value="Meter Damaged">Meter Damaged</option>
                <option value="Customer Moved Out">Customer Moved Out</option>
                <option value="Fraud Investigation">Fraud Investigation</option>
                <option value="Other">Other</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Notes</label>
              <Input value={deactivateNote} onChange={(e) => setDeactivateNote(e.target.value)} placeholder="Optional details..." />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeactivateDialog(null)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDeactivate} disabled={!deactivateReason || submitting}>
              {submitting ? "Processing…" : "Deactivate"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Transfer dialog */}
      <Dialog open={!!transferDialog} onOpenChange={() => setTransferDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Transfer Meter Ownership</DialogTitle>
            <DialogDescription>
              Transfer <strong className="font-mono">{transferDialog?.meter_no}</strong> from <strong>{transferDialog?.user.name}</strong> to a new owner.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-sm font-medium">New Owner&apos;s User ID *</label>
              <Input
                type="number"
                placeholder="User's system ID"
                value={transferUserId}
                onChange={(e) => setTransferUserId(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Notes</label>
              <Input value={transferNote} onChange={(e) => setTransferNote(e.target.value)} placeholder="Reason for transfer..." />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTransferDialog(null)}>Cancel</Button>
            <Button onClick={handleTransfer} disabled={!transferUserId || submitting}>
              {submitting ? "Transferring…" : "Transfer Ownership"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
