import { ReportClient } from "@/components/ReportClient";

type ReportPageProps = {
  params: Promise<{ sessionId: string }>;
};

export default async function ReportPage({ params }: ReportPageProps) {
  const { sessionId } = await params;
  return <ReportClient sessionId={sessionId} />;
}
