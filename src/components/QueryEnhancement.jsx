import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Spinner } from '@heroui/react'
import { chatService } from '../services/chatService'

/**
 * Component hiển thị gợi ý cải thiện câu hỏi
 * 
 * Props:
 * - query: Câu hỏi gốc
 * - onApplySuggestion: Callback khi user chọn áp dụng gợi ý
 * - darkMode: Dark mode flag
 */
function QueryEnhancement({ query, onApplySuggestion, darkMode = false }) {
  const [analysis, setAnalysis] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [expanded, setExpanded] = useState(false)

  const analyzeQuery = async () => {
    if (!query || query.trim().length < 5) {
      return
    }

    setLoading(true)
    setError(null)
    setExpanded(true)

    try {
      const data = await chatService.enhanceQuery(query)
      setAnalysis(data)
    } catch (err) {
      console.error('Query analysis error:', err)
      setError('Không thể phân tích câu hỏi. Vui lòng thử lại.')
    } finally {
      setLoading(false)
    }
  }

  const handleApplySuggestion = (improvedQuery) => {
    onApplySuggestion(improvedQuery)
    setExpanded(false)
    setAnalysis(null)
  }

  // Không hiển thị nếu câu hỏi quá ngắn
  if (!query || query.trim().length < 5) {
    return null
  }

  // Nếu đã phân tích và chất lượng tốt, không hiển thị
  if (analysis && analysis.is_good_quality) {
    return null
  }

  return (
    <div className="mb-3">
      {/* Trigger button */}
      {!expanded && !analysis && (
        <button
          onClick={analyzeQuery}
          disabled={loading}
          className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
            darkMode
              ? 'bg-yellow-900/30 text-yellow-400 hover:bg-yellow-900/50'
              : 'bg-yellow-50 text-yellow-700 hover:bg-yellow-100'
          }`}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <span>Câu hỏi chính xác hơn sẽ cho kết quả tốt hơn</span>
        </button>
      )}

      {/* Analysis panel */}
      <AnimatePresence>
        {(expanded || analysis) && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className={`overflow-hidden rounded-xl border ${
              darkMode
                ? 'bg-gray-800 border-gray-700'
                : 'bg-white border-gray-200'
            } shadow-sm`}
          >
            <div className="p-4">
              {/* Header */}
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-full bg-yellow-100 flex items-center justify-center">
                    <svg
                      className="w-4 h-4 text-yellow-600"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                      />
                    </svg>
                  </div>
                  <div>
                    <h4
                      className={`font-medium ${darkMode ? 'text-white' : 'text-gray-800'}`}
                    >
                      Gợi ý cải thiện câu hỏi
                    </h4>
                    {analysis && (
                      <p className="text-xs text-gray-500">
                        Điểm chất lượng: {(analysis.quality_score * 100).toFixed(0)}%
                      </p>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => {
                    setExpanded(false)
                    setAnalysis(null)
                  }}
                  className={`p-1 rounded-lg ${
                    darkMode
                      ? 'hover:bg-gray-700 text-gray-400'
                      : 'hover:bg-gray-100 text-gray-500'
                  }`}
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              </div>

              {/* Loading */}
              {loading && (
                <div className="flex items-center justify-center py-8">
                  <Spinner size="md" />
                  <span className={`ml-3 text-sm ${darkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                    Đang phân tích câu hỏi...
                  </span>
                </div>
              )}

              {/* Error */}
              {error && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                  {error}
                </div>
              )}

              {/* Suggestions */}
              {analysis && !loading && (
                <div className="space-y-3">
                  <p className={`text-sm ${darkMode ? 'text-gray-300' : 'text-gray-600'}`}>
                    Thêm các yếu tố sau để câu hỏi rõ ràng hơn:
                  </p>

                  {/* Category tags */}
                  <div className="flex flex-wrap gap-2">
                    {analysis.suggestions.map((suggestion, idx) => (
                      <span
                        key={idx}
                        className={`px-2.5 py-1 rounded-full text-xs font-medium ${
                          darkMode
                            ? 'bg-blue-900/30 text-blue-400'
                            : 'bg-blue-50 text-blue-700'
                        }`}
                      >
                        {getCategoryLabel(suggestion.category)}
                      </span>
                    ))}
                  </div>

                  {/* Individual suggestions */}
                  <div className="space-y-2">
                    {analysis.suggestions.map((suggestion, idx) => (
                      <motion.div
                        key={idx}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: idx * 0.1 }}
                        className={`p-3 rounded-lg border ${
                          darkMode
                            ? 'bg-gray-700/50 border-gray-600'
                            : 'bg-gray-50 border-gray-200'
                        }`}
                      >
                        <p className={`text-sm mb-2 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>
                          {suggestion.suggestion}
                        </p>
                        <button
                          onClick={() => handleApplySuggestion(suggestion.improved_query)}
                          className={`w-full text-left p-2 rounded-lg text-sm transition-colors ${
                            darkMode
                              ? 'bg-gray-600 hover:bg-gray-500 text-white'
                              : 'bg-white hover:bg-blue-50 text-gray-800 border border-gray-200'
                          }`}
                        >
                          <div className="flex items-start gap-2">
                            <svg
                              className="w-4 h-4 mt-0.5 flex-shrink-0 text-blue-500"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M13 7l5 5m0 0l-5 5m5-5H6"
                              />
                            </svg>
                            <span className="flex-1">{suggestion.improved_query}</span>
                          </div>
                        </button>
                      </motion.div>
                    ))}
                  </div>

                  {/* Best improved query */}
                  {analysis.improved_query && (
                    <div
                      className={`p-4 rounded-lg border-2 ${
                        darkMode
                          ? 'bg-blue-900/20 border-blue-700'
                          : 'bg-blue-50 border-blue-200'
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <svg
                          className="w-5 h-5 text-blue-500"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M5 13l4 4L19 7"
                          />
                        </svg>
                        <span
                          className={`text-sm font-medium ${
                            darkMode ? 'text-blue-400' : 'text-blue-700'
                          }`}
                        >
                          Câu hỏi được đề xuất
                        </span>
                      </div>
                      <p className={`text-sm mb-3 ${darkMode ? 'text-gray-200' : 'text-gray-800'}`}>
                        {analysis.improved_query}
                      </p>
                      <button
                        onClick={() => handleApplySuggestion(analysis.improved_query)}
                        className="w-full px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M5 13l4 4L19 7"
                          />
                        </svg>
                        Sử dụng câu hỏi này
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function getCategoryLabel(category) {
  const labels = {
    specificity: 'Tính cụ thể',
    comparative_approach: 'So sánh',
    impact_assessment: 'Đánh giá tác động',
    context: 'Ngữ cảnh',
    scope: 'Phạm vi',
    general: 'Chung',
  }
  return labels[category] || category
}

export default QueryEnhancement
