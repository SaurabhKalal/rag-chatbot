import React, { useState, useEffect } from 'react';
import { User, Shield, Send, Upload, Globe, MessageCircle, FileText, Sparkles, Brain, Zap, Star, AlertCircle, CheckCircle, Lock, ArrowRight, Eye, EyeOff } from 'lucide-react';

export default function DualInterface() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [loginType, setLoginType] = useState(''); // 'user' or 'admin'
  const [showLoginForm, setShowLoginForm] = useState(false);
  const [loginData, setLoginData] = useState({ sessionId: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [loginError, setLoginError] = useState('');
  
  const [selectedRole, setSelectedRole] = useState('');
  const [query, setQuery] = useState('');
  const [answer, setAnswer] = useState('');
  const [webUrl, setWebUrl] = useState('');
  const [uploadedFile, setUploadedFile] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const [sessionId, setSessionId] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [processingStatus, setProcessingStatus] = useState([]);
  const [showNextSteps, setShowNextSteps] = useState(false);
  const [sessionMode, setSessionMode] = useState(''); // 'new' or 'existing'
  const [availableNamespaces, setAvailableNamespaces] = useState([]);
  const [selectedNamespace, setSelectedNamespace] = useState('');
  const [newSessionName, setNewSessionName] = useState('');

  // API base URL - update this to match your FastAPI server
  // const API_BASE_URL = 'http://127.0.0.1:8000';    // main API_BASE_URL
  const API_BASE_URL = 'https://bz65xp3b-8000.inc1.devtunnels.ms';  // temp API_BASE_URL
  
  // const TEMP_URL = "chat_legal"
  const TEMP_URL = "query"

  const generateSessionId = () => {
    const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    setSessionId(newSessionId);
    resetForm();
  };

  // Test API connection
  const testConnection = async () => {
    try {
      console.log('Testing connection to:', `${API_BASE_URL}/health`);
      const response = await fetch(`${API_BASE_URL}/health`, {
        method: 'GET',
        mode: 'cors',
      });
      console.log('Connection test result:', response.status, response.ok);
      if (response.ok) {
        const data = await response.json();
        console.log('Health check response:', data);
        setSuccess('✅ Connection to backend successful!');
        setTimeout(() => setSuccess(''), 3000);
      } else {
        setError('❌ Backend is running but not responding correctly');
      }
    } catch (err) {
      console.error('Connection test failed:', err);
      setError('❌ Cannot connect to backend. Make sure it is running on http://127.0.0.1:8000');
    }
  };

  // Fetch available namespaces for admin
  const fetchNamespaces = async () => {
    try {
      console.log('Fetching namespaces from:', `${API_BASE_URL}/namespaces`);
      const response = await fetch(`${API_BASE_URL}/namespaces`, {
        method: 'GET',
        mode: 'cors',
      });
      
      if (response.ok) {
        const data = await response.json();
        console.log('Available namespaces:', data.namespaces);
        setAvailableNamespaces(data.namespaces || []);
      } else {
        console.error('Failed to fetch namespaces');
        setAvailableNamespaces([]);
      }
    } catch (err) {
      console.error('Error fetching namespaces:', err);
      setAvailableNamespaces([]);
    }
  };

  // Generate new session ID
  const generateNewSessionId = () => {
    const timestamp = Date.now().toString(36);
    const random = Math.random().toString(36).substr(2, 5);
    return `${timestamp}_${random}`;
  };

  // Handle session mode change
  const handleSessionModeChange = (mode) => {
    setSessionMode(mode);
    if (mode === 'existing') {
      fetchNamespaces();
    } else if (mode === 'new') {
      const newId = generateNewSessionId();
      setNewSessionName(newId);
    }
  };

  useEffect(() => {
    console.log('API_BASE_URL:', API_BASE_URL);
    const handleMouseMove = (e) => {
      setMousePosition({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  const handlePortalChoice = (type) => {
    setLoginType(type);
    if (type === 'admin') {
      // Admin gets direct access - NO default session ID
      setSelectedRole('admin');
      setIsLoggedIn(true);
      // Initialize admin form state
      setSessionMode('');
      setSelectedNamespace('');
      setNewSessionName('');
      setAvailableNamespaces([]);
      // Don't set any default sessionId for admin!
    } else {
      // User needs to provide session_id and password
      setShowLoginForm(true);
    }
    setLoginError('');
  };

  const handleUserLogin = async () => {
    // Simple password validation (default = "password")
    if (loginData.password !== 'password') {
      setLoginError('Invalid password. Default password is "password".');
      return;
    }
    
    if (!loginData.sessionId.trim()) {
      setLoginError('Please enter a session ID.');
      return;
    }
    
    // Start validation process
    setIsLoading(true);
    setLoginError('');
    
    try {
      console.log('Validating session:', loginData.sessionId);
      
      // Call backend to validate session
      const response = await fetch(`${API_BASE_URL}/validate-session`, {
        method: 'POST',
        mode: 'cors',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: loginData.sessionId.trim()
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      console.log('Session validation response:', data);

      if (data.valid) {
        // Session exists - proceed with login
        console.log(`✅ Session validated: ${data.session_id} with ${data.vector_count} documents`);
        setSessionId(loginData.sessionId.trim());
        setSelectedRole('user');
        setIsLoggedIn(true);
        setShowLoginForm(false);
        setLoginError('');
        setSuccess(`Welcome! Session "${data.session_id}" loaded with ${data.vector_count} documents.`);
        setTimeout(() => setSuccess(''), 5000);
      } else {
        // Session doesn't exist or is empty
        console.log('❌ Session validation failed:', data.error);
        setLoginError(data.error || 'Session not found');
      }
      
    } catch (err) {
      console.error('Session validation error:', err);
      if (err.name === 'TypeError' && err.message.includes('fetch')) {
        setLoginError('Cannot connect to server. Please make sure the backend is running.');
      } else {
        setLoginError('Failed to validate session. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = () => {
    setIsLoggedIn(false);
    setShowLoginForm(false);
    setLoginType('');
    setSelectedRole('');
    setLoginData({ sessionId: '', password: '' });
    setSessionId('');
    setSuccess(''); // Clear success messages
    resetForm();
  };

  const handleGetAnswer = async () => {
    if (!query.trim()) return;
    
    setIsLoading(true);
    setError('');
    setAnswer('');
    
    try {
      console.log('Making query request to:', `${API_BASE_URL}/${TEMP_URL}`);
      
      // For admin: use special session_id to access all namespaces
      // For user: use their specific session_id
      const querySessionId = loginType === 'admin' ? '*' : sessionId;
      
      console.log('Query data:', { 
        question: query, 
        session_id: querySessionId,
        is_admin: loginType === 'admin'
      });

      const response = await fetch(`${API_BASE_URL}/${TEMP_URL}`, {
        method: 'POST',
        mode: 'cors',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question: query,
          session_id: querySessionId,
          is_admin: loginType === 'admin' // Send admin flag to backend
        })
      });

      console.log('Query response status:', response.status);
      console.log('Query response ok:', response.ok);

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Query error response:', errorText);
        throw new Error(`HTTP error! status: ${response.status} - ${errorText}`);
      }

      const data = await response.json();
      console.log('Query success response:', data);

      setAnswer(data.answer);
      
    } catch (err) {
      console.error('Query error:', err);
      if (err.name === 'TypeError' && err.message.includes('fetch')) {
        setError('Cannot connect to server. Please make sure the backend is running and CORS is enabled.');
      } else {
        setError(err.message || 'Failed to get answer. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  // FIXED: Updated handleAdminSubmit function
  const handleAdminSubmit = async () => {
    if (!webUrl.trim() && !uploadedFile) {
      setError('Please provide either a URL or upload a document.');
      return;
    }
    
    // FIX: Determine the correct session ID based on user selection
    let targetSessionId;
    if (sessionMode === 'new') {
      targetSessionId = newSessionName.trim();
    } else if (sessionMode === 'existing') {
      targetSessionId = selectedNamespace;
    } else {
      setError('Please select a session mode and provide session details.');
      return;
    }
    
    if (!targetSessionId) {
      setError('Please provide a valid session ID.');
      return;
    }
    
    setIsLoading(true);
    setError('');
    setSuccess('');
    setProcessingStatus([]);
    setShowNextSteps(false);
    
    try {
      const formData = new FormData();
      
      if (webUrl.trim()) {
        formData.append('url', webUrl);
      }
      
      if (uploadedFile) {
        formData.append('file', uploadedFile);
      }
      
      // FIX: Use the correct session ID
      formData.append('session_id', targetSessionId);

      console.log('Making request to:', `${API_BASE_URL}/process`);
      console.log('Target Session ID:', targetSessionId); // Updated log
      console.log('URL:', webUrl);
      console.log('File:', uploadedFile?.name);

      const response = await fetch(`${API_BASE_URL}/process`, {
        method: 'POST',
        mode: 'cors',
        body: formData
      });

      console.log('Response status:', response.status);
      console.log('Response ok:', response.ok);

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Error response:', errorText);
        throw new Error(`HTTP error! status: ${response.status} - ${errorText}`);
      }

      const data = await response.json();
      console.log('Success response:', data);

      setSuccess(data.status);
      setProcessingStatus(data.processing_details || []);
      
      // FIX: Update the sessionId state for subsequent operations
      setSessionId(targetSessionId);
      
      // Clear form on success
      setWebUrl('');
      setUploadedFile(null);
      
      // Show next steps options
      setTimeout(() => {
        setShowNextSteps(true);
      }, 2000);
      
    } catch (err) {
      console.error('Processing error:', err);
      if (err.name === 'TypeError' && err.message.includes('fetch')) {
        setError('Cannot connect to server. Please make sure the backend is running on http://127.0.0.1:8000 and CORS is enabled.');
      } else {
        setError(err.message || 'Failed to process sources. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  // FIXED: Updated handleChatWithDocument
  const handleChatWithDocument = () => {
    // Ensure sessionId is set correctly before switching to user mode
    let targetSessionId;
    if (sessionMode === 'new') {
      targetSessionId = newSessionName.trim();
    } else if (sessionMode === 'existing') {
      targetSessionId = selectedNamespace;
    }
    
    if (targetSessionId && targetSessionId !== sessionId) {
      setSessionId(targetSessionId);
    }
    
    setSelectedRole('user');
    setShowNextSteps(false);
    setSuccess('Content processed successfully! You can now ask questions about it.');
    setError('');
    setProcessingStatus([]);
  };

  const handleUploadNewDocument = () => {
    setShowNextSteps(false);
    setSuccess('');
    setError('');
    setProcessingStatus([]);
    // Reset session selection for new upload
    setSessionMode('');
    setSelectedNamespace('');
    setNewSessionName('');
    setAvailableNamespaces([]);
    setWebUrl('');
    setUploadedFile(null);
    // Stay in admin mode for new upload
  };

  const switchToAdmin = () => {
    // Only allow admin switching if user logged in as admin
    if (loginType === 'admin') {
      setSelectedRole('admin');
      setError('');
      setSuccess('');
      setAnswer('');
      setQuery('');
      // Reset admin form state
      setSessionMode('');
      setSelectedNamespace('');
      setNewSessionName('');
      setWebUrl('');
      setUploadedFile(null);
      setShowNextSteps(false);
    }
  };

  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (file && !file.type.includes('pdf')) {
      setError('Please upload only PDF files.');
      return;
    }
    setUploadedFile(file);
    setError('');
  };

  const resetForm = () => {
    setQuery('');
    setAnswer('');
    setWebUrl('');
    setUploadedFile(null);
    setError('');
    setSuccess('');
    setProcessingStatus([]);
    setShowNextSteps(false);
    setSessionMode('');
    setSelectedNamespace('');
    setNewSessionName('');
    setAvailableNamespaces([]);
  };

  // ADDED: Submit validation function
  const isSubmitDisabled = () => {
    const hasContent = webUrl.trim() || uploadedFile;
    const hasValidSession = sessionMode && 
      ((sessionMode === 'new' && newSessionName.trim()) || 
       (sessionMode === 'existing' && selectedNamespace));
    
    return !hasContent || !hasValidSession || isLoading;
  };

  // ADDED: SessionInfo component
  const SessionInfo = () => {
    const currentSession = sessionMode === 'new' ? newSessionName : selectedNamespace;
    const sessionType = sessionMode === 'new' ? 'New Session' : 'Existing Session';
    
    if (!sessionMode || !currentSession) return null;
    
    return (
      <div className="bg-gradient-to-r from-emerald-500/20 to-cyan-500/20 backdrop-blur-sm border border-emerald-400/30 rounded-2xl p-4 mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-lg">
            <CheckCircle className="w-5 h-5 text-white" />
          </div>
          <div>
            <p className="text-emerald-300 font-semibold">
              {sessionType}: {currentSession}
            </p>
            <p className="text-emerald-200 text-sm">
              Documents will be {sessionMode === 'new' ? 'stored in new namespace' : 'added to existing namespace'}
            </p>
          </div>
        </div>
      </div>
    );
  };

  // Login Page Component
  if (!isLoggedIn) {
    return (
      <div className="min-h-screen relative overflow-hidden" style={{background: 'linear-gradient(to bottom right, #1a1f3a, #171d1e, #000000)'}}>
        {/* Animated Background Elements */}
        <div className="absolute inset-0">
          <div className="absolute top-0 left-0 w-full h-full" style={{background: 'linear-gradient(to bottom right, rgba(59, 130, 246, 0.1), rgba(139, 92, 246, 0.1), rgba(0, 0, 0, 0.3))'}}></div>
          <div 
            className="absolute w-96 h-96 bg-gradient-to-r from-cyan-400/30 to-blue-500/30 rounded-full blur-3xl animate-pulse"
            style={{
              left: mousePosition.x / 10 + 'px',
              top: mousePosition.y / 10 + 'px',
            }}
          ></div>
          <div className="absolute top-1/4 right-1/4 w-64 h-64 bg-gradient-to-r from-purple-400/20 to-pink-500/20 rounded-full blur-2xl animate-bounce"></div>
          <div className="absolute bottom-1/4 left-1/3 w-80 h-80 bg-gradient-to-r from-emerald-400/20 to-cyan-500/20 rounded-full blur-3xl animate-pulse delay-1000"></div>
        </div>

        {/* Floating Particles */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          {[...Array(20)].map((_, i) => (
            <div
              key={i}
              className="absolute w-2 h-2 bg-white/20 rounded-full animate-ping"
              style={{
                left: Math.random() * 100 + '%',
                top: Math.random() * 100 + '%',
                animationDelay: Math.random() * 3 + 's',
                animationDuration: (Math.random() * 3 + 2) + 's'
              }}
            ></div>
          ))}
        </div>

        <div className="relative z-10 min-h-screen flex items-center justify-center p-6">
          <div className="w-full max-w-4xl">
            {/* Header */}
            <div className="text-center mb-12">
              <div className="flex justify-center items-center gap-3 mb-4">
                <h1 className="text-4xl font-black bg-gradient-to-r from-cyan-400 via-blue-400 to-purple-400 bg-clip-text text-transparent">
                  RAG Chatbot Assistant   
                </h1>
              </div>
            </div>

            {!showLoginForm ? (
              /* Portal Selection */
              <div className="backdrop-blur-xl bg-white/10 rounded-3xl shadow-2xl border border-white/20 p-8 animate-in slide-in-from-bottom-6 duration-700">
                <div className="text-center mb-8">
                  <div className="p-4 bg-gradient-to-r from-yellow-400 to-orange-500 rounded-2xl w-fit mx-auto mb-4">
                    <Lock className="w-8 h-8 text-white" />
                  </div>
                  <h2 className="text-3xl font-bold text-white mb-2">Choose Your Portal</h2>
                  <p className="text-gray-300">Select your access level to continue</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                  {/* User Portal */}
                  <button
                    onClick={() => handlePortalChoice('user')}
                    className="group relative overflow-hidden p-8 rounded-2xl border-2 border-white/20 hover:border-cyan-400/50 bg-white/5 hover:bg-white/10 transition-all duration-500 transform hover:scale-105"
                  >
                    <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/10 to-blue-600/10 opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
                    <div className="relative text-center">
                      <div className="p-6 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-3xl shadow-lg group-hover:shadow-cyan-500/50 transition-shadow duration-300 w-fit mx-auto mb-4">
                        <User className="w-12 h-12 text-white" />
                      </div>
                      <h3 className="text-2xl font-bold text-white mb-2">User Portal</h3>
                      <p className="text-cyan-300 mb-4">Ask questions and get intelligent answers</p>
                      <div className="flex items-center justify-center gap-2 text-sm text-gray-400 mb-4">
                        <Lock className="w-4 h-4" />
                        <span>Requires Session ID & Password</span>
                      </div>
                      <div className="flex items-center justify-center gap-2 text-cyan-400">
                        <span>Continue</span>
                        <ArrowRight className="w-5 h-5" />
                      </div>
                    </div>
                  </button>

                  {/* Admin Portal */}
                  <button
                    onClick={() => handlePortalChoice('admin')}
                    className="group relative overflow-hidden p-8 rounded-2xl border-2 border-white/20 hover:border-purple-400/50 bg-white/5 hover:bg-white/10 transition-all duration-500 transform hover:scale-105"
                  >
                    <div className="absolute inset-0 bg-gradient-to-br from-purple-500/10 to-pink-600/10 opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
                    <div className="relative text-center">
                      <div className="p-6 bg-gradient-to-r from-purple-500 to-pink-500 rounded-3xl shadow-lg group-hover:shadow-purple-500/50 transition-shadow duration-300 w-fit mx-auto mb-4">
                        <Shield className="w-12 h-12 text-white" />
                      </div>
                      <h3 className="text-2xl font-bold text-white mb-2">Admin Console</h3>
                      <p className="text-purple-300 mb-4">Manage content and upload documents</p>
                      <div className="flex items-center justify-center gap-2 text-sm text-gray-400 mb-4">
                        <Zap className="w-4 h-4" />
                        <span>Direct Access</span>
                      </div>
                      <div className="flex items-center justify-center gap-2 text-purple-400">
                        <span>Enter</span>
                        <ArrowRight className="w-5 h-5" />
                      </div>
                    </div>
                  </button>
                </div>
              </div>
            ) : (
              /* User Login Form */
              <div className="backdrop-blur-xl bg-white/10 rounded-3xl shadow-2xl border border-white/20 p-8 animate-in slide-in-from-bottom-6 duration-700">
                <div className="text-center mb-8">
                  <div className="p-4 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-2xl w-fit mx-auto mb-4">
                    <User className="w-8 h-8 text-white" />
                  </div>
                  <h2 className="text-3xl font-bold text-white mb-2">User Portal Login</h2>
                  <p className="text-cyan-300">Enter your credentials to access the AI Query Interface</p>
                </div>

                {loginError && (
                  <div className="mb-6 p-4 bg-red-500/20 border border-red-500/50 rounded-2xl flex items-center gap-3">
                    <AlertCircle className="w-5 h-5 text-red-400" />
                    <span className="text-red-200">{loginError}</span>
                  </div>
                )}

                {success && (
                  <div className="mb-6 p-4 bg-green-500/20 border border-green-500/50 rounded-2xl flex items-center gap-3">
                    <CheckCircle className="w-5 h-5 text-green-400" />
                    <span className="text-green-200">{success}</span>
                  </div>
                )}

                <div className="space-y-6 max-w-md mx-auto">
                  {/* Session ID Input */}
                  <div>
                    <label className="block text-lg font-semibold text-white mb-3 flex items-center gap-2">
                      <Brain className="w-5 h-5 text-cyan-400" />
                      Session ID
                    </label>
                    <input
                      type="text"
                      value={loginData.sessionId}
                      onChange={(e) => setLoginData({...loginData, sessionId: e.target.value})}
                      placeholder="Enter your session ID"
                      className="w-full p-4 bg-white/10 backdrop-blur-sm border border-white/20 rounded-xl focus:ring-4 focus:ring-cyan-500/50 focus:border-cyan-400 transition-all duration-300 text-white placeholder-gray-400 text-lg"
                      disabled={isLoading}
                    />
                    <p className="text-sm text-gray-400 mt-2">
                      Session ID must exist with processed documents. Contact admin if you need access to a session.
                    </p>
                  </div>

                  {/* Password Input */}
                  <div>
                    <label className="block text-lg font-semibold text-white mb-3 flex items-center gap-2">
                      <Lock className="w-5 h-5 text-cyan-400" />
                      Password
                    </label>
                    <div className="relative">
                      <input
                        type={showPassword ? "text" : "password"}
                        value={loginData.password}
                        onChange={(e) => setLoginData({...loginData, password: e.target.value})}
                        placeholder="Default: password"
                        className="w-full p-4 bg-white/10 backdrop-blur-sm border border-white/20 rounded-xl focus:ring-4 focus:ring-cyan-500/50 focus:border-cyan-400 transition-all duration-300 text-white placeholder-gray-400 text-lg pr-12"
                        disabled={isLoading}
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-4 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-white transition-colors"
                      >
                        {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                      </button>
                    </div>
                    <p className="text-sm text-gray-400 mt-2">Default password is "password"</p>
                  </div>

                  {/* Login Button */}
                  <button
                    onClick={handleUserLogin}
                    disabled={!loginData.sessionId.trim() || !loginData.password.trim() || isLoading}
                    className="w-full bg-gradient-to-r from-cyan-500 via-blue-500 to-purple-500 text-white py-4 px-8 rounded-2xl font-bold text-lg flex items-center justify-center gap-3 hover:from-cyan-400 hover:via-blue-400 hover:to-purple-400 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300 transform hover:scale-105 shadow-2xl hover:shadow-cyan-500/50"
                  >
                    {isLoading ? (
                      <>
                        <div className="w-6 h-6 border-3 border-white border-t-transparent rounded-full animate-spin"></div>
                        <span>Validating Session...</span>
                      </>
                    ) : (
                      <>
                        <Lock className="w-6 h-6" />
                        <span>Access Portal</span>
                        <ArrowRight className="w-6 h-6" />
                      </>
                    )}
                  </button>

                  {/* Back Button */}
                  <button
                    onClick={() => setShowLoginForm(false)}
                    disabled={isLoading}
                    className="w-full bg-white/10 hover:bg-white/20 text-white py-3 px-6 rounded-xl font-medium transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    ← Back to Portal Selection
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Main Application (after login)
  return (
    <div className="min-h-screen relative overflow-hidden" style={{background: 'linear-gradient(to bottom right, #1a1f3a, #171d1e, #000000)'}}>
      {/* Animated Background Elements */}
      <div className="absolute inset-0">
        <div className="absolute top-0 left-0 w-full h-full" style={{background: 'linear-gradient(to bottom right, rgba(59, 130, 246, 0.1), rgba(139, 92, 246, 0.1), rgba(0, 0, 0, 0.3))'}}></div>
        <div 
          className="absolute w-96 h-96 bg-gradient-to-r from-cyan-400/30 to-blue-500/30 rounded-full blur-3xl animate-pulse"
          style={{
            left: mousePosition.x / 10 + 'px',
            top: mousePosition.y / 10 + 'px',
          }}
        ></div>
        <div className="absolute top-1/4 right-1/4 w-64 h-64 bg-gradient-to-r from-purple-400/20 to-pink-500/20 rounded-full blur-2xl animate-bounce"></div>
        <div className="absolute bottom-1/4 left-1/3 w-80 h-80 bg-gradient-to-r from-emerald-400/20 to-cyan-500/20 rounded-full blur-3xl animate-pulse delay-1000"></div>
      </div>

      {/* Floating Particles */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {[...Array(20)].map((_, i) => (
          <div
            key={i}
            className="absolute w-2 h-2 bg-white/20 rounded-full animate-ping"
            style={{
              left: Math.random() * 100 + '%',
              top: Math.random() * 100 + '%',
              animationDelay: Math.random() * 3 + 's',
              animationDuration: (Math.random() * 3 + 2) + 's'
            }}
          ></div>
        ))}
      </div>

      <div className="relative z-10 min-h-screen p-6">
        <div className="max-w-5xl mx-auto">
          {/* Header with Logout */}
          <div className="text-center mb-8">
            <div className="flex justify-between items-center mb-4">
              <div></div>
              <div className="flex justify-center items-center gap-3">
                <div className="p-3 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-2xl shadow-lg">
                  <Brain className="w-8 h-8 text-white" />
                </div>
                <h1 className="text-6xl font-black bg-gradient-to-r from-cyan-400 via-blue-400 to-purple-400 bg-clip-text text-transparent">
                  NeuroPortal
                </h1>
                <div className="p-3 bg-gradient-to-r from-purple-500 to-pink-500 rounded-2xl shadow-lg">
                  <Sparkles className="w-8 h-8 text-white animate-spin" />
                </div>
              </div>
              <button
                onClick={handleLogout}
                className="bg-red-500/20 hover:bg-red-500/30 text-red-300 px-4 py-2 rounded-xl border border-red-500/50 transition-all duration-300"
              >
                Logout
              </button>
            </div>
            <p className="text-xl text-gray-300 font-medium mb-2">
              {selectedRole === 'user' ? 'AI Query Interface' : 'Admin Control Center'}
            </p>
            <p className="text-cyan-400">
              {selectedRole === 'user' ? 'Get intelligent answers to your questions' : 'Process content and resources for AI training'}
            </p>
            
            {/* UPDATED: Session Info */}
            <div className="mt-4 flex justify-center items-center gap-4">
              <div className="text-sm text-gray-400">
                Session: <span className="text-cyan-400 font-mono">
                  {selectedRole === 'admin' 
                    ? (sessionMode === 'new' 
                        ? newSessionName || 'Not selected' 
                        : selectedNamespace || 'Not selected')
                    : sessionId
                  }
                </span>
              </div>
              <div className="text-sm">
                <span className={selectedRole === 'user' ? 'text-cyan-400' : 'text-purple-400'}>
                  {selectedRole === 'user' ? '👤 User Portal' : '🛡️ Admin Console'}
                </span>
              </div>
            </div>
          </div>

          {/* Error/Success Messages */}
          {error && (
            <div className="mb-6 p-4 bg-red-500/20 border border-red-500/50 rounded-2xl flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-red-400" />
              <span className="text-red-200">{error}</span>
            </div>
          )}
          
          {success && (
            <div className="mb-6 p-4 bg-green-500/20 border border-green-500/50 rounded-2xl flex items-center gap-3">
              <CheckCircle className="w-5 h-5 text-green-400" />
              <span className="text-green-200">{success}</span>
            </div>
          )}

          {/* User Interface */}
          {selectedRole === 'user' && (
            <div className="backdrop-blur-xl bg-white/10 rounded-3xl shadow-2xl border border-white/20 p-8 animate-in slide-in-from-bottom-6 duration-700">
              <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-4">
                  <div className="p-3 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-2xl shadow-lg">
                    <MessageCircle className="w-8 h-8 text-white" />
                  </div>
                  <div>
                    <h2 className="text-3xl font-bold text-white">AI Query Interface</h2>
                    <p className="text-cyan-300">Get intelligent answers to your questions</p>
                  </div>
                </div>
                
                {/* Upload New Document Button - Only for Admin login type */}
                {loginType === 'admin' && (
                  <button
                    onClick={switchToAdmin}
                    className="flex items-center gap-2 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-400 hover:to-pink-400 text-white px-4 py-2 rounded-xl font-semibold transition-all duration-300 transform hover:scale-105 shadow-lg"
                  >
                    <Upload className="w-5 h-5" />
                    <span>Upload New Document</span>
                  </button>
                )}
              </div>
              
              <div className="space-y-6">
                <div className="relative">
                  <label className="block text-lg font-semibold text-white mb-3 flex items-center gap-2">
                    <Brain className="w-5 h-5 text-cyan-400" />
                    Your Question
                  </label>
                  <textarea
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder={loginType === 'admin' 
                      ? "Ask anything about ALL processed documents across all sessions... 🔍 (Global Search)" 
                      : "Ask me anything about the processed documents... 🤖"
                    }
                    className="w-full p-6 bg-white/10 backdrop-blur-sm border border-white/20 rounded-2xl focus:ring-4 focus:ring-cyan-500/50 focus:border-cyan-400 resize-none h-40 transition-all duration-300 text-white placeholder-gray-400 text-lg"
                    disabled={isLoading}
                  />
                  <div className="absolute bottom-4 right-4 text-sm text-gray-400">
                    {query.length}/500
                  </div>
                </div>
                
                <button
                  onClick={handleGetAnswer}
                  disabled={!query.trim() || isLoading}
                  className="w-full bg-gradient-to-r from-cyan-500 via-blue-500 to-purple-500 text-white py-4 px-8 rounded-2xl font-bold text-lg flex items-center justify-center gap-3 hover:from-cyan-400 hover:via-blue-400 hover:to-purple-400 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300 transform hover:scale-105 shadow-2xl hover:shadow-cyan-500/50"
                >
                  {isLoading ? (
                    <>
                      <div className="w-6 h-6 border-3 border-white border-t-transparent rounded-full animate-spin"></div>
                      <span>Processing your question...</span>
                    </>
                  ) : (
                    <>
                      <Send className="w-6 h-6" />
                      <span>Get Intelligent Answer</span>
                      <Sparkles className="w-6 h-6" />
                    </>
                  )}
                </button>
                
                {answer && (
                  <div className="relative overflow-hidden bg-gradient-to-r from-emerald-500/20 to-cyan-500/20 rounded-2xl border border-emerald-400/30 p-6 animate-in slide-in-from-bottom-4 duration-500">
                    <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-emerald-400 to-cyan-400"></div>
                    <div className="flex items-center gap-3 mb-4">
                      <div className="p-2 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-xl">
                        <Brain className="w-5 h-5 text-white" />
                      </div>
                      <h3 className="text-xl font-bold text-white">AI Response</h3>
                      <div className="flex gap-1">
                        {[...Array(5)].map((_, i) => (
                          <Star key={i} className="w-4 h-4 text-yellow-400 fill-current" />
                        ))}
                      </div>
                    </div>
                    <p className="text-gray-200 leading-relaxed text-lg whitespace-pre-wrap">{answer}</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Admin Interface */}
          {selectedRole === 'admin' && (
            <div className="backdrop-blur-xl bg-white/10 rounded-3xl shadow-2xl border border-white/20 p-8 animate-in slide-in-from-bottom-6 duration-700">
              <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-4">
                  <div className="p-3 bg-gradient-to-r from-purple-500 to-pink-500 rounded-2xl shadow-lg">
                    <Shield className="w-8 h-8 text-white" />
                  </div>
                  <div>
                    <h2 className="text-3xl font-bold text-white">Admin Control Center</h2>
                    <p className="text-purple-300">Process content and resources for AI training</p>
                  </div>
                </div>
                
                {/* Go to Chat Button */}
                <button
                  onClick={() => setSelectedRole('user')}
                  className="flex items-center gap-2 bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-400 hover:to-blue-400 text-white px-4 py-2 rounded-xl font-semibold transition-all duration-300 transform hover:scale-105 shadow-lg"
                >
                  <MessageCircle className="w-5 h-5" />
                  <span>Go to Chat</span>
                </button>
              </div>
              
              <div className="space-y-8">
                {/* Session ID Selection - Show when not showing next steps */}
                {!showNextSteps && (
                  <div className="relative overflow-hidden bg-white/5 backdrop-blur-sm border border-white/20 rounded-2xl p-6 hover:bg-white/10 transition-all duration-300">
                    <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-yellow-400 to-orange-400"></div>
                    <label className="block text-lg font-semibold text-white mb-4 flex items-center gap-3">
                      <div className="p-2 bg-gradient-to-r from-yellow-500 to-orange-500 rounded-xl">
                        <Star className="w-5 h-5 text-white" />
                      </div>
                      Session ID Selection
                    </label>
                    
                    <div className="space-y-4">
                      {/* Session Mode Selection */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <button
                          onClick={() => handleSessionModeChange('new')}
                          disabled={isLoading}
                          className={`p-4 rounded-xl border-2 transition-all duration-300 ${
                            sessionMode === 'new'
                              ? 'border-emerald-400 bg-emerald-500/20 text-emerald-300'
                              : 'border-white/20 hover:border-emerald-400/50 text-gray-300 hover:text-white'
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <div className="p-2 bg-gradient-to-r from-emerald-500 to-green-500 rounded-lg">
                              <Sparkles className="w-5 h-5 text-white" />
                            </div>
                            <div className="text-left">
                              <div className="font-semibold">Create New Session</div>
                              <div className="text-sm opacity-75">Generate a new namespace</div>
                            </div>
                          </div>
                        </button>
                        
                        <button
                          onClick={() => handleSessionModeChange('existing')}
                          disabled={isLoading}
                          className={`p-4 rounded-xl border-2 transition-all duration-300 ${
                            sessionMode === 'existing'
                              ? 'border-blue-400 bg-blue-500/20 text-blue-300'
                              : 'border-white/20 hover:border-blue-400/50 text-gray-300 hover:text-white'
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <div className="p-2 bg-gradient-to-r from-blue-500 to-cyan-500 rounded-lg">
                              <FileText className="w-5 h-5 text-white" />
                            </div>
                            <div className="text-left">
                              <div className="font-semibold">Use Existing Session</div>
                              <div className="text-sm opacity-75">Select from existing namespaces</div>
                            </div>
                          </div>
                        </button>
                      </div>
                      
                      {/* New Session Input */}
                      {sessionMode === 'new' && (
                        <div className="animate-in slide-in-from-bottom-2 duration-300">
                          <label className="block text-sm font-medium text-gray-300 mb-2">
                            New Session Name
                          </label>
                          <input
                            type="text"
                            value={newSessionName}
                            onChange={(e) => setNewSessionName(e.target.value)}
                            placeholder="Enter session name or use generated ID"
                            className="w-full p-3 bg-white/10 backdrop-blur-sm border border-white/20 rounded-lg focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-400 transition-all duration-300 text-white placeholder-gray-400"
                            disabled={isLoading}
                          />
                        </div>
                      )}
                      
                      {/* Existing Session Dropdown */}
                      {sessionMode === 'existing' && (
                        <div className="animate-in slide-in-from-bottom-2 duration-300">
                          <label className="block text-sm font-medium text-gray-300 mb-2">
                            Select Existing Namespace
                          </label>
                          <select
                            value={selectedNamespace}
                            onChange={(e) => setSelectedNamespace(e.target.value)}
                            className="w-full p-3 bg-white/10 backdrop-blur-sm border border-white/20 rounded-lg focus:ring-2 focus:ring-blue-500/50 focus:border-blue-400 transition-all duration-300 text-white"
                            disabled={isLoading}
                          >
                            <option value="" className="bg-gray-800">Select a namespace...</option>
                            {availableNamespaces.map((namespace) => (
                              <option key={namespace} value={namespace} className="bg-gray-800">
                                {namespace}
                              </option>
                            ))}
                          </select>
                          {availableNamespaces.length === 0 && (
                            <p className="text-sm text-gray-400 mt-2">
                              Loading namespaces... If empty, no documents have been processed yet.
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* UPDATED: Selected Session Display */}
                <SessionInfo />

                {/* Web URL Section - Only show after session is selected */}
                {!showNextSteps && sessionMode && ((sessionMode === 'new' && newSessionName.trim()) || (sessionMode === 'existing' && selectedNamespace)) && (
                  <div className="relative overflow-hidden bg-white/5 backdrop-blur-sm border border-white/20 rounded-2xl p-6 hover:bg-white/10 transition-all duration-300">
                    <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-400 to-cyan-400"></div>
                    <label className="block text-lg font-semibold text-white mb-4 flex items-center gap-3">
                      <div className="p-2 bg-gradient-to-r from-blue-500 to-cyan-500 rounded-xl">
                        <Globe className="w-5 h-5 text-white" />
                      </div>
                      Web Resource URL
                    </label>
                    <input
                      type="url"
                      value={webUrl}
                      onChange={(e) => setWebUrl(e.target.value)}
                      placeholder="https://example.com/page-to-process"
                      className="w-full p-4 bg-white/10 backdrop-blur-sm border border-white/20 rounded-xl focus:ring-4 focus:ring-blue-500/50 focus:border-blue-400 transition-all duration-300 text-white placeholder-gray-400 text-lg"
                      disabled={isLoading}
                    />
                  </div>
                )}
                
                {/* Document Upload Section - Only show after session is selected */}
                {!showNextSteps && sessionMode && ((sessionMode === 'new' && newSessionName.trim()) || (sessionMode === 'existing' && selectedNamespace)) && (
                  <div className="relative overflow-hidden bg-white/5 backdrop-blur-sm border border-white/20 rounded-2xl p-6 hover:bg-white/10 transition-all duration-300">
                    <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-purple-400 to-pink-400"></div>
                    <label className="block text-lg font-semibold text-white mb-4 flex items-center gap-3">
                      <div className="p-2 bg-gradient-to-r from-purple-500 to-pink-500 rounded-xl">
                        <FileText className="w-5 h-5 text-white" />
                      </div>
                      Document Upload (PDF Only)
                    </label>
                    <div className="relative">
                      <input
                        type="file"
                        onChange={handleFileUpload}
                        className="hidden"
                        id="file-upload"
                        accept=".pdf"
                        disabled={isLoading}
                      />
                      <label
                        htmlFor="file-upload"
                        className="group flex items-center justify-center gap-4 w-full p-8 border-2 border-dashed border-white/30 rounded-2xl hover:border-purple-400 hover:bg-purple-500/10 cursor-pointer transition-all duration-300 transform hover:scale-105"
                      >
                        <div className="p-3 bg-gradient-to-r from-purple-500 to-pink-500 rounded-2xl group-hover:shadow-lg transition-shadow duration-300">
                          <Upload className="w-8 h-8 text-white" />
                        </div>
                        <div className="text-center">
                          <div className="text-white font-semibold text-lg mb-1">
                            {uploadedFile ? uploadedFile.name : 'Drop your PDF file here'}
                          </div>
                          <div className="text-gray-400 text-sm">
                            or click to browse • PDF files only
                          </div>
                        </div>
                      </label>
                    </div>
                    {uploadedFile && (
                      <div className="mt-4 p-4 bg-gradient-to-r from-emerald-500/20 to-green-500/20 border border-emerald-400/30 rounded-xl animate-in slide-in-from-bottom-2 duration-300">
                        <div className="flex items-center gap-3">
                          <div className="p-2 bg-gradient-to-r from-emerald-500 to-green-500 rounded-lg">
                            <FileText className="w-5 h-5 text-white" />
                          </div>
                          <div>
                            <p className="text-emerald-300 font-semibold">File Ready!</p>
                            <p className="text-white text-sm">{uploadedFile.name}</p>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}
                
                {/* Processing Status */}
                {processingStatus.length > 0 && (
                  <div className="bg-white/5 backdrop-blur-sm border border-white/20 rounded-2xl p-6">
                    <h4 className="text-white font-semibold mb-3">Processing Status:</h4>
                    <div className="space-y-2">
                      {processingStatus.map((status, index) => (
                        <div key={index} className="text-sm text-gray-300 flex items-center gap-2">
                          {status.startsWith('✓') ? (
                            <CheckCircle className="w-4 h-4 text-green-400" />
                          ) : (
                            <AlertCircle className="w-4 h-4 text-red-400" />
                          )}
                          {status}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Next Steps Options */}
                {showNextSteps && (
                  <div className="bg-gradient-to-r from-emerald-500/20 to-cyan-500/20 backdrop-blur-sm border border-emerald-400/30 rounded-2xl p-8 animate-in slide-in-from-bottom-4 duration-500">
                    <div className="text-center mb-6">
                      <div className="p-3 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-2xl w-fit mx-auto mb-4">
                        <CheckCircle className="w-8 h-8 text-white" />
                      </div>
                      <h3 className="text-2xl font-bold text-white mb-2">Processing Complete!</h3>
                      <p className="text-emerald-300">What would you like to do next?</p>
                    </div>
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      {/* Chat with Document */}
                      <button
                        onClick={handleChatWithDocument}
                        className="group relative overflow-hidden p-6 rounded-2xl border-2 border-cyan-400/50 bg-gradient-to-br from-cyan-500/20 to-blue-600/20 hover:from-cyan-500/30 hover:to-blue-600/30 transition-all duration-500 transform hover:scale-105"
                      >
                        <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/10 to-blue-600/10 opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
                        <div className="relative text-center">
                          <div className="p-4 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-2xl shadow-lg group-hover:shadow-cyan-500/50 transition-shadow duration-300 w-fit mx-auto mb-4">
                            <MessageCircle className="w-8 h-8 text-white" />
                          </div>
                          <h4 className="text-xl font-bold text-white mb-2">Chat with Document</h4>
                          <p className="text-cyan-300 text-sm mb-4">Start asking questions about the processed content</p>
                          <div className="flex items-center justify-center gap-2 text-cyan-400">
                            <span className="font-semibold">Start Chatting</span>
                            <ArrowRight className="w-5 h-5" />
                          </div>
                        </div>
                      </button>

                      {/* Upload New Document */}
                      <button
                        onClick={handleUploadNewDocument}
                        className="group relative overflow-hidden p-6 rounded-2xl border-2 border-purple-400/50 bg-gradient-to-br from-purple-500/20 to-pink-600/20 hover:from-purple-500/30 hover:to-pink-600/30 transition-all duration-500 transform hover:scale-105"
                      >
                        <div className="absolute inset-0 bg-gradient-to-br from-purple-500/10 to-pink-600/10 opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
                        <div className="relative text-center">
                          <div className="p-4 bg-gradient-to-r from-purple-500 to-pink-500 rounded-2xl shadow-lg group-hover:shadow-purple-500/50 transition-shadow duration-300 w-fit mx-auto mb-4">
                            <Upload className="w-8 h-8 text-white" />
                          </div>
                          <h4 className="text-xl font-bold text-white mb-2">Upload New Document</h4>
                          <p className="text-purple-300 text-sm mb-4">Add more content to the knowledge base</p>
                          <div className="flex items-center justify-center gap-2 text-purple-400">
                            <span className="font-semibold">Add More Content</span>
                            <ArrowRight className="w-5 h-5" />
                          </div>
                        </div>
                      </button>
                    </div>
                  </div>
                )}
                
                {/* UPDATED: Submit Button with proper validation */}
                {!showNextSteps && (
                  <button
                    onClick={handleAdminSubmit}
                    disabled={isSubmitDisabled()}
                    className="w-full bg-gradient-to-r from-purple-500 via-pink-500 to-red-500 text-white py-4 px-8 rounded-2xl font-bold text-lg flex items-center justify-center gap-3 hover:from-purple-400 hover:via-pink-400 hover:to-red-400 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300 transform hover:scale-105 shadow-2xl hover:shadow-purple-500/50"
                  >
                    {isLoading ? (
                      <>
                        <div className="w-6 h-6 border-3 border-white border-t-transparent rounded-full animate-spin"></div>
                        <span>Processing sources...</span>
                      </>
                    ) : (
                      <>
                        <Send className="w-6 h-6" />
                        <span>Process & Index Content</span>
                        <Zap className="w-6 h-6" />
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}