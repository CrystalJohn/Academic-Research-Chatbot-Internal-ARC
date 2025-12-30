/**
 * Chat Service - API integration for RAG chat
 * Task #36: Build chat interface UI
 */

import { authService } from './authService'

const API_URL = import.meta.env.VITE_API_URL

/**
 * Send a chat message to the RAG API
 * @param {Object} params - Chat parameters
 * @param {string} params.query - User question
 * @param {string} [params.conversationId] - Conversation ID for history
 * @param {string} [params.userId] - User ID
 * @param {string[]} [params.docIds] - Filter by specific documents
 * @param {string} [params.template] - Prompt template (default, academic, concise, detailed)
 * @param {number} [params.topK] - Number of context chunks (1-20)
 * @param {boolean} [params.includeHistory] - Include conversation history
 * @returns {Promise<Object>} Chat response with answer, citations, usage
 */
export async function sendChatMessage({
  query,
  conversationId = null,
  userId = 'anonymous',
  docIds = null,
  template = 'default',
  topK = 3,  // Only top 3 most relevant citations
  includeHistory = true
}) {
  const token = await authService.getAccessToken()
  
  const response = await fetch(`${API_URL}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      query,
      conversation_id: conversationId,
      user_id: userId,
      doc_ids: docIds,
      template,
      top_k: topK,
      include_history: includeHistory
    })
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `API error: ${response.status}`)
  }

  return await response.json()
}

/**
 * Send a chat message with streaming response
 * @param {Object} params - Chat parameters
 * @param {Function} onChunk - Callback for each text chunk
 * @param {Function} onDone - Callback when streaming completes
 * @param {Function} onError - Callback on error
 */
export async function sendChatMessageStream({
  query,
  conversationId = null,
  userId = 'anonymous',
  docIds = null,
  template = 'default',
  topK = 3,
  includeHistory = true,
  onChunk,
  onDone,
  onError
}) {
  const token = await authService.getAccessToken()
  
  try {
    const response = await fetch(`${API_URL}/api/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        query,
        conversation_id: conversationId,
        user_id: userId,
        doc_ids: docIds,
        template,
        top_k: topK,
        include_history: includeHistory,
        stream: true
      })
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `API error: ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let fullText = ''
    let citations = []
    let convId = null

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value, { stream: true })
      const lines = chunk.split('\n')

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') {
            onDone?.(fullText, citations, convId)
            return
          }
          if (data.startsWith('[ERROR]')) {
            onError?.(new Error(data.slice(8)))
            return
          }
          if (data.startsWith('[CITATIONS]')) {
            try {
              const citationsJson = data.slice(11)
              console.log('Received citations JSON:', citationsJson.substring(0, 100))
              citations = JSON.parse(citationsJson)
              console.log('Parsed citations:', citations.length, 'items')
            } catch (e) {
              console.error('Failed to parse citations:', e)
            }
            continue
          }
          if (data.startsWith('[CONV_ID]')) {
            convId = data.slice(9)
            continue
          }
          // Decode escaped newlines from SSE
          const decodedData = data.replace(/\\n/g, '\n')
          fullText += decodedData
          onChunk?.(decodedData, fullText)
        }
      }
    }
    
    onDone?.(fullText, citations, convId)
  } catch (error) {
    onError?.(error)
  }
}

/**
 * Get conversation history
 * @param {string} conversationId - Conversation ID
 * @returns {Promise<Object>} Conversation history
 */
export async function getConversationHistory(conversationId, limit = 100) {
  const token = await authService.getAccessToken()
  
  const response = await fetch(`${API_URL}/api/chat/history/${conversationId}?limit=${limit}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  })

  if (!response.ok) {
    throw new Error(`Failed to fetch history: ${response.status}`)
  }

  return await response.json()
}

/**
 * List all conversations for current user
 * Backend automatically filters by authenticated user from token
 * @param {number} [limit] - Max conversations to return
 * @returns {Promise<Object>} List of conversations
 */
export async function listConversations(limit = 50) {
  const token = await authService.getAccessToken()

  const response = await fetch(`${API_URL}/api/chat/history?limit=${limit}`, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })

  if (!response.ok) {
    throw new Error(`Failed to list conversations: ${response.status}`)
  }

  return await response.json()
}

/**
 * Delete a conversation
 * @param {string} conversationId - Conversation ID
 * @returns {Promise<Object>} Deletion result
 */
export async function deleteConversation(conversationId) {
  const token = await authService.getAccessToken()
  
  const response = await fetch(`${API_URL}/api/chat/history/${conversationId}`, {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  })

  if (!response.ok) {
    throw new Error(`Failed to delete conversation: ${response.status}`)
  }

  return await response.json()
}

/**
 * Check rate limit status
 * @returns {Promise<Object>} Rate limit status
 */
export async function checkRateLimit() {
  const token = await authService.getAccessToken()
  const user = await authService.getCurrentUser()
  
  const response = await fetch(
    `${API_URL}/api/chat/rate-limit?user_id=${user?.username || 'anonymous'}`,
    {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    }
  )

  if (!response.ok) {
    throw new Error(`Failed to check rate limit: ${response.status}`)
  }

  return await response.json()
}

/**
 * Check budget status
 * @returns {Promise<Object>} Budget status and model recommendation
 */
export async function checkBudget() {
  const token = await authService.getAccessToken()
  const user = await authService.getCurrentUser()
  
  const response = await fetch(
    `${API_URL}/api/chat/budget?user_id=${user?.username || 'anonymous'}`,
    {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    }
  )

  if (!response.ok) {
    throw new Error(`Failed to check budget: ${response.status}`)
  }

  return await response.json()
}

/**
 * Enhance query - analyze and suggest improvements
 * @param {string} query - User query to analyze
 * @returns {Promise<Object>} Analysis with suggestions
 */
export async function enhanceQuery(query) {
  const token = await authService.getAccessToken()
  
  const response = await fetch(`${API_URL}/api/chat/enhance-query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({ query })
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `Failed to enhance query: ${response.status}`)
  }

  return await response.json()
}

export const chatService = {
  sendChatMessage,
  sendChatMessageStream,
  getConversationHistory,
  listConversations,
  deleteConversation,
  checkRateLimit,
  checkBudget,
  enhanceQuery
}
