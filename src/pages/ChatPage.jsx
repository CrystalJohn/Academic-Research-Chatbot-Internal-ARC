import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { authService } from '../services/authService'
import { chatService } from '../services/chatService'
import { Spinner } from '@heroui/react'
import { motion, AnimatePresence } from 'framer-motion'
import DocumentViewerModal from '../components/DocumentViewerModal'
import AnswerWithCitations from '../components/AnswerWithCitations'
import Sidebar from '../components/Sidebar'
import QueryEnhancement from '../components/QueryEnhancement'
import arcLogo from '../assets/Logo ARC-chatbot.png'

function ChatPage() {
  const navigate = useNavigate()
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content:
        'Xin chào! 👋 Tôi là ARC Chatbot - trợ lý nghiên cứu tài liệu của bạn.\n\nTôi có thể giúp bạn:\n📚 Tìm kiếm thông tin trong các tài liệu đã upload\n📝 Trả lời câu hỏi dựa trên nội dung tài liệu\n🔍 Trích dẫn nguồn chính xác với số trang\n\nBạn muốn hỏi về vấn đề gì trong tài liệu? Hãy đặt câu hỏi cụ thể để tôi hỗ trợ tốt nhất nhé! 😊',
      timestamp: new Date().toISOString(),
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [conversationId, setConversationId] = useState(null)
  const [selectedCitation, setSelectedCitation] = useState(null)
  const [selectedQuery, setSelectedQuery] = useState('')
  const [user, setUser] = useState(null)
  const [showAccountMenu, setShowAccountMenu] = useState(false)
  const [activeMenu, setActiveMenu] = useState('chat')
  const [activeSubMenu, setActiveSubMenu] = useState('current')
  const [darkMode, setDarkMode] = useState(false)
  const [showEnhancement, setShowEnhancement] = useState(false)
  const messagesEndRef = useRef(null)

  // History state
  const [conversations, setConversations] = useState([])
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [historyError, setHistoryError] = useState(null)

  useEffect(() => {
    loadUser()
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Load history when switching to history tab
  useEffect(() => {
    if (activeSubMenu === 'history') {
      loadConversations()
    }
  }, [activeSubMenu])

  const loadUser = async () => {
    const currentUser = await authService.getCurrentUser()
    setUser(currentUser)
  }

  const loadConversations = async () => {
    setLoadingHistory(true)
    setHistoryError(null)
    try {
      const data = await chatService.listConversations(50)
      setConversations(data.conversations || [])
    } catch (err) {
      console.error('Failed to load conversations:', err)
      setHistoryError('Failed to load conversation history')
    } finally {
      setLoadingHistory(false)
    }
  }

  const loadConversation = async (convId) => {
    setLoading(true)
    try {
      const data = await chatService.getConversationHistory(convId)
      
      // Convert to message format
      const loadedMessages = (data.messages || []).map(msg => {
        console.log('Loading message:', msg.role, 'citations:', msg.citations)
        return {
          role: msg.role,
          content: msg.content,
          timestamp: msg.created_at || msg.timestamp,
          citations: msg.citations || [],
        }
      })
      
      if (loadedMessages.length > 0) {
        setMessages(loadedMessages)
        setConversationId(convId)
        setActiveSubMenu('current')
      }
    } catch (err) {
      console.error('Failed to load conversation:', err)
      setError('Failed to load conversation')
    } finally {
      setLoading(false)
    }
  }

  const deleteConversation = async (convId, e) => {
    e.stopPropagation()
    if (!confirm('Delete this conversation?')) return
    
    try {
      await chatService.deleteConversation(convId)
      setConversations(prev => prev.filter(c => c.conversation_id !== convId))
      
      // If deleting current conversation, reset
      if (convId === conversationId) {
        handleNewChat()
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err)
    }
  }

  const formatDate = (timestamp) => {
    if (!timestamp) return ''
    const date = new Date(timestamp)
    const now = new Date()
    const diff = now - date
    
    if (diff < 86400000) { // Less than 24 hours
      return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
    } else if (diff < 604800000) { // Less than 7 days
      return date.toLocaleDateString('en-US', { weekday: 'short' })
    } else {
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    }
  }

  const formatTime = (timestamp) => {
    if (!timestamp) return ''
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true })
  }

  const handleSend = async (e) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    // Ẩn enhancement panel khi gửi
    setShowEnhancement(false)

    const userQuery = input
    const userMessage = {
      role: 'user',
      content: userQuery,
      timestamp: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setLoading(true)
    setError(null)

    // Add placeholder for streaming response
    const streamingMessageId = Date.now()
    setMessages((prev) => [
      ...prev,
      {
        id: streamingMessageId,
        role: 'assistant',
        content: '',
        isStreaming: true,
        timestamp: new Date().toISOString(),
      },
    ])

    try {
      await chatService.sendChatMessageStream({
        query: userQuery,
        conversationId,
        userId: user?.username || 'anonymous',
        template: 'default',
        topK: 3,
        includeHistory: true,
        onChunk: (chunk, fullText) => {
          // Update streaming message with new content
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === streamingMessageId ? { ...msg, content: fullText } : msg
            )
          )
        },
        onDone: (fullText, citations, convId) => {
          console.log('Stream done - citations:', citations?.length || 0, 'convId:', convId)
          
          // Update conversation ID if new
          if (convId && !conversationId) {
            setConversationId(convId)
          }

          // Update message with citations from stream
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === streamingMessageId
                ? {
                    ...msg,
                    content: fullText,
                    citations: citations || [],
                    isStreaming: false,
                  }
                : msg
            )
          )
          setLoading(false)
        },
        onError: (err) => {
          console.error('Stream error:', err)
          setError(err.message || 'Failed to get response. Please try again.')
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === streamingMessageId
                ? {
                    ...msg,
                    content: `Sorry, I encountered an error: ${err.message}. Please try again.`,
                    isError: true,
                    isStreaming: false,
                  }
                : msg
            )
          )
          setLoading(false)
        },
      })
    } catch (err) {
      console.error('Chat error:', err)
      setError(err.message || 'Failed to get response. Please try again.')
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === streamingMessageId
            ? {
                ...msg,
                content: `Sorry, I encountered an error: ${err.message}. Please try again.`,
                isError: true,
                isStreaming: false,
              }
            : msg
        )
      )
      setLoading(false)
    }
  }

  const handleViewDocument = (citation, query) => {
    setSelectedCitation(citation)
    setSelectedQuery(query || '')
  }

  const handleCloseModal = () => {
    setSelectedCitation(null)
    setSelectedQuery('')
  }

  const handleLogout = async () => {
    await authService.logout()
    navigate('/login')
  }

  const handleNewChat = () => {
    console.log('New Chat clicked - resetting conversation')
    setMessages([
      {
        role: 'assistant',
        content:
          'Xin chào! 👋 Tôi là ARC Chatbot - trợ lý nghiên cứu tài liệu của bạn.\n\nTôi có thể giúp bạn:\n📚 Tìm kiếm thông tin trong các tài liệu đã upload\n📝 Trả lời câu hỏi dựa trên nội dung tài liệu\n🔍 Trích dẫn nguồn chính xác với số trang\n\nBạn muốn hỏi về vấn đề gì trong tài liệu? Hãy đặt câu hỏi cụ thể để tôi hỗ trợ tốt nhất nhé! 😊',
        timestamp: new Date().toISOString(),
      },
    ])
    setConversationId(null)
    setError(null)
    // Switch to Current Chat view
    setActiveSubMenu('current')
  }

  const isAdmin = user?.groups?.includes('admin')
  const userInitials = user?.username
    ? user.username
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    : 'U'

  return (
    <div className={`flex h-screen ${darkMode ? 'bg-gray-900' : 'bg-slate-100'}`}>
      {/* Sidebar */}
      <Sidebar
        activeMenu={activeMenu}
        setActiveMenu={setActiveMenu}
        activeSubMenu={activeSubMenu}
        setActiveSubMenu={setActiveSubMenu}
        user={user}
        darkMode={darkMode}
        onNewChat={handleNewChat}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div
          className={`${darkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'} border-b px-6 py-4 flex items-center justify-between`}
        >
          <div className="flex items-center gap-3">
            <h2 className={`text-lg font-semibold ${darkMode ? 'text-white' : 'text-gray-800'}`}>
              Research Chat
            </h2>
            <span className="px-2 py-1 bg-emerald-100 text-emerald-600 text-xs font-medium rounded-full">
              ONLINE
            </span>
          </div>

          <div className="flex items-center gap-4">
            {/* Dark Mode Toggle */}
            <button
              onClick={() => setDarkMode(!darkMode)}
              className={`p-2 rounded-lg ${darkMode ? 'bg-gray-700 text-yellow-400' : 'bg-gray-100 text-gray-600'} hover:opacity-80 transition-colors`}
            >
              {darkMode ? (
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    fillRule="evenodd"
                    d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z"
                    clipRule="evenodd"
                  />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
                </svg>
              )}
            </button>

            {/* User Profile */}
            <div className="relative">
              <button
                onClick={() => setShowAccountMenu(!showAccountMenu)}
                className="flex items-center gap-3"
              >
                <div className="text-right">
                  <p
                    className={`text-sm font-medium ${darkMode ? 'text-white' : 'text-gray-800'}`}
                  >
                    {user?.username || 'User'}
                  </p>
                  <p className={`text-xs ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                    {isAdmin ? 'Administrator' : 'Researcher'}
                  </p>
                </div>
                <div className="w-10 h-10 bg-pink-500 text-white rounded-full flex items-center justify-center font-medium text-sm">
                  {userInitials}
                </div>
              </button>

              {showAccountMenu && (
                <div
                  className={`absolute right-0 mt-2 w-56 ${darkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'} rounded-xl shadow-lg border py-2 z-50`}
                >
                  <div
                    className={`px-4 py-3 border-b ${darkMode ? 'border-gray-700' : 'border-gray-200'}`}
                  >
                    <p
                      className={`text-sm font-medium ${darkMode ? 'text-white' : 'text-gray-800'}`}
                    >
                      {user?.username || 'User'}
                    </p>
                    <p className={`text-xs ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                      {user?.email || 'No email'}
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      setShowAccountMenu(false)
                      handleLogout()
                    }}
                    className={`w-full px-4 py-2 text-left text-sm text-red-500 hover:bg-red-50 flex items-center gap-2`}
                  >
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                      />
                    </svg>
                    <span>Logout</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* History Panel */}
        {activeSubMenu === 'history' && (
          <div className={`flex-1 overflow-y-auto p-6 ${darkMode ? 'bg-gray-900' : 'bg-slate-100'}`}>
            <div className="max-w-3xl mx-auto">
              <h3 className={`text-lg font-semibold mb-4 ${darkMode ? 'text-white' : 'text-gray-800'}`}>
                Conversation History
              </h3>
              
              {loadingHistory && (
                <div className="flex justify-center py-8">
                  <Spinner size="lg" />
                </div>
              )}
              
              {historyError && (
                <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
                  {historyError}
                </div>
              )}
              
              {!loadingHistory && conversations.length === 0 && (
                <div className={`text-center py-12 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                  <svg className="w-16 h-16 mx-auto mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                  <p>No conversations yet</p>
                  <p className="text-sm mt-1">Start a new chat to see your history here</p>
                </div>
              )}
              
              <div className="space-y-2">
                {conversations.map((conv) => (
                  <motion.div
                    key={conv.conversation_id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    onClick={() => loadConversation(conv.conversation_id)}
                    className={`p-4 rounded-xl cursor-pointer transition-all group ${
                      conv.conversation_id === conversationId
                        ? 'bg-blue-50 border-2 border-blue-200'
                        : darkMode
                          ? 'bg-gray-800 hover:bg-gray-700 border border-gray-700'
                          : 'bg-white hover:bg-gray-50 border border-gray-200'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <p className={`font-medium truncate ${darkMode ? 'text-white' : 'text-gray-800'}`}>
                          {conv.title || conv.preview || `Conversation ${conv.conversation_id?.slice(0, 8)}...`}
                        </p>
                        <div className="flex items-center gap-3 mt-1">
                          <span className={`text-xs ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                            {formatDate(conv.last_message_at || conv.last_message_time || conv.updated_at)}
                          </span>
                          <span className={`text-xs ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                            {conv.message_count || 0} messages
                          </span>
                        </div>
                      </div>
                      <button
                        onClick={(e) => deleteConversation(conv.conversation_id, e)}
                        className="opacity-0 group-hover:opacity-100 p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Messages */}
        {activeSubMenu === 'current' && (
        <div
          className={`flex-1 overflow-y-auto p-6 space-y-6 ${darkMode ? 'bg-gray-900' : 'bg-slate-100'}`}
        >
          <AnimatePresence>
            {messages.map((msg, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {msg.role === 'assistant' && (
                  <div className="flex gap-3 max-w-2xl">
                    <img
                      src={arcLogo}
                      alt="ARC"
                      className="flex-shrink-0 w-9 h-9 rounded-full object-cover"
                    />
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span
                          className={`text-sm font-medium ${darkMode ? 'text-white' : 'text-gray-800'}`}
                        >
                          ARC Chatbot
                        </span>
                        <span
                          className={`text-xs ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}
                        >
                          {formatTime(msg.timestamp)}
                        </span>
                      </div>
                      <div
                        className={`px-4 py-3 rounded-2xl rounded-tl-md ${
                          msg.isError
                            ? 'bg-red-50 border border-red-200 text-red-800'
                            : darkMode
                              ? 'bg-gray-800 text-gray-100'
                              : 'bg-white text-gray-800'
                        } shadow-sm`}
                      >
                        {msg.isStreaming ? (
                          // Show plain text while streaming for better UX
                          <div className="text-sm leading-relaxed">
                            <p className="whitespace-pre-wrap">
                              {msg.content}
                              <span className="inline-block w-2 h-4 ml-1 bg-blue-500 animate-pulse rounded-sm" />
                            </p>
                          </div>
                        ) : (
                          // Render with inline citation badges
                          <AnswerWithCitations
                            content={msg.content}
                            citations={msg.citations || []}
                            onViewDocument={(citation) => {
                              const userQuery =
                                idx > 0 && messages[idx - 1]?.role === 'user'
                                  ? messages[idx - 1].content
                                  : ''
                              handleViewDocument(citation, userQuery)
                            }}
                            query={
                              idx > 0 && messages[idx - 1]?.role === 'user'
                                ? messages[idx - 1].content
                                : ''
                            }
                          />
                        )}

                        {/* Compact Sources List */}
                        {msg.citations && msg.citations.length > 0 && !msg.isStreaming && (
                          <div className="mt-4 pt-3 border-t border-gray-100">
                            <p className="text-xs text-gray-500 mb-2">📚 Sources ({msg.citations.length}):</p>
                            <div className="flex flex-wrap gap-2">
                              {msg.citations.map((citation) => {
                                const userQuery =
                                  idx > 0 && messages[idx - 1]?.role === 'user'
                                    ? messages[idx - 1].content
                                    : ''
                                return (
                                  <button
                                    key={citation.id}
                                    onClick={() => handleViewDocument(citation, userQuery)}
                                    className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-gray-100 hover:bg-blue-100 text-gray-700 hover:text-blue-700 rounded-lg text-xs transition-colors"
                                    title={citation.text_snippet}
                                  >
                                    <span className="font-medium">[{citation.id}]</span>
                                    <span className="truncate max-w-[120px]">
                                      {citation.filename || `Doc ${citation.doc_id?.slice(0, 6)}`}
                                    </span>
                                    {citation.page && (
                                      <span className="text-gray-400">p.{citation.page}</span>
                                    )}
                                  </button>
                                )
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {msg.role === 'user' && (
                  <div className="flex flex-col items-end max-w-2xl">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                        {formatTime(msg.timestamp)}
                      </span>
                      <span
                        className={`text-sm font-medium ${darkMode ? 'text-white' : 'text-gray-800'}`}
                      >
                        You
                      </span>
                    </div>
                    <div className="px-4 py-3 bg-blue-500 text-white rounded-2xl rounded-tr-md shadow-sm">
                      <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                    </div>
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>

          {/* Only show Thinking indicator if loading but no streaming message yet */}
          {loading && !messages.some(m => m.isStreaming) && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex justify-start"
            >
              <div className="flex gap-3">
                <img
                  src={arcLogo}
                  alt="ARC"
                  className="flex-shrink-0 w-9 h-9 rounded-full object-cover"
                />
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className={`text-sm font-medium ${darkMode ? 'text-white' : 'text-gray-800'}`}
                    >
                      ARC Chatbot
                    </span>
                    <span className={`text-xs ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                      Thinking...
                    </span>
                  </div>
                  <div
                    className={`px-4 py-3 rounded-2xl rounded-tl-md ${darkMode ? 'bg-gray-800' : 'bg-white'} shadow-sm`}
                  >
                    <div className="flex items-center gap-1">
                      <div
                        className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"
                        style={{ animationDelay: '0ms' }}
                      ></div>
                      <div
                        className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"
                        style={{ animationDelay: '150ms' }}
                      ></div>
                      <div
                        className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"
                        style={{ animationDelay: '300ms' }}
                      ></div>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          <div ref={messagesEndRef} />
        </div>
        )}

        {/* Input - only show in chat mode */}
        {activeMenu === 'chat' && (
        <div className="px-6 py-4">
          <div className="max-w-4xl mx-auto">
            {/* Query Enhancement */}
            {showEnhancement && input.trim().length > 5 && (
              <QueryEnhancement
                query={input}
                onApplySuggestion={(improvedQuery) => {
                  setInput(improvedQuery)
                  setShowEnhancement(false)
                }}
                darkMode={darkMode}
              />
            )}

            <form onSubmit={handleSend} className="relative">
              <input
                type="text"
                value={input}
                onChange={(e) => {
                  setInput(e.target.value)
                  // Tự động hiển thị enhancement khi user gõ đủ dài
                  if (e.target.value.trim().length > 10 && !showEnhancement) {
                    setShowEnhancement(true)
                  }
                }}
                placeholder="Enter a prompt here..."
                disabled={loading}
                className={`w-full h-12 pl-5 pr-28 text-sm ${darkMode ? 'bg-gray-800 text-white border-gray-700 placeholder:text-gray-500' : 'bg-white text-gray-700 border-gray-200 placeholder:text-gray-400'} border rounded-full focus:outline-none focus:border-blue-300 focus:ring-1 focus:ring-blue-50 transition-all shadow-[0_2px_8px_rgba(0,0,0,0.04)]`}
              />
              
              {/* Enhancement toggle button */}
              {input.trim().length > 5 && !loading && (
                <button
                  type="button"
                  onClick={() => setShowEnhancement(!showEnhancement)}
                  className={`absolute right-12 top-1/2 -translate-y-1/2 w-8 h-8 flex items-center justify-center rounded-full transition-colors ${
                    showEnhancement
                      ? 'bg-yellow-500 text-white'
                      : darkMode
                        ? 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                        : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                  }`}
                  title="Cải thiện câu hỏi"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                    />
                  </svg>
                </button>
              )}

              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="absolute right-1.5 top-1/2 -translate-y-1/2 w-9 h-9 flex items-center justify-center bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 text-white rounded-full transition-colors"
              >
                {loading ? (
                  <Spinner size="sm" color="white" />
                ) : (
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
                  </svg>
                )}
              </button>
            </form>

            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg"
              >
                <p className="text-sm text-red-800">⚠️ {error}</p>
              </motion.div>
            )}
          </div>
        </div>
        )}
      </div>

      {selectedCitation && (
        <DocumentViewerModal
          citation={selectedCitation}
          onClose={handleCloseModal}
          query={selectedQuery}
        />
      )}
    </div>
  )
}

export default ChatPage
