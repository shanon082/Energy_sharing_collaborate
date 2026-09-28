"use client";

import CardWrapper from "@/components/common/card-wrapper";
import RegisterMeter from "../register-meter";


export default function RegisterMeterPage() {
  const handleSuccess = () => {
    // Redirect back to loan application after successful registration
    window.location.href = '/dashboard/request-loan';
  };

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="max-w-2xl mx-auto">
        <CardWrapper title="Register Electricity Meter">
          <RegisterMeter onSuccess={handleSuccess} />
        </CardWrapper>
      </div>
    </div>
  );
}