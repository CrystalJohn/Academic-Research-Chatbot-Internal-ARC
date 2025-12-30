/**
 * Answer With Citations Component
 * Renders answer text with inline citation badges
 * Parses [1], [2], etc. and replaces with interactive CitationBadge components
 */

import { useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import CitationBadge from './CitationBadge'

function AnswerWithCitations({ content, citations = [], onViewDocument, query = '' }) {
  // Create citation map for quick lookup
  const citationMap = useMemo(() => {
    const map = {}
    citations.forEach(c => {
      map[c.id] = c
    })
    return map
  }, [citations])

  // Custom renderer that handles citation badges within text
  const renderTextWithCitations = (text) => {
    if (!text || typeof text !== 'string') return text
    
    // Match [1], [2], etc.
    const citationRegex = /\[(\d+)\]/g
    const parts = []
    let lastIndex = 0
    let match

    while ((match = citationRegex.exec(text)) !== null) {
      // Add text before citation
      if (match.index > lastIndex) {
        parts.push(text.slice(lastIndex, match.index))
      }
      
      // Add citation badge
      const citationId = parseInt(match[1], 10)
      const citation = citationMap[citationId]
      
      parts.push(
        <CitationBadge
          key={`citation-${match.index}-${citationId}`}
          citation={citation}
          index={citationId}
          onViewDocument={onViewDocument}
          query={query}
        />
      )
      
      lastIndex = match.index + match[0].length
    }
    
    // Add remaining text
    if (lastIndex < text.length) {
      parts.push(text.slice(lastIndex))
    }
    
    return parts.length > 0 ? parts : text
  }

  // Custom components for ReactMarkdown
  const markdownComponents = {
    // Handle code blocks
    code({ node, inline, className, children, ...props }) {
      const match = /language-(\w+)/.exec(className || '')
      return !inline && match ? (
        <SyntaxHighlighter
          style={oneDark}
          language={match[1]}
          PreTag="div"
          className="rounded-lg text-xs"
          {...props}
        >
          {String(children).replace(/\n$/, '')}
        </SyntaxHighlighter>
      ) : (
        <code className="bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded text-xs font-mono" {...props}>
          {children}
        </code>
      )
    },
    // Handle paragraphs - inject citation badges
    p({ children }) {
      const processedChildren = processChildren(children)
      return <p className="my-2">{processedChildren}</p>
    },
    // Handle list items
    li({ children }) {
      const processedChildren = processChildren(children)
      return <li>{processedChildren}</li>
    },
    // Handle strong text
    strong({ children }) {
      const processedChildren = processChildren(children)
      return <strong className="font-semibold text-gray-900 dark:text-gray-100">{processedChildren}</strong>
    },
    // Headers
    h2: ({ children }) => (
      <h2 className="text-base font-semibold text-gray-800 dark:text-gray-200 mt-4 mb-2">{children}</h2>
    ),
    h3: ({ children }) => (
      <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mt-3 mb-1">{children}</h3>
    ),
    // Lists
    ul: ({ children }) => (
      <ul className="list-disc list-inside space-y-1 my-2">{children}</ul>
    ),
    ol: ({ children }) => (
      <ol className="list-decimal list-inside space-y-1 my-2">{children}</ol>
    ),
  }

  // Process children to inject citation badges
  function processChildren(children) {
    if (!children) return children
    
    if (typeof children === 'string') {
      return renderTextWithCitations(children)
    }
    
    if (Array.isArray(children)) {
      return children.map((child, i) => {
        if (typeof child === 'string') {
          return <span key={i}>{renderTextWithCitations(child)}</span>
        }
        return child
      })
    }
    
    return children
  }

  return (
    <div className="text-sm leading-relaxed prose prose-sm max-w-none dark:prose-invert">
      <ReactMarkdown components={markdownComponents}>
        {content}
      </ReactMarkdown>
    </div>
  )
}

export default AnswerWithCitations
