/**
 * Syllabus Viewer Component
 * Displays structured syllabus data with tabs for different sections
 */

import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Spinner } from '@heroui/react'
import { syllabusService } from '../services/syllabusService'

function SyllabusViewer({ subjectCode, darkMode = false }) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [syllabusData, setSyllabusData] = useState(null)
  const [activeTab, setActiveTab] = useState('overview')

  useEffect(() => {
    if (subjectCode) {
      loadSyllabus()
    }
  }, [subjectCode])

  const loadSyllabus = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await syllabusService.getSyllabus(subjectCode)
      setSyllabusData(data)
    } catch (err) {
      console.error('Failed to load syllabus:', err)
      setError(err.message || 'Failed to load syllabus')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center py-12">
        <Spinner size="lg" />
      </div>
    )
  }

  if (error) {
    return (
      <div className={`p-6 rounded-xl border ${darkMode ? 'bg-red-900/20 border-red-800 text-red-300' : 'bg-red-50 border-red-200 text-red-700'}`}>
        <p className="font-medium">Error loading syllabus</p>
        <p className="text-sm mt-1">{error}</p>
      </div>
    )
  }

  if (!syllabusData) {
    return (
      <div className={`p-6 rounded-xl border text-center ${darkMode ? 'bg-gray-800 border-gray-700 text-gray-400' : 'bg-gray-50 border-gray-200 text-gray-500'}`}>
        <p>No syllabus data available</p>
      </div>
    )
  }

  const tabs = [
    { id: 'overview', label: 'Overview', icon: '📋' },
    { id: 'sessions', label: `Sessions (${syllabusData.total_sessions})`, icon: '📚' },
    { id: 'assessments', label: `Assessments (${syllabusData.total_assessments})`, icon: '📝' },
    { id: 'clos', label: `CLOs (${syllabusData.clos?.length || 0})`, icon: '🎯' },
    { id: 'materials', label: `Materials (${syllabusData.materials?.length || 0})`, icon: '📖' },
  ]

  return (
    <div className={`rounded-xl border ${darkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'}`}>
      {/* Header */}
      {syllabusData.course_info && (
        <div className={`p-6 border-b ${darkMode ? 'border-gray-700' : 'border-gray-200'}`}>
          <div className="flex items-start justify-between">
            <div>
              <h2 className={`text-2xl font-bold ${darkMode ? 'text-white' : 'text-gray-900'}`}>
                {syllabusData.course_info.course_name}
              </h2>
              <div className="flex items-center gap-4 mt-2">
                <span className={`text-sm ${darkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                  {syllabusData.course_info.subject_code}
                </span>
                <span className={`px-2 py-1 rounded text-xs font-medium ${darkMode ? 'bg-blue-900/30 text-blue-300' : 'bg-blue-100 text-blue-700'}`}>
                  {syllabusData.course_info.credits} Credits
                </span>
                {syllabusData.course_info.department && (
                  <span className={`text-sm ${darkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                    {syllabusData.course_info.department}
                  </span>
                )}
              </div>
            </div>
            <div className="text-right">
              <p className={`text-xs ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                Decision No.
              </p>
              <p className={`text-sm font-medium ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>
                {syllabusData.course_info.decision_no}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className={`flex gap-2 px-6 pt-4 border-b ${darkMode ? 'border-gray-700' : 'border-gray-200'}`}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors relative ${
              activeTab === tab.id
                ? darkMode
                  ? 'bg-gray-700 text-white'
                  : 'bg-gray-100 text-gray-900'
                : darkMode
                  ? 'text-gray-400 hover:text-gray-300 hover:bg-gray-700/50'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
            }`}
          >
            <span className="mr-2">{tab.icon}</span>
            {tab.label}
            {activeTab === tab.id && (
              <motion.div
                layoutId="activeTab"
                className={`absolute bottom-0 left-0 right-0 h-0.5 ${darkMode ? 'bg-blue-400' : 'bg-blue-500'}`}
              />
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="p-6">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
          >
            {activeTab === 'overview' && (
              <OverviewTab data={syllabusData} darkMode={darkMode} />
            )}
            {activeTab === 'sessions' && (
              <SessionsTab sessions={syllabusData.sessions} darkMode={darkMode} />
            )}
            {activeTab === 'assessments' && (
              <AssessmentsTab assessments={syllabusData.assessments} totalWeight={syllabusData.total_weight} darkMode={darkMode} />
            )}
            {activeTab === 'clos' && (
              <CLOsTab clos={syllabusData.clos} darkMode={darkMode} />
            )}
            {activeTab === 'materials' && (
              <MaterialsTab materials={syllabusData.materials} darkMode={darkMode} />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}

// Overview Tab
function OverviewTab({ data, darkMode }) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          label="Total Sessions"
          value={data.total_sessions}
          icon="📚"
          darkMode={darkMode}
        />
        <StatCard
          label="Assessments"
          value={data.total_assessments}
          icon="📝"
          darkMode={darkMode}
        />
        <StatCard
          label="Total Weight"
          value={`${data.total_weight}%`}
          icon="⚖️"
          darkMode={darkMode}
        />
      </div>

      {data.course_info?.instructor && (
        <div className={`p-4 rounded-lg ${darkMode ? 'bg-gray-700' : 'bg-gray-50'}`}>
          <p className={`text-sm ${darkMode ? 'text-gray-400' : 'text-gray-600'}`}>
            Instructor
          </p>
          <p className={`font-medium ${darkMode ? 'text-white' : 'text-gray-900'}`}>
            {data.course_info.instructor}
          </p>
        </div>
      )}
    </div>
  )
}

// Stat Card Component
function StatCard({ label, value, icon, darkMode }) {
  return (
    <div className={`p-4 rounded-lg border ${darkMode ? 'bg-gray-700 border-gray-600' : 'bg-gray-50 border-gray-200'}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className={`text-sm ${darkMode ? 'text-gray-400' : 'text-gray-600'}`}>
            {label}
          </p>
          <p className={`text-2xl font-bold mt-1 ${darkMode ? 'text-white' : 'text-gray-900'}`}>
            {value}
          </p>
        </div>
        <span className="text-3xl">{icon}</span>
      </div>
    </div>
  )
}

// Sessions Tab
function SessionsTab({ sessions, darkMode }) {
  const [filterCLO, setFilterCLO] = useState('')

  const filteredSessions = filterCLO
    ? sessions.filter(s => s.clo_coverage.includes(filterCLO))
    : sessions

  // Extract unique CLOs
  const allCLOs = [...new Set(sessions.flatMap(s => s.clo_coverage))].sort()

  return (
    <div className="space-y-4">
      {/* Filter */}
      {allCLOs.length > 0 && (
        <div className="flex items-center gap-2">
          <span className={`text-sm ${darkMode ? 'text-gray-400' : 'text-gray-600'}`}>
            Filter by CLO:
          </span>
          <select
            value={filterCLO}
            onChange={(e) => setFilterCLO(e.target.value)}
            className={`px-3 py-1 rounded-lg border text-sm ${
              darkMode
                ? 'bg-gray-700 border-gray-600 text-white'
                : 'bg-white border-gray-300 text-gray-900'
            }`}
          >
            <option value="">All CLOs</option>
            {allCLOs.map(clo => (
              <option key={clo} value={clo}>{clo}</option>
            ))}
          </select>
        </div>
      )}

      {/* Sessions List */}
      <div className="space-y-3">
        {filteredSessions.map((session) => (
          <div
            key={session.session_number}
            className={`p-4 rounded-lg border ${darkMode ? 'bg-gray-700 border-gray-600' : 'bg-gray-50 border-gray-200'}`}
          >
            <div className="flex items-start gap-4">
              <div className={`flex-shrink-0 w-12 h-12 rounded-lg flex items-center justify-center font-bold ${
                darkMode ? 'bg-blue-900/30 text-blue-300' : 'bg-blue-100 text-blue-700'
              }`}>
                {session.session_number}
              </div>
              <div className="flex-1">
                <div className="flex items-start justify-between">
                  <div>
                    <h4 className={`font-medium ${darkMode ? 'text-white' : 'text-gray-900'}`}>
                      {session.topics.join(', ')}
                    </h4>
                    <div className="flex items-center gap-3 mt-2">
                      {session.mode && (
                        <span className={`text-xs px-2 py-1 rounded ${
                          darkMode ? 'bg-gray-600 text-gray-300' : 'bg-gray-200 text-gray-700'
                        }`}>
                          {session.mode}
                        </span>
                      )}
                      {session.session_type && (
                        <span className={`text-xs px-2 py-1 rounded ${
                          darkMode ? 'bg-purple-900/30 text-purple-300' : 'bg-purple-100 text-purple-700'
                        }`}>
                          {session.session_type}
                        </span>
                      )}
                    </div>
                  </div>
                  {session.clo_coverage.length > 0 && (
                    <div className="flex gap-1">
                      {session.clo_coverage.map(clo => (
                        <span
                          key={clo}
                          className={`text-xs px-2 py-1 rounded font-medium ${
                            darkMode ? 'bg-green-900/30 text-green-300' : 'bg-green-100 text-green-700'
                          }`}
                        >
                          {clo}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                {session.activities && (
                  <p className={`text-sm mt-2 ${darkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                    📌 {session.activities}
                  </p>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// Assessments Tab
function AssessmentsTab({ assessments, totalWeight, darkMode }) {
  return (
    <div className="space-y-4">
      {/* Total Weight */}
      <div className={`p-4 rounded-lg border ${
        totalWeight === 100
          ? darkMode ? 'bg-green-900/20 border-green-800' : 'bg-green-50 border-green-200'
          : darkMode ? 'bg-yellow-900/20 border-yellow-800' : 'bg-yellow-50 border-yellow-200'
      }`}>
        <p className={`text-sm ${
          totalWeight === 100
            ? darkMode ? 'text-green-300' : 'text-green-700'
            : darkMode ? 'text-yellow-300' : 'text-yellow-700'
        }`}>
          Total Weight: <span className="font-bold">{totalWeight}%</span>
          {totalWeight === 100 ? ' ✓' : ' ⚠️'}
        </p>
      </div>

      {/* Assessments Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className={`border-b ${darkMode ? 'border-gray-700' : 'border-gray-200'}`}>
              <th className={`text-left py-3 px-4 text-sm font-medium ${darkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                Category
              </th>
              <th className={`text-center py-3 px-4 text-sm font-medium ${darkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                Weight
              </th>
              <th className={`text-left py-3 px-4 text-sm font-medium ${darkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                CLOs
              </th>
              <th className={`text-left py-3 px-4 text-sm font-medium ${darkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                Duration
              </th>
            </tr>
          </thead>
          <tbody>
            {assessments.map((assessment, idx) => (
              <tr
                key={idx}
                className={`border-b ${darkMode ? 'border-gray-700' : 'border-gray-100'}`}
              >
                <td className={`py-3 px-4 ${darkMode ? 'text-white' : 'text-gray-900'}`}>
                  <div>
                    <p className="font-medium">{assessment.category}</p>
                    {assessment.part && (
                      <p className={`text-xs ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                        Part {assessment.part}
                      </p>
                    )}
                  </div>
                </td>
                <td className="py-3 px-4 text-center">
                  <span className={`inline-block px-3 py-1 rounded-full font-bold ${
                    darkMode ? 'bg-blue-900/30 text-blue-300' : 'bg-blue-100 text-blue-700'
                  }`}>
                    {assessment.weight_percentage}%
                  </span>
                </td>
                <td className="py-3 px-4">
                  <div className="flex flex-wrap gap-1">
                    {assessment.clo_mapping.map(clo => (
                      <span
                        key={clo}
                        className={`text-xs px-2 py-1 rounded ${
                          darkMode ? 'bg-green-900/30 text-green-300' : 'bg-green-100 text-green-700'
                        }`}
                      >
                        {clo}
                      </span>
                    ))}
                  </div>
                </td>
                <td className={`py-3 px-4 text-sm ${darkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                  {assessment.duration || '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// CLOs Tab
function CLOsTab({ clos, darkMode }) {
  return (
    <div className="space-y-4">
      {clos.map((clo, idx) => (
        <div
          key={clo.clo_id}
          className={`p-4 rounded-lg border ${darkMode ? 'bg-gray-700 border-gray-600' : 'bg-gray-50 border-gray-200'}`}
        >
          <div className="flex items-start gap-4">
            <div className={`flex-shrink-0 w-16 h-16 rounded-lg flex items-center justify-center font-bold text-lg ${
              darkMode ? 'bg-green-900/30 text-green-300' : 'bg-green-100 text-green-700'
            }`}>
              {clo.clo_id}
            </div>
            <div className="flex-1">
              <p className={`${darkMode ? 'text-white' : 'text-gray-900'}`}>
                {clo.description}
              </p>
              {clo.plo_mapping.length > 0 && (
                <div className="flex items-center gap-2 mt-2">
                  <span className={`text-xs ${darkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                    Maps to:
                  </span>
                  {clo.plo_mapping.map(plo => (
                    <span
                      key={plo}
                      className={`text-xs px-2 py-1 rounded ${
                        darkMode ? 'bg-blue-900/30 text-blue-300' : 'bg-blue-100 text-blue-700'
                      }`}
                    >
                      {plo}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

// Materials Tab
function MaterialsTab({ materials, darkMode }) {
  if (materials.length === 0) {
    return (
      <div className={`text-center py-8 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
        <p>No materials listed</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {materials.map((material) => (
        <div
          key={material.material_id}
          className={`p-4 rounded-lg border ${darkMode ? 'bg-gray-700 border-gray-600' : 'bg-gray-50 border-gray-200'}`}
        >
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <h4 className={`font-medium ${darkMode ? 'text-white' : 'text-gray-900'}`}>
                  {material.title}
                </h4>
                {material.is_main_material && (
                  <span className={`text-xs px-2 py-1 rounded font-medium ${
                    darkMode ? 'bg-yellow-900/30 text-yellow-300' : 'bg-yellow-100 text-yellow-700'
                  }`}>
                    Main
                  </span>
                )}
              </div>
              {material.author && (
                <p className={`text-sm mt-1 ${darkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                  By {material.author}
                </p>
              )}
              <div className="flex items-center gap-3 mt-2">
                {material.publisher && (
                  <span className={`text-xs ${darkMode ? 'text-gray-500' : 'text-gray-500'}`}>
                    {material.publisher}
                  </span>
                )}
                {material.published_date && (
                  <span className={`text-xs ${darkMode ? 'text-gray-500' : 'text-gray-500'}`}>
                    {material.published_date}
                  </span>
                )}
                {material.edition && (
                  <span className={`text-xs ${darkMode ? 'text-gray-500' : 'text-gray-500'}`}>
                    {material.edition}
                  </span>
                )}
              </div>
              <div className="flex gap-2 mt-2">
                {material.is_hard_copy && (
                  <span className={`text-xs px-2 py-1 rounded ${
                    darkMode ? 'bg-gray-600 text-gray-300' : 'bg-gray-200 text-gray-700'
                  }`}>
                    📚 Hard Copy
                  </span>
                )}
                {material.is_online && (
                  <span className={`text-xs px-2 py-1 rounded ${
                    darkMode ? 'bg-blue-900/30 text-blue-300' : 'bg-blue-100 text-blue-700'
                  }`}>
                    🌐 Online
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

export default SyllabusViewer
