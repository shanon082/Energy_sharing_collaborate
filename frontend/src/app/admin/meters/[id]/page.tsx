'use client';

export const dynamic = "force-dynamic";

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/use-toast';
import { ArrowLeft, KeyRound, Save, Trash2, Zap } from 'lucide-react';
import { get, patch, post } from '@/lib/fetch-client';
import { getErrorMessage } from '@/lib/errors';

interface MeterDetail {
  id: number;
  meter_no: string;
  label: string;
  status: string;
  architecture: 'STS' | 'AMI';
  units: number;
  static_ip: string;
  iot_device_token: string;
  has_iot_token: boolean;
  linked_user: {
    id: number;
    name: string;
    phone: string;
    email: string;
  };
  registration_date: string;
  last_token_loaded: string | null;
  last_token_units: number | null;
  total_tokens_issued: number;
  total_kwh_issued: number;
  transfers_received_kwh: number;
  deactivation_reason: string | null;
  deactivated_at: string | null;
}

export default function MeterDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { toast } = useToast();
  const [meter, setMeter] = useState<MeterDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [editToken, setEditToken] = useState('');
  const [editLabel, setEditLabel] = useState('');

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const res = await get<any>(`admin/meters/${params.id}/`);
        if (cancelled) return;
        if (res.data?.meter) {
          setMeter(res.data.meter);
          setEditToken(res.data.meter.iot_device_token || '');
          setEditLabel(res.data.meter.label || '');
        } else if (res.error) {
          toast({ title: 'Error', description: getErrorMessage(res.error) || 'Meter not found', variant: 'destructive' });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    if (params.id) load();
    return () => { cancelled = true; };
  }, [params.id]);

  async function handleSave() {
    if (!meter) return;
    if (meter.architecture === 'AMI' && !editToken.trim()) {
      toast({ title: 'Token required', description: 'AMI meters need a ThingsBoard device token.', variant: 'destructive' });
      return;
    }
    setSaving(true);
    try {
      const payload: Record<string, string> = { label: editLabel.trim() || meter.label };
      if (meter.architecture === 'AMI') {
        payload.iot_device_token = editToken.trim();
      }
      const res = await patch<any>(`admin/meters/${meter.id}/`, payload);
      if (res.data?.success) {
        toast({ title: 'Saved', description: 'Meter updated' });
        const refresh = await get<any>(`admin/meters/${params.id}/`);
        if (refresh.data?.meter) setMeter(refresh.data.meter);
      } else {
        toast({ title: 'Error', description: res.data?.error || getErrorMessage(res.error) || 'Update failed', variant: 'destructive' });
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!meter) return;
    const confirmed = window.confirm(
      `Remove meter ${meter.meter_no} from ${meter.linked_user.email}? The number can be registered again later. An audit record will be kept.`
    );
    if (!confirmed) return;
    setDeleting(true);
    try {
      const res = await post<any>(`admin/meters/${meter.id}/delete/`, {
        reason: 'Removed by admin',
      });
      if (res.data?.success) {
        toast({ title: 'Meter removed', description: res.data.message });
        router.push('/admin/meters');
      } else {
        toast({
          title: 'Error',
          description: res.data?.error || getErrorMessage(res.error) || 'Delete failed',
          variant: 'destructive',
        });
      }
    } finally {
      setDeleting(false);
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (!meter) {
    return (
      <div className="space-y-4">
        <Button variant="outline" onClick={() => router.push('/admin/meters')}>
          <ArrowLeft className="h-4 w-4 mr-2" /> Back to meters
        </Button>
        <p className="text-muted-foreground">Meter not found.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="outline" size="icon" onClick={() => router.push('/admin/meters')}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight font-mono">{meter.meter_no}</h1>
          <p className="text-sm text-muted-foreground">{meter.label} · {meter.architecture} · {meter.status}</p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Zap className="h-4 w-4" /> Meter info
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Type</span>
              <Badge variant={meter.architecture === 'AMI' ? 'default' : 'secondary'}>{meter.architecture}</Badge>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Balance</span>
              <span className="font-medium tabular-nums">{meter.units.toFixed(2)} kWh</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Static IP</span>
              <span className="font-mono">{meter.static_ip || '—'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Registered</span>
              <span>{new Date(meter.registration_date).toLocaleString()}</span>
            </div>
            <div className="space-y-1">
              <label className="text-muted-foreground">Label</label>
              <Input value={editLabel} onChange={(e) => setEditLabel(e.target.value)} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Owner</CardTitle>
            <CardDescription>{meter.linked_user.email}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p className="font-medium">{meter.linked_user.name}</p>
            <p className="text-muted-foreground">{meter.linked_user.phone || 'No phone'}</p>
            <Button variant="outline" size="sm" onClick={() => router.push(`/admin/users/${meter.linked_user.id}`)}>
              View user profile
            </Button>
          </CardContent>
        </Card>

        {meter.architecture === 'AMI' && (
          <Card className="md:col-span-2">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <KeyRound className="h-4 w-4" /> ThingsBoard device token
              </CardTitle>
              <CardDescription>
                Required for pushing purchased units and reading live balance from ThingsBoard. STS meters do not use this field.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {!meter.has_iot_token && (
                <Badge variant="outline" className="text-amber-700 border-amber-300">
                  No token set — AMI sync disabled until configured
                </Badge>
              )}
              <Input
                value={editToken}
                onChange={(e) => setEditToken(e.target.value)}
                placeholder="Paste ThingsBoard device access token"
                className="font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">
                Copy from ThingsBoard → Devices → your device → Access token. Use <code className="text-xs">dev-</code> prefix for local stub testing.
              </p>
            </CardContent>
          </Card>
        )}

        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Usage summary</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-3 text-sm">
            <div>
              <p className="text-muted-foreground">Tokens issued</p>
              <p className="text-xl font-semibold">{meter.total_tokens_issued}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Total kWh issued</p>
              <p className="text-xl font-semibold">{meter.total_kwh_issued.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Transfers received</p>
              <p className="text-xl font-semibold">{meter.transfers_received_kwh.toFixed(2)} kWh</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="flex gap-2">
        <Button onClick={handleSave} disabled={saving}>
          <Save className="h-4 w-4 mr-2" />
          {saving ? 'Saving…' : 'Save changes'}
        </Button>
        <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
          <Trash2 className="h-4 w-4 mr-2" />
          {deleting ? 'Removing…' : 'Remove from account'}
        </Button>
      </div>
    </div>
  );
}
