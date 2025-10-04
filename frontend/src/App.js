/**
 * HyperSearch AI Platform - Main React Application
 * Enterprise-grade search interface with cognitive agents
 */

import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { CssBaseline, Box, AppBar, Toolbar, Typography, Container } from '@mui/material';
import { QueryClient, QueryClientProvider } from 'react-query';
import { ReactQueryDevtools } from 'react-query/devtools';

// Import components
import SearchInterface from './components/SearchInterface';
import AgentDashboard from './components/AgentDashboard';
import MonitoringDashboard from './components/MonitoringDashboard';
import SettingsPanel from './components/SettingsPanel';
import NavigationMenu from './components/NavigationMenu';

// Import contexts
import { AuthProvider } from './contexts/AuthContext';
import { LanguageProvider } from './contexts/LanguageContext';

// Import utilities
import { apiClient } from './utils/apiClient';
import ErrorBoundary from './components/ErrorBoundary';

// Create theme
const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#2196f3',
      dark: '#1976d2',
      light: '#64b5f6',
    },
    secondary: {
      main: '#f50057',
      dark: '#c51162',
      light: '#ff5983',
    },
    background: {
      default: '#f5f5f5',
      paper: '#ffffff',
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    h1: {
      fontSize: '2.5rem',
      fontWeight: 600,
    },
    h2: {
      fontSize: '2rem',
      fontWeight: 500,
    },
    body1: {
      fontSize: '1rem',
      lineHeight: 1.6,
    },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          textTransform: 'none',
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        },
      },
    },
  },
});

// Create React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      refetchOnWindowFocus: false,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});

function App() {
  const [currentView, setCurrentView] = useState('search');
  const [systemStatus, setSystemStatus] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // Check system health on startup
  useEffect(() => {
    const checkSystemHealth = async () => {
      try {
        const health = await apiClient.get('/api/health');
        setSystemStatus(health.data);
      } catch (error) {
        console.error('System health check failed:', error);
        setSystemStatus({ status: 'unhealthy' });
      } finally {
        setIsLoading(false);
      }
    };

    checkSystemHealth();
    
    // Periodic health checks
    const interval = setInterval(checkSystemHealth, 30000); // Every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const renderMainContent = () => {
    switch (currentView) {
      case 'search':
        return <SearchInterface />;
      case 'agents':
        return <AgentDashboard />;
      case 'monitoring':
        return <MonitoringDashboard />;
      case 'settings':
        return <SettingsPanel />;
      default:
        return <SearchInterface />;
    }
  };

  if (isLoading) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Box
          display="flex"
          justifyContent="center"
          alignItems="center"
          minHeight="100vh"
          flexDirection="column"
        >
          <Typography variant="h4" color="primary" gutterBottom>
            🧠 HyperSearch AI Platform
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Initializing cognitive agents...
          </Typography>
        </Box>
      </ThemeProvider>
    );
  }

  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <LanguageProvider>
            <ThemeProvider theme={theme}>
              <CssBaseline />
              <Router>
                <Box sx={{ flexGrow: 1, minHeight: '100vh' }}>
                  {/* Header */}
                  <AppBar position="static" elevation={1}>
                    <Toolbar>
                      <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
                        🧠 HyperSearch AI Platform
                      </Typography>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        {systemStatus && (
                          <Box
                            sx={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 1,
                              px: 2,
                              py: 0.5,
                              borderRadius: 1,
                              bgcolor: systemStatus.status === 'healthy' ? 'success.main' : 'error.main',
                              color: 'white',
                            }}
                          >
                            <Box
                              sx={{
                                width: 8,
                                height: 8,
                                borderRadius: '50%',
                                bgcolor: 'currentColor',
                              }}
                            />
                            <Typography variant="caption">
                              {systemStatus.status === 'healthy' ? 'System Healthy' : 'System Issues'}
                            </Typography>
                          </Box>
                        )}
                      </Box>
                    </Toolbar>
                  </AppBar>

                  <Box sx={{ display: 'flex' }}>
                    {/* Navigation Sidebar */}
                    <NavigationMenu
                      currentView={currentView}
                      onViewChange={setCurrentView}
                      systemStatus={systemStatus}
                    />

                    {/* Main Content */}
                    <Box
                      component="main"
                      sx={{
                        flexGrow: 1,
                        p: 3,
                        backgroundColor: 'background.default',
                        minHeight: 'calc(100vh - 64px)',
                      }}
                    >
                      <Container maxWidth="xl">
                        <Routes>
                          <Route path="/" element={<Navigate to="/search" replace />} />
                          <Route path="/search" element={<SearchInterface />} />
                          <Route path="/agents" element={<AgentDashboard />} />
                          <Route path="/monitoring" element={<MonitoringDashboard />} />
                          <Route path="/settings" element={<SettingsPanel />} />
                        </Routes>
                      </Container>
                    </Box>
                  </Box>
                </Box>
              </Router>
              
              {/* Development tools */}
              {process.env.NODE_ENV === 'development' && (
                <ReactQueryDevtools initialIsOpen={false} />
              )}
            </ThemeProvider>
          </LanguageProvider>
        </AuthProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;