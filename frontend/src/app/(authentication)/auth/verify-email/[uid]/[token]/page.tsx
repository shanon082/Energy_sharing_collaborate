import VerifyEmail from '../../_components/verify';

interface VerifyEmailPageProps {
  params: Promise<{
    uid: string;
    token: string;
  }>;
}

export default async function VerifyEmailPage({ params }: VerifyEmailPageProps) {
  const { uid, token } = await params;
  return <VerifyEmail uid={uid} token={token} />;
}