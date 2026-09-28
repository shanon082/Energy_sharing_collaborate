import { UserAccount } from "@/lib/schema";
import { 
  UserCircleIcon, 
  EnvelopeIcon, 
  PhoneIcon, 
  HomeIcon, 
  LightBulbIcon, 
  CreditCardIcon,
  WifiIcon,
  Battery100Icon
} from "@heroicons/react/24/outline";

interface AccountDetailsProps {
  accountData: UserAccount;
  onEdit: () => void;
  onViewLoans?: () => void;
  onViewMeter?: () => void;
}

const AccountDetails = ({ accountData, onEdit, onViewLoans, onViewMeter }: AccountDetailsProps) => {
  const DetailItem = ({ 
    icon: Icon, 
    label, 
    value, 
    subtext,
    action 
  }: { 
    icon: any; 
    label: string; 
    value: string; 
    subtext?: string;
    action?: {
      label: string;
      onClick: () => void;
    };
  }) => (
    <div className="flex items-start justify-between p-4 hover:bg-gray-50 rounded-lg transition-colors">
      <div className="flex items-start space-x-3">
        <div className="mt-1">
          <Icon className="h-5 w-5 text-gray-400" />
        </div>
        <div>
          <p className="text-sm font-medium text-gray-500">{label}</p>
          <p className="text-lg font-semibold text-gray-900">{value}</p>
          {subtext && <p className="text-sm text-gray-600">{subtext}</p>}
        </div>
      </div>
      {action && (
        <button
          onClick={action.onClick}
          className="text-sm text-blue-600 hover:text-blue-800 font-medium"
        >
          {action.label}
        </button>
      )}
    </div>
  );

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Account Overview</h2>
            <p className="text-gray-600">Manage your account settings and preferences</p>
          </div>
          <button
            onClick={onEdit}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium transition-colors"
          >
            Edit Profile
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column - Personal Information */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <div className="px-6 py-4 bg-gray-50 border-b">
            <h3 className="text-lg font-semibold text-gray-900">Personal Information</h3>
          </div>
          <div className="divide-y divide-gray-100">
            <DetailItem
              icon={UserCircleIcon}
              label="Account Number"
              value={accountData.accountNumber}
              subtext="Unique account identifier"
            />
            <DetailItem
              icon={UserCircleIcon}
              label="Full Name"
              value={`${accountData.firstName} ${accountData.lastName}`}
            />
            <DetailItem
              icon={EnvelopeIcon}
              label="Email Address"
              value={accountData.email}
            />
            <DetailItem
              icon={PhoneIcon}
              label="Phone Number"
              value={accountData.phoneNumber}
            />
            <DetailItem
              icon={HomeIcon}
              label="Address"
              value={accountData.address || "Not provided"}
              action={!accountData.address ? {
                label: "Add Address",
                onClick: onEdit
              } : undefined}
            />
          </div>
        </div>

        {/* Right Column - Preferences & Services */}
        <div className="space-y-6">
          {/* Account Preferences */}
          <div className="bg-white rounded-xl shadow-sm overflow-hidden">
            <div className="px-6 py-4 bg-gray-50 border-b">
              <h3 className="text-lg font-semibold text-gray-900">Account Preferences</h3>
            </div>
            <div className="divide-y divide-gray-100">
              <DetailItem
                icon={LightBulbIcon}
                label="Electricity Preference"
                value={accountData.energyPreference ? 
                  accountData.energyPreference.charAt(0).toUpperCase() + 
                  accountData.energyPreference.slice(1).toLowerCase() 
                  : "Not set"
                }
                action={!accountData.energyPreference ? {
                  label: "Set Preference",
                  onClick: onEdit
                } : undefined}
              />
              <DetailItem
                icon={CreditCardIcon}
                label="Payment Method"
                value={accountData.paymentMethod ? 
                  (accountData.paymentMethod === 'CREDIT_CARD' ? 'Credit Card' :
                  accountData.paymentMethod === 'MOBILE_MONEY' ? 'Mobile Money' :
                  accountData.paymentMethod === 'BANK_TRANSFER' ? 'Bank Transfer' :
                  accountData.paymentMethod)
                  : "Not set"
                }
                action={!accountData.paymentMethod ? {
                  label: "Add Payment",
                  onClick: onEdit
                } : undefined}
              />
            </div>
          </div>

          {/* Meter Information */}
          {accountData.meter && (
            <div className="bg-white rounded-xl shadow-sm overflow-hidden">
              <div className="px-6 py-4 bg-gray-50 border-b">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-gray-900">Meter Information</h3>
                  {onViewMeter && (
                    <button
                      onClick={onViewMeter}
                      className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                    >
                      View Details
                    </button>
                  )}
                </div>
              </div>
              <div className="divide-y divide-gray-100">
                <DetailItem
                  icon={WifiIcon}
                  label="Meter Number"
                  value={accountData.meter.meter_no}
                />
                <DetailItem
                  icon={Battery100Icon}
                  label="Available Units"
                  value={`${accountData.meter.units.toFixed(2)} units`}
                  subtext="Current balance"
                />
              </div>
            </div>
          )}

          {/* Profile Completion */}
          {accountData.profileCompletion && (
            <div className="bg-white rounded-xl shadow-sm overflow-hidden">
              <div className="px-6 py-4 bg-gray-50 border-b">
                <h3 className="text-lg font-semibold text-gray-900">Account Status</h3>
              </div>
              <div className="p-6">
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <div className={`h-3 w-3 rounded-full ${
                        accountData.profileCompletion.hasCompleteProfile 
                          ? "bg-green-500" 
                          : "bg-yellow-500"
                      }`} />
                      <span className="text-sm font-medium">Account Setup</span>
                    </div>
                    <span className={`text-sm font-medium ${
                      accountData.profileCompletion.hasCompleteProfile 
                        ? "text-green-600" 
                        : "text-yellow-600"
                    }`}>
                      {accountData.profileCompletion.hasCompleteProfile ? "✓" : "Required"}
                    </span>
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <div className={`h-3 w-3 rounded-full ${
                        accountData.profileCompletion.hasMeter 
                          ? "bg-green-500" 
                          : "bg-blue-500"
                      }`} />
                      <span className="text-sm font-medium">Meter Registered</span>
                    </div>
                    <span className={`text-sm font-medium ${
                      accountData.profileCompletion.hasMeter 
                        ? "text-green-600" 
                        : "text-blue-600"
                    }`}>
                      {accountData.profileCompletion.hasMeter ? "✓" : "Register Now"}
                    </span>
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <div className={`h-3 w-3 rounded-full ${
                        accountData.profileCompletion.isLoanEligible 
                          ? "bg-green-500" 
                          : "bg-gray-400"
                      }`} />
                      <span className="text-sm font-medium">Loan Eligibility</span>
                    </div>
                    <span className={`text-sm font-medium ${
                      accountData.profileCompletion.isLoanEligible 
                        ? "text-green-600" 
                        : "text-gray-600"
                    }`}>
                      {accountData.profileCompletion.isLoanEligible ? "Eligible" : "Not Eligible"}
                    </span>
                  </div>
                </div>

                {!accountData.profileCompletion.hasCompleteProfile && (
                  <div className="mt-4 pt-4 border-t border-gray-100">
                    <button
                      onClick={onEdit}
                      className="w-full px-4 py-2 bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 font-medium transition-colors"
                    >
                      Update Account Details
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Loan Information */}
      {accountData.loans && accountData.loans.length > 0 && (
        <div className="mt-6 bg-white rounded-xl shadow-sm overflow-hidden">
          <div className="px-6 py-4 bg-gray-50 border-b">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">Recent Loans</h3>
              {onViewLoans && (
                <button
                  onClick={onViewLoans}
                  className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                >
                  View All Loans
                </button>
              )}
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead>
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Loan ID
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Amount
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Date
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {accountData.loans.slice(0, 3).map((loan) => (
                  <tr key={loan.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <span className="font-mono text-sm">{loan.loan_id}</span>
                    </td>
                    <td className="px-6 py-4">
                      <div>
                        <p className="font-medium">UGX {loan.amount_requested.toLocaleString()}</p>
                        {loan.amount_approved && (
                          <p className="text-sm text-gray-600">
                            Approved: UGX {loan.amount_approved.toLocaleString()}
                          </p>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                        loan.status === 'APPROVED' ? 'bg-green-100 text-green-800' :
                        loan.status === 'DISBURSED' ? 'bg-blue-100 text-blue-800' :
                        loan.status === 'PENDING' ? 'bg-yellow-100 text-yellow-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {loan.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {new Date(loan.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default AccountDetails;

