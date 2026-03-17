import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Toaster, toast } from 'sonner';
import { ChartLineUp, Brain, ShieldCheck } from '@phosphor-icons/react';

export const LoginPage = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      toast.success('Welcome back!');
      navigate('/');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex" data-testid="login-page">
      <Toaster position="top-right" richColors />
      
      {/* Left Panel - Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-indigo-600 to-violet-600 p-12 flex-col justify-between">
        <div>
          <h1 className="text-3xl font-heading font-bold text-white">OmniMine</h1>
          <p className="text-indigo-100 mt-2">AI-Powered Opinion Mining Platform</p>
        </div>
        
        <div className="space-y-8">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-white/10 rounded-lg">
              <Brain size={24} weight="duotone" className="text-white" />
            </div>
            <div>
              <h3 className="text-white font-semibold">AI-Powered Analysis</h3>
              <p className="text-indigo-100 text-sm">Sentiment, emotion & theme detection with GPT-5.2</p>
            </div>
          </div>
          
          <div className="flex items-start gap-4">
            <div className="p-3 bg-white/10 rounded-lg">
              <ChartLineUp size={24} weight="duotone" className="text-white" />
            </div>
            <div>
              <h3 className="text-white font-semibold">Real-Time Insights</h3>
              <p className="text-indigo-100 text-sm">Track sentiment trends across all channels</p>
            </div>
          </div>
          
          <div className="flex items-start gap-4">
            <div className="p-3 bg-white/10 rounded-lg">
              <ShieldCheck size={24} weight="duotone" className="text-white" />
            </div>
            <div>
              <h3 className="text-white font-semibold">Closed Feedback Loop</h3>
              <p className="text-indigo-100 text-sm">Resolve issues & verify customer satisfaction</p>
            </div>
          </div>
        </div>
        
        <p className="text-indigo-200 text-sm">© 2024 OmniMine. Enterprise-grade CX Intelligence.</p>
      </div>
      
      {/* Right Panel - Login Form */}
      <div className="flex-1 flex items-center justify-center p-8 bg-slate-50">
        <Card className="w-full max-w-md border-slate-200">
          <CardHeader className="text-center">
            <div className="lg:hidden mb-4">
              <h1 className="text-2xl font-heading font-bold text-indigo-600">OmniMine</h1>
            </div>
            <CardTitle className="text-2xl font-heading">Welcome back</CardTitle>
            <CardDescription>Enter your credentials to access the dashboard</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  data-testid="login-email-input"
                  className="focus-ring"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  data-testid="login-password-input"
                  className="focus-ring"
                />
              </div>
              <Button 
                type="submit" 
                className="w-full bg-indigo-600 hover:bg-indigo-700"
                disabled={loading}
                data-testid="login-submit-btn"
              >
                {loading ? 'Signing in...' : 'Sign in'}
              </Button>
            </form>
            
            <div className="mt-6 text-center text-sm text-muted-foreground">
              Don't have an account?{' '}
              <Link to="/register" className="text-indigo-600 hover:underline font-medium" data-testid="register-link">
                Create account
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export const RegisterPage = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('analyst');
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await register(email, password, name, role);
      toast.success('Account created successfully!');
      navigate('/');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex" data-testid="register-page">
      <Toaster position="top-right" richColors />
      
      {/* Left Panel */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-indigo-600 to-violet-600 p-12 flex-col justify-between">
        <div>
          <h1 className="text-3xl font-heading font-bold text-white">OmniMine</h1>
          <p className="text-indigo-100 mt-2">AI-Powered Opinion Mining Platform</p>
        </div>
        
        <div className="text-white">
          <h2 className="text-2xl font-heading font-semibold mb-4">Start your journey</h2>
          <p className="text-indigo-100">Join organizations worldwide using OmniMine to transform customer feedback into actionable insights.</p>
        </div>
        
        <p className="text-indigo-200 text-sm">© 2024 OmniMine. Enterprise-grade CX Intelligence.</p>
      </div>
      
      {/* Right Panel - Register Form */}
      <div className="flex-1 flex items-center justify-center p-8 bg-slate-50">
        <Card className="w-full max-w-md border-slate-200">
          <CardHeader className="text-center">
            <div className="lg:hidden mb-4">
              <h1 className="text-2xl font-heading font-bold text-indigo-600">OmniMine</h1>
            </div>
            <CardTitle className="text-2xl font-heading">Create account</CardTitle>
            <CardDescription>Get started with OmniMine today</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Full Name</Label>
                <Input
                  id="name"
                  type="text"
                  placeholder="John Doe"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  data-testid="register-name-input"
                  className="focus-ring"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  data-testid="register-email-input"
                  className="focus-ring"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={6}
                  data-testid="register-password-input"
                  className="focus-ring"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="role">Role</Label>
                <Select value={role} onValueChange={setRole}>
                  <SelectTrigger data-testid="register-role-select" className="focus-ring">
                    <SelectValue placeholder="Select role" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="analyst">Analyst</SelectItem>
                    <SelectItem value="agent">Agent</SelectItem>
                    <SelectItem value="manager">Manager</SelectItem>
                    <SelectItem value="admin">Admin</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button 
                type="submit" 
                className="w-full bg-indigo-600 hover:bg-indigo-700"
                disabled={loading}
                data-testid="register-submit-btn"
              >
                {loading ? 'Creating account...' : 'Create account'}
              </Button>
            </form>
            
            <div className="mt-6 text-center text-sm text-muted-foreground">
              Already have an account?{' '}
              <Link to="/login" className="text-indigo-600 hover:underline font-medium" data-testid="login-link">
                Sign in
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
