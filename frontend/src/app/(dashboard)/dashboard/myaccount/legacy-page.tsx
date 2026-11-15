"use client";

import { Suspense, useState, useEffect } from 'react';
import DesktopSidebar from "../_components/desktop-sidebar";
import RightHeader from "../_components/right-header";
import AccountForm from './_components/form';
import AccountDetails from './_components/account-details';
import ProfileDashboard from './_components/profile-dashboard';
import { getUserProfile, updateProfileData, UserProfile } from '@/lib/schema';
import { 
  UserCircleIcon, 
  Cog6ToothIcon, 
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon 
} from '@heroicons/react/24/outline';

const AccountPage = () => {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    const fetchProfileData = async () => {
      try {
        setError(null);
        const data = await getUserProfile();
        setProfile(data);
      } catch (error) {
        console.error('Failed to fetch profile data:', error);
        setError('Failed to load profile information. Please try again.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchProfileData();
  }, []);

  const handleEdit = () => {
    setIsEditing(true);
    setSuccessMessage(null);
  };

  const handleCancel = () => {
    setIsEditing(false);
    setSuccessMessage(null);
  };

  const handleSave = (updatedData: any) => {
    const profileUpdateData: Partial<UserProfile> = {
      firstName: updatedData.firstName,
      lastName: updatedData.lastName,
      phoneNumber: updatedData.phoneNumber,
      email: updatedData.email,
      address: updatedData.address,
      energyPreference: updatedData.energyPreference,
      paymentMethod: updatedData.paymentMethod,
    };

    (async () => {
      try {
        setError(null);
        setSuccessMessage(null);
        
        const data = await updateProfileData(profileUpdateData);
        setProfile(data);
        setIsEditing(false);
        setSuccessMessage('Profile updated successfully!');
        
        // Clear success message after 5 seconds
        setTimeout(() => setSuccessMessage(null), 5000);
      } catch (error) {
        console.error('Failed to update profile:', error);
        setError('Failed to update profile information. Please try again.');
      }
    })();
  };

  const handleViewLoans = () => {
    window.location.href = '/dashboard/myloans';
  };

  const handleViewMeter = () => {
    window.location.href = '/dashboard/request-loan/register-meter';
  };

  const handleRefresh = async () => {
    setIsLoading(true);
    setError(null);
    setSuccessMessage(null);
    
    try {
      const data = await getUserProfile();
      setProfile(data);
      setSuccessMessage('Profile refreshed successfully!');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (error) {
      console.error('Failed to refresh profile:', error);
      setError('Failed to refresh profile data.');
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="grid min-h-screen w-full md:grid-cols-[220px_1fr] lg:grid-cols-[280px_1fr]">
        <DesktopSidebar />
        <div className="flex flex-col">
          <RightHeader />
          <main className="flex flex-1 flex-col gap-4 p-4 lg:gap-6 lg:p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <UserCircleIcon className="h-6 w-6 text-gray-600" />
                <h1 className="text-lg font-semibold md:text-2xl">My Profile</h1>
              </div>
            </div>
            <div className="flex flex-1 flex-col items-center justify-center space-y-4">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
              <p className="text-gray-600">Loading your profile information...</p>
            </div>
          </main>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="grid min-h-screen w-full md:grid-cols-[220px_1fr] lg:grid-cols-[280px_1fr]">
        <DesktopSidebar />
        <div className="flex flex-col">
          <RightHeader />
          <main className="flex flex-1 flex-col gap-4 p-4 lg:gap-6 lg:p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <UserCircleIcon className="h-6 w-6 text-gray-600" />
                <h1 className="text-lg font-semibold md:text-2xl">My Profile</h1>
              </div>
            </div>
            <div className="flex flex-1 flex-col items-center justify-center space-y-4">
              <ExclamationTriangleIcon className="h-16 w-16 text-red-500" />
              <div className="text-center">
                <p className="text-red-600 mb-2 font-medium">{error}</p>
                <p className="text-gray-600 mb-4">Please try refreshing the page or check your connection.</p>
                <div className="flex space-x-3">
                  <button
                    onClick={() => window.location.reload()}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium transition-colors"
                  >
                    Refresh Page
                  </button>
                  <button
                    onClick={() => handleRefresh()}
                    className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium transition-colors"
                  >
                    Try Again
                  </button>
                </div>
              </div>
            </div>
          </main>
        </div>
      </div>
    );
  }

  return (
    <div className="grid min-h-screen w-full md:grid-cols-[220px_1fr] lg:grid-cols-[280px_1fr]">
      <DesktopSidebar />
      <div className="flex flex-col">
        <RightHeader />
        <main className="flex flex-1 flex-col gap-4 p-4 lg:gap-6 lg:p-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <UserCircleIcon className="h-6 w-6 text-gray-600" />
              <h1 className="text-lg font-semibold md:text-2xl">My Profile</h1>
            </div>
            <div className="flex items-center space-x-2">
              {successMessage && (
                <div className="flex items-center space-x-1 text-green-600">
                  <CheckCircleIcon className="h-4 w-4" />
                  <span className="text-sm">{successMessage}</span>
                </div>
              )}
              <button
                onClick={handleRefresh}
                disabled={isLoading}
                className="flex items-center space-x-1 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ArrowPathIcon className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
                <span>Refresh</span>
              </button>
              {!isEditing && (
                <button
                  onClick={handleEdit}
                  className="flex items-center space-x-1 px-3 py-1.5 text-sm text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded-lg transition-colors"
                >
                  <Cog6ToothIcon className="h-4 w-4" />
                  <span>Edit Profile</span>
                </button>
              )}
            </div>
          </div>

          {/* Success Alert */}
          {successMessage && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <div className="flex items-center">
                <CheckCircleIcon className="h-5 w-5 text-green-600 mr-2" />
                <p className="text-green-800">{successMessage}</p>
              </div>
            </div>
          )}

          {/* Error Alert */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex items-center">
                <ExclamationTriangleIcon className="h-5 w-5 text-red-600 mr-2" />
                <p className="text-red-800">{error}</p>
              </div>
            </div>
          )}

          {/* Main Content */}
          <div className="flex flex-1 justify-center rounded-lg border border-dashed shadow-sm">
            <div className="flex flex-col gap-1 w-full">
              {isEditing && profile ? (
                <AccountForm 
                  accountData={{
                    id: profile.id,
                    accountNumber: profile.accountNumber,
                    meterNumber: profile.meter?.meter_no || "",
                    phoneNumber: profile.phoneNumber,
                    email: profile.email,
                    firstName: profile.firstName,
                    lastName: profile.lastName,
                    address: profile.address,
                    energyPreference: profile.energyPreference,
                    paymentMethod: profile.paymentMethod,
                  }} 
                  onCancel={handleCancel} 
                  onSave={handleSave} 
                />
              ) : profile ? (
                <>
                  {/* Profile Dashboard View */}
                  <ProfileDashboard profile={profile} />
                  
                  {/* Or use the detailed view for backward compatibility */}
                  {/* <AccountDetails 
                    accountData={{
                      id: profile.id,
                      accountNumber: profile.accountNumber,
                      meterNumber: profile.meter?.meter_no || "",
                      phoneNumber: profile.phoneNumber,
                      email: profile.email,
                      firstName: profile.firstName,
                      lastName: profile.lastName,
                      address: profile.address,
                      energyPreference: profile.energyPreference,
                      paymentMethod: profile.paymentMethod,
                      meter: profile.meter,
                      loans: profile.loans,
                      profileCompletion: profile.profileCompletion
                    }}
                    onEdit={handleEdit}
                    onViewLoans={handleViewLoans}
                    onViewMeter={handleViewMeter}
                  /> */}
                </>
              ) : (
                <div className="p-8 text-center">
                  <ExclamationTriangleIcon className="h-12 w-12 text-yellow-500 mx-auto mb-4" />
                  <p className="text-gray-600 mb-2">Failed to load profile data.</p>
                  <button
                    onClick={handleRefresh}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
                  >
                    Try Again
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Quick Stats Footer */}
          {profile && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-white rounded-lg p-4 shadow-sm border">
                <p className="text-sm text-gray-600">Profile Completion</p>
                <div className="flex items-center space-x-2 mt-1">
                  <div className="h-2 flex-1 bg-gray-200 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-green-500 rounded-full"
                      style={{ width: `${profile.profileCompletion.completionPercentage}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium">{profile.profileCompletion.completionPercentage}%</span>
                </div>
              </div>
              
              <div className="bg-white rounded-lg p-4 shadow-sm border">
                <p className="text-sm text-gray-600">Available Units</p>
                <p className="text-xl font-bold text-green-600">
                  {profile.meter?.units.toFixed(2) || '0.00'} units
                </p>
              </div>
              
              <div className="bg-white rounded-lg p-4 shadow-sm border">
                <p className="text-sm text-gray-600">Active Loans</p>
                <p className="text-xl font-bold text-blue-600">
                  {profile.loanStats?.active_loans || 0} loans
                </p>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
};

export default AccountPage;
