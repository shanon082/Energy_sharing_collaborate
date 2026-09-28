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
import { Pencil, Trash2, Plus, X, Save, Download, Zap } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/use-toast';
import { get, put, del, post } from '@/lib/fetch-client';
import { getApiErrorMessage } from '@/lib/api-response';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

interface TariffBlock {
  id?: number;
  block_name: string;
  min_units: number;
  max_units?: number | null;
  rate_per_unit: number;
  block_order: number;
  is_lifeline_block?: boolean;
  non_lifeline_rate?: number | null;
}

interface Tariff {
  id: number;
  tariff_code: string;
  tariff_name: string;
  tariff_type: 'DOMESTIC' | 'COMMERCIAL' | 'INDUSTRIAL';
  voltage_level: string;
  voltage_value: string;
  service_charge: number;
  is_active: boolean;
  effective_date: string;
  effective_from?: string | null;
  effective_to?: string | null;
  blocks: TariffBlock[];
}

const ERA_TEMPLATE_BLOCKS: TariffBlock[] = [
  {
    block_name: 'Lifeline (first 15 units)',
    min_units: 0,
    max_units: 15,
    rate_per_unit: 250,
    block_order: 1,
    is_lifeline_block: true,
    non_lifeline_rate: 756.2,
  },
  {
    block_name: 'Normal (16-80 units)',
    min_units: 16,
    max_units: 80,
    rate_per_unit: 756.2,
    block_order: 2,
    is_lifeline_block: false,
  },
  {
    block_name: 'Cooking tariff (81-150 units)',
    min_units: 81,
    max_units: 150,
    rate_per_unit: 412,
    block_order: 3,
    is_lifeline_block: false,
  },
  {
    block_name: 'Super normal (above 150 units)',
    min_units: 151,
    max_units: null,
    rate_per_unit: 756,
    block_order: 4,
    is_lifeline_block: false,
  },
];

export default function TariffsManagementPage() {
  const { toast } = useToast();
  const [tariffs, setTariffs] = useState<Tariff[]>([]);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedTariff, setSelectedTariff] = useState<Tariff | null>(null);

  const activeTariff = tariffs.find(t => t.is_active);

  // Form state for create/edit
  const [form, setForm] = useState<Tariff>({
    id: 0,
    tariff_code: '',
    tariff_name: '',
    tariff_type: 'DOMESTIC',
    voltage_level: '',
    voltage_value: '',
    service_charge: 0,
    is_active: true,
    effective_date: new Date().toISOString().split('T')[0],
    blocks: [],
  });

  const fetchTariffs = async () => {
    try {
      setLoading(true);
      const response = await get<Tariff[]>('admin/tariffs/');

      if (response.error) {
        throw new Error(getApiErrorMessage(response.error, 'Failed to load tariffs'));
      }

      setTariffs(response.data || []);
    } catch (err: any) {
      toast({
        title: 'Error',
        description: err.message || 'Could not load tariffs',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTariffs();
  }, []);

  const openCreateModal = (useEraTemplate = false) => {
    const today = new Date().toISOString().split('T')[0];
    const hasActive = tariffs.some(t => t.is_active);
    setSelectedTariff(null);
    setForm({
      id: 0,
      tariff_code: useEraTemplate ? 'DOM-10.1-2026Q1' : '',
      tariff_name: useEraTemplate ? 'ERA Domestic Code 10.1 (Q1 2026)' : '',
      tariff_type: 'DOMESTIC',
      voltage_level: useEraTemplate ? 'Low Voltage Single Phase' : '',
      voltage_value: useEraTemplate ? '240V' : '',
      service_charge: useEraTemplate ? 3360 : 0,
      is_active: !hasActive,
      effective_date: today,
      effective_from: useEraTemplate ? '2026-01-01' : today,
      effective_to: null,
      blocks: useEraTemplate ? ERA_TEMPLATE_BLOCKS.map(b => ({ ...b })) : [],
    });
    setModalOpen(true);
  };

  const handleImportEra = async () => {
    if (!confirm('Import ERA domestic Code 10.1 rates and set as the active system tariff?')) return;
    try {
      setSeeding(true);
      const response = await post<{ message?: string }>('admin/tariffs/seed-era/', {});
      if (response.error) {
        throw new Error(getApiErrorMessage(response.error, 'Import failed'));
      }
      toast({
        title: 'ERA tariff imported',
        description: response.data?.message || 'Default ERA domestic tariff is now active.',
      });
      fetchTariffs();
    } catch (err: any) {
      toast({ title: 'Error', description: err.message, variant: 'destructive' });
    } finally {
      setSeeding(false);
    }
  };

  const handleActivate = async (id: number) => {
    try {
      const response = await post<{ message?: string }>(`admin/tariffs/${id}/activate/`, {});
      if (response.error) {
        throw new Error(getApiErrorMessage(response.error, 'Activation failed'));
      }
      toast({
        title: 'Tariff activated',
        description: response.data?.message || 'This tariff is now used system-wide.',
      });
      fetchTariffs();
    } catch (err: any) {
      toast({ title: 'Error', description: err.message, variant: 'destructive' });
    }
  };

  const openEditModal = (tariff: Tariff) => {
    setSelectedTariff(tariff);
    setForm({
      ...tariff,
      blocks: (tariff.blocks || []).map(block => ({
        ...block,
        id: block.id 
      }))
    });
    setModalOpen(true);
  };

  const addBlock = () => {
    setForm(prev => {
      const currentBlocks = Array.isArray(prev.blocks) ? prev.blocks : [];
      const lastBlock = currentBlocks[currentBlocks.length - 1];
      
      let defaultMinUnits = 0;
      if (currentBlocks.length === 0) {
        defaultMinUnits = 0;
      } else if (lastBlock && lastBlock.max_units) {
        defaultMinUnits = lastBlock.max_units + 1;
      } else if (lastBlock) {
        defaultMinUnits = (lastBlock.min_units || 0) + 100;
      }

      const newBlock: TariffBlock = {
        block_name: `Block ${currentBlocks.length + 1}`,
        min_units: defaultMinUnits,
        max_units: null,
        rate_per_unit: 0,
        block_order: currentBlocks.length + 1,
      };

      return {
        ...prev,
        blocks: [...currentBlocks, newBlock],
      };
    });
  };

  const updateBlock = (index: number, field: keyof TariffBlock, value: any) => {
    setForm(prev => {
      const currentBlocks = Array.isArray(prev.blocks) ? prev.blocks : [];
      const newBlocks = [...currentBlocks];
      
      if (newBlocks[index]) {
        newBlocks[index] = { ...newBlocks[index], [field]: value };
      }
      
      return { ...prev, blocks: newBlocks };
    });
  };

  const removeBlock = (index: number) => {
    setForm(prev => {
      const currentBlocks = Array.isArray(prev.blocks) ? prev.blocks : [];
      return {
        ...prev,
        blocks: currentBlocks.filter((_, i) => i !== index),
      };
    });
  };

  const handleSave = async () => {
    try {
      // Validate required fields
      if (!form.tariff_code?.trim()) {
        toast({ title: 'Error', description: 'Tariff code is required', variant: 'destructive' });
        return;
      }
      if (!form.tariff_name?.trim()) {
        toast({ title: 'Error', description: 'Tariff name is required', variant: 'destructive' });
        return;
      }

      // Validate blocks
      const blocks = Array.isArray(form.blocks) ? form.blocks : [];
      const isValid = blocks.every(block => 
        block.block_name?.trim() && 
        typeof block.min_units === 'number' && 
        block.rate_per_unit > 0
      );

      if (blocks.length > 0 && !isValid) {
        toast({
          title: 'Validation Error',
          description: 'Please fill in all required block fields with valid values',
          variant: 'destructive',
        });
        return;
      }

      // Prepare the payload exactly like loan-tiers pattern
      const payload = {
        tariff_code: form.tariff_code,
        tariff_name: form.tariff_name,
        tariff_type: form.tariff_type,
        voltage_level: form.voltage_level,
        voltage_value: form.voltage_value,
        service_charge: Number(form.service_charge),
        is_active: form.is_active,
        effective_date: form.effective_date,
        effective_from: form.effective_from || form.effective_date,
        effective_to: form.effective_to || null,
        blocks: blocks.map((block, index) => {
          const blockPayload: Record<string, unknown> = {
            block_name: block.block_name,
            min_units: Number(block.min_units),
            max_units: block.max_units != null ? Number(block.max_units) : null,
            rate_per_unit: Number(block.rate_per_unit),
            block_order: block.block_order || index + 1,
            is_lifeline_block: Boolean(block.is_lifeline_block),
            non_lifeline_rate: block.non_lifeline_rate != null ? Number(block.non_lifeline_rate) : null,
          };
          if (block.id) blockPayload.id = block.id;
          return blockPayload;
        }),
      };

      let response;
      if (selectedTariff?.id) {
        // Update existing
        response = await put<Tariff>(`admin/tariffs/${selectedTariff.id}/`, payload);
      } else {
        // Create new
        response = await post<Tariff>('admin/tariffs/', payload);
      }

      if (response.error) {
        throw new Error(getApiErrorMessage(response.error, 'Failed to save tariff'));
      }

      toast({ 
        title: 'Success', 
        description: `Tariff ${selectedTariff?.id ? 'updated' : 'created'} successfully` 
      });
      
      setModalOpen(false);
      fetchTariffs(); // Refresh the list
      
    } catch (err: any) {
      console.error('Save error:', err);
      toast({
        title: 'Error',
        description: err.message || 'Could not save tariff',
        variant: 'destructive',
      });
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this tariff? This action cannot be undone.')) return;
    
    try {
      const response = await del(`admin/tariffs/${id}/`);
      
      if (response.error) {
        throw new Error(getApiErrorMessage(response.error, 'Delete failed'));
      }
      
      toast({ title: 'Success', description: 'Tariff deleted successfully' });
      fetchTariffs();
    } catch (err: any) {
      toast({ 
        title: 'Error', 
        description: err.message || 'Could not delete tariff', 
        variant: 'destructive' 
      });
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto py-10">
        <Skeleton className="h-12 w-64 mb-6" />
        <Skeleton className="h-[500px] w-full" />
      </div>
    );
  }

  return (
    <div className="container mx-auto py-10">
      <Alert className="mb-6">
        <AlertTitle>ERA billing — one active tariff</AlertTitle>
        <AlertDescription>
          Buy Units, loan disbursement, and unit estimates use the single <strong>Active</strong> domestic
          tariff (tiered blocks + service charge + 18% VAT). Adding or editing tariffs here takes effect
          system-wide once marked Active; all other schedules are set Inactive automatically.
          {activeTariff ? (
            <> Current active: <strong>{activeTariff.tariff_code}</strong> — {activeTariff.tariff_name}.</>
          ) : (
            <> No active tariff — import ERA defaults or create one and set it Active.</>
          )}
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle>Tariffs Management</CardTitle>
            <CardDescription>
              ERA/UEDCL electricity rates used for wallet top-ups, STS tokens, and loan unit calculations
            </CardDescription>
          </div>
          <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
            <Button
              variant="outline"
              onClick={handleImportEra}
              disabled={seeding}
              className="w-full sm:w-auto"
            >
              <Download className="h-4 w-4 mr-2" />
              {seeding ? 'Importing…' : 'Import ERA defaults'}
            </Button>
            <Button
              variant="outline"
              onClick={() => openCreateModal(true)}
              className="w-full sm:w-auto"
            >
              <Plus className="h-4 w-4 mr-2" /> New from ERA template
            </Button>
            <Button onClick={() => openCreateModal(false)} className="w-full sm:w-auto">
              <Plus className="h-4 w-4 mr-2" /> New Tariff
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border overflow-x-auto">
            <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Code</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Service Charge</TableHead>
                <TableHead>Blocks</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tariffs.map(tariff => (
                <TableRow key={tariff.id}>
                  <TableCell className="font-medium">{tariff.tariff_code}</TableCell>
                  <TableCell>{tariff.tariff_name}</TableCell>
                  <TableCell>{tariff.tariff_type}</TableCell>
                  <TableCell>{tariff.service_charge.toLocaleString()} UGX</TableCell>
                  <TableCell>
                    <div className="space-y-1">
                      <span className="font-medium">{tariff.blocks?.length || 0} blocks</span>
                      {tariff.blocks && tariff.blocks.length > 0 && (
                        <div className="text-xs text-muted-foreground">
                          Range: {tariff.blocks[0].min_units} - {tariff.blocks[tariff.blocks.length-1].max_units ?? '∞'} units
                        </div>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant={tariff.is_active ? 'default' : 'secondary'}>
                      {tariff.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right space-x-1">
                    {!tariff.is_active && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleActivate(tariff.id)}
                        title="Set as active system-wide tariff"
                      >
                        <Zap className="h-4 w-4 mr-1" /> Activate
                      </Button>
                    )}
                    <Button variant="ghost" size="sm" onClick={() => openEditModal(tariff)}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive hover:text-destructive/90"
                      onClick={() => handleDelete(tariff.id)}
                      disabled={tariff.is_active}
                      title={tariff.is_active ? 'Activate another tariff before deleting this one' : 'Delete tariff'}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              
              {tariffs.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="h-48 text-center text-muted-foreground">
                    No tariffs yet. Click <strong>Import ERA defaults</strong> to load Code 10.1 domestic
                    rates, or create a custom schedule.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Modal for Create/Edit*/}
      {modalOpen && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-background rounded-xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold">
                  {selectedTariff?.id ? 'Edit Tariff' : 'Create New Tariff'}
                </h2>
                <Button variant="ghost" size="icon" onClick={() => setModalOpen(false)}>
                  <X className="h-5 w-5" />
                </Button>
              </div>

              {/* Basic fields */}
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div>
                  <label className="block text-sm font-medium mb-1.5">Code *</label>
                  <Input
                    value={form.tariff_code}
                    onChange={e => setForm({ ...form, tariff_code: e.target.value })}
                    placeholder="e.g. RES-001"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1.5">Name *</label>
                  <Input
                    value={form.tariff_name}
                    onChange={e => setForm({ ...form, tariff_name: e.target.value })}
                    placeholder="e.g. Residential Standard"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1.5">Tariff Type</label>
                  <select
                    className="w-full border rounded-md px-3 py-2"
                    value={form.tariff_type}
                    onChange={e => setForm({ ...form, tariff_type: e.target.value as Tariff['tariff_type'] })}
                  >
                    <option value="DOMESTIC">Domestic</option>
                    <option value="COMMERCIAL">Commercial</option>
                    <option value="INDUSTRIAL">Industrial</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1.5">Voltage Level</label>
                  <Input
                    value={form.voltage_level}
                    onChange={e => setForm({ ...form, voltage_level: e.target.value })}
                    placeholder="e.g. Low Voltage"
                  />  
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1.5">Voltage Value</label>
                  <Input
                    value={form.voltage_value}
                    onChange={e => setForm({ ...form, voltage_value: e.target.value })}
                    placeholder="e.g. 240V"
                  />  
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1.5">Service Charge (UGX)</label>
                  <Input
                    type="number" 
                    value={form.service_charge}
                    onChange={e => setForm({ ...form, service_charge: Number(e.target.value) })}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1.5">Effective from</label>
                  <Input
                    type="date"
                    value={form.effective_from ?? form.effective_date}
                    onChange={e => setForm({ ...form, effective_from: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1.5">Effective to (optional)</label>
                  <Input
                    type="date"
                    value={form.effective_to ?? ''}
                    onChange={e => setForm({ ...form, effective_to: e.target.value || null })}
                  />
                </div>
                <div className="col-span-2 flex items-center">
                  <label className="flex items-center gap-2 text-sm font-medium">
                    <input
                      type="checkbox"
                      checked={form.is_active}
                      onChange={e => setForm({ ...form, is_active: e.target.checked })}
                      className="w-4 h-4 rounded border-gray-300"
                    />
                    Set as Active (deactivates all other tariffs)
                  </label>
                </div>
              </div>

              {/* Blocks Section */}
              <div className="mb-6">
                <div className="flex justify-between items-center mb-3">
                  <h3 className="font-medium">Pricing Blocks</h3>
                  <Button variant="outline" size="sm" onClick={addBlock}>
                    <Plus className="h-4 w-4 mr-1" /> Add Block
                  </Button>
                </div>

                {(!form.blocks || form.blocks.length === 0) ? (
                  <p className="text-sm text-muted-foreground text-center py-8 border rounded">
                    No blocks added. Click "Add Block" to create pricing blocks.
                  </p>
                ) : (
                  <div className="space-y-3">
                    {Array.isArray(form.blocks) && form.blocks.map((block, idx) => (
                      <div key={block.id || idx} className="border rounded p-4">
                        <div className="grid grid-cols-12 gap-3 items-end">
                          <div className="col-span-3">
                            <label className="block text-xs mb-1">Block Name</label>
                            <Input
                              placeholder="Block name"
                              value={block.block_name}
                              onChange={e => updateBlock(idx, 'block_name', e.target.value)}
                            />
                          </div>
                          <div className="col-span-2">
                            <label className="block text-xs mb-1">Min Units</label>
                            <Input
                              type="number"
                              placeholder="Min"
                              value={block.min_units}
                              onChange={e => updateBlock(idx, 'min_units', Number(e.target.value))}
                            />
                          </div>
                          <div className="col-span-2">
                            <label className="block text-xs mb-1">Max Units</label>
                            <Input
                              type="number"
                              placeholder="Max (∞ if empty)"
                              value={block.max_units ?? ''}
                              onChange={e => updateBlock(idx, 'max_units', e.target.value ? Number(e.target.value) : null)}
                            />
                          </div>
                          <div className="col-span-3">
                            <label className="block text-xs mb-1">Rate per Unit</label>
                            <Input
                              type="number"
                              step="0.01"
                              placeholder="Rate"
                              value={block.rate_per_unit}
                              onChange={e => updateBlock(idx, 'rate_per_unit', Number(e.target.value))}
                            />
                          </div>
                          <div className="col-span-2">
                            <Button 
                              variant="destructive" 
                              size="sm" 
                              onClick={() => removeBlock(idx)}
                              className="w-full"
                            >
                              <X className="h-4 w-4 mr-1" /> Remove
                            </Button>
                          </div>
                        </div>
                        <div className="mt-3 flex flex-wrap items-center gap-4 text-sm">
                          <label className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={Boolean(block.is_lifeline_block)}
                              onChange={e => updateBlock(idx, 'is_lifeline_block', e.target.checked)}
                              className="w-4 h-4 rounded border-gray-300"
                            />
                            Lifeline block
                          </label>
                          {block.is_lifeline_block && (
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-muted-foreground">Non-lifeline rate:</span>
                              <Input
                                type="number"
                                step="0.01"
                                className="h-8 w-28"
                                value={block.non_lifeline_rate ?? ''}
                                onChange={e =>
                                  updateBlock(
                                    idx,
                                    'non_lifeline_rate',
                                    e.target.value ? Number(e.target.value) : null
                                  )
                                }
                              />
                            </div>
                          )}
                        </div>
                        {block.id && (
                          <div className="mt-2 text-xs text-muted-foreground">
                            Block ID: {block.id}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Modal Footer  */}
              <div className="flex justify-end gap-3 mt-8">
                <Button variant="outline" onClick={() => setModalOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={handleSave}>
                  <Save className="h-4 w-4 mr-2" />
                  {selectedTariff?.id ? 'Update' : 'Create'} Tariff
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

