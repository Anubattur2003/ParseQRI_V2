import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload, Database, FileText, Server, CheckCircle, AlertCircle, Loader } from 'lucide-react'

interface DatabaseConnection {
  server_name: string
  database_name: string
  use_windows_auth: boolean
  description?: string
  db_type: 'mssql'
}

const DataSourceSelection: React.FC = () => {
  const navigate = useNavigate()
  const [selectedOption, setSelectedOption] = useState<'file' | 'database' | null>(null)
  const [showDatabaseForm, setShowDatabaseForm] = useState(false)
  const [isConnecting, setIsConnecting] = useState(false)
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [connectionMessage, setConnectionMessage] = useState('')
  
  const [databaseConfig, setDatabaseConfig] = useState<DatabaseConnection>({
    server_name: '',
    database_name: '',
    use_windows_auth: true,
    description: '',
    db_type: 'mssql'
  })

  const handleOptionSelect = (option: 'file' | 'database') => {
    setSelectedOption(option)
    if (option === 'file') {
      // Store the selection and navigate to dashboard
      localStorage.setItem('dataSource', 'file')
      localStorage.setItem('dataSourceSelected', 'true')
      navigate('/dashboard')
    } else {
      setShowDatabaseForm(true)
    }
  }

  const handleDatabaseConfigChange = (field: keyof DatabaseConnection, value: string | number | boolean) => {
    setDatabaseConfig(prev => ({
      ...prev,
      [field]: value
    }))
  }

  const testConnection = async () => {
    setIsConnecting(true)
    setConnectionStatus('idle')
    
    try {
      const token = localStorage.getItem('token')
      const response = await fetch('/db/test-connection', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(databaseConfig)
      })
      
      const result = await response.json()
      
      if (result.status === 'success') {
        setConnectionStatus('success')
        setConnectionMessage('Connection successful!')
      } else {
        setConnectionStatus('error')
        setConnectionMessage(result.message || 'Connection failed')
      }
    } catch (error: any) {
      console.error('Test connection error:', error)
      
      // Handle server down scenario in development
      if (error.message && error.message.includes('Failed to fetch')) {
        if (window.location.hostname === 'localhost') {
          console.log('Using mock test connection in development mode')
          // Simulate successful connection after a short delay
          setTimeout(() => {
            setConnectionStatus('success')
            setConnectionMessage('Mock connection successful! (Server is offline, using development mode)')
          }, 800)
          return
        }
      }
      
      setConnectionStatus('error')
      setConnectionMessage('Failed to test connection')
    } finally {
      setIsConnecting(false)
    }
  }

  const handleDatabaseConnect = async () => {
    if (connectionStatus !== 'success') {
      await testConnection()
      return
    }

    try {
      const token = localStorage.getItem('token')
      
      // Check if we're in development mode with server down
      const isDevelopment = window.location.hostname === 'localhost'
      const isMockAuth = localStorage.getItem('isMockAuth') === 'true'
      
      let configResult;
      
      if (isMockAuth && isDevelopment) {
        // Use mock data
        configResult = {
          id: 1,
          ...databaseConfig,
          created_at: new Date().toISOString()
        }
        console.log('Using mock database configuration:', configResult)
      } else {
        // Save database configuration
        const configResponse = await fetch('/db/config', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify(databaseConfig)
        })
        
        if (!configResponse.ok) {
          throw new Error('Failed to save database configuration')
        }
        
        configResult = await configResponse.json()
        
        // Extract metadata
        const metadataResponse = await fetch(`/db/extract-metadata/${configResult.id}`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`
          }
        })
        
        if (!metadataResponse.ok) {
          throw new Error('Failed to extract metadata')
        }
      }
      
      // Store the selection and navigate to dashboard
      localStorage.setItem('dataSource', 'database')
      localStorage.setItem('databaseConfigId', configResult.id.toString())
      localStorage.setItem('dataSourceSelected', 'true')
      navigate('/dashboard')
      
    } catch (error: any) {
      console.error('Database connect error:', error)
      
      // Handle server down scenario in development
      if (error.message && (error.message.includes('Failed to fetch') || error.message === 'Network Error')) {
        if (window.location.hostname === 'localhost') {
          console.log('Using mock database connection in development mode')
          
          // Store mock configuration and navigate to dashboard
          localStorage.setItem('dataSource', 'database')
          localStorage.setItem('databaseConfigId', '1')
          localStorage.setItem('dataSourceSelected', 'true')
          navigate('/dashboard')
          return
        }
      }
      
      setConnectionStatus('error')
      setConnectionMessage('Failed to connect and extract metadata')
    }
  }

  // Remove getPortPlaceholder function as it's no longer needed for MSSQL

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 to-primary-100 flex items-center justify-center p-4">
      <div className="max-w-4xl w-full">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">Choose Your Data Source</h1>
          <p className="text-xl text-gray-600">Select how you want to provide your data for analysis</p>
        </div>

        {!showDatabaseForm ? (
          <div className="grid md:grid-cols-2 gap-8">
            {/* File Upload Option - Coming Soon */}
            <div 
              className="bg-white rounded-xl shadow-lg p-8 transition-all duration-300 border-2 border-gray-200 opacity-60 cursor-not-allowed"
              title="CSV upload feature coming soon"
            >
              <div className="text-center">
                <div className="mx-auto w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mb-4">
                  <Upload className="w-8 h-8 text-primary-600" />
                </div>
                <h3 className="text-2xl font-semibold text-gray-900 mb-4">Upload Files</h3>
                <p className="text-gray-600 mb-6">
                  CSV file upload and processing capabilities coming soon! This feature will support automatic schema detection and data analysis.
                </p>
                <div className="flex items-center justify-center space-x-4 text-sm text-gray-500">
                  <div className="flex items-center">
                    <FileText className="w-4 h-4 mr-1" />
                    CSV (Coming Soon)
                  </div>
                  <div className="flex items-center">
                    <AlertCircle className="w-4 h-4 mr-1" />
                    In Development
                  </div>
                </div>
              </div>
            </div>

            {/* Database Connection Option */}
            <div 
              className={`bg-white rounded-xl shadow-lg p-8 cursor-pointer transition-all duration-300 hover:shadow-xl border-2 ${
                selectedOption === 'database' ? 'border-green-500 bg-green-50' : 'border-gray-200 hover:border-green-300'
              }`}
              onClick={() => handleOptionSelect('database')}
            >
              <div className="text-center">
                <div className="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4">
                  <Database className="w-8 h-8 text-green-600" />
                </div>
                <h3 className="text-2xl font-semibold text-gray-900 mb-4">Connect Database</h3>
                <p className="text-gray-600 mb-6">
                  Connect to your Microsoft SQL Server database for real-time analysis with Windows Authentication.
                </p>
                <div className="flex items-center justify-center space-x-4 text-sm text-gray-500">
                  <div className="flex items-center">
                    <Server className="w-4 h-4 mr-1" />
                    SQL Server
                  </div>
                  <div className="flex items-center">
                    <CheckCircle className="w-4 h-4 mr-1" />
                    Windows Auth
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* Database Configuration Form */
          <div className="bg-white rounded-xl shadow-lg p-8 max-w-2xl mx-auto">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-2xl font-semibold text-gray-900">Database Configuration</h3>
              <button
                onClick={() => setShowDatabaseForm(false)}
                className="text-gray-500 hover:text-gray-700"
              >
                ✕
              </button>
            </div>

            <div className="space-y-6">
              {/* Database Type */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Database Type
                </label>
                <select
                  value={databaseConfig.db_type}
                  disabled
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 bg-gray-50"
                >
                  <option value="mssql">Microsoft SQL Server</option>
                </select>
              </div>

              {/* Server Name and Database Name */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Server Name
                  </label>
                  <input
                    type="text"
                    value={databaseConfig.server_name}
                    onChange={(e) => handleDatabaseConfigChange('server_name', e.target.value)}
                    placeholder="C2C-LP-25-012"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Database Name
                  </label>
                  <input
                    type="text"
                    value={databaseConfig.database_name}
                    onChange={(e) => handleDatabaseConfigChange('database_name', e.target.value)}
                    placeholder="INSMA"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>
              </div>

              {/* Windows Authentication */}
              <div>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={databaseConfig.use_windows_auth}
                    onChange={(e) => handleDatabaseConfigChange('use_windows_auth', e.target.checked)}
                    className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                  />
                  <span className="text-sm font-medium text-gray-700">
                    Use Windows Authentication (Recommended)
                  </span>
                </label>
                <p className="text-xs text-gray-500 mt-1">
                  Windows Authentication provides secure, single sign-on access to SQL Server
                </p>
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Description (Optional)
                </label>
                <input
                  type="text"
                  value={databaseConfig.description || ''}
                  onChange={(e) => handleDatabaseConfigChange('description', e.target.value)}
                  placeholder="Production database for equipment management"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>

              {/* Connection Status */}
              {connectionStatus !== 'idle' && (
                <div className={`p-4 rounded-md flex items-center ${
                  connectionStatus === 'success' 
                    ? 'bg-green-50 text-green-800' 
                    : 'bg-red-50 text-red-800'
                }`}>
                  {connectionStatus === 'success' ? (
                    <CheckCircle className="w-5 h-5 mr-2" />
                  ) : (
                    <AlertCircle className="w-5 h-5 mr-2" />
                  )}
                  {connectionMessage}
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex space-x-4">
                <button
                  onClick={testConnection}
                  disabled={isConnecting}
                  className="flex-1 bg-primary-600 text-white py-2 px-4 rounded-md hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
                >
                  {isConnecting ? (
                    <>
                      <Loader className="w-4 h-4 mr-2 animate-spin" />
                      Testing...
                    </>
                  ) : (
                    'Test Connection'
                  )}
                </button>
                
                {connectionStatus === 'success' && (
                  <button
                    onClick={handleDatabaseConnect}
                    className="flex-1 bg-green-600 text-white py-2 px-4 rounded-md hover:bg-green-700 flex items-center justify-center"
                  >
                    Connect & Continue
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default DataSourceSelection 