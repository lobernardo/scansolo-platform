import {
  getGroundTruthStats,
  getTrainingSessions,
  getRecalibracaoResults,
} from "@/app/actions/training-actions";
import { TreinamentoClient } from "./TreinamentoClient";

export const dynamic = "force-dynamic";

export default async function TreinamentoPage() {
  const [stats, sessions, recalResults] = await Promise.all([
    getGroundTruthStats(),
    getTrainingSessions(),
    getRecalibracaoResults(),
  ]);

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <TreinamentoClient
        initialStats={stats}
        initialSessions={sessions}
        initialRecalResults={recalResults}
      />
    </div>
  );
}
