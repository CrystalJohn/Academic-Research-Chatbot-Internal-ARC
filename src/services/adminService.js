/**
 * Admin Service - API integration for document management
 * Task #38: Build admin dashboard for document upload
 * Task #39: Show document processing status
 */

import { authService } from './authService'

const API_URL = import.meta.env.VITE_API_URL

/**
 * Upload a PDF document
 * @param {File} file - PDF file to upload
 * @param {string} [uploadedBy] - User ID
 * @returns {Promise<Object>} Upload response with doc_id, status
 */
export async function uploadDocument(file, uploadedBy = 'admin') {
  const token = await authService.getAccessToken()
  const user = await authService.getCurrentUser()
  
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await fetch(
    `${API_URL}/api/admin/upload?uploaded_by=${user?.username || uploadedBy}`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
      },
      body: formData
    }
  )

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `Upload failed: ${response.status}`)
  }

  return await response.json()
}

/**
 * List all documents with pagination and filtering
 * @param {Object} params - Query parameters
 * @param {number} [params.page] - Page number (default: 1)
 * @param {number} [params.pageSize] - Items per page (default: 20)
 * @param {string} [params.status] - Filter by status
 * @returns {Promise<Object>} List of documents with pagination info
 */
export async function listDocuments({ page = 1, pageSize = 20, status = null } = {}) {
  const token = await authService.getAccessToken()
  
  let url = `${API_URL}/api/admin/documents?page=${page}&page_size=${pageSize}`
  if (status) {
    url += `&status=${status}`
  }
  
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  })

  if (!response.ok) {
    throw new Error(`Failed to fetch documents: ${response.status}`)
  }

  return await response.json()
}

/**
 * Get a single document by ID
 * @param {string} docId - Document ID
 * @returns {Promise<Object>} Document details
 */
export async function getDocument(docId) {
  const token = await authService.getAccessToken()
  
  const response = await fetch(`${API_URL}/api/admin/documents/${docId}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  })

  if (!response.ok) {
    throw new Error(`Failed to fetch document: ${response.status}`)
  }

  return await response.json()
}

/**
 * Delete a document
 * @param {string} docId - Document ID
 * @returns {Promise<Object>} Deletion result
 */
export async function deleteDocument(docId) {
  const token = await authService.getAccessToken()
  
  const response = await fetch(`${API_URL}/api/admin/documents/${docId}`, {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `Failed to delete document: ${response.status}`)
  }

  return await response.json()
}

/**
 * Update a document
 * @param {string} docId - Document ID
 * @param {Object} data - Update data (filename, status)
 * @returns {Promise<Object>} Updated document
 */
export async function updateDocument(docId, data) {
  const token = await authService.getAccessToken()
  
  const response = await fetch(`${API_URL}/api/admin/documents/${docId}`, {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `Failed to update document: ${response.status}`)
  }

  return await response.json()
}

/**
 * Reprocess a failed document
 * @param {string} docId - Document ID
 * @returns {Promise<Object>} Reprocess result
 */
export async function reprocessDocument(docId) {
  const token = await authService.getAccessToken()
  
  const response = await fetch(`${API_URL}/api/admin/documents/${docId}/reprocess`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `Failed to reprocess document: ${response.status}`)
  }

  return await response.json()
}

/**
 * Download a document
 * @param {string} docId - Document ID
 * @returns {Promise<Object>} Download URL info
 */
export async function downloadDocument(docId) {
  const token = await authService.getAccessToken()
  
  const response = await fetch(`${API_URL}/api/admin/documents/${docId}/download`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `Failed to get download URL: ${response.status}`)
  }

  return await response.json()
}

/**
 * Get document statistics
 * @returns {Promise<Object>} Statistics (total, by status, etc.)
 */
export async function getDocumentStats() {
  const token = await authService.getAccessToken()
  
  const response = await fetch(`${API_URL}/api/admin/stats`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  })

  if (!response.ok) {
    // If stats endpoint doesn't exist, return null
    return null
  }

  return await response.json()
}

export const adminService = {
  uploadDocument,
  listDocuments,
  getDocument,
  deleteDocument,
  updateDocument,
  reprocessDocument,
  downloadDocument,
  getDocumentStats
}
