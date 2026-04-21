// ontology-engine-ui/tests/simulation.test.ts
import { simulationApi } from '../simulation';

describe('simulationApi', () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue({
      json: () => Promise.resolve({
        success: true,
        data: {
          session_id: 'test-123',
          execution_tree: { schema_id: 'schema_001', target_output: 'decision', layers: [], total_steps: 0, rule_group_count: 0 },
          required_inputs: [],
          current_inputs: {},
        },
      }),
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('should create simulation session', async () => {
    const result = await simulationApi.createTree({
      schema_id: 'schema_001',
      target_output: 'decision',
    });

    expect(result.session_id).toBe('test-123');
    expect(global.fetch).toHaveBeenCalledWith(
      '/v1/simulation/tree',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ schema_id: 'schema_001', target_output: 'decision' }),
      })
    );
  });

  it('should get simulation session', async () => {
    const result = await simulationApi.getSession('test-123');

    expect(result.session_id).toBe('test-123');
    expect(global.fetch).toHaveBeenCalledWith(
      '/v1/simulation/test-123',
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('should update simulation inputs', async () => {
    const mockResponse = {
      json: () => Promise.resolve({
        success: true,
        data: {
          session_id: 'test-123',
          updated_inputs: { credit_score: 750 },
          result: null,
          missing_inputs: [],
        },
      }),
    };
    (global.fetch as jest.Mock).mockResolvedValueOnce(mockResponse);

    const result = await simulationApi.updateInputs('test-123', {
      input_values: { credit_score: 750 },
    });

    expect(result.session_id).toBe('test-123');
    expect(result.updated_inputs).toEqual({ credit_score: 750 });
  });

  it('should delete simulation session', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true });

    await simulationApi.deleteSession('test-123');

    expect(global.fetch).toHaveBeenCalledWith(
      '/v1/simulation/test-123',
      expect.objectContaining({ method: 'DELETE' })
    );
  });
});