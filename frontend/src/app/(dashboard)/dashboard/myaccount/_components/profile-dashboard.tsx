"use client";

import { UserProfile, LoanStatus, LoanTier, EnergyPreference, PaymentMethod, ProfileCompletionStatus } from "@/lib/schema";
import { 
  UserCircleIcon, 
  LightBulbIcon, 
  CreditCardIcon, 
  HomeIcon, 
  DevicePhoneMobileIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ClockIcon,
  CurrencyDollarIcon,
  ChartBarIcon,
  Battery100Icon,
  WifiIcon
} from "@heroicons/react/24/outline";
import Link from "next/link";

interface ProfileDashboardProps {
  profile: UserProfile;
}

const ProfileDashboard = ({ profile }: ProfileDashboardProps) => {
  const formatDate = (dateString?: string) => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric"
    });
  };

  const getLoanStatusColor = (status: LoanStatus) => {
    switch (status) {
      case LoanStatus.APPROVED:
        return "bg-green-100 text-green-800";
      case LoanStatus.DISBURSED:
        return "bg-blue-100 text-blue-800";
      case LoanStatus.PENDING:
        return "bg-yellow-100 text-yellow-800";
      case LoanStatus.REJECTED:
        return "bg-red-100 text-red-800";
      case LoanStatus.COMPLETED:
        return "bg-gray-100 text-gray-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const getTierColor = (tier?: LoanTier) => {
    switch (tier) {
      case LoanTier.PLATINUM:
        return "bg-purple-100 text-purple-800";
      case LoanTier.GOLD:
        return "bg-yellow-100 text-yellow-800";
      case LoanTier.SILVER:
        return "bg-gray-100 text-gray-800";
      case LoanTier.BRONZE:
        return "bg-orange-100 text-orange-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  return (
    <div className="space-y-6">
      {/* Profile Header */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="h-16 w-16 bg-blue-100 rounded-full flex items-center justify-center">
              <UserCircleIcon className="h-10 w-10 text-blue-600" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-900">
                {profile.firstName} {profile.lastName}
              </h2>
              <p className="text-gray-600">{profile.email}</p>
              <div className="flex items-center space-x-2 mt-1">
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                  profile.emailVerified 
                    ? "bg-green-100 text-green-800" 
                    : "bg-yellow-100 text-yellow-800"
                }`}>
                  {profile.emailVerified ? "Verified" : "Unverified"}
                </span>
                <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs font-medium">
                  {profile.userRole}
                </span>
              </div>
            </div>
          </div>
          <div className="text-right">
            <p className="text-sm text-gray-600">Account Number</p>
            <p className="text-lg font-mono font-semibold">{profile.accountNumber}</p>
          </div>
        </div>
      </div>

      {/* Profile Completion */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Profile Completion</h3>
          <span className="text-sm font-medium text-blue-600">
            {profile.profileCompletion.completionPercentage}% Complete
          </span>
        </div>
        
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <CheckCircleIcon className={`h-5 w-5 ${
                profile.emailVerified ? "text-green-500" : "text-gray-400"
              }`} />
              <span className="text-sm text-gray-800">Email Verified</span>
            </div>
            {profile.emailVerified ? (
              <span className="text-green-600 text-sm">✓ Complete</span>
            ) : (
              <Link href="/dashboard/myaccount" className="text-blue-600 text-sm hover:underline">
                Verify Now
              </Link>
            )}
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <HomeIcon className={`h-5 w-5 ${
                profile.address ? "text-green-500" : "text-gray-400"
              }`} />
              <span className="text-sm text-gray-800">Address Provided</span>
            </div>
            {profile.address ? (
              <span className="text-green-600 text-sm">✓ Complete</span>
            ) : (
              <span className="text-yellow-600 text-sm">Required</span>
            )}
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <WifiIcon className={`h-5 w-5 ${
                profile.profileCompletion.hasMeter ? "text-green-500" : "text-gray-400"
              }`} />
              <span className="text-sm text-gray-800">Meter Registered</span>
            </div>
            {profile.profileCompletion.hasMeter ? (
              <span className="text-green-600 text-sm">✓ Complete</span>
            ) : (
              <Link href="/dashboard/request-loan/register-meter" className="text-blue-600 text-sm hover:underline">
                Register Meter
              </Link>
            )}
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <ChartBarIcon className={`h-5 w-5 ${
                profile.profileCompletion.hasCompleteProfile ? "text-green-500" : "text-gray-400"
              }`} />
              <span className="text-sm text-gray-800">Full Profile Complete</span>
            </div>
            {profile.profileCompletion.hasCompleteProfile ? (
              <span className="text-green-600 text-sm">✓ Complete</span>
            ) : (
              <span className="text-yellow-600 text-sm">
                {profile.profileCompletion.missingFields.length} items missing
              </span>
            )}
          </div>
        </div>

        {/* Progress Bar */}
        <div className="mt-4">
          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
            <div 
              className="h-full bg-green-500 rounded-full transition-all duration-500"
              style={{ width: `${profile.profileCompletion.completionPercentage}%` }}
            />
          </div>
        </div>
      </div>

      {/* Grid Layout for Details */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Contact Information */}
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Contact Information</h3>
          <div className="space-y-4">
            <div>
              <p className="text-sm text-gray-800">Email Address</p>
              <p className="font-medium text-gray-400">{profile.email}</p>
            </div>
            <div>
              <p className="text-sm text-gray-800">Phone Number</p>
              <p className="font-medium text-gray-400">{profile.phoneNumber}</p>
            </div>
            <div>
              <p className="text-sm text-gray-800">Address</p>
              <p className="font-medium text-gray-400">{profile.address || "Not provided"}</p>
            </div>
          </div>
        </div>

        {/* Account Preferences */}
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Account Preferences</h3>
          <div className="space-y-4">
            <div>
              <p className="text-sm text-gray-800">Energy Preference</p>
              <p className="font-medium capitalize text-gray-500">
                {profile.energyPreference?.toLowerCase() || "Not set"}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-800">Payment Method</p>
              <p className="font-medium text-gray-500">
                {profile.paymentMethod === PaymentMethod.CREDIT_CARD && "Credit Card"}
                {profile.paymentMethod === PaymentMethod.MOBILE_MONEY && "Mobile Money"}
                {profile.paymentMethod === PaymentMethod.BANK_TRANSFER && "Bank Transfer"}
                {!profile.paymentMethod && "Not set"}
              </p>
            </div>
          </div>
        </div>

        {/* Meter Information */}
        {profile.meter && (
          <div className="bg-white rounded-xl shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Meter Information</h3>
              <Battery100Icon className="h-6 w-6 text-green-500" />
            </div>
            <div className="space-y-4">
              <div>
                <p className="text-sm text-gray-800">Meter Number</p>
                <p className="font-mono font-medium text-gray-400">{profile.meter.meter_no}</p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-gray-800">Available Units</p>
                  <p className="text-2xl font-bold text-green-600">{profile.meter.units.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-800">Static IP</p>
                  <p className="font-mono text-sm text-gray-400">{profile.meter.static_ip}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Loan Statistics */}
        <div className="bg-white rounded-xl shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Loan Statistics</h3>
            <CurrencyDollarIcon className="h-6 w-6 text-blue-500" />
          </div>
          {profile.loanStats ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-blue-50 p-3 rounded-lg">
                  <p className="text-sm text-blue-600">Active Loans</p>
                  <p className="text-xl font-bold text-blue-900">{profile.loanStats.active_loans}</p>
                </div>
                <div className="bg-green-50 p-3 rounded-lg">
                  <p className="text-sm text-green-600">Total Borrowed</p>
                  <p className="text-xl font-bold text-green-900">UGX {profile.loanStats.total_borrowed.toLocaleString()}</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-purple-50 p-3 rounded-lg">
                  <p className="text-sm text-purple-600">Outstanding</p>
                  <p className="text-xl font-bold text-purple-900">UGX {profile.loanStats.outstanding_balance.toLocaleString()}</p>
                </div>
                <div className="bg-yellow-50 p-3 rounded-lg">
                  <p className="text-sm text-yellow-600">Credit Score</p>
                  <p className="text-xl font-bold text-yellow-900">{profile.loanStats.credit_score || 0}/100</p>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-8">
              <p className="text-gray-500">No loan statistics available</p>
              <Link 
                href="/dashboard/request-loan" 
                className="mt-2 inline-block text-blue-600 hover:underline"
              >
                Apply for your first loan
              </Link>
            </div>
          )}
        </div>
      </div>

      {/* Recent Loans */}
      {profile.loans.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-semibold text-gray-900">Recent Loan Applications</h3>
            <Link href="/dashboard/myloans" className="text-blue-600 text-sm hover:underline">
              View All
            </Link>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead>
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Loan ID
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Amount
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Tier
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Date
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {profile.loans.slice(0, 3).map((loan) => (
                  <tr key={loan.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <Link 
                        href="/dashboard/myloans"
                        className="text-blue-600 hover:underline font-mono"
                      >
                        {loan.loan_id}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <div>
                        <p className="font-medium">UGX {loan.amount_requested.toLocaleString()}</p>
                        {loan.amount_approved && (
                          <p className="text-sm text-green-600">
                            Approved: UGX {loan.amount_approved.toLocaleString()}
                          </p>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${getLoanStatusColor(loan.status)}`}>
                        {loan.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {loan.loan_tier && (
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${getTierColor(loan.loan_tier)}`}>
                          {loan.loan_tier}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {formatDate(loan.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Quick Actions */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Link
            href="/dashboard/myaccount"
            className="bg-blue-50 hover:bg-blue-100 p-4 rounded-lg text-center transition-colors"
          >
            <UserCircleIcon className="h-8 w-8 text-blue-600 mx-auto mb-2" />
            <span className="text-sm font-medium text-blue-600">Edit Profile</span>
          </Link>
          
          {!profile.meter && (
            <Link
              href="/dashboard/request-loan/register-meter"
              className="bg-green-50 hover:bg-green-100 p-4 rounded-lg text-center transition-colors"
            >
              <WifiIcon className="h-8 w-8 text-green-600 mx-auto mb-2" />
              <span className="text-sm font-medium text-green-600">Register Meter</span>
            </Link>
          )}
          
          <Link
            href="/dashboard/buy-units"
            className="bg-purple-50 hover:bg-purple-100 p-4 rounded-lg text-center transition-colors"
          >
            <Battery100Icon className="h-8 w-8 text-purple-600 mx-auto mb-2" />
            <span className="text-sm font-medium text-purple-600">Buy Units</span>
          </Link>
          
          <Link
            href="/dashboard/request-loan"
            className="bg-yellow-50 hover:bg-yellow-100 p-4 rounded-lg text-center transition-colors"
          >
            <CurrencyDollarIcon className="h-8 w-8 text-yellow-600 mx-auto mb-2" />
            <span className="text-sm font-medium text-yellow-600">Apply for Loan</span>
          </Link>
        </div>
      </div>
    </div>
  );
};

export default ProfileDashboard;
