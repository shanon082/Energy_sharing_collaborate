'use client';

export const dynamic = "force-dynamic";

import { useEffect, useState } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
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
import { Pencil, Save, Trash2, Plus, X, ArrowLeft } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/use-toast';
import { useRouter } from 'next/navigation';
import { get, put, del, post } from '@/lib/fetch-client';
import { getApiErrorMessage } from '@/lib/api-response';
import Link from 'next/link';

interface LoanTier {
  id: number;
  name: string;
  display_name: string;
  min_score: number;
  max_score: number;
  max_amount: number;
  interest_rate: number;
  is_active: boolean;
}

export default function LoanTiersManagementPage() {
  const router = useRouter();
  const { toast } = useToast();

  const [tiers, setTiers] = useState<LoanTier[]>([]);
  const [loading, setLoading] = useState(true);


  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<Partial<LoanTier>>({});


  const [creating, setCreating] = useState(false);
  const [newForm, setNewForm] = useState<Partial<LoanTier>>({
    name: '',
    display_name: '',
    min_score: 0,
    max_score: 0,
    max_amount: 0,
    interest_rate: 0,
    is_active: true,
  });

  const fetchTiers = async () => {
    try {
      setLoading(true);
      const response = await get<LoanTier[]>('admin/loan-tiers/');

      if (response.error) {
        throw new Error(getApiErrorMessage(response.error, 'Failed to load tiers'));
      }

      setTiers(response.data || []);
    } catch (err: any) {
      console.error(err);
      toast({
        title: 'Error',
        description: err.message || 'Failed to load loan tiers',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTiers();
  }, []);

  const startEdit = (tier: LoanTier) => {
    setEditingId(tier.id);
    setEditForm({ ...tier });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditForm({});
  };

  const saveEdit = async (id: number) => {
    try {
      const response = await put<LoanTier>(`admin/loan-tiers/${id}/`, editForm);

      if (response.error) {
        throw new Error(getApiErrorMessage(response.error, 'Failed to update tier'));
      }

      toast({ title: 'Success', description: 'Loan tier updated' });
      setEditingId(null);
      fetchTiers();
    } catch (err: any) {
      toast({
        title: 'Error',
        description: err.message || 'Could not save changes',
        variant: 'destructive',
      });
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this loan tier permanently?')) return;

    try {
      const response = await del(`admin/loan-tiers/${id}/`);

      if (response.error) {
        throw new Error(getApiErrorMessage(response.error, 'Failed to delete'));
      }

      toast({ title: 'Success', description: 'Tier deleted' });
      fetchTiers();
    } catch (err: any) {
      toast({
        title: 'Error',
        description: err.message || 'Could not delete tier',
        variant: 'destructive',
      });
    }
  };

  const handleEditChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setEditForm(prev => ({
      ...prev,
      [name]: ['min_score', 'max_score', 'max_amount', 'interest_rate'].includes(name)
        ? Number(value) || 0
        : value,
    }));
  };


  const handleNewChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setNewForm(prev => ({
      ...prev,
      [name]: ['min_score', 'max_score', 'max_amount', 'interest_rate'].includes(name)
        ? Number(value) || 0
        : value,
    }));
  };

  const handleCreate = async () => {
    // Basic client-side validation
    if (!newForm.name?.trim()) {
      toast({ title: 'Error', description: 'Name is required', variant: 'destructive' });
      return;
    }
    if (!newForm.display_name?.trim()) {
      toast({ title: 'Error', description: 'Display name is required', variant: 'destructive' });
      return;
    }
    if ((newForm.min_score ?? 0) >= (newForm.max_score ?? 0)) {
      toast({ title: 'Error', description: 'Min score must be less than max score', variant: 'destructive' });
      return;
    }

    try {
      const response = await post<LoanTier>('admin/loan-tiers/', newForm);

      if (response.error) {
        throw new Error(getApiErrorMessage(response.error, 'Failed to create tier'));
      }

      toast({ title: 'Success', description: 'New loan tier created' });
      setCreating(false);
      setNewForm({
        name: '',
        display_name: '',
        min_score: 0,
        max_score: 0,
        max_amount: 0,
        interest_rate: 0,
        is_active: true,
      });
      fetchTiers();
    } catch (err: any) {
      toast({
        title: 'Error',
        description: err.message || 'Could not create tier',
        variant: 'destructive',
      });
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto py-10">
        <Skeleton className="h-12 w-64 mb-6" />
        <Skeleton className="h-[400px] w-full" />
      </div>
    );
  }

  return (
    <div className="container mx-auto py-10">
      {/* Back button */}
    <div className="mb-6">
      <Button 
        variant="ghost" 
        size="sm" 
        asChild
        className="gap-2 text-muted-foreground hover:text-foreground"
      >
        <Link href="/admin/loans">
          <ArrowLeft className="h-4 w-4" />
          Back to Loans Management
        </Link>
      </Button>
    </div>
      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between space-y-0 pb-2">
          <div>
            <CardTitle>Loan Tiers Management</CardTitle>
            <CardDescription>View, edit and create dynamic loan tiers</CardDescription>
          </div>
          <Button onClick={() => setCreating(true)} className="w-full sm:w-auto">
            <Plus className="h-4 w-4 mr-2" />
            New Loan Tier
          </Button>
        </CardHeader>

        <CardContent>
          <div className="rounded-md border overflow-x-auto">
            <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Display Name</TableHead>
                <TableHead>Score Range</TableHead>
                <TableHead>Max Amount (UGX)</TableHead>
                <TableHead>Interest Rate (%)</TableHead>
                <TableHead>Active</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tiers.map(tier => (
                <TableRow key={tier.id}>
                  <TableCell className="font-medium">
                    {editingId === tier.id ? (
                      <Input
                        name="name"
                        value={editForm.name || ''}
                        onChange={handleEditChange}
                      />
                    ) : (
                      tier.name
                    )}
                  </TableCell>
                  <TableCell>
                    {editingId === tier.id ? (
                      <Input
                        name="display_name"
                        value={editForm.display_name || ''}
                        onChange={handleEditChange}
                      />
                    ) : (
                      tier.display_name
                    )}
                  </TableCell>
                  <TableCell>
                    {editingId === tier.id ? (
                      <div className="flex items-center gap-2">
                        <Input
                          name="min_score"
                          type="number"
                          value={editForm.min_score ?? ''}
                          onChange={handleEditChange}
                          className="w-20"
                        />
                        <span>-</span>
                        <Input
                          name="max_score"
                          type="number"
                          value={editForm.max_score ?? ''}
                          onChange={handleEditChange}
                          className="w-20"
                        />
                      </div>
                    ) : (
                      `${tier.min_score} - ${tier.max_score}`
                    )}
                  </TableCell>
                  <TableCell>
                    {editingId === tier.id ? (
                      <Input
                        name="max_amount"
                        type="number"
                        value={editForm.max_amount ?? ''}
                        onChange={handleEditChange}
                      />
                    ) : (
                      tier.max_amount.toLocaleString()
                    )}
                  </TableCell>
                  <TableCell>
                    {editingId === tier.id ? (
                      <Input
                        name="interest_rate"
                        type="number"
                        step="0.1"
                        value={editForm.interest_rate ?? ''}
                        onChange={handleEditChange}
                      />
                    ) : (
                      `${tier.interest_rate}%`
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant={tier.is_active ? 'default' : 'secondary'}>
                      {tier.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    {editingId === tier.id ? (
                      <div className="flex justify-end gap-2">
                        <Button
                          size="sm"
                          variant="default"
                          onClick={() => saveEdit(tier.id)}
                        >
                          <Save className="h-4 w-4 mr-1" />
                          Save
                        </Button>
                        <Button size="sm" variant="outline" onClick={cancelEdit}>
                          Cancel
                        </Button>
                      </div>
                    ) : (
                      <div className="flex justify-end gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => startEdit(tier)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-destructive hover:text-destructive/90"
                          onClick={() => handleDelete(tier.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              ))}

              {tiers.length === 0 && !loading && (
                <TableRow>
                  <TableCell colSpan={7} className="h-32 text-center text-muted-foreground">
                    No loan tiers found
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      
      {creating && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-background rounded-xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold">Create New Loan Tier</h2>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setCreating(false)}
                >
                  <X className="h-5 w-5" />
                </Button>
              </div>

              <div className="grid gap-5">
                <div>
                  <label className="block text-sm font-medium mb-1.5">
                    Internal Name (code)
                  </label>
                  <Input
                    value={newForm.name || ''}
                    onChange={handleNewChange}
                    name="name"
                    placeholder="e.g. Diamond"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1.5">
                    Display Name
                  </label>
                  <Input
                    value={newForm.display_name || ''}
                    onChange={handleNewChange}
                    name="display_name"
                    placeholder="e.g. Diamond Tier"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1.5">
                      Min Credit Score
                    </label>
                    <Input
                      type="number"
                      name="min_score"
                      value={newForm.min_score ?? ''}
                      onChange={handleNewChange}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1.5">
                      Max Credit Score
                    </label>
                    <Input
                      type="number"
                      name="max_score"
                      value={newForm.max_score ?? ''}
                      onChange={handleNewChange}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1.5">
                      Max Loan Amount (UGX)
                    </label>
                    <Input
                      type="number"
                      name="max_amount"
                      value={newForm.max_amount ?? ''}
                      onChange={handleNewChange}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1.5">
                      Interest Rate (%)
                    </label>
                    <Input
                      type="number"
                      step="0.1"
                      name="interest_rate"
                      value={newForm.interest_rate ?? ''}
                      onChange={handleNewChange}
                    />
                  </div>
                </div>

                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="is_active"
                    checked={newForm.is_active ?? true}
                    onChange={e =>
                      setNewForm(prev => ({ ...prev, is_active: e.target.checked }))
                    }
                    className="h-4 w-4 rounded border-gray-300"
                  />
                  <label htmlFor="is_active" className="ml-2 text-sm font-medium">
                    Active (available for new loans)
                  </label>
                </div>
              </div>

              <div className="flex justify-end gap-3 mt-8">
                <Button variant="outline" onClick={() => setCreating(false)}>
                  Cancel
                </Button>
                <Button onClick={handleCreate}>
                  Create Loan Tier
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

