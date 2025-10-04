/**
 * HyperSearch Search Interface Component
 * Advanced multimodal search with cognitive agents
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  Box,
  TextField,
  Button,
  Card,
  CardContent,
  Typography,
  Chip,
  Grid,
  Paper,
  IconButton,
  Menu,
  MenuItem,
  FormControl,
  InputLabel,
  Select,
  Tooltip,
  CircularProgress,
  Alert,
  Divider,
  Avatar,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
} from '@mui/material';
import {
  Search as SearchIcon,
  Mic as MicIcon,
  PhotoCamera as PhotoIcon,
  Upload as UploadIcon,
  Settings as SettingsIcon,
  History as HistoryIcon,
  TrendingUp as TrendingUpIcon,
  Psychology as PsychologyIcon,
  AutoAwesome as AutoAwesomeIcon,
} from '@mui/icons-material';
import { useQuery, useMutation } from 'react-query';

import { apiClient } from '../utils/apiClient';
import { useLanguage } from '../contexts/LanguageContext';

const SearchInterface = () => {
  const { t } = useLanguage();
  const [query, setQuery] = useState('');
  const [searchType, setSearchType] = useState('comprehensive');
  const [modalities, setModalities] = useState(['text']);
  const [results, setResults] = useState(null);
  const [searchHistory, setSearchHistory] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [showAdvanced, setShowAdvanced] = useState(false);
  
  const fileInputRef = useRef(null);
  const queryInputRef = useRef(null);

  // Search mutation
  const searchMutation = useMutation(
    (searchData) => apiClient.post('/api/search', searchData),
    {
      onSuccess: (data) => {
        setResults(data.data);
        // Add to search history
        setSearchHistory(prev => [
          { query: data.data.query, timestamp: new Date(), results: data.data.results.length },
          ...prev.slice(0, 9) // Keep last 10 searches
        ]);
      },
      onError: (error) => {
        console.error('Search failed:', error);
      },
    }
  );

  // Suggestions query
  const { data: suggestionsData } = useQuery(
    ['suggestions', query],
    () => apiClient.post('/api/search/suggestions', { query }),
    {
      enabled: query.length > 2,
      onSuccess: (data) => setSuggestions(data.data.suggestions || []),
    }
  );

  // Handle search submission
  const handleSearch = useCallback(async (searchQuery = query) => {
    if (!searchQuery.trim()) return;

    const searchData = {
      query: searchQuery,
      type: searchType,
      modalities,
      filters: {},
    };

    searchMutation.mutate(searchData);
  }, [query, searchType, modalities, searchMutation]);

  // Handle file upload
  const handleFileUpload = useCallback((event) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    // TODO: Implement file upload API call
    console.log('File uploaded:', file.name);
  }, []);

  // Handle voice input (placeholder)
  const handleVoiceInput = useCallback(() => {
    // TODO: Implement voice recognition
    console.log('Voice input requested');
  }, []);

  // Handle modality toggle
  const toggleModality = useCallback((modality) => {
    setModalities(prev => 
      prev.includes(modality)
        ? prev.filter(m => m !== modality)
        : [...prev, modality]
    );
  }, []);

  return (
    <Box sx={{ maxWidth: '100%', mx: 'auto' }}>
      {/* Search Header */}
      <Paper
        elevation={2}
        sx={{
          p: 3,
          mb: 3,
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          color: 'white',
          borderRadius: 2,
        }}
      >
        <Typography variant="h4" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <PsychologyIcon sx={{ fontSize: '2rem' }} />
          AI-Powered Cognitive Search
        </Typography>
        <Typography variant="subtitle1" sx={{ opacity: 0.9 }}>
          Advanced multimodal search with autonomous cognitive agents
        </Typography>
      </Paper>

      {/* Search Input */}
      <Card elevation={2} sx={{ mb: 3 }}>
        <CardContent>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
            <TextField
              ref={queryInputRef}
              fullWidth
              variant="outlined"
              placeholder={t('search.placeholder', 'Enter your search query...')}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              InputProps={
                endAdornment: (
                  <Box sx={{ display: 'flex', gap: 1 }}>
                    <Tooltip title="Voice Search">
                      <IconButton onClick={handleVoiceInput} size="small">
                        <MicIcon />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Upload File">
                      <IconButton onClick={() => fileInputRef.current?.click()} size="small">
                        <UploadIcon />
                      </IconButton>
                    </Tooltip>
                  </Box>
                )
              }
            />
            
            <Button
              variant="contained"
              size="large"
              startIcon={searchMutation.isLoading ? <CircularProgress size={20} /> : <SearchIcon />}
              onClick={() => handleSearch()}
              disabled={searchMutation.isLoading || !query.trim()}
              sx={{ minWidth: '120px' }}
            >
              {searchMutation.isLoading ? 'Searching...' : 'Search'}
            </Button>
          </Box>

          {/* Search Configuration */}
          <Box sx={{ mt: 2, display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>Search Type</InputLabel>
              <Select
                value={searchType}
                onChange={(e) => setSearchType(e.target.value)}
                label="Search Type"
              >
                <MenuItem value="comprehensive">Comprehensive</MenuItem>
                <MenuItem value="quick">Quick</MenuItem>
                <MenuItem value="detailed">Detailed</MenuItem>
                <MenuItem value="creative">Creative</MenuItem>
              </Select>
            </FormControl>

            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {['text', 'image', 'audio', 'video', 'code'].map((modality) => (
                <Chip
                  key={modality}
                  label={modality}
                  variant={modalities.includes(modality) ? 'filled' : 'outlined'}
                  color={modalities.includes(modality) ? 'primary' : 'default'}
                  onClick={() => toggleModality(modality)}
                  size="small"
                />
              ))}
            </Box>
          </Box>

          {/* Search Suggestions */}
          {suggestions.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Suggestions:
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                {suggestions.slice(0, 5).map((suggestion, index) => (
                  <Chip
                    key={index}
                    label={suggestion}
                    variant="outlined"
                    size="small"
                    onClick={() => {
                      setQuery(suggestion);
                      handleSearch(suggestion);
                    }}
                  />
                ))}
              </Box>
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Search Results */}
      {results && (
        <Card elevation={2}>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <AutoAwesomeIcon color="primary" />
                Search Results
                <Chip 
                  label={`${results.results?.length || 0} results`} 
                  size="small" 
                  color="primary" 
                />
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Processing time: {results.processing_time?.toFixed(2) || 0}s
              </Typography>
            </Box>
            
            {results.results && results.results.length > 0 ? (
              <Grid container spacing={2}>
                {results.results.map((result, index) => (
                  <Grid item xs={12} key={index}>
                    <Paper 
                      elevation={1} 
                      sx={{ 
                        p: 2, 
                        borderLeft: '4px solid',
                        borderLeftColor: 'primary.main',
                        '&:hover': { boxShadow: 2 }
                      }}
                    >
                      <Typography variant="h6" gutterBottom>
                        {result.title || `Result ${index + 1}`}
                      </Typography>
                      <Typography variant="body2" color="text.secondary" paragraph>
                        {result.description || result.content || 'No description available'}
                      </Typography>
                      
                      {result.metadata && (
                        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1 }}>
                          {Object.entries(result.metadata).map(([key, value]) => (
                            <Chip 
                              key={key} 
                              label={`${key}: ${value}`} 
                              size="small" 
                              variant="outlined" 
                            />
                          ))}
                        </Box>
                      )}
                    </Paper>
                  </Grid>
                ))}
              </Grid>
            ) : (
              <Alert severity="info">
                No results found. Try adjusting your search terms or modalities.
              </Alert>
            )}
          </CardContent>
        </Card>
      )}

      {/* Search History Sidebar */}
      {searchHistory.length > 0 && (
        <Card elevation={1} sx={{ mt: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <HistoryIcon color="primary" />
              Recent Searches
            </Typography>
            <List dense>
              {searchHistory.slice(0, 5).map((search, index) => (
                <ListItem 
                  key={index}
                  button
                  onClick={() => {
                    setQuery(search.query);
                    handleSearch(search.query);
                  }}
                >
                  <ListItemText
                    primary={search.query}
                    secondary={`${search.results} results • ${search.timestamp.toLocaleString()}`}
                  />
                </ListItem>
              ))}
            </List>
          </CardContent>
        </Card>
      )}

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        hidden
        onChange={handleFileUpload}
        accept="image/*,video/*,audio/*,.pdf,.doc,.docx,.txt"
      />
    </Box>
  );
};

export default SearchInterface;