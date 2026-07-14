import { useCallback, useEffect, useRef, useState } from 'react';
import { externalToolApi } from '../api/externalTool';
import type { ExternalToolTaskAccepted, ExternalToolTaskStatus } from '../types';

const POLL_INTERVAL_MS = 750;
const MAX_POLLS = 800;

export function useExternalToolTask() {
  const [task, setTask] = useState<ExternalToolTaskStatus | null>(null);
  const [error, setError] = useState<unknown>(null);
  const generationRef = useRef(0);

  const cancelPolling = useCallback(() => {
    generationRef.current += 1;
  }, []);

  useEffect(() => cancelPolling, [cancelPolling]);

  const run = useCallback(async (submit: () => Promise<ExternalToolTaskAccepted>) => {
    const generation = generationRef.current + 1;
    generationRef.current = generation;
    setError(null);
    setTask(null);
    try {
      const accepted = await submit();
      setTask(accepted);
      for (let attempt = 0; attempt < MAX_POLLS; attempt += 1) {
        if (generationRef.current !== generation) return null;
        const current = await externalToolApi.getTask(accepted.taskId);
        if (generationRef.current !== generation) return null;
        setTask(current);
        if (current.status === 'completed') return current;
        if (current.status === 'failed') {
          throw new Error(current.error || current.message || 'ExternalTool task failed');
        }
        await new Promise((resolve) => window.setTimeout(resolve, POLL_INTERVAL_MS));
      }
      throw new Error('ExternalTool task polling timed out');
    } catch (caught) {
      if (generationRef.current === generation) setError(caught);
      throw caught;
    }
  }, []);

  return {
    task,
    error,
    isRunning: task?.status === 'pending' || task?.status === 'processing',
    run,
    reset: () => {
      cancelPolling();
      setTask(null);
      setError(null);
    },
  };
}
