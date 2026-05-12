import type { StatusResponse } from '../types/api'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

export async function getStatus(): Promise<StatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/status`)
  if (!response.ok) {
    throw new Error(`API request failed with ${response.status}`)
  }

  return response.json() as Promise<StatusResponse>
}
