/**
 * Syllabus Service - API integration for structured syllabus data
 */

import { authService } from './authService'

const API_URL = import.meta.env.VITE_API_URL

/**
 * Get syllabus data for a subject
 * @param {string} subjectCode - Subject code (e.g., SWD392)
 * @param {string} [version] - Optional specific version (approved_date)
 * @returns {Promise<Object>} Syllabus data with course info, CLOs, sessions, assessments, materials
 */
export async function getSyllabus(subjectCode, version = null) {
  const token = await authService.getAccessToken()
  
  const url = version 
    ? `${API_URL}/api/syllabus/${subjectCode}?version=${version}`
    : `${API_URL}/api/syllabus/${subjectCode}`
  
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `Failed to fetch syllabus: ${response.status}`)
  }

  return await response.json()
}

/**
 * List all versions of a syllabus
 * @param {string} subjectCode - Subject code
 * @returns {Promise<Object>} List of versions with approved_date and decision_no
 */
export async function listVersions(subjectCode) {
  const token = await authService.getAccessToken()
  
  const response = await fetch(`${API_URL}/api/syllabus/${subjectCode}/versions`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `Failed to list versions: ${response.status}`)
  }

  return await response.json()
}

/**
 * Get sessions for a syllabus
 * @param {string} subjectCode - Subject code
 * @param {string} [version] - Optional specific version
 * @param {string} [clo] - Optional CLO filter (e.g., CLO1)
 * @returns {Promise<Object>} Sessions data
 */
export async function getSessions(subjectCode, version = null, clo = null) {
  const token = await authService.getAccessToken()
  
  const params = new URLSearchParams()
  if (version) params.append('version', version)
  if (clo) params.append('clo', clo)
  
  const url = `${API_URL}/api/syllabus/${subjectCode}/sessions${params.toString() ? '?' + params.toString() : ''}`
  
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `Failed to fetch sessions: ${response.status}`)
  }

  return await response.json()
}

/**
 * Get assessments for a syllabus
 * @param {string} subjectCode - Subject code
 * @param {string} [version] - Optional specific version
 * @param {number} [minWeight] - Optional minimum weight filter
 * @returns {Promise<Object>} Assessments data
 */
export async function getAssessments(subjectCode, version = null, minWeight = null) {
  const token = await authService.getAccessToken()
  
  const params = new URLSearchParams()
  if (version) params.append('version', version)
  if (minWeight !== null) params.append('min_weight', minWeight)
  
  const url = `${API_URL}/api/syllabus/${subjectCode}/assessments${params.toString() ? '?' + params.toString() : ''}`
  
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `Failed to fetch assessments: ${response.status}`)
  }

  return await response.json()
}

/**
 * Get CLOs for a syllabus
 * @param {string} subjectCode - Subject code
 * @param {string} [version] - Optional specific version
 * @returns {Promise<Object>} CLOs data
 */
export async function getCLOs(subjectCode, version = null) {
  const token = await authService.getAccessToken()
  
  const url = version 
    ? `${API_URL}/api/syllabus/${subjectCode}/clos?version=${version}`
    : `${API_URL}/api/syllabus/${subjectCode}/clos`
  
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `Failed to fetch CLOs: ${response.status}`)
  }

  return await response.json()
}

/**
 * Get materials for a syllabus
 * @param {string} subjectCode - Subject code
 * @param {string} [version] - Optional specific version
 * @returns {Promise<Object>} Materials data
 */
export async function getMaterials(subjectCode, version = null) {
  const token = await authService.getAccessToken()
  
  const url = version 
    ? `${API_URL}/api/syllabus/${subjectCode}/materials?version=${version}`
    : `${API_URL}/api/syllabus/${subjectCode}/materials`
  
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `Failed to fetch materials: ${response.status}`)
  }

  return await response.json()
}

/**
 * Upload a syllabus markdown file
 * @param {File} file - Markdown file to upload
 * @returns {Promise<Object>} Upload result with subject_code, sessions_count, etc.
 */
export async function uploadSyllabus(file) {
  const token = await authService.getAccessToken()
  
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await fetch(`${API_URL}/api/syllabus/upload`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    },
    body: formData
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `Failed to upload syllabus: ${response.status}`)
  }

  return await response.json()
}

export const syllabusService = {
  getSyllabus,
  listVersions,
  getSessions,
  getAssessments,
  getCLOs,
  getMaterials,
  uploadSyllabus
}
