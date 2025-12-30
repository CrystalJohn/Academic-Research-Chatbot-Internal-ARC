/**
 * Citation Popover Component
 * Shows source preview on hover/click of citation badge
 * Similar to Sana's citation popover design
 */

import { useEffect, useRef, useMemo, useState } from 'react'

function CitationPopover({ citation, onClose, onViewDocument, query = '', anchorRef }) {
  const popoverRef = useRef(null)
  const [position, setPosition] = useState({ top: true, left: 0 })

  // Extract keywords from query for highlighting
  const keywords = useMemo(() => {
    if (!query) return []
    const stopWords = ['là', 'gì', 'và', 'của', 'có', 'được', 'trong', 'cho', 'với', 'này', 'đó', 'các', 'một', 'những', 'như', 'thế', 'nào', 'khi', 'để', 'từ', 'về', 'theo', 'trên', 'the', 'is', 'are', 'what', 'how', 'and', 'or', 'a', 'an', 'to', 'of', 'in', 'for', 'on', 'with']
    return query
      .toLowerCase()
      .split(/\s+/)
      .filter(word => word.length > 2 && !stopWords.includes(word))
  }, [query])

  // Highlight keywords in text
  const highlightText = (text) => {
    if (!text || keywords.length === 0) return text
    
    const escapeRegex = (str) => str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const pattern = keywords.map(escapeRegex).join('|')
    const regex = new RegExp(`(${pattern})`, 'gi')
    const parts = text.split(regex)
    
    return parts.map((part, i) => {
      const isKeyword = keywords.some(kw => part.toLowerCase() === kw.toLowerCase())
      if (isKeyword) {
        return <mark key={i} className="bg-purple-200 text-purple-900 px-0.5 rounded font-medium">{part}</mark>
      }
      return <span key={i}>{part}</span>
    })
  }

  // Calculate position to avoid overflow
  useEffect(() => {
    if (popoverRef.current && anchorRef?.current) {
      const popover = popoverRef.current
      const anchor = anchorRef.current
      const rect = anchor.getBoundingClientRect()
      const popoverRect = popover.getBoundingClientRect()
      
      // Check if popover would overflow right edge
      const rightOverflow = rect.left + popoverRect.width > window.innerWidth - 20
      setPosition({
        top: rect.bottom + popoverRect.height < window.innerHeight - 20,
        left: rightOverflow ? -(popoverRect.width - anchor.offsetWidth - 10) : 0
      })
    }
  }, [anchorRef])

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target) &&
          anchorRef?.current && !anchorRef.current.contains(e.target)) {
        onClose()
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [onClose, anchorRef])

  // Close on Escape
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [onClose])

  const handleViewDocument = () => {
    if (onViewDocument) {
      onViewDocument(citation)
    }
    onClose()
  }

  const formatDate = (timestamp) => {
    if (!timestamp) return ''
    const date = new Date(timestamp)
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    })
  }

  return (
    <div
      ref={popoverRef}
      style={{ left: position.left }}
      className={`citation-popover absolute z-50 ${position.top ? 'top-full mt-2' : 'bottom-full mb-2'} w-80 bg-white rounded-xl shadow-xl border border-gray-200 overflow-hidden`}
    >
      {/* Quote Section */}
      <div className="p-4 bg-gray-50 border-b border-gray-100">
        <div className="flex items-start gap-2">
          <span className="text-gray-400 text-lg leading-none">"</span>
          <p className="text-sm text-gray-700 leading-relaxed line-clamp-4">
            {highlightText(citation.text_snippet)}
          </p>
        </div>
      </div>

      {/* View in Document Link */}
      <button
        onClick={handleViewDocument}
        className="w-full px-4 py-2.5 text-left text-sm text-blue-600 hover:bg-blue-50 transition-colors flex items-center gap-2 border-b border-gray-100"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
        </svg>
        View in document
      </button>

      {/* Document Info */}
      <div className="px-4 py-3 flex items-center gap-3">
        <div className="w-8 h-8 bg-red-100 rounded flex items-center justify-center flex-shrink-0">
          <svg className="w-4 h-4 text-red-600" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clipRule="evenodd" />
          </svg>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900 truncate">
            {citation.filename || `Document ${citation.doc_id?.slice(0, 8)}`}
          </p>
          <p className="text-xs text-gray-500">
            Page {citation.page} • {formatDate(new Date())}
          </p>
        </div>
      </div>
    </div>
  )
}

export default CitationPopover
