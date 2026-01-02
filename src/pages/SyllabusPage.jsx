/**
 * Syllabus Page
 * View structured syllabus data for FPT University courses
 */

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import SyllabusViewer from '../components/SyllabusViewer'
import Sidebar from '../components/Sidebar'
import { authService } from '../services/authService'

function SyllabusPage() {
  const navigate = useNavigate()
  const [subjectCode, setSubjectCode] = useState('SWD392')
  const [inputValue, setInputValue] = useState('SWD392')
  const [darkMode, setDarkMode] = useState(false)
  const [activeMenu, setActiveMenu] = useState('syllabus')
  const [activeSubMenu, setActiveSubMenu] = useState('current')
  const [user, setUser] = useState(null)
  const [showAccountMenu, setShowAccountMenu] = useState(false)

  const loadUser = async () => {
    const currentUser = await authService.getCurrentUser()
    setUser(currentUser)
  }

  useEffect(() => {
    loadUser()
  }, [])

  const handleSearch = (e) => {
    e.preventDefault()
    if (inputValue.trim()) {
      setSubjectCode(inputValue.trim().toUpperCase())
    }
  }

  const handleLogout = async () => {
    await authService.logout()
    navigate('/login')
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
        onNewChat={() => navigate('/chat')}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div
          className={`${darkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'} border-b px-6 py-4 flex items-center justify-between`}
        >
          <div className="flex items-center gap-3">
            <h2 className={`text-lg font-semibold ${darkMode ? 'text-white' : 'text-gray-800'}`}>
              Syllabus Viewer
            </h2>
            <span className="px-2 py-1 bg-purple-100 text-purple-600 text-xs font-medium rounded-full">
              BETA
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

        {/* Search Bar */}
        <div className={`px-6 py-4 border-b ${darkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'}`}>
          <form onSubmit={handleSearch} className="max-w-2xl mx-auto">
            <div className="flex gap-2">
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder="Enter subject code (e.g., SWD392, EXE401)"
                className={`flex-1 px-4 py-2 rounded-lg border ${
                  darkMode
                    ? 'bg-gray-700 border-gray-600 text-white placeholder:text-gray-400'
                    : 'bg-white border-gray-300 text-gray-900 placeholder:text-gray-400'
                } focus:outline-none focus:ring-2 focus:ring-blue-500`}
              />
              <button
                type="submit"
                className="px-6 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium transition-colors"
              >
                Search
              </button>
            </div>
          </form>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-6xl mx-auto">
            <motion.div
              key={subjectCode}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
            >
              <SyllabusViewer subjectCode={subjectCode} darkMode={darkMode} />
            </motion.div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default SyllabusPage
