/**
 * Citation Badge Component
 * Inline badge [1], [2] that appears within answer text
 * Hover/click to show citation popover
 */

import { useState, useRef } from 'react'
import CitationPopover from './CitationPopover'

function CitationBadge({ citation, index, onViewDocument, query = '' }) {
  const [showPopover, setShowPopover] = useState(false)
  const badgeRef = useRef(null)

  const handleClick = (e) => {
    e.stopPropagation()
    setShowPopover(!showPopover)
  }

  const handleMouseEnter = () => {
    setShowPopover(true)
  }

  const handleMouseLeave = (e) => {
    // Check if mouse is moving to popover
    const relatedTarget = e.relatedTarget
    if (relatedTarget?.closest?.('.citation-popover')) {
      return
    }
    setShowPopover(false)
  }

  return (
    <span className="relative inline-block">
      <button
        ref={badgeRef}
        onClick={handleClick}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        className="inline-flex items-center justify-center min-w-[1.5rem] h-5 px-1.5 mx-0.5 text-xs font-medium text-blue-700 bg-blue-100 hover:bg-blue-200 rounded-full cursor-pointer transition-colors align-middle"
        title={citation?.filename || `Source ${index}`}
      >
        {index}
      </button>
      
      {showPopover && citation && (
        <CitationPopover
          citation={citation}
          onClose={() => setShowPopover(false)}
          onViewDocument={onViewDocument}
          query={query}
          anchorRef={badgeRef}
        />
      )}
    </span>
  )
}

export default CitationBadge
