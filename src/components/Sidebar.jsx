import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { authService } from '../services/authService'
import arcLogo from '../assets/Logo ARC-chatbot.png'

function Sidebar({
  activeMenu,
  setActiveMenu,
  user,
  darkMode = false,
  onNewChat = null,
  activeSubMenu = 'current',
  setActiveSubMenu = null,
}) {
  const navigate = useNavigate()
  const isAdmin = user?.groups?.includes('admin')
  const [chatExpanded, setChatExpanded] = useState(true)

  const handleLogout = async () => {
    await authService.logout()
    navigate('/login')
  }

  const menuItems = [
    {
      id: 'documents',
      label: 'Document Management',
      icon: 'document',
      path: '/admin',
      adminOnly: true,
    },
    {
      id: 'syllabus',
      label: 'Syllabus Viewer',
      icon: 'syllabus',
      path: '/syllabus',
      adminOnly: false,
    },
    { id: 'users', label: 'Users', icon: 'users', adminOnly: true },
    { id: 'settings', label: 'Settings', icon: 'settings', adminOnly: true },
  ]

  const getIcon = (iconName) => {
    const icons = {
      chat: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
          />
        </svg>
      ),
      history: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      ),
      current: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
          />
        </svg>
      ),
      document: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
      ),
      users: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
          />
        </svg>
      ),
      settings: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
          />
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
          />
        </svg>
      ),
      syllabus: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
          />
        </svg>
      ),
      help: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      ),
      logout: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
          />
        </svg>
      ),
      chevron: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      ),
    }
    return icons[iconName] || null
  }

  const handleMenuClick = (item) => {
    if (item.path) {
      navigate(item.path)
    }
    if (setActiveMenu) {
      setActiveMenu(item.id)
    }
  }

  const handleChatClick = () => {
    setChatExpanded(!chatExpanded)
    if (setActiveMenu) {
      setActiveMenu('chat')
    }
    navigate('/chat')
  }

  const handleSubMenuClick = (subId) => {
    if (setActiveSubMenu) {
      setActiveSubMenu(subId)
    }
    if (setActiveMenu) {
      setActiveMenu('chat')
    }
  }

  const isChatActive = activeMenu === 'chat'

  return (
    <div
      className={`w-60 ${darkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'} border-r flex flex-col`}
    >
      {/* Logo */}
      <div className={`p-5 border-b ${darkMode ? 'border-gray-700' : 'border-gray-200'}`}>
        <div className="flex items-center gap-3">
          <img src={arcLogo} alt="ARC Chatbot" className="w-10 h-10 rounded-full object-cover" />
          <div>
            <h1 className={`font-semibold ${darkMode ? 'text-white' : 'text-gray-800'}`}>
              ARC Chatbot
            </h1>
            <p className="text-xs text-emerald-500">Research Assistant</p>
          </div>
        </div>
      </div>

      {/* New Chat Button */}
      {onNewChat && (
        <div className="px-3 py-4">
          <motion.button
            onClick={onNewChat}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-500 hover:bg-blue-600 text-white rounded-xl transition-colors font-medium"
          >
            <span className="text-lg">+</span>
            <span>New Chat</span>
          </motion.button>
        </div>
      )}

      {/* Menu */}
      <nav className={`flex-1 px-3 ${onNewChat ? '' : 'py-4'} space-y-1`}>
        {/* Chat Menu with Sub-items */}
        <div>
          <motion.button
            onClick={handleChatClick}
            whileHover={{ x: 4 }}
            whileTap={{ scale: 0.98 }}
            className={`w-full flex items-center justify-between px-4 py-3 rounded-xl text-sm transition-colors relative ${
              isChatActive
                ? 'bg-blue-50 text-blue-600 font-medium'
                : `${darkMode ? 'text-gray-300 hover:bg-gray-700' : 'text-gray-600 hover:bg-gray-100'}`
            }`}
          >
            <div className="flex items-center gap-3">
              {isChatActive && (
                <motion.div
                  layoutId="activeIndicator"
                  className="absolute left-0 top-0 bottom-0 w-1 bg-blue-500 rounded-r-full"
                  initial={false}
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}
              {getIcon('chat')}
              <span>Chat</span>
            </div>
            <motion.div
              animate={{ rotate: chatExpanded ? 180 : 0 }}
              transition={{ duration: 0.2 }}
            >
              {getIcon('chevron')}
            </motion.div>
          </motion.button>

          {/* Sub-menu */}
          <AnimatePresence>
            {chatExpanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden"
              >
                <div className="ml-4 mt-1 space-y-1">
                  <motion.button
                    onClick={() => handleSubMenuClick('current')}
                    whileHover={{ x: 4 }}
                    whileTap={{ scale: 0.98 }}
                    className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm transition-colors ${
                      activeSubMenu === 'current' && isChatActive
                        ? 'bg-blue-100 text-blue-600 font-medium'
                        : `${darkMode ? 'text-gray-400 hover:bg-gray-700' : 'text-gray-500 hover:bg-gray-100'}`
                    }`}
                  >
                    {getIcon('current')}
                    <span>Current Chat</span>
                  </motion.button>

                  <motion.button
                    onClick={() => handleSubMenuClick('history')}
                    whileHover={{ x: 4 }}
                    whileTap={{ scale: 0.98 }}
                    className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm transition-colors ${
                      activeSubMenu === 'history' && isChatActive
                        ? 'bg-blue-100 text-blue-600 font-medium'
                        : `${darkMode ? 'text-gray-400 hover:bg-gray-700' : 'text-gray-500 hover:bg-gray-100'}`
                    }`}
                  >
                    {getIcon('history')}
                    <span>History</span>
                  </motion.button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Other Menu Items */}
        {menuItems.map((item) => {
          if (item.adminOnly && !isAdmin) return null
          const isActive = activeMenu === item.id
          return (
            <motion.button
              key={item.id}
              onClick={() => handleMenuClick(item)}
              whileHover={{ x: 4 }}
              whileTap={{ scale: 0.98 }}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm transition-colors relative ${
                isActive
                  ? 'bg-blue-50 text-blue-600 font-medium'
                  : `${darkMode ? 'text-gray-300 hover:bg-gray-700' : 'text-gray-600 hover:bg-gray-100'}`
              }`}
            >
              {isActive && (
                <motion.div
                  layoutId="activeIndicator"
                  className="absolute left-0 top-0 bottom-0 w-1 bg-blue-500 rounded-r-full"
                  initial={false}
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}
              {getIcon(item.icon)}
              <span>{item.label}</span>
            </motion.button>
          )
        })}
      </nav>

      {/* Bottom Menu */}
      <div className={`p-4 border-t ${darkMode ? 'border-gray-700' : 'border-gray-200'} space-y-1`}>
        <motion.button
          whileHover={{ x: 4 }}
          whileTap={{ scale: 0.98 }}
          className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm ${darkMode ? 'text-gray-300 hover:bg-gray-700' : 'text-gray-600 hover:bg-gray-100'}`}
        >
          {getIcon('help')}
          <span>Help</span>
        </motion.button>
        <motion.button
          onClick={handleLogout}
          whileHover={{ x: 4 }}
          whileTap={{ scale: 0.98 }}
          className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm ${darkMode ? 'text-gray-300 hover:bg-gray-700' : 'text-gray-600 hover:bg-gray-100'}`}
        >
          {getIcon('logout')}
          <span>Logout</span>
        </motion.button>
      </div>
    </div>
  )
}

export default Sidebar
