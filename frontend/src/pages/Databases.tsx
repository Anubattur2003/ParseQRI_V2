import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import Sidebar from '../components/Sidebar'
import Header from '../components/Header'
import { 
  RiDatabaseLine, 
  RiAddLine, 
  RiCalendarLine, 
  RiTableLine,
  RiDeleteBinLine,
  RiEditLine,
  RiDownloadLine,
  RiEyeLine,
  RiRefreshLine,
  RiSearchLine,
  RiCloseLine,
  RiUploadLine,
  RiArrowLeftLine,
  RiArrowRightLine,
  RiFileTextLine,
  RiFolder3Line,
  RiFolder3Fill,
  RiCheckboxBlankCircleLine,
  RiCheckboxCircleFill
} from 'react-icons/ri'
import { datasetService, dbService, sqlService, authService, apiDiagnostic, endpointDiscovery } from '../services/api'
import apiClient from '../services/api'
import DatabaseMetadataModal from '../components/DatabaseMetadataModal'

interface Database {
  id: number
  name: string
  type: string
  created_at: string
  size?: number
  tables?: number
  status: 'active' | 'inactive' | 'error'
  server_name?: string
  database_name?: string
  use_windows_auth?: boolean
  description?: string
}

const Databases = () => {
  const [databases, setDatabases] = useState<Database[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [showDataSourceModal, setShowDataSourceModal] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [showDataViewer, setShowDataViewer] = useState(false)
  const [selectedDatabase, setSelectedDatabase] = useState<Database | null>(null)
  const [tableData, setTableData] = useState<any[]>([])
  const [tableColumns, setTableColumns] = useState<string[]>([])
  const [isLoadingData, setIsLoadingData] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const [itemsPerPage] = useState(10)
  const [databaseSchema, setDatabaseSchema] = useState<any>(null)
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set())
  const [viewMode, setViewMode] = useState<'data' | 'schema'>('schema')
  const [showMetadataModal, setShowMetadataModal] = useState(false)
  const [selectedDatabaseForMetadata, setSelectedDatabaseForMetadata] = useState<Database | null>(null)
  const navigate = useNavigate()

  // Mock data for demonstration
  const mockDatabases: Database[] = [
    {
      id: 1,
      name: 'INSMA Production',
      type: 'MSSQL',
      created_at: '2024-01-15T10:30:00Z',
      size: 2048,
      tables: 45,
      status: 'active'
    },
    {
      id: 2,
      name: 'Equipment Database',
      type: 'MSSQL',
      created_at: '2024-01-10T14:22:00Z',
      size: 1536,
      tables: 28,
      status: 'active'
    },
    {
      id: 3,
      name: 'Archive Database',
      type: 'MSSQL',
      created_at: '2024-01-08T09:15:00Z',
      size: 512,
      tables: 15,
      status: 'inactive'
    }
  ]

  useEffect(() => {
    const initializePage = async () => {
      try {
        const authStatus = await authService.checkAuth()
        if (!authStatus.isAuthenticated) {
          navigate('/login')
          return
        }
        
        const currentUser = await authService.getCurrentUser()
        console.log('Current user:', currentUser)
        
        await loadDatabases()
      } catch (error) {
        console.error('Error initializing page:', error)
        setError('Authentication error. Please log in again.')
      }
    }
    
    initializePage()
  }, [])

  const loadDatabases = async () => {
    setIsLoading(true)
    setError(null)
    
    try {
      const token = localStorage.getItem('token')
      
            console.log('Loading user database configurations...')
      
      const response = await fetch('/db/configs', {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })
      
      if (response.ok) {
        const dbConfigs = await response.json()
        console.log('Loaded database configurations:', dbConfigs)
        
        const userDatabases = dbConfigs.map((config: any) => ({
          id: config.id,
          name: config.description || `${config.server_name}\\${config.database_name}`,
          type: config.db_type.toUpperCase(),
          created_at: new Date().toISOString(),
          server_name: config.server_name,
          database_name: config.database_name,
          use_windows_auth: config.use_windows_auth,
          description: config.description,
          size: Math.floor(Math.random() * 2000) + 500, // Mock size until we get real metadata
          tables: Math.floor(Math.random() * 50) + 10,  // Mock table count until we get real metadata
          status: 'active' as const
        }))
        
        if (userDatabases.length > 0) {
          setDatabases(userDatabases)
          console.log('Set user databases:', userDatabases)
        } else {
          console.log('No user databases found, using mock data')
          setDatabases(mockDatabases)
        }
      } else {
        console.log('API call failed, using mock data')
        setDatabases(mockDatabases)
      }
    } catch (error) {
      console.error('Error loading databases:', error)
      console.log('Using mock data as fallback')
      setDatabases(mockDatabases)
    } finally {
      setIsLoading(false)
    }
  }

  const handleViewMetadata = (database: Database) => {
    setSelectedDatabaseForMetadata(database)
    setShowMetadataModal(true)
  }

  const handleFileUpload = async (file: File) => {
    setIsUploading(true)
    setError(null)
    
    try {
      let dbId = 1
      try {
        const configs = await dbService.getConfigs()
        if (configs && configs.length > 0) {
          dbId = configs[0].id
        }
      } catch (configError) {
        console.warn('Could not fetch database configs, using default:', configError)
      }

      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch(`/data/upload/${dbId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: formData
      })

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`)
      }

      const result = await response.json()
      
      setSuccessMessage(`File "${file.name}" uploaded successfully!`)
      setShowUploadModal(false)
      
      await loadDatabases()
      
    } catch (error: any) {
      console.error('Upload error:', error)
      setError(`Failed to upload file: ${error.message}`)
    } finally {
      setIsUploading(false)
    }
  }

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    })
  }

  const handleViewDatabase = async (database: Database) => {
    setSelectedDatabase(database)
    setShowDataViewer(true)
    setIsLoadingData(true)
    
    try {
      setTableData([])
      setTableColumns([])
    } catch (error) {
      console.error('Error loading database data:', error)
      setError('Failed to load database data')
    } finally {
      setIsLoadingData(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400'
      case 'inactive':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400'
      case 'error':
        return 'bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-900/20 dark:text-gray-400'
    }
  }

  const getDataTypeIcon = (type: string) => {
    if (type === 'CSV') return <RiFileTextLine />
    if (type === 'MSSQL') return <RiDatabaseLine />
    return <RiFolder3Line />
  }

  const filteredDatabases = databases.filter(database =>
    database.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    database.type.toLowerCase().includes(searchTerm.toLowerCase())
  )

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-dark-950">
      <div className="flex">
      <Sidebar />
        <div className="flex-1">
        <Header />
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5 }}
            className="p-6"
          >
            {/* Error/Success Messages */}
            <AnimatePresence>
              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  className="mb-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded-lg"
                >
                  {error}
                  <button 
                    onClick={() => setError(null)}
                    className="float-right text-red-500 hover:text-red-700 ml-4"
                  >
                    <RiCloseLine size={20} />
                  </button>
                </motion.div>
              )}
              
              {successMessage && (
                <motion.div
                  initial={{ opacity: 0, y: -20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  className="mb-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 text-green-700 dark:text-green-400 px-4 py-3 rounded-lg"
                >
                  {successMessage}
                  <button 
                    onClick={() => setSuccessMessage(null)}
                    className="float-right text-green-500 hover:text-green-700 ml-4"
                  >
                    <RiCloseLine size={20} />
                  </button>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Header */}
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6">
              <div>
                <motion.h1 
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5 }}
                  className="text-3xl font-bold text-gray-900 dark:text-white flex items-center"
                >
                  <RiDatabaseLine className="mr-3 text-primary-600 dark:text-primary-400" />
                  Databases
                </motion.h1>
                <motion.p 
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, delay: 0.1 }}
                  className="mt-1 text-sm text-gray-600 dark:text-gray-400"
                >
                  Manage your SQL Server database connections
                </motion.p>
              </div>
              
              <div className="mt-4 sm:mt-0 flex space-x-3">
                <button
                  onClick={() => {
                    localStorage.removeItem('datasetEndpointsUnavailable')
                    localStorage.removeItem('datasetEndpointsUnavailableExpiry')
                    localStorage.removeItem('sqlEndpointsUnavailable')
                    localStorage.removeItem('sqlEndpointsUnavailableExpiry')
                    loadDatabases()
                  }}
                  className="inline-flex items-center px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-dark-800 hover:bg-gray-50 dark:hover:bg-dark-700 transition-colors"
                >
                  <RiRefreshLine className="mr-2" size={16} />
                  Refresh
                </button>
                <button
                  onClick={() => setShowDataSourceModal(true)}
                  className="inline-flex items-center px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg text-sm font-medium transition-colors"
                >
                  <RiAddLine className="mr-2" size={16} />
                  Add Database
                </button>
              </div>
            </div>

            {/* Search Bar */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="mb-6"
            >
              <div className="relative">
                <RiSearchLine className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={20} />
                <input
                  type="text"
                  placeholder="Search databases..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-3 bg-white dark:bg-dark-800 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent text-gray-900 dark:text-white"
                />
              </div>
            </motion.div>

            {/* Database Cards */}
              <motion.div
              initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.3 }}
            >
            {isLoading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="bg-white dark:bg-dark-900 rounded-xl shadow-md p-6 animate-pulse">
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center">
                          <div className="bg-gray-200 dark:bg-gray-700 p-2 rounded-lg mr-3 w-10 h-10"></div>
                          <div>
                            <div className="bg-gray-200 dark:bg-gray-700 h-4 w-32 rounded mb-2"></div>
                            <div className="bg-gray-200 dark:bg-gray-700 h-3 w-20 rounded"></div>
                          </div>
                        </div>
                        <div className="bg-gray-200 dark:bg-gray-700 h-6 w-16 rounded-full"></div>
                      </div>
                      <div className="space-y-2 mb-4">
                        <div className="bg-gray-200 dark:bg-gray-700 h-3 w-full rounded"></div>
                        <div className="bg-gray-200 dark:bg-gray-700 h-3 w-3/4 rounded"></div>
                      </div>
                      <div className="flex justify-between pt-4 border-t border-gray-200 dark:border-gray-700">
                        <div className="flex space-x-2">
                          <div className="bg-gray-200 dark:bg-gray-700 w-8 h-8 rounded"></div>
                          <div className="bg-gray-200 dark:bg-gray-700 w-8 h-8 rounded"></div>
                          <div className="bg-gray-200 dark:bg-gray-700 w-8 h-8 rounded"></div>
                        </div>
                        <div className="bg-gray-200 dark:bg-gray-700 w-8 h-8 rounded"></div>
                      </div>
                  </div>
                ))}
              </div>
              ) : filteredDatabases.length === 0 ? (
                <div className="text-center py-12">
                  <RiDatabaseLine className="mx-auto h-12 w-12 text-gray-400 dark:text-gray-600 mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">No databases found</h3>
                  <p className="text-gray-500 dark:text-gray-400 mb-4">
                    {searchTerm ? 'No databases match your search criteria.' : 'Get started by adding your first database connection.'}
                  </p>
                      <button
                        onClick={() => setShowDataSourceModal(true)}
                        className="inline-flex items-center px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg text-sm font-medium transition-colors"
                      >
                    <RiAddLine className="mr-2" size={16} />
                    Add Database
                      </button>
                  </div>
                ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {filteredDatabases.map((database, index) => (
                    <motion.div
                      key={database.id}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.5, delay: index * 0.1 }}
                      className="bg-white dark:bg-dark-900 rounded-xl shadow-md hover:shadow-lg hover:scale-[1.02] transition-all duration-200 p-6 cursor-pointer"
                      onClick={() => handleViewDatabase(database)}
                    >
                      <div className="flex items-start justify-between mb-4">
                        <div className="flex items-center">
                          <div className="bg-primary-100 dark:bg-primary-900/30 p-2 rounded-lg mr-3">
                            {getDataTypeIcon(database.type)}
                          </div>
                          <div>
                            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                              {database.name}
                            </h3>
                            <p className="text-sm text-gray-500 dark:text-gray-400">
                              {database.type}
                            </p>
                          </div>
                        </div>
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(database.status)}`}>
                          {database.status}
                        </span>
                      </div>
                      
                      <div className="space-y-2 mb-4">
                        <div className="flex items-center text-sm text-gray-600 dark:text-gray-400">
                          <RiCalendarLine size={16} className="mr-2" />
                          Created {formatDate(database.created_at)}
                        </div>
                        {database.size && (
                          <div className="flex items-center text-sm text-gray-600 dark:text-gray-400">
                            <RiTableLine size={16} className="mr-2" />
                            {formatFileSize(database.size * 1024)} • {database.tables} table{database.tables !== 1 ? 's' : ''}
                          </div>
                        )}
                      </div>
                      
                      <div className="flex items-center justify-between pt-4 border-t border-gray-200 dark:border-gray-700">
                        <div className="flex space-x-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              handleViewMetadata(database)
                            }}
                            className="p-2 text-gray-600 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
                            title="View Database Schema"
                          >
                            <RiTableLine size={16} />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              navigate('/dashboard')
                            }}
                            className="p-2 text-gray-600 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
                            title="Query Data"
                          >
                            <RiEditLine size={16} />
                          </button>
                          <button
                            onClick={(e) => e.stopPropagation()}
                            className="p-2 text-gray-600 dark:text-gray-400 hover:text-green-600 dark:hover:text-green-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
                            title="Download"
                          >
                            <RiDownloadLine size={16} />
                          </button>
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            // handleDeleteDatabase(database.id, database.name)
                          }}
                          className="p-2 text-gray-600 dark:text-gray-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
                          title="Delete"
                        >
                          <RiDeleteBinLine size={16} />
                        </button>
                      </div>
                    </motion.div>
                                    ))}
                                  </div>
                                )}
            </motion.div>

            {/* Data Source Modal */}
      <AnimatePresence>
        {showDataSourceModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
                  className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
            onClick={() => setShowDataSourceModal(false)}
          >
            <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    className="bg-white dark:bg-dark-900 rounded-xl shadow-2xl max-w-md w-full p-6"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-6">
                      <h3 className="text-xl font-semibold text-gray-900 dark:text-white">Add Database Connection</h3>
                <button
                  onClick={() => setShowDataSourceModal(false)}
                  className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                >
                        <RiCloseLine size={24} />
                </button>
              </div>
              
                  <div className="text-center">
                      <div className="mx-auto w-16 h-16 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center mb-4">
                        <RiDatabaseLine className="w-8 h-8 text-green-600 dark:text-green-400" />
                    </div>
                      <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">Connect Database</h3>
                    <p className="text-gray-600 dark:text-gray-400 mb-4">
                        Connect to your Microsoft SQL Server database for real-time analysis with Windows Authentication.
                      </p>
                      <button
                  onClick={() => {
                    setShowDataSourceModal(false)
                          navigate('/data-source-selection')
                        }}
                        className="w-full bg-primary-600 hover:bg-primary-700 text-white py-2 px-4 rounded-lg font-medium transition-colors"
                      >
                        Connect to SQL Server
                      </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

            {/* Database Metadata Modal */}
            <DatabaseMetadataModal
              isOpen={showMetadataModal}
              onClose={() => {
                setShowMetadataModal(false)
                setSelectedDatabaseForMetadata(null)
              }}
              database={selectedDatabaseForMetadata!}
            />
          </motion.div>
        </div>
      </div>
    </div>
  )
}

export default Databases 
