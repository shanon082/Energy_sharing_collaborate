import { get } from '@/lib/fetch';
import { User } from '@/interface/user.interface';

export interface SetupStatus {
  hasMeter: boolean;
  completedSetup: boolean;
  currentStep: 'meter' | 'complete';
}

export async function checkUserSetupStatus(user: User | null): Promise<SetupStatus> {
  if (!user) {
    return {
      hasMeter: false,
      completedSetup: false,
      currentStep: 'meter'
    };
  }

  // Admins don't need setup
  if (user.is_admin || user.user_role === 'ADMIN') {
    return {
      hasMeter: true,
      completedSetup: true,
      currentStep: 'complete'
    };
  }

  try {
    // Check meter registration
    const meterResponse = await get<any>('meter/my-meter/');
    const hasMeter = !meterResponse.error && 
                     meterResponse.data?.success && 
                     meterResponse.data.data?.has_meter;
    
    let currentStep: 'meter' | 'complete' = 'complete';
    if (!hasMeter) {
      currentStep = 'meter';
    }

    return {
      hasMeter,
      completedSetup: hasMeter,
      currentStep
    };
  } catch (error) {
    console.error('Failed to check setup status:', error);
    return {
      hasMeter: false,
      completedSetup: false,
      currentStep: 'meter'
    };
  }
}
