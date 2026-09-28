"use client";

import { updateAccountData, UserAccount, EnergyPreference, PaymentMethod } from '@/lib/schema';
import { useState } from 'react';
import { 
  UserCircleIcon, 
  EnvelopeIcon, 
  PhoneIcon, 
  HomeIcon, 
  LightBulbIcon, 
  CreditCardIcon,
  ExclamationCircleIcon 
} from '@heroicons/react/24/outline';

interface AccountFormProps {
  accountData: UserAccount;
  onCancel: () => void;
  onSave: (data: UserAccount) => void;
}

const AccountForm = ({ accountData, onCancel, onSave }: AccountFormProps) => {
  const [formData, setFormData] = useState<UserAccount>(accountData);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validateField = (name: string, value: string) => {
    const newErrors = { ...errors };
    
    switch (name) {
      case 'firstName':
        if (!value.trim()) newErrors.firstName = 'First name is required';
        else if (value.length < 2) newErrors.firstName = 'First name must be at least 2 characters';
        else delete newErrors.firstName;
        break;
      case 'lastName':
        if (!value.trim()) newErrors.lastName = 'Last name is required';
        else if (value.length < 2) newErrors.lastName = 'Last name must be at least 2 characters';
        else delete newErrors.lastName;
        break;
      case 'email':
        if (!value.trim()) newErrors.email = 'Email is required';
        else if (!/\S+@\S+\.\S+/.test(value)) newErrors.email = 'Please enter a valid email address';
        else delete newErrors.email;
        break;
      case 'phoneNumber':
        if (!value.trim()) newErrors.phoneNumber = 'Phone number is required';
        else if (!/^\+?[\d\s\-()]+$/.test(value)) newErrors.phoneNumber = 'Please enter a valid phone number';
        else delete newErrors.phoneNumber;
        break;
      default:
        delete newErrors[name];
    }
    
    setErrors(newErrors);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    validateField(name, value);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validate all fields
    const requiredFields = ['firstName', 'lastName', 'email', 'phoneNumber'];
    let hasErrors = false;
    const newErrors = { ...errors };
    
    requiredFields.forEach(field => {
      const value = formData[field as keyof UserAccount];
      if (!value || (typeof value === 'string' && !value.trim())) {
        newErrors[field] = `${field.replace(/([A-Z])/g, ' $1')} is required`;
        hasErrors = true;
      }
    });
    
    setErrors(newErrors);
    if (hasErrors) return;
    
    setIsSubmitting(true);
    try {
      const updatedData = await updateAccountData(formData);
      onSave(updatedData);
    } catch (error) {
      console.error('Failed to update account:', error);
      setErrors({ 
        submit: 'Failed to update account. Please try again.' 
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const FormField = ({ 
    id, 
    name, 
    label, 
    type = "text", 
    icon: Icon, 
    required = false,
    disabled = false,
    placeholder = "",
    children 
  }: {
    id: string;
    name: string;
    label: string;
    type?: string;
    icon: any;
    required?: boolean;
    disabled?: boolean;
    placeholder?: string;
    children?: React.ReactNode;
  }) => (
    <div className="space-y-2">
      <label htmlFor={id} className="block text-sm font-medium text-gray-700">
        <div className="flex items-center space-x-1">
          <Icon className="h-4 w-4" />
          <span>{label} {required && <span className="text-red-500">*</span>}</span>
        </div>
      </label>
      {children ? children : (
        <input
          type={type}
          id={id}
          name={name}
          value={formData[name as keyof UserAccount] as string || ''}
          onChange={handleChange}
          disabled={disabled}
          placeholder={placeholder}
          className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors ${
            errors[name] ? 'border-red-300' : 'border-gray-300'
          } ${disabled ? 'bg-gray-100 cursor-not-allowed' : ''}`}
        />
      )}
      {errors[name] && (
        <p className="text-sm text-red-600 flex items-center">
          <ExclamationCircleIcon className="h-4 w-4 mr-1" />
          {errors[name]}
        </p>
      )}
    </div>
  );

  return (
    <form onSubmit={handleSubmit} className="p-6 space-y-6">
      <div className="border-b pb-4">
        <h2 className="text-xl font-semibold text-gray-900">Edit Profile Information</h2>
        <p className="text-gray-600 mt-1">Update your account details and preferences</p>
      </div>

      {errors.submit && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center">
            <ExclamationCircleIcon className="h-5 w-5 text-red-600 mr-2" />
            <p className="text-red-800">{errors.submit}</p>
          </div>
        </div>
      )}

      {/* Account Information */}
      <div className="bg-gray-50 rounded-lg p-4">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Account Information</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FormField
            id="accountNumber"
            name="accountNumber"
            label="Account Number"
            icon={UserCircleIcon}
            disabled
          />
          <div className="space-y-2">
            <p className="text-xs text-gray-500">
              Account number cannot be changed as it's your unique identifier.
            </p>
          </div>
        </div>
      </div>

      {/* Personal Information */}
      <div className="bg-gray-50 rounded-lg p-4">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Personal Information</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FormField
            id="firstName"
            name="firstName"
            label="First Name"
            icon={UserCircleIcon}
            required
          />
          <FormField
            id="lastName"
            name="lastName"
            label="Last Name"
            icon={UserCircleIcon}
            required
          />
          <FormField
            id="email"
            name="email"
            label="Email Address"
            type="email"
            icon={EnvelopeIcon}
            required
          />
          <FormField
            id="phoneNumber"
            name="phoneNumber"
            label="Phone Number"
            type="tel"
            icon={PhoneIcon}
            required
          />
        </div>
      </div>

      {/* Address & Preferences */}
      <div className="bg-gray-50 rounded-lg p-4">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Address & Preferences</h3>
        <div className="space-y-4">
          <FormField
            id="address"
            name="address"
            label="Address"
            icon={HomeIcon}
            placeholder="Enter your full address"
          />
          
          <FormField
            id="energyPreference"
            name="energyPreference"
            label="Electricity Preference"
            icon={LightBulbIcon}
          >
            <select
              id="energyPreference"
              name="energyPreference"
              value={formData.energyPreference || ''}
              onChange={handleChange}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">Select Electricity Preference</option>
              <option value={EnergyPreference.SOLAR}>Solar</option>
              <option value={EnergyPreference.HYDRO}>Hydro</option>
              <option value={EnergyPreference.THERMAL}>Thermal</option>
              <option value={EnergyPreference.OTHER}>Other</option>
            </select>
          </FormField>

          <FormField
            id="paymentMethod"
            name="paymentMethod"
            label="Payment Method"
            icon={CreditCardIcon}
          >
            <select
              id="paymentMethod"
              name="paymentMethod"
              value={formData.paymentMethod || ''}
              onChange={handleChange}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">Select Payment Method</option>
              <option value={PaymentMethod.CREDIT_CARD}>Credit Card</option>
              <option value={PaymentMethod.MOBILE_MONEY}>Mobile Money</option>
              <option value={PaymentMethod.BANK_TRANSFER}>Bank Transfer</option>
            </select>
          </FormField>
        </div>
      </div>

      {/* Form Actions */}
      <div className="flex justify-end space-x-3 pt-6 border-t">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium transition-colors disabled:opacity-50"
          disabled={isSubmitting}
        >
          Cancel
        </button>
        <button
          type="submit"
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
          disabled={isSubmitting}
        >
          {isSubmitting ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              <span>Saving...</span>
            </>
          ) : (
            <span>Save Changes</span>
          )}
        </button>
      </div>
    </form>
  );
};

export default AccountForm;