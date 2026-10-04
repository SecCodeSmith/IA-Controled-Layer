import { http, HttpResponse } from 'msw'
import { CONTROL_LAYER_URL } from '../api/client'
import {
  CLASSIFIER_STATUS_FIXTURE,
  CURATION_SUMMARY_FIXTURE,
  PROJECTION_TRACE_FIXTURE,
  PROMPT_TRACE_FIXTURE,
  RESOURCE_MATRIX_FIXTURE,
  RETRAIN_JOB_FIXTURE,
  SAMPLES_FIXTURE,
} from './workbenchFixtures'
import type { SamplePatch } from '../types/classifier'
import type { TraceRequest } from '../types/workbench'

export const workbenchHandlers = [
  http.get(`${CONTROL_LAYER_URL}/api/classifier`, () => HttpResponse.json(CLASSIFIER_STATUS_FIXTURE)),

  http.get(`${CONTROL_LAYER_URL}/api/classifier/samples`, ({ request }) => {
    const status = new URL(request.url).searchParams.get('status')
    const samples = status ? SAMPLES_FIXTURE.filter((sample) => sample.status === status) : SAMPLES_FIXTURE
    return HttpResponse.json({ items: samples })
  }),

  http.patch(`${CONTROL_LAYER_URL}/api/classifier/samples/:sampleId`, async ({ params, request }) => {
    const patch = (await request.json()) as SamplePatch
    const sample = SAMPLES_FIXTURE.find((candidate) => candidate.id === params.sampleId)
    return sample
      ? HttpResponse.json({ ...sample, ...patch })
      : HttpResponse.json({ error: { code: 'not_found', reason: 'Unknown sample' } }, { status: 404 })
  }),

  http.post(`${CONTROL_LAYER_URL}/api/classifier/samples/curate`, () =>
    HttpResponse.json(CURATION_SUMMARY_FIXTURE),
  ),

  http.post(`${CONTROL_LAYER_URL}/api/classifier/retrain`, () => HttpResponse.json(RETRAIN_JOB_FIXTURE)),

  http.post(`${CONTROL_LAYER_URL}/api/workbench/trace`, async ({ request }) => {
    const body = (await request.json()) as TraceRequest
    return HttpResponse.json(body.kind === 'tool_call' ? PROJECTION_TRACE_FIXTURE : PROMPT_TRACE_FIXTURE)
  }),

  http.get(`${CONTROL_LAYER_URL}/api/workbench/resources`, () => HttpResponse.json(RESOURCE_MATRIX_FIXTURE)),
]
