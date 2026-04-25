// ontology-engine-ui/src/pages/simulation/SimulationEmbedPage.tsx
import { useSearchParams } from 'react-router-dom';
import { SimulationProvider } from '../../components/simulation/SimulationProvider';
import { SimulationPanel } from '../../components/simulation/SimulationPanel';
import type { SimulationResult } from '../../types/simulation';

interface SimulationEmbedPageProps {
  schemaId?: string;
  entityId?: string;
  targetOutput?: string;
  onResultChange?: (result: SimulationResult) => void;
  onError?: (error: string) => void;
}

export default function SimulationEmbedPage({
  schemaId: initialSchemaId,
  entityId: initialEntityId,
  targetOutput: initialTargetOutput,
  onResultChange,
  onError,
}: SimulationEmbedPageProps) {
  const [searchParams] = useSearchParams();

  const schemaId = searchParams.get('schemaId') || initialSchemaId || '';
  const entityId = searchParams.get('entityId') || initialEntityId;
  const targetOutput = searchParams.get('targetOutput') || initialTargetOutput || '';

  const hasUrlParams = Boolean(searchParams.get('targetOutput') || initialTargetOutput);

  return (
    <SimulationProvider schemaId={schemaId}>
      <div style={{ padding: 16 }}>
        <SimulationPanel
          initialSchemaId={schemaId}
          initialEntityId={entityId}
          initialTargetOutput={targetOutput}
          autoBuild={hasUrlParams}
          onResultChange={onResultChange}
          onError={onError}
        />
      </div>
    </SimulationProvider>
  );
}
