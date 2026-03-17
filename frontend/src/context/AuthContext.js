import { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';

const AuthContext = createContext(null);

const API_URL = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('omnimine_token'));
  const [loading, setLoading] = useState(true);
  const [activeOrgId, setActiveOrgId] = useState(localStorage.getItem('omnimine_org_id') || null);

  useEffect(() => {
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      fetchUser();
    } else {
      setLoading(false);
    }
  }, [token]);

  const fetchUser = async () => {
    try {
      const response = await axios.get(`${API_URL}/auth/me`);
      setUser(response.data);
      const orgId = response.data?.org_id || activeOrgId;
      if (orgId) {
        setActiveOrgId(orgId);
        localStorage.setItem('omnimine_org_id', orgId);
      }
    } catch (error) {
      console.error('Failed to fetch user:', error);
      logout();
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    const response = await axios.post(`${API_URL}/auth/login`, { email, password });
    const { access_token, user: userData } = response.data;
    localStorage.setItem('omnimine_token', access_token);
    if (userData?.org_id) localStorage.setItem('omnimine_org_id', userData.org_id);
    axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
    setToken(access_token);
    setUser(userData);
    setActiveOrgId(userData?.org_id || null);
    return userData;
  };

  const register = async (email, password, name, role = 'analyst') => {
    const response = await axios.post(`${API_URL}/auth/register`, { email, password, name, role });
    const { access_token, user: userData } = response.data;
    localStorage.setItem('omnimine_token', access_token);
    if (userData?.org_id) localStorage.setItem('omnimine_org_id', userData.org_id);
    axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
    setToken(access_token);
    setUser(userData);
    setActiveOrgId(userData?.org_id || null);
    return userData;
  };

  const switchOrg = async (orgId) => {
    const response = await axios.post(`${API_URL}/auth/switch-org`, { org_id: orgId });
    const { access_token, user: userData } = response.data;
    localStorage.setItem('omnimine_token', access_token);
    localStorage.setItem('omnimine_org_id', userData?.org_id || orgId);
    axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
    setToken(access_token);
    setUser(userData);
    setActiveOrgId(userData?.org_id || orgId);
    return userData;
  };

  const logout = () => {
    localStorage.removeItem('omnimine_token');
    localStorage.removeItem('omnimine_org_id');
    delete axios.defaults.headers.common['Authorization'];
    setToken(null);
    setUser(null);
    setActiveOrgId(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, activeOrgId, login, register, switchOrg, logout, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
