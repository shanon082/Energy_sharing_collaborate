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
import { Skeleton } from '@/components/ui/skeleton';
import { Download, Lock, RefreshCw, Search } from 'lucide-react';
import { get } from "@/lib/fetch-client";

interface AuditEntry {
  id: number;
  timestamp: string;
  staff_member: { id: number; email: string; name: string } | null;
  action_type: string;
  target_type: string;
  target_id: string;
  target_repr: string;
  details: Record<string, any>;
  ip_address: string;
  notes: string;
}

const ACTION_BADGE_COLORS: Record<string, string> = {
  "Account Suspension": "bg-red-100 text-red-800",
  "Account Reactivation": "bg-green-100 text-green-800",
  "Credential Reset": "bg-blue-100 text-blue-800",
  "KYC Verify": "bg-green-100 text-green-800",
  "KYC Reject": "bg-red-100 text-red-800",
  "Refund": "bg-orange-100 text-orange-800",
  "Fraud Flag": "bg-red-100 text-red-800",
  "Fraud Clear": "bg-green-100 text-green-800",
  "Staff Create": "bg-purple-100 text-purple-800",
  "Staff Deactivate": "bg-red-100 text-red-800",
  "Penalty Waiver": "bg-amber-100 text-amber-800",
};

export default function AuditLogPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [actionTypes, setActionTypes] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);

  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [actionType, setActionType] = useState('');
  const [staffId, setStaffId] = useState('');

  const fetchLog = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), limit: '50' });
      if (dateFrom) params.set('date_from', dateFrom);
      if (dateTo) params.set('date_to', dateTo);
      if (actionType) params.set('action_type', actionType);
      if (staffId) params.set('staff_id', staffId);

      const res = await get<any>(`admin/audit-log/?${params}`);
      if (res.data) {
        setEntries(res.data.entries || []);
        setActionTypes(res.data.action_types || []);
        setTotal(res.data.pagination?.total || 0);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [page, dateFrom, dateTo, actionType, staffId]);

  useEffect(() => { fetchLog(); }, [fetchLog]);

  function exportCSV() {
    const headers = ['Timestamp', 'Staff', 'Action', 'Target Type', 'Target', 'IP', 'Notes'];
    const rows = entries.map(e => [
      e.timestamp,
      e.staff_member?.email ?? 'Unknown',
      e.action_type,
      e.target_type,
      e.target_repr,
      e.ip_address,
      e.notes,
    ]);
    const csv = [headers, ...rows].map(r => r.map(v => `"${v ?? ''}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `audit-log-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  }

  const totalPages = Math.ceil(total / 50);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Audit Log</h1>
          <p className="text-sm text-muted-foreground flex items-center gap-1 mt-0.5">
            <Lock className="h-3 w-3" /> Append-only — entries cannot be edited or deleted
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={fetchLog}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="sm" onClick={exportCSV}>
            <Download className="h-4 w-4 mr-2" /> Export CSV
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Select value={actionType} onValueChange={(v) => { setActionType(v === '__all__' ? '' : v); setPage(1); }}>
              <SelectTrigger><SelectValue placeholder="Action type" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All Actions</SelectItem>
                {actionTypes.map(t => (
                  <SelectItem key={t} value={t}>{t}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              placeholder="Staff ID"
              value={staffId}
              onChange={(e) => { setStaffId(e.target.value); setPage(1); }}
            />
            <Input type="date" value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setPage(1); }} />
            <Input type="date" value={dateTo} onChange={(e) => { setDateTo(e.target.value); setPage(1); }} />
          </div>
        </CardContent>
      </Card>

      {/* Log table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Log Entries ({total.toLocaleString()})</CardTitle>
          <CardDescription>All state-changing actions performed by staff members</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-2">
              {[...Array(8)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
            </div>
          ) : entries.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">No log entries found</p>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-muted-foreground text-xs">
                      <th className="text-left py-2 pr-3">Timestamp</th>
                      <th className="text-left py-2 pr-3">Staff</th>
                      <th className="text-left py-2 pr-3">Action</th>
                      <th className="text-left py-2 pr-3">Target</th>
                      <th className="text-left py-2 pr-3">IP Address</th>
                      <th className="text-left py-2">Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {entries.map((e) => (
                      <tr key={e.id} className="border-b last:border-0 hover:bg-muted/30 group">
                        <td className="py-2 pr-3 text-xs text-muted-foreground whitespace-nowrap">
                          {new Date(e.timestamp).toLocaleString()}
                        </td>
                        <td className="py-2 pr-3">
                          <div className="font-medium text-xs">{e.staff_member?.name ?? '—'}</div>
                          <div className="text-xs text-muted-foreground">{e.staff_member?.email}</div>
                        </td>
                        <td className="py-2 pr-3">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${ACTION_BADGE_COLORS[e.action_type] ?? 'bg-gray-100 text-gray-700'}`}>
                            {e.action_type}
                          </span>
                        </td>
                        <td className="py-2 pr-3">
                          <div className="text-xs">{e.target_repr || '—'}</div>
                          <div className="text-xs text-muted-foreground capitalize">{e.target_type}</div>
                        </td>
                        <td className="py-2 pr-3 font-mono text-xs text-muted-foreground">
                          {e.ip_address ?? '—'}
                        </td>
                        <td className="py-2 text-xs text-muted-foreground max-w-[200px] truncate" title={e.notes}>
                          {e.notes || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex items-center justify-between mt-4">
                <p className="text-sm text-muted-foreground">Page {page} of {totalPages}</p>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
                    Previous
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => setPage(p => p + 1)} disabled={page >= totalPages}>
                    Next
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
