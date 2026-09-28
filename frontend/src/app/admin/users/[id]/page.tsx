'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/use-toast';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  CheckCircle,
  CreditCard,
  KeyRound,
  RefreshCw,
  Shield,
  XCircle,
  Zap,
} from 'lucide-react';
import { get, post } from '@/lib/fetch-client';

interface UserDetail {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  phone_number: string;
  national_id: string | null;
  gender: string;
  email_verified: boolean;
  account_active: boolean;
  is_suspended: boolean;
  suspension_reason: string | null;
  suspension_note: string | null;
  suspended_at: string | null;
  kyc_status: string;
  created_at: string;
  last_login: string | null;
  profile_data: {
    monthly_expenditure: string;
    purchase_frequency: string;
    payment_consistency: string;
    disconnection_history: string;
    meter_sharing: string;
    monthly_income: string;
    income_stability: string;
    consumption_level: string;
    profile_complete: boolean;
  };
  wallet_summary: { balance: number; total_transactions: number };
  meter: {
    id: number;
    meter_no: string;
    label: string;
    status: string;
    static_ip: string;
    units: number;
    created_at: string;
    updated_at: string;
  } | null;
  account_details: {
    account_number: string;
    address: string;
    energy_preference: string;
    payment_method: string;
    created_at: string;
  } | null;
  active_loans: {
    id: number;
    loan_id: string;
    amount_requested: number;
    amount_approved: number | null;
    status: string;
    due_date: string | null;
    outstanding_balance: number;
  }[];
  credit_score: number | null;
  credit_limit_override_kwh: number | null;
  transaction_history: {
    id: string;
    type: string;
    amount_kwh: number;
    amount_ugx: number;
    status: string;
    channel: string;
    created_at: string;
  }[];
  flags: {
    id: number;
    flag_type: string;
    status: string;
    trigger: string;
    created_at: string;
  }[];
}

const KYC_COLORS: Record<string, string> = {
  VERIFIED: "bg-green-100 text-green-800",
  UNVERIFIED: "bg-gray-100 text-gray-700",
  FLAGGED: "bg-red-100 text-red-800",
};

export default function UserDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const [user, setUser] = useState<UserDetail | null>(null);
  const [loading, setLoading] = useState(true);

  // Dialog state
  const [suspendDialog, setSuspendDialog] = useState(false);
  const [suspendReason, setSuspendReason] = useState('');
  const [suspendNote, setSuspendNote] = useState('');
  const [pinResetDialog, setPinResetDialog] = useState(false);
  const [pinResetNotes, setPinResetNotes] = useState('');
  const [creditLimitDialog, setCreditLimitDialog] = useState(false);
  const [newCreditLimit, setNewCreditLimit] = useState('');
  const [creditLimitReason, setCreditLimitReason] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function fetchUser() {
    setLoading(true);
    try {
      const res = await get<any>(`admin/users/${params.id}/`);
      if (res.data?.user) setUser(res.data.user);
    } catch (err) {
      toast({ title: 'Error', description: 'Failed to load user', variant: 'destructive' });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchUser(); }, [params.id]);

  async function handleSuspend() {
    if (!user) return;
    setSubmitting(true);
    try {
      const res = await post<any>(`admin/users/${user.id}/suspend/`, {
        action: user.is_suspended ? 'reactivate' : 'suspend',
        reason: suspendReason,
        note: suspendNote,
      });
      if (res.data?.success) {
        toast({ title: 'Success', description: res.data.message });
        setSuspendDialog(false);
        setSuspendReason('');
        setSuspendNote('');
        fetchUser();
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handleKYC(action: 'verify' | 'reject') {
    if (!user) return;
    const res = await post<any>(`admin/users/${user.id}/kyc/`, { action });
    if (res.data?.success) {
      toast({ title: 'Success', description: res.data.message });
      fetchUser();
    }
  }

  async function handlePINReset() {
    if (!user) return;
    setSubmitting(true);
    try {
      const res = await post<any>(`admin/users/${user.id}/reset-pin/`, {
        type: 'pin',
        notes: pinResetNotes,
      });
      if (res.data?.success) {
        toast({ title: 'Success', description: res.data.message });
        setPinResetDialog(false);
        setPinResetNotes('');
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCreditLimitOverride() {
    if (!user || !newCreditLimit || !creditLimitReason) return;
    const val = parseFloat(newCreditLimit);
    if (val > 20) {
      toast({ title: 'Error', description: 'Credit limit cannot exceed 20 kWh', variant: 'destructive' });
      return;
    }
    setSubmitting(true);
    try {
      const res = await post<any>(`admin/users/${user.id}/credit-limit/`, {
        credit_limit_kwh: val,
        reason: creditLimitReason,
      });
      if (res.data?.success) {
        toast({ title: 'Success', description: 'Credit limit updated' });
        setCreditLimitDialog(false);
        setNewCreditLimit('');
        setCreditLimitReason('');
        fetchUser();
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <UserDetailSkeleton />;

  if (!user) return (
    <div className="py-10 text-center">
      <AlertCircle className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
      <p className="text-muted-foreground mb-4">User not found</p>
      <Button onClick={() => router.push('/admin/users')} variant="outline">
        <ArrowLeft className="mr-2 h-4 w-4" /> Back
      </Button>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="outline" size="icon" onClick={() => router.push('/admin/users')}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-xl font-bold">{user.first_name} {user.last_name}</h1>
            <p className="text-sm text-muted-foreground">{user.email} · ID #{user.id}</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={fetchUser}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main content */}
        <div className="lg:col-span-2 space-y-4">
          <Tabs defaultValue="overview">
            <TabsList>
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="transactions">Transactions</TabsTrigger>
              <TabsTrigger value="loans">Loans</TabsTrigger>
              <TabsTrigger value="flags">Flags</TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="space-y-4">
              {/* Personal info */}
              <Card>
                <CardHeader><CardTitle className="text-sm">Personal Information</CardTitle></CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <InfoRow label="Full Name" value={`${user.first_name} ${user.last_name}`} />
                    <InfoRow label="Phone" value={user.phone_number || '—'} />
                    <InfoRow label="National ID" value={user.national_id || '—'} />
                    <InfoRow label="Gender" value={user.gender || '—'} />
                    <InfoRow label="Joined" value={new Date(user.created_at).toLocaleDateString()} />
                    <InfoRow label="Last Login" value={user.last_login ? new Date(user.last_login).toLocaleString() : 'Never'} />
                  </div>
                </CardContent>
              </Card>

              {/* Meter info */}
              <Card>
                <CardHeader><CardTitle className="text-sm">Meter</CardTitle></CardHeader>
                <CardContent>
                  {user.meter ? (
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <InfoRow label="Meter No" value={user.meter.meter_no} mono />
                      <InfoRow label="Label" value={user.meter.label} />
                      <InfoRow label="Units" value={`${user.meter.units.toFixed(2)} kWh`} />
                      <InfoRow label="Status" value={user.meter.status} />
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">No meter assigned</p>
                  )}
                </CardContent>
              </Card>

              {/* Account details */}
              {user.account_details && (
                <Card>
                  <CardHeader><CardTitle className="text-sm">Account Details</CardTitle></CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <InfoRow label="Account No" value={user.account_details.account_number} mono />
                      <InfoRow label="Payment Method" value={user.account_details.payment_method || '—'} />
                      <InfoRow label="Address" value={user.account_details.address || '—'} />
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Profile assessment */}
              <Card>
                <CardHeader><CardTitle className="text-sm">Loan Profile</CardTitle></CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <InfoRow label="Monthly Expenditure" value={user.profile_data.monthly_expenditure || '—'} />
                    <InfoRow label="Monthly Income" value={user.profile_data.monthly_income || '—'} />
                    <InfoRow label="Purchase Frequency" value={user.profile_data.purchase_frequency || '—'} />
                    <InfoRow label="Payment Consistency" value={user.profile_data.payment_consistency || '—'} />
                    <InfoRow label="Consumption Level" value={user.profile_data.consumption_level || '—'} />
                    <InfoRow
                      label="Profile Complete"
                      value={user.profile_data.profile_complete ? "Yes" : "Incomplete"}
                    />
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="transactions">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">
                    Transaction History (last 20)
                    <span className="ml-2 text-muted-foreground font-normal">
                      {user.wallet_summary.total_transactions} total
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {user.transaction_history.length === 0 ? (
                    <p className="text-muted-foreground text-sm text-center py-6">No transactions yet</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b text-muted-foreground text-xs">
                            <th className="text-left py-1.5 pr-3">Type</th>
                            <th className="text-right py-1.5 pr-3">kWh</th>
                            <th className="text-right py-1.5 pr-3">UGX</th>
                            <th className="text-left py-1.5 pr-3">Status</th>
                            <th className="text-left py-1.5">Date</th>
                          </tr>
                        </thead>
                        <tbody>
                          {user.transaction_history.map(t => (
                            <tr key={t.id} className="border-b last:border-0">
                              <td className="py-1.5 pr-3 capitalize text-xs">{t.type.replace(/_/g, ' ')}</td>
                              <td className="py-1.5 pr-3 text-right tabular-nums text-xs">{t.amount_kwh.toFixed(2)}</td>
                              <td className="py-1.5 pr-3 text-right tabular-nums text-xs">{t.amount_ugx.toLocaleString()}</td>
                              <td className="py-1.5 pr-3 text-xs">{t.status}</td>
                              <td className="py-1.5 text-xs text-muted-foreground whitespace-nowrap">{new Date(t.created_at).toLocaleDateString()}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="loans">
              <Card>
                <CardHeader><CardTitle className="text-sm">Active Loans</CardTitle></CardHeader>
                <CardContent>
                  {user.active_loans.length === 0 ? (
                    <p className="text-muted-foreground text-sm text-center py-6">No active loans</p>
                  ) : (
                    <div className="space-y-3">
                      {user.active_loans.map(l => (
                        <div key={l.id} className="border rounded-lg p-3">
                          <div className="flex items-center justify-between mb-2">
                            <span className="font-mono text-xs">{l.loan_id}</span>
                            <Badge variant="outline" className="text-xs">{l.status}</Badge>
                          </div>
                          <div className="grid grid-cols-3 gap-2 text-xs">
                            <div>
                              <p className="text-muted-foreground">Approved</p>
                              <p className="font-medium">{l.amount_approved?.toLocaleString() ?? '—'} UGX</p>
                            </div>
                            <div>
                              <p className="text-muted-foreground">Outstanding</p>
                              <p className="font-medium">{l.outstanding_balance.toLocaleString()} UGX</p>
                            </div>
                            <div>
                              <p className="text-muted-foreground">Due</p>
                              <p className="font-medium">{l.due_date ? new Date(l.due_date).toLocaleDateString() : '—'}</p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  {user.credit_score !== null && (
                    <div className="mt-3 p-3 bg-muted rounded-lg text-sm">
                      <span className="text-muted-foreground">Credit Score: </span>
                      <span className="font-bold">{user.credit_score}%</span>
                      {user.credit_limit_override_kwh !== null && (
                        <span className="ml-3 text-muted-foreground">
                          · Limit override: <span className="font-medium">{user.credit_limit_override_kwh} kWh</span>
                        </span>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="flags">
              <Card>
                <CardHeader><CardTitle className="text-sm">Fraud Flags & Notes</CardTitle></CardHeader>
                <CardContent>
                  {user.flags.length === 0 ? (
                    <div className="text-center py-6">
                      <CheckCircle className="h-8 w-8 text-green-500 mx-auto mb-2" />
                      <p className="text-muted-foreground text-sm">No fraud flags</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {user.flags.map(f => (
                        <div key={f.id} className={`border rounded-lg p-3 ${f.status === 'OPEN' ? 'border-amber-300 bg-amber-50' : ''}`}>
                          <div className="flex items-center justify-between mb-1">
                            <div className="flex items-center gap-2">
                              <AlertTriangle className="h-4 w-4 text-amber-500" />
                              <span className="font-medium text-sm">{f.flag_type}</span>
                            </div>
                            <Badge variant={f.status === 'OPEN' ? 'destructive' : 'secondary'} className="text-xs">
                              {f.status}
                            </Badge>
                          </div>
                          <p className="text-xs text-muted-foreground">{f.trigger}</p>
                          <p className="text-xs text-muted-foreground mt-1">
                            {new Date(f.created_at).toLocaleString()}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>

        {/* Right panel */}
        <div className="space-y-4">
          {/* Status card */}
          <Card>
            <CardHeader><CardTitle className="text-sm flex items-center gap-2"><Shield className="h-4 w-4" /> Account Status</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Account</span>
                <Badge variant={user.account_active ? "default" : "secondary"}>
                  {user.account_active ? "Active" : "Inactive"}
                </Badge>
              </div>
              {user.is_suspended && (
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Suspended</span>
                  <Badge variant="destructive">Yes</Badge>
                </div>
              )}
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">KYC</span>
                <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${KYC_COLORS[user.kyc_status] ?? ''}`}>
                  {user.kyc_status}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Email</span>
                <Badge variant={user.email_verified ? "default" : "outline"}>
                  {user.email_verified ? "Verified" : "Unverified"}
                </Badge>
              </div>
            </CardContent>
          </Card>

          {/* Wallet summary */}
          <Card>
            <CardHeader><CardTitle className="text-sm">Wallet</CardTitle></CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{user.wallet_summary.balance.toLocaleString()} <span className="text-sm font-normal text-muted-foreground">UGX</span></p>
              <p className="text-xs text-muted-foreground mt-1">{user.wallet_summary.total_transactions} transactions total</p>
            </CardContent>
          </Card>

          {/* Actions */}
          <Card>
            <CardHeader><CardTitle className="text-sm">Actions</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {/* Suspend / Reactivate */}
              <Button
                variant={user.is_suspended ? "default" : "destructive"}
                size="sm"
                className="w-full justify-start"
                onClick={() => setSuspendDialog(true)}
              >
                <XCircle className="mr-2 h-4 w-4" />
                {user.is_suspended ? "Reactivate Account" : "Suspend Account"}
              </Button>

              {/* KYC actions */}
              {user.kyc_status !== 'VERIFIED' && (
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full justify-start text-green-700 border-green-300"
                  onClick={() => handleKYC('verify')}
                >
                  <CheckCircle className="mr-2 h-4 w-4" />
                  Verify Identity (KYC)
                </Button>
              )}
              {user.kyc_status === 'VERIFIED' && (
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full justify-start text-red-700 border-red-300"
                  onClick={() => handleKYC('reject')}
                >
                  <XCircle className="mr-2 h-4 w-4" />
                  Reject Identity (KYC)
                </Button>
              )}

              {/* PIN Reset */}
              <Button
                variant="outline"
                size="sm"
                className="w-full justify-start"
                onClick={() => setPinResetDialog(true)}
              >
                <KeyRound className="mr-2 h-4 w-4" />
                Reset PIN
              </Button>

              {/* Credit limit override */}
              <Button
                variant="outline"
                size="sm"
                className="w-full justify-start"
                onClick={() => setCreditLimitDialog(true)}
              >
                <CreditCard className="mr-2 h-4 w-4" />
                Override Credit Limit
              </Button>
            </CardContent>
          </Card>

          {/* Suspension info */}
          {user.is_suspended && user.suspension_reason && (
            <Card className="border-red-200 bg-red-50">
              <CardContent className="pt-4">
                <p className="text-xs font-medium text-red-800">Suspended: {user.suspension_reason}</p>
                {user.suspension_note && <p className="text-xs text-red-700 mt-1">{user.suspension_note}</p>}
                {user.suspended_at && (
                  <p className="text-xs text-red-600 mt-1">{new Date(user.suspended_at).toLocaleString()}</p>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Suspend dialog */}
      <Dialog open={suspendDialog} onOpenChange={setSuspendDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{user.is_suspended ? "Reactivate Account" : "Suspend Account"}</DialogTitle>
            <DialogDescription>
              {user.is_suspended
                ? `Reactivate account for ${user.email}?`
                : `Suspend account for ${user.email}. This blocks all access immediately.`}
            </DialogDescription>
          </DialogHeader>
          {!user.is_suspended && (
            <div className="space-y-3">
              <div className="space-y-1">
                <label className="text-sm font-medium">Reason *</label>
                <select
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  value={suspendReason}
                  onChange={(e) => setSuspendReason(e.target.value)}
                >
                  <option value="">Select reason</option>
                  <option value="Fraud Suspicion">Fraud Suspicion</option>
                  <option value="Non-Payment">Non-Payment</option>
                  <option value="Policy Violation">Policy Violation</option>
                  <option value="Account Compromise">Account Compromise</option>
                  <option value="Other">Other</option>
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium">Notes</label>
                <Input
                  placeholder="Additional details..."
                  value={suspendNote}
                  onChange={(e) => setSuspendNote(e.target.value)}
                />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setSuspendDialog(false)}>Cancel</Button>
            <Button
              variant={user.is_suspended ? "default" : "destructive"}
              onClick={handleSuspend}
              disabled={(!user.is_suspended && !suspendReason) || submitting}
            >
              {submitting ? "Processing…" : user.is_suspended ? "Reactivate" : "Suspend"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* PIN Reset dialog */}
      <Dialog open={pinResetDialog} onOpenChange={setPinResetDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reset PIN</DialogTitle>
            <DialogDescription>
              Send a PIN reset SMS to {user.phone_number || user.email}. Never reset credentials based on a phone call alone — require ID verification first.
            </DialogDescription>
          </DialogHeader>
          <Input
            placeholder="Notes (optional)"
            value={pinResetNotes}
            onChange={(e) => setPinResetNotes(e.target.value)}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setPinResetDialog(false)}>Cancel</Button>
            <Button onClick={handlePINReset} disabled={submitting}>
              {submitting ? "Sending…" : "Send PIN Reset"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Credit limit override dialog */}
      <Dialog open={creditLimitDialog} onOpenChange={setCreditLimitDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Override Credit Limit</DialogTitle>
            <DialogDescription>
              Current override: {user.credit_limit_override_kwh ?? "None"} kWh.
              Hard cap is <strong>20 kWh</strong> — cannot exceed this.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-sm font-medium">New limit (kWh, max 20) *</label>
              <Input
                type="number"
                step="0.5"
                min="0"
                max="20"
                value={newCreditLimit}
                onChange={(e) => setNewCreditLimit(e.target.value)}
                placeholder="e.g. 15"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Reason *</label>
              <Input
                value={creditLimitReason}
                onChange={(e) => setCreditLimitReason(e.target.value)}
                placeholder="e.g. Consistent repayment history"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreditLimitDialog(false)}>Cancel</Button>
            <Button
              onClick={handleCreditLimitOverride}
              disabled={!newCreditLimit || !creditLimitReason || submitting}
            >
              {submitting ? "Saving…" : "Update Limit"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function InfoRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`text-sm mt-0.5 ${mono ? 'font-mono' : ''}`}>{value}</p>
    </div>
  );
}

function UserDetailSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Skeleton className="h-10 w-10" />
        <div className="space-y-2">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-4 w-56" />
        </div>
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Skeleton className="h-80" />
        </div>
        <div className="space-y-4">
          <Skeleton className="h-40" />
          <Skeleton className="h-32" />
        </div>
      </div>
    </div>
  );
}
