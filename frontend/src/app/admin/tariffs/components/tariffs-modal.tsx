// Updated tariffs-modal.tsx with post/put instead of authFetch
// Also added missing fields for completeness (voltage_level, voltage_value, is_active, effective_date)

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Plus, Trash2 } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { post, put } from '@/lib/fetch-client';
import { Switch } from '@headlessui/react';
import { getApiErrorMessage } from '@/lib/api-response';

interface TariffBlock {
  id?: number;
  block_name: string;
  min_units: number;
  max_units?: number;
  rate_per_unit: number;
  block_order: number;
}

interface Tariff {
  id: number;
  tariff_code: string;
  tariff_name: string;
  tariff_type: string;
  voltage_level: string;
  voltage_value: string;
  service_charge: number;
  is_active: boolean;
  effective_date: string;
  blocks: TariffBlock[];
}

interface TariffsModalProps {
  tariff: Tariff | null;
  onSave: () => void;
}

export default function TariffsModal({ tariff, onSave }: TariffsModalProps) {
  const { toast } = useToast();
  const [form, setForm] = useState<Tariff>(tariff || {
    id: 0,
    tariff_code: '',
    tariff_name: '',
    tariff_type: 'DOMESTIC',
    voltage_level: '',
    voltage_value: '',
    service_charge: 0,
    is_active: true,
    effective_date: new Date().toISOString().split('T')[0],  // Default to today
    blocks: [],
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setForm((prev) => ({ 
      ...prev, 
      [name]: ['service_charge'].includes(name) ? parseFloat(value) || 0 : value 
    }));
  };

  const handleBlockChange = (index: number, name: keyof TariffBlock, value: string) => {
    const newBlocks = [...form.blocks];
    newBlocks[index] = { 
      ...newBlocks[index], 
      [name]: ['min_units', 'max_units', 'rate_per_unit', 'block_order'].includes(name) 
        ? parseFloat(value) || 0 
        : value 
    };
    setForm((prev) => ({ ...prev, blocks: newBlocks }));
  };

  const addBlock = () => {
    setForm((prev) => ({
      ...prev,
      blocks: [
        ...prev.blocks,
        { block_name: '', min_units: 0, max_units: undefined, rate_per_unit: 0, block_order: prev.blocks.length + 1 },
      ],
    }));
  };

  const removeBlock = (index: number) => {
    const newBlocks = form.blocks.filter((_, i) => i !== index);
    setForm((prev) => ({ ...prev, blocks: newBlocks }));
  };

  const handleSubmit = async () => {
    // Basic validation
    if (!form.tariff_code.trim()) {
      toast({ title: 'Error', description: 'Tariff code is required', variant: 'destructive' });
      return;
    }
    if (!form.tariff_name.trim()) {
      toast({ title: 'Error', description: 'Tariff name is required', variant: 'destructive' });
      return;
    }

    try {
      const endpoint = form.id ? `admin/tariffs/${form.id}/` : 'admin/tariffs/';
      const method = form.id ? put : post;
      const res = await method<Tariff>(endpoint, form);
      
      if (res.error) {
        throw new Error(getApiErrorMessage(res.error, 'Failed to save tariff'));
      }
      
      toast({ title: 'Success', description: 'Tariff saved successfully' });
      onSave();
    } catch (error: any) {
      console.error('Save error:', error);
      toast({ title: 'Error', description: error.message || 'Failed to save tariff', variant: 'destructive' });
    }
  };

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button>{form.id ? 'Edit' : 'Create Tariff'}</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[800px] max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{form.id ? 'Edit Tariff' : 'Create New Tariff'}</DialogTitle>
          <DialogDescription>Configure tariff details, including pricing blocks and activation status.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-6 py-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="tariff_code">Tariff Code *</Label>
              <Input 
                id="tariff_code" 
                name="tariff_code" 
                value={form.tariff_code} 
                onChange={handleChange} 
                placeholder="e.g. DOM-2026-01"
              />
            </div>
            <div>
              <Label htmlFor="tariff_name">Tariff Name *</Label>
              <Input 
                id="tariff_name" 
                name="tariff_name" 
                value={form.tariff_name} 
                onChange={handleChange} 
                placeholder="e.g. Domestic Low Voltage 2026"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="tariff_type">Type *</Label>
              <Select
                value={form.tariff_type}
                onValueChange={(value) => setForm((prev) => ({ ...prev, tariff_type: value }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="DOMESTIC">Domestic</SelectItem>
                  <SelectItem value="COMMERCIAL">Commercial</SelectItem>
                  <SelectItem value="INDUSTRIAL">Industrial</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="voltage_level">Voltage Level *</Label>
              <Input 
                id="voltage_level" 
                name="voltage_level" 
                value={form.voltage_level} 
                onChange={handleChange} 
                placeholder="e.g. Low Voltage"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="voltage_value">Voltage Value</Label>
              <Input 
                id="voltage_value" 
                name="voltage_value" 
                value={form.voltage_value} 
                onChange={handleChange} 
                placeholder="e.g. 240V"
              />
            </div>
            <div>
              <Label htmlFor="service_charge">Service Charge (UGX) *</Label>
              <Input
                id="service_charge"
                name="service_charge"
                type="number"
                value={form.service_charge}
                onChange={handleChange}
                placeholder="e.g. 15000"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="effective_date">Effective Date</Label>
              <Input 
                id="effective_date" 
                name="effective_date" 
                type="date"
                value={form.effective_date}
                onChange={handleChange}
              />
            </div>
            <div className="flex items-center pt-5">
              <Switch
                id="is_active"
                checked={form.is_active}
                onChange={(checked) => setForm((prev) => ({ ...prev, is_active: checked }))}
              />
              <Label htmlFor="is_active" className="ml-2">Active</Label>
            </div>
          </div>

          {/* Blocks section */}
          <div>
            <Label className="text-lg font-semibold">Pricing Blocks</Label>
            {form.blocks.map((block, index) => (
              <div key={index} className="grid grid-cols-[1fr_1fr_1fr_1fr_auto] gap-3 mt-3 items-center">
                <Input
                  placeholder="Block Name"
                  value={block.block_name}
                  onChange={(e) => handleBlockChange(index, 'block_name', e.target.value)}
                />
                <Input
                  type="number"
                  placeholder="Min Units"
                  value={block.min_units}
                  onChange={(e) => handleBlockChange(index, 'min_units', e.target.value)}
                />
                <Input
                  type="number"
                  placeholder="Max Units (optional)"
                  value={block.max_units || ''}
                  onChange={(e) => handleBlockChange(index, 'max_units', e.target.value)}
                />
                <Input
                  type="number"
                  step="0.01"
                  placeholder="Rate per Unit"
                  value={block.rate_per_unit}
                  onChange={(e) => handleBlockChange(index, 'rate_per_unit', e.target.value)}
                />
                <Button variant="destructive" size="icon" onClick={() => removeBlock(index)}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
            <Button variant="outline" onClick={addBlock} className="mt-4">
              <Plus className="h-4 w-4 mr-2" /> Add Pricing Block
            </Button>
          </div>
        </div>

        <div className="flex justify-end mt-4">
          <Button onClick={handleSubmit}>Save Changes</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
